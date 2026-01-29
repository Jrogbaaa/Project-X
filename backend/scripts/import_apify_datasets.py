"""
Import existing Apify dataset posts into the database.

This script fetches posts from existing Apify datasets (already paid for)
and runs them through the enrichment pipeline to populate:
- influencer_posts table
- Influencer niche detection columns (primary_niche, content_themes, etc.)

Usage:
    cd backend && source ../venv/bin/activate
    python scripts/import_apify_datasets.py
"""

import asyncio
import logging
import httpx
from collections import defaultdict, Counter
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import re

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import get_settings
from app.models.influencer import Influencer
from app.models.influencer_post import InfluencerPost
from app.services.brand_intelligence_service import get_brand_intelligence_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Dataset IDs from your Apify runs (already paid for)
DATASET_IDS = [
    "iuNqrrFN8CwMKN6ex",  # 1,852 posts - successful run
    "Nw7IGlb2tlowbMQwT",  # 3,691 posts - timed out but has data
    "aK2US7wSXdOW16NhU",  # 3,037 posts
    "ycjDuX9ChjGTwcobd",  # 3,441 posts
    "3mVefW1JB83a23geZ",  # 266 posts
]

# Theme detection keywords (same as enrichment service)
THEME_KEYWORDS = {
    "behind_the_scenes": [
        "behindthescenes", "bts", "makingof", "dayinmylife", "trasmicamaras",
        "entretelones", "making", "detras", "backstage"
    ],
    "training": [
        "training", "entrenamiento", "workout", "gym", "practice", "practica",
        "ejercicio", "fitness", "preparacion", "warmup"
    ],
    "competition": [
        "torneo", "campeonato", "final", "partido", "competition", "match",
        "tournament", "championship", "semifinal", "cuartos"
    ],
    "lifestyle": [
        "lifestyle", "vida", "daily", "cotidiano", "ootd", "everyday",
        "routine", "rutina", "diario"
    ],
    "travel": [
        "travel", "viaje", "trip", "explore", "adventure", "aventura",
        "vacation", "vacaciones", "destino", "wanderlust"
    ],
    "family": [
        "family", "familia", "kids", "hijos", "mom", "dad", "mama", "papa",
        "hijo", "hija", "bebe", "baby"
    ],
    "motivation": [
        "motivation", "inspire", "dream", "goals", "nevergivingup", "motivacion",
        "suenos", "metas", "superacion", "esfuerzo", "dedicacion"
    ],
    "food": [
        "food", "comida", "foodie", "recipe", "receta", "cocina", "cooking",
        "chef", "gastronomia", "delicious"
    ],
    "fashion": [
        "fashion", "moda", "style", "estilo", "outfit", "look", "streetstyle",
        "fashionista", "trendy"
    ],
    "beauty": [
        "beauty", "belleza", "makeup", "maquillaje", "skincare", "cosmetics",
        "tutorial", "glam"
    ],
}


class ApifyDatasetImporter:
    """Import posts from existing Apify datasets."""

    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory
        self.settings = get_settings()
        self.stats = {
            "datasets_processed": 0,
            "posts_fetched": 0,
            "posts_saved": 0,
            "influencers_matched": 0,
            "influencers_enriched": 0,
            "errors": 0,
        }

    async def fetch_dataset(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Fetch all items from an Apify dataset."""
        url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
        params = {
            "token": self.settings.apify_api_token,
            "format": "json",
            "clean": "true",
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            logger.info(f"Fetching dataset {dataset_id}...")
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch dataset {dataset_id}: {response.status_code}")
                return []
            
            items = response.json()
            logger.info(f"Fetched {len(items)} items from dataset {dataset_id}")
            return items

    def extract_username_from_item(self, item: Dict[str, Any]) -> Optional[str]:
        """Extract the influencer username from a post item."""
        # Try ownerUsername first (the actual poster)
        username = item.get("ownerUsername")
        if username:
            return username.lower()
        
        # Fall back to inputUrl
        input_url = item.get("inputUrl", "")
        if input_url:
            # Extract username from URL like https://www.instagram.com/username/
            match = re.search(r'instagram\.com/([^/]+)', input_url)
            if match:
                return match.group(1).lower()
        
        return None

    def is_valid_post(self, item: Dict[str, Any]) -> bool:
        """Check if item is a valid post (not an error)."""
        if item.get("error"):
            return False
        if not item.get("id") and not item.get("shortCode"):
            return False
        return True

    async def get_influencer_by_username(
        self, 
        session: AsyncSession, 
        username: str
    ) -> Optional[Influencer]:
        """Find influencer by username."""
        result = await session.execute(
            select(Influencer).where(
                Influencer.username.ilike(username)
            )
        )
        return result.scalar_one_or_none()

    async def save_post(
        self,
        session: AsyncSession,
        influencer: Influencer,
        item: Dict[str, Any]
    ) -> bool:
        """Save a post to the database."""
        post_id = item.get("id") or item.get("shortCode")
        if not post_id:
            return False

        # Check if post already exists
        existing = await session.execute(
            select(InfluencerPost).where(
                and_(
                    InfluencerPost.influencer_id == influencer.id,
                    InfluencerPost.instagram_post_id == str(post_id)
                )
            )
        )
        existing_post = existing.scalar_one_or_none()

        # Parse data
        caption = item.get("caption", "")
        hashtags = item.get("hashtags", [])
        mentions = item.get("mentions", [])
        
        # Detect if sponsored
        is_sponsored = any(tag in ["ad", "sponsored", "publicidad", "colaboracion"] 
                         for tag in [h.lower() for h in hashtags])
        
        # Parse timestamp
        posted_at = None
        if item.get("timestamp"):
            try:
                posted_at = datetime.fromisoformat(
                    item["timestamp"].replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        if existing_post:
            # Update existing
            existing_post.caption = caption
            existing_post.hashtags = hashtags
            existing_post.mentions = mentions
            existing_post.likes_count = item.get("likesCount")
            existing_post.comments_count = item.get("commentsCount")
            existing_post.views_count = item.get("videoViewCount")
            existing_post.is_sponsored = is_sponsored
            existing_post.apify_scraped_at = datetime.now(timezone.utc)
            return False  # Not a new post
        else:
            # Create new
            new_post = InfluencerPost(
                influencer_id=influencer.id,
                instagram_post_id=str(post_id),
                shortcode=item.get("shortCode"),
                post_url=item.get("url"),
                caption=caption,
                hashtags=hashtags,
                mentions=mentions,
                post_type=item.get("type", "").lower() if item.get("type") else None,
                posted_at=posted_at,
                likes_count=item.get("likesCount"),
                comments_count=item.get("commentsCount"),
                views_count=item.get("videoViewCount"),
                thumbnail_url=item.get("displayUrl"),
                is_sponsored=is_sponsored,
                apify_scraped_at=datetime.now(timezone.utc)
            )
            session.add(new_post)
            return True  # New post

    def extract_keywords(self, caption: str) -> List[str]:
        """Extract meaningful keywords from caption."""
        if not caption:
            return []
        # Remove hashtags and mentions
        text = re.sub(r'[#@]\w+', '', caption)
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        # Extract words 4+ chars
        words = re.findall(r'\b[a-zA-ZáéíóúñüÁÉÍÓÚÑÜ]{4,}\b', text.lower())
        # Filter stopwords
        stopwords = {
            'this', 'that', 'with', 'from', 'have', 'what', 'your', 'been',
            'will', 'more', 'when', 'there', 'their', 'about', 'would', 'which',
            'como', 'para', 'este', 'esta', 'esto', 'estos', 'estas', 'pero',
            'todo', 'todos', 'toda', 'todas', 'muy', 'bien', 'aquí', 'ahora',
            'siempre', 'nunca', 'también', 'porque', 'cuando', 'donde', 'quien'
        }
        return [w for w in words if w not in stopwords]

    def detect_language(self, text: str) -> str:
        """Simple language detection."""
        if not text or len(text) < 20:
            return "es"
        
        text_lower = text.lower()
        
        spanish_words = ['que', 'con', 'por', 'para', 'una', 'del', 'los', 'las', 'más', 'pero']
        spanish_count = sum(1 for w in spanish_words if f' {w} ' in f' {text_lower} ')
        
        english_words = ['the', 'and', 'for', 'you', 'with', 'this', 'that', 'have', 'are', 'from']
        english_count = sum(1 for w in english_words if f' {w} ' in f' {text_lower} ')
        
        if spanish_count > english_count:
            return "es"
        elif english_count > spanish_count:
            return "en"
        return "es"

    def detect_themes(
        self,
        hashtags: List[str],
        captions: List[str],
        sponsored_ratio: float
    ) -> Dict[str, Any]:
        """Detect content themes."""
        hashtag_text = " ".join(hashtags).lower()
        caption_text = " ".join(captions).lower()
        combined_text = hashtag_text + " " + caption_text
        
        detected_themes = []
        for theme, keywords in THEME_KEYWORDS.items():
            if any(kw in combined_text for kw in keywords):
                detected_themes.append(theme)
        
        # Calculate avg caption length
        caption_lengths = [len(c) for c in captions if c]
        avg_caption_length = sum(caption_lengths) / len(caption_lengths) if caption_lengths else 0
        
        # Determine narrative style
        if sponsored_ratio > 0.5:
            narrative_style = "promotional"
        elif avg_caption_length > 200:
            narrative_style = "storytelling"
        elif avg_caption_length > 50:
            narrative_style = "casual"
        else:
            narrative_style = "minimal"
        
        return {
            "detected_themes": detected_themes,
            "narrative_style": narrative_style,
            "avg_caption_length": int(avg_caption_length)
        }

    def extract_likely_brands(self, mention_counts: Dict[str, int]) -> List[str]:
        """Extract likely brand handles from mentions."""
        non_brand_patterns = [r'^[a-z]+\d+$', r'^\d']
        brand_indicators = ['oficial', 'official', 'brand', 'sport', 'store', 'shop']
        
        likely_brands = []
        for mention, count in mention_counts.items():
            mention_lower = mention.lower()
            is_non_brand = any(re.match(p, mention_lower) for p in non_brand_patterns)
            if is_non_brand:
                continue
            has_brand_indicator = any(ind in mention_lower for ind in brand_indicators)
            if count >= 2 or has_brand_indicator or len(mention) > 15:
                likely_brands.append(mention_lower)
        
        return likely_brands[:20]

    async def enrich_influencer(
        self,
        session: AsyncSession,
        influencer: Influencer,
        posts: List[Dict[str, Any]]
    ):
        """Enrich influencer with aggregated post content."""
        if not posts:
            return

        # Aggregate data
        all_hashtags = []
        all_mentions = []
        all_captions = []
        all_keywords = []
        total_engagement = 0
        sponsored_count = 0

        for post in posts:
            hashtags = post.get("hashtags", [])
            mentions = post.get("mentions", [])
            caption = post.get("caption", "")
            
            all_hashtags.extend(hashtags)
            all_mentions.extend(mentions)
            all_captions.append(caption)
            all_keywords.extend(self.extract_keywords(caption))
            
            total_engagement += (post.get("likesCount") or 0) + (post.get("commentsCount") or 0)
            
            if any(tag.lower() in ["ad", "sponsored", "publicidad"] for tag in hashtags):
                sponsored_count += 1

        hashtag_counts = Counter(all_hashtags).most_common(30)
        mention_counts = Counter(all_mentions).most_common(20)
        keyword_counts = Counter(all_keywords).most_common(50)
        
        avg_engagement = total_engagement / len(posts) if posts else 0
        sponsored_ratio = sponsored_count / len(posts) if posts else 0.0

        # Build aggregated content
        post_content = {
            "top_hashtags": dict(hashtag_counts),
            "top_mentions": dict(mention_counts),
            "caption_keywords": dict(keyword_counts),
            "post_count": len(posts),
            "avg_post_engagement": round(avg_engagement, 2),
            "last_scraped_at": datetime.now(timezone.utc).isoformat(),
            "scrape_status": "complete"
        }
        influencer.post_content_aggregated = post_content

        # Detect primary niche using brand intelligence service
        brand_intel = get_brand_intelligence_service()
        primary_niche, matched_keywords, confidence = brand_intel.detect_influencer_niche_enhanced(
            interests=influencer.interests or [],
            bio=influencer.bio or "",
            post_content=post_content
        )
        influencer.primary_niche = primary_niche
        influencer.niche_confidence = round(confidence, 3) if confidence else None

        # Detected brands
        influencer.detected_brands = self.extract_likely_brands(dict(mention_counts))

        # Sponsored ratio
        influencer.sponsored_ratio = round(sponsored_ratio, 2)

        # Content language
        combined_text = " ".join(all_captions)
        influencer.content_language = self.detect_language(combined_text)

        # Content themes
        influencer.content_themes = self.detect_themes(
            all_hashtags, all_captions, sponsored_ratio
        )

        conf_str = f"{confidence:.2f}" if confidence else "0"
        logger.info(
            f"Enriched @{influencer.username}: niche={primary_niche}, "
            f"confidence={conf_str}, posts={len(posts)}"
        )

    async def run(self):
        """Run the import process."""
        logger.info("=" * 60)
        logger.info("Apify Dataset Import")
        logger.info("=" * 60)
        logger.info(f"Datasets to process: {len(DATASET_IDS)}")

        # Collect all posts grouped by username
        posts_by_username: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for dataset_id in DATASET_IDS:
            try:
                items = await self.fetch_dataset(dataset_id)
                self.stats["datasets_processed"] += 1
                
                for item in items:
                    if not self.is_valid_post(item):
                        continue
                    
                    username = self.extract_username_from_item(item)
                    if username:
                        posts_by_username[username].append(item)
                        self.stats["posts_fetched"] += 1
                
            except Exception as e:
                logger.error(f"Error fetching dataset {dataset_id}: {e}")
                self.stats["errors"] += 1

        logger.info(f"Fetched {self.stats['posts_fetched']} valid posts for {len(posts_by_username)} usernames")

        # Process each influencer
        logger.info("Connecting to database...")
        async with self.session_factory() as session:
            logger.info("Database connected. Processing influencers...")
            processed = 0
            for username, posts in posts_by_username.items():
                processed += 1
                if processed % 50 == 0:
                    logger.info(f"Progress: {processed}/{len(posts_by_username)} usernames processed")
                try:
                    influencer = await self.get_influencer_by_username(session, username)
                    
                    if not influencer:
                        # Try without underscores/dots variations
                        continue
                    
                    self.stats["influencers_matched"] += 1
                    
                    # Save posts
                    new_posts = 0
                    for post in posts:
                        if await self.save_post(session, influencer, post):
                            new_posts += 1
                            self.stats["posts_saved"] += 1
                    
                    # Enrich influencer
                    await self.enrich_influencer(session, influencer, posts)
                    self.stats["influencers_enriched"] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing @{username}: {e}")
                    self.stats["errors"] += 1
                    continue

            # Commit all changes
            await session.commit()
            logger.info("Database changes committed")

        # Summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("Import Complete!")
        logger.info("=" * 60)
        logger.info(f"Datasets processed: {self.stats['datasets_processed']}")
        logger.info(f"Posts fetched: {self.stats['posts_fetched']}")
        logger.info(f"Influencers matched: {self.stats['influencers_matched']}")
        logger.info(f"New posts saved: {self.stats['posts_saved']}")
        logger.info(f"Influencers enriched: {self.stats['influencers_enriched']}")
        logger.info(f"Errors: {self.stats['errors']}")


async def main():
    """Entry point."""
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    importer = ApifyDatasetImporter(session_factory)
    await importer.run()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
