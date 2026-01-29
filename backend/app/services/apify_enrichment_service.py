"""
Apify Post Enrichment Pipeline

Batch processes influencers to scrape their Instagram posts for improved niche detection.
Stores posts in influencer_posts table and aggregates content signals.
Populates niche detection columns: primary_niche, niche_confidence, detected_brands,
sponsored_ratio, content_language, content_themes.

Usage:
    # Dry run - see what would be scraped
    python -m app.services.apify_enrichment_service --dry-run

    # Run enrichment on all influencers (under 2.5M followers)
    python -m app.services.apify_enrichment_service

    # Run with custom batch size
    python -m app.services.apify_enrichment_service --batch-size 25 --posts-per-user 20

    # Limit to specific number of influencers
    python -m app.services.apify_enrichment_service --limit 100
"""

import asyncio
import argparse
import logging
import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import get_settings
from app.models.influencer import Influencer
from app.models.influencer_post import InfluencerPost
from app.services.apify_client import ApifyInstagramClient, InstagramPost, ApifyAPIError
from app.services.brand_intelligence_service import get_brand_intelligence_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Follower threshold - skip influencers above this count
MAX_FOLLOWER_COUNT = 2_500_000

# Theme detection keywords for content_themes
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


class ApifyEnrichmentPipeline:
    """Pipeline for enriching influencers with post content via Apify."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
        batch_size: int = 50,
        posts_per_user: int = 30,
        progress_file: str = ".tmp/apify_progress.json"
    ):
        self.session_factory = session_factory
        self.db = None  # Will be set per-batch
        self.client = ApifyInstagramClient()
        self.batch_size = batch_size
        self.posts_per_user = posts_per_user
        self.progress_file = Path(progress_file)

        # Ensure progress directory exists
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)

        # Stats tracking
        self.stats = {
            "total": 0,
            "processed": 0,
            "success": 0,
            "failed": 0,
            "posts_scraped": 0,
            "estimated_cost": 0.0
        }

    async def get_influencers_to_enrich(
        self,
        limit: Optional[int] = None
    ) -> List[dict]:
        """
        Get influencers that need post content enrichment.
        
        Filters:
        - Instagram platform only
        - Has username
        - Under 2.5M followers (skip celebrities who use existing interests)

        Orders by follower count (highest first) for priority.
        Returns dict data to avoid detached session issues.
        """
        async with self.session_factory() as session:
            query = (
                select(Influencer)
                .where(
                    and_(
                        Influencer.platform_type == "instagram",
                        Influencer.username.isnot(None),
                        # Skip celebrities with > 2.5M followers
                        or_(
                            Influencer.follower_count.is_(None),
                            Influencer.follower_count < MAX_FOLLOWER_COUNT
                        )
                    )
                )
                .order_by(Influencer.follower_count.desc().nullslast())
            )

            if limit:
                query = query.limit(limit)

            result = await session.execute(query)
            influencers = list(result.scalars().all())
            
            # Return as dicts to avoid detached session issues
            return [
                {
                    "id": inf.id,
                    "username": inf.username,
                    "follower_count": inf.follower_count,
                    "interests": inf.interests,
                    "bio": inf.bio,
                }
                for inf in influencers
            ]

    async def process_batch(
        self,
        influencer_data: List[dict],
        batch_num: int,
        total_batches: int
    ) -> Dict[str, Any]:
        """
        Process a batch of influencers.
        Uses single Apify actor run for efficiency.
        Creates fresh DB session per batch to avoid connection timeouts.
        """
        usernames = [inf["username"] for inf in influencer_data]
        logger.info(f"Batch {batch_num}/{total_batches}: Processing {len(usernames)} influencers")

        try:
            # Scrape posts for all users in batch (this can take several minutes)
            posts_by_user = await self.client.scrape_users_batch(
                usernames=usernames,
                results_per_user=self.posts_per_user,
                timeout_secs=600
            )

            # Create fresh session for DB operations after scrape completes
            async with self.session_factory() as session:
                self.db = session
                
                # Save posts and update influencers
                for inf_data in influencer_data:
                    # Fetch fresh influencer from DB
                    result = await session.execute(
                        select(Influencer).where(Influencer.id == inf_data["id"])
                    )
                    inf = result.scalar_one_or_none()
                    
                    if not inf:
                        logger.warning(f"Influencer {inf_data['username']} not found in DB")
                        self.stats["failed"] += 1
                        self.stats["processed"] += 1
                        continue
                    
                    username_lower = inf.username.lower()
                    posts = posts_by_user.get(username_lower, [])

                    if posts:
                        await self._save_posts(inf, posts)
                        await self._update_aggregated_content(inf, posts)
                        self.stats["success"] += 1
                        self.stats["posts_scraped"] += len(posts)
                        logger.debug(f"  {inf.username}: {len(posts)} posts saved")
                    else:
                        # Mark as scraped but no posts found
                        await self._mark_scrape_status(inf, "no_posts", "No posts found")
                        self.stats["failed"] += 1
                        logger.debug(f"  {inf.username}: No posts found")

                    self.stats["processed"] += 1

                await session.commit()

            # Calculate cost estimate (~$2.30 per 1000 posts)
            total_posts = sum(len(posts) for posts in posts_by_user.values())
            self.stats["estimated_cost"] += total_posts * 0.0023

            return {"success": True, "posts_scraped": total_posts}

        except ApifyAPIError as e:
            logger.error(f"Batch {batch_num} failed: {e}")
            # Mark all as failed with fresh session
            async with self.session_factory() as session:
                for inf_data in influencer_data:
                    result = await session.execute(
                        select(Influencer).where(Influencer.id == inf_data["id"])
                    )
                    inf = result.scalar_one_or_none()
                    if inf:
                        self.db = session
                        await self._mark_scrape_status(inf, "failed", str(e))
                    self.stats["failed"] += 1
                    self.stats["processed"] += 1
                await session.commit()
            return {"success": False, "error": str(e)}

    async def _save_posts(
        self,
        influencer: Influencer,
        posts: List[InstagramPost]
    ):
        """Save posts to influencer_posts table."""
        for post in posts:
            # Check if post already exists
            existing = await self.db.execute(
                select(InfluencerPost).where(
                    and_(
                        InfluencerPost.influencer_id == influencer.id,
                        InfluencerPost.instagram_post_id == post.post_id
                    )
                )
            )
            existing_post = existing.scalar_one_or_none()

            if existing_post:
                # Update existing post
                existing_post.caption = post.caption
                existing_post.hashtags = post.hashtags
                existing_post.mentions = post.mentions
                existing_post.likes_count = post.likes_count
                existing_post.comments_count = post.comments_count
                existing_post.views_count = post.views_count
                existing_post.apify_scraped_at = datetime.now(timezone.utc)
            else:
                # Insert new post
                new_post = InfluencerPost(
                    influencer_id=influencer.id,
                    instagram_post_id=post.post_id,
                    shortcode=post.shortcode,
                    post_url=post.post_url,
                    caption=post.caption,
                    hashtags=post.hashtags,
                    mentions=post.mentions,
                    post_type=post.post_type,
                    posted_at=post.posted_at,
                    likes_count=post.likes_count,
                    comments_count=post.comments_count,
                    views_count=post.views_count,
                    thumbnail_url=post.thumbnail_url,
                    is_sponsored=post.is_sponsored,
                    apify_scraped_at=datetime.now(timezone.utc)
                )
                self.db.add(new_post)

    async def _update_aggregated_content(
        self,
        influencer: Influencer,
        posts: List[InstagramPost]
    ):
        """Update aggregated content field and populate niche detection columns."""
        # Aggregate hashtags
        all_hashtags = []
        all_mentions = []
        all_caption_words = []
        all_captions = []
        total_engagement = 0
        sponsored_count = 0

        for post in posts:
            all_hashtags.extend(post.hashtags)
            all_mentions.extend(post.mentions)
            # Extract significant words from captions
            words = self._extract_keywords(post.caption)
            all_caption_words.extend(words)
            all_captions.append(post.caption or "")
            total_engagement += (post.likes_count or 0) + (post.comments_count or 0)
            if post.is_sponsored:
                sponsored_count += 1

        hashtag_counts = Counter(all_hashtags).most_common(30)
        mention_counts = Counter(all_mentions).most_common(20)
        keyword_counts = Counter(all_caption_words).most_common(50)

        # Calculate avg engagement per post
        avg_engagement = total_engagement / len(posts) if posts else 0

        # Store aggregated content
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

        # === Populate niche detection columns ===

        # 1. Detect primary niche using brand intelligence service
        brand_intel = get_brand_intelligence_service()
        primary_niche, matched_keywords, confidence = brand_intel.detect_influencer_niche_enhanced(
            interests=influencer.interests or [],
            bio=influencer.bio or "",
            post_content=post_content
        )
        influencer.primary_niche = primary_niche
        influencer.niche_confidence = round(confidence, 3) if confidence else None

        # 2. Detected brands from mentions (filter to likely brands)
        influencer.detected_brands = self._extract_likely_brands(dict(mention_counts))

        # 3. Sponsored ratio
        influencer.sponsored_ratio = round(sponsored_count / len(posts), 2) if posts else 0.0

        # 4. Content language detection
        combined_text = " ".join(all_captions)
        influencer.content_language = self._detect_language(combined_text)

        # 5. Content themes for creative matching
        hashtag_text = " ".join(all_hashtags).lower()
        caption_text = " ".join(all_captions).lower()
        influencer.content_themes = self._detect_content_themes(
            posts=posts,
            hashtag_text=hashtag_text,
            caption_text=caption_text,
            sponsored_ratio=influencer.sponsored_ratio
        )

    async def _mark_scrape_status(
        self,
        influencer: Influencer,
        status: str,
        message: str
    ):
        """Mark influencer with scrape status."""
        influencer.post_content_aggregated = {
            "scrape_status": status,
            "message": message,
            "last_scraped_at": datetime.now(timezone.utc).isoformat()
        }

    @staticmethod
    def _extract_keywords(caption: str) -> List[str]:
        """Extract meaningful keywords from caption."""
        # Remove hashtags and mentions
        text = re.sub(r'[#@]\w+', '', caption)
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        # Extract words 4+ chars (more significant)
        words = re.findall(r'\b[a-zA-ZáéíóúñüÁÉÍÓÚÑÜ]{4,}\b', text.lower())
        # Filter common stopwords (English + Spanish)
        stopwords = {
            'this', 'that', 'with', 'from', 'have', 'what', 'your', 'been',
            'will', 'more', 'when', 'there', 'their', 'about', 'would', 'which',
            'como', 'para', 'este', 'esta', 'esto', 'estos', 'estas', 'pero',
            'todo', 'todos', 'toda', 'todas', 'muy', 'bien', 'aquí', 'ahora',
            'siempre', 'nunca', 'también', 'porque', 'cuando', 'donde', 'quien'
        }
        return [w for w in words if w not in stopwords]

    @staticmethod
    def _extract_likely_brands(mention_counts: Dict[str, int]) -> List[str]:
        """
        Extract likely brand handles from mentions.
        Filters out personal accounts and common non-brand mentions.
        """
        # Common non-brand patterns to filter out
        non_brand_patterns = [
            r'^[a-z]+\d+$',  # Likely personal accounts like "john123"
            r'^\d',  # Starts with number
            r'^(oficial|official)$',
        ]
        
        # Known brand suffixes/patterns
        brand_indicators = ['oficial', 'official', 'brand', 'sport', 'sports', 'store', 'shop']
        
        likely_brands = []
        for mention, count in mention_counts.items():
            mention_lower = mention.lower()
            
            # Skip if matches non-brand pattern
            is_non_brand = any(re.match(p, mention_lower) for p in non_brand_patterns)
            if is_non_brand:
                continue
            
            # Include if mentioned multiple times or has brand indicators
            has_brand_indicator = any(ind in mention_lower for ind in brand_indicators)
            if count >= 2 or has_brand_indicator or len(mention) > 15:
                likely_brands.append(mention_lower)
        
        return likely_brands[:20]  # Limit to top 20

    @staticmethod
    def _detect_language(text: str) -> str:
        """
        Simple language detection based on common word patterns.
        Returns 'es' (Spanish), 'en' (English), or 'ca' (Catalan).
        """
        if not text or len(text) < 20:
            return "es"  # Default to Spanish
        
        text_lower = text.lower()
        
        # Spanish indicators
        spanish_words = ['que', 'con', 'por', 'para', 'una', 'del', 'los', 'las', 'más', 'pero', 'muy', 'también', 'está', 'este']
        spanish_count = sum(1 for w in spanish_words if f' {w} ' in f' {text_lower} ')
        
        # English indicators
        english_words = ['the', 'and', 'for', 'you', 'with', 'this', 'that', 'have', 'are', 'from', 'your', 'was', 'been']
        english_count = sum(1 for w in english_words if f' {w} ' in f' {text_lower} ')
        
        # Catalan indicators
        catalan_words = ['amb', 'per', 'què', 'més', 'molt', 'això', 'aquesta', 'aquest', 'seva', 'són']
        catalan_count = sum(1 for w in catalan_words if f' {w} ' in f' {text_lower} ')
        
        # Return language with highest count
        counts = {'es': spanish_count, 'en': english_count, 'ca': catalan_count}
        detected = max(counts, key=counts.get)
        
        # Default to Spanish if no clear winner
        if counts[detected] < 2:
            return "es"
        
        return detected

    @staticmethod
    def _detect_content_themes(
        posts: List[InstagramPost],
        hashtag_text: str,
        caption_text: str,
        sponsored_ratio: float
    ) -> Dict[str, Any]:
        """
        Detect content themes for creative matching.
        
        Returns dict with:
        - detected_themes: List of theme keys found
        - narrative_style: "storytelling", "casual", "minimal", or "promotional"
        - format_preference: List of post types used
        - avg_caption_length: Average caption length
        """
        # Detect themes from hashtags and captions
        detected_themes = []
        combined_text = hashtag_text + " " + caption_text
        
        for theme, keywords in THEME_KEYWORDS.items():
            if any(kw in combined_text for kw in keywords):
                detected_themes.append(theme)
        
        # Calculate average caption length
        caption_lengths = [len(p.caption or "") for p in posts]
        avg_caption_length = sum(caption_lengths) / len(caption_lengths) if caption_lengths else 0
        
        # Determine narrative style based on caption length and content
        if sponsored_ratio > 0.5:
            narrative_style = "promotional"
        elif avg_caption_length > 200:
            narrative_style = "storytelling"
        elif avg_caption_length > 50:
            narrative_style = "casual"
        else:
            narrative_style = "minimal"
        
        # Get format preferences (post types used)
        format_preference = list(set(p.post_type for p in posts if p.post_type))
        
        return {
            "detected_themes": detected_themes,
            "narrative_style": narrative_style,
            "format_preference": format_preference,
            "avg_caption_length": int(avg_caption_length)
        }

    def _save_progress(self, processed_ids: List[str]):
        """Save progress for resume capability."""
        progress = {
            "processed_ids": processed_ids,
            "stats": self.stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        with open(self.progress_file, 'w') as f:
            json.dump(progress, f)

    async def run_full_enrichment(
        self,
        limit: Optional[int] = None,
        dry_run: bool = False
    ):
        """
        Run full enrichment pipeline.

        Args:
            limit: Max influencers to process (None = all)
            dry_run: If True, don't actually scrape, just report what would be done
        """
        influencers = await self.get_influencers_to_enrich(limit=limit)
        self.stats["total"] = len(influencers)

        logger.info("=" * 60)
        logger.info(f"Apify Post Enrichment Pipeline")
        logger.info("=" * 60)
        logger.info(f"Total influencers to enrich: {len(influencers)}")
        logger.info(f"Posts per influencer: {self.posts_per_user}")
        logger.info(f"Batch size: {self.batch_size}")

        if dry_run:
            estimated_posts = len(influencers) * self.posts_per_user
            estimated_cost = estimated_posts * 0.0023
            
            # Count skipped (over 2.5M followers)
            async with self.session_factory() as session:
                skipped_query = await session.execute(
                    select(Influencer)
                    .where(
                        and_(
                            Influencer.platform_type == "instagram",
                            Influencer.username.isnot(None),
                            Influencer.follower_count >= MAX_FOLLOWER_COUNT
                        )
                    )
                )
                skipped_count = len(list(skipped_query.scalars().all()))
            
            logger.info("")
            logger.info("DRY RUN - No actual scraping will occur")
            logger.info(f"Influencers to scrape: {len(influencers):,} (under {MAX_FOLLOWER_COUNT:,} followers)")
            logger.info(f"Influencers skipped: {skipped_count:,} (over {MAX_FOLLOWER_COUNT:,} followers)")
            logger.info(f"Would scrape approximately: {estimated_posts:,} posts")
            logger.info(f"Estimated cost: ${estimated_cost:.2f}")
            logger.info("")
            logger.info("New columns to populate:")
            logger.info("  - primary_niche (from niche taxonomy)")
            logger.info("  - niche_confidence (0.0-1.0)")
            logger.info("  - detected_brands (from @mentions)")
            logger.info("  - sponsored_ratio (0.0-1.0)")
            logger.info("  - content_language (es/en/ca)")
            logger.info("  - content_themes (for creative matching)")
            logger.info("")
            logger.info("Sample influencers (first 10):")
            for inf in influencers[:10]:
                followers = inf["follower_count"] or 0
                logger.info(f"  - @{inf['username']} ({followers:,} followers)")
            return

        # Process in batches
        total_batches = (len(influencers) + self.batch_size - 1) // self.batch_size
        processed_ids = []

        for i in range(0, len(influencers), self.batch_size):
            batch = influencers[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1

            result = await self.process_batch(batch, batch_num, total_batches)

            # Track progress
            processed_ids.extend([str(inf["id"]) for inf in batch])
            self._save_progress(processed_ids)

            # Progress update
            logger.info(
                f"Progress: {self.stats['processed']}/{self.stats['total']} | "
                f"Success: {self.stats['success']} | "
                f"Failed: {self.stats['failed']} | "
                f"Posts: {self.stats['posts_scraped']:,} | "
                f"Est. Cost: ${self.stats['estimated_cost']:.2f}"
            )

            # Small delay between batches to avoid overwhelming the API
            if i + self.batch_size < len(influencers):
                await asyncio.sleep(5)

        # Final summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("Enrichment Complete!")
        logger.info("=" * 60)
        logger.info(f"Total processed: {self.stats['processed']}")
        logger.info(f"Successful: {self.stats['success']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(f"Posts scraped: {self.stats['posts_scraped']:,}")
        logger.info(f"Estimated cost: ${self.stats['estimated_cost']:.2f}")


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Enrich influencers with Instagram post content via Apify"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of influencers per batch (default: 50)"
    )
    parser.add_argument(
        "--posts-per-user",
        type=int,
        default=6,
        help="Number of posts to scrape per influencer (default: 6, ~$55 for 4000 influencers)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit total influencers to process (default: all)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be scraped without actually scraping"
    )
    args = parser.parse_args()

    # Setup database connection with connection pool settings
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url, 
        echo=False,
        pool_pre_ping=True,  # Check connections before use
        pool_recycle=300,    # Recycle connections after 5 minutes
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    pipeline = ApifyEnrichmentPipeline(
        session_factory=session_factory,
        batch_size=args.batch_size,
        posts_per_user=args.posts_per_user
    )

    await pipeline.run_full_enrichment(
        limit=args.limit,
        dry_run=args.dry_run
    )
    
    # Cleanup
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
