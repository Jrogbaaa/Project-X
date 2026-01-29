"""
Apify Post Enrichment Pipeline

Batch processes influencers to scrape their Instagram posts for improved niche detection.
Stores posts in influencer_posts table and aggregates content signals.

Usage:
    # Dry run - see what would be scraped
    python -m app.services.apify_enrichment_service --dry-run

    # Run enrichment on all influencers
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
from collections import Counter
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import get_settings
from app.models.influencer import Influencer
from app.models.influencer_post import InfluencerPost
from app.services.apify_client import ApifyInstagramClient, InstagramPost, ApifyAPIError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ApifyEnrichmentPipeline:
    """Pipeline for enriching influencers with post content via Apify."""

    def __init__(
        self,
        db_session: AsyncSession,
        batch_size: int = 50,
        posts_per_user: int = 30,
        progress_file: str = ".tmp/apify_progress.json"
    ):
        self.db = db_session
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
    ) -> List[Influencer]:
        """
        Get all influencers that need post content enrichment.
        Does NOT skip any - processes all influencers.

        Orders by follower count (highest first) for priority.
        """
        query = (
            select(Influencer)
            .where(
                and_(
                    Influencer.platform_type == "instagram",
                    Influencer.username.isnot(None),
                )
            )
            .order_by(Influencer.follower_count.desc().nullslast())
        )

        if limit:
            query = query.limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def process_batch(
        self,
        influencers: List[Influencer],
        batch_num: int,
        total_batches: int
    ) -> Dict[str, Any]:
        """
        Process a batch of influencers.
        Uses single Apify actor run for efficiency.
        """
        usernames = [inf.username for inf in influencers]
        logger.info(f"Batch {batch_num}/{total_batches}: Processing {len(usernames)} influencers")

        try:
            # Scrape posts for all users in batch
            posts_by_user = await self.client.scrape_users_batch(
                usernames=usernames,
                results_per_user=self.posts_per_user,
                timeout_secs=600
            )

            # Save posts and update influencers
            for inf in influencers:
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

            await self.db.commit()

            # Calculate cost estimate (~$2.30 per 1000 posts)
            total_posts = sum(len(posts) for posts in posts_by_user.values())
            self.stats["estimated_cost"] += total_posts * 0.0023

            return {"success": True, "posts_scraped": total_posts}

        except ApifyAPIError as e:
            logger.error(f"Batch {batch_num} failed: {e}")
            # Mark all as failed
            for inf in influencers:
                await self._mark_scrape_status(inf, "failed", str(e))
                self.stats["failed"] += 1
                self.stats["processed"] += 1
            await self.db.commit()
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
        """Update aggregated content field for fast niche queries."""
        # Aggregate hashtags
        all_hashtags = []
        all_mentions = []
        all_caption_words = []
        total_engagement = 0

        for post in posts:
            all_hashtags.extend(post.hashtags)
            all_mentions.extend(post.mentions)
            # Extract significant words from captions
            words = self._extract_keywords(post.caption)
            all_caption_words.extend(words)
            total_engagement += (post.likes_count or 0) + (post.comments_count or 0)

        hashtag_counts = Counter(all_hashtags).most_common(30)
        mention_counts = Counter(all_mentions).most_common(20)
        keyword_counts = Counter(all_caption_words).most_common(50)

        # Calculate avg engagement per post
        avg_engagement = total_engagement / len(posts) if posts else 0

        influencer.post_content_aggregated = {
            "top_hashtags": dict(hashtag_counts),
            "top_mentions": dict(mention_counts),
            "caption_keywords": dict(keyword_counts),
            "post_count": len(posts),
            "avg_post_engagement": round(avg_engagement, 2),
            "last_scraped_at": datetime.now(timezone.utc).isoformat(),
            "scrape_status": "complete"
        }

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
        import re
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
            logger.info("")
            logger.info("DRY RUN - No actual scraping will occur")
            logger.info(f"Would scrape approximately: {estimated_posts:,} posts")
            logger.info(f"Estimated cost: ${estimated_cost:.2f}")
            logger.info("")
            logger.info("Sample influencers (first 10):")
            for inf in influencers[:10]:
                logger.info(f"  - @{inf.username} ({inf.follower_count:,} followers)")
            return

        # Process in batches
        total_batches = (len(influencers) + self.batch_size - 1) // self.batch_size
        processed_ids = []

        for i in range(0, len(influencers), self.batch_size):
            batch = influencers[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1

            result = await self.process_batch(batch, batch_num, total_batches)

            # Track progress
            processed_ids.extend([str(inf.id) for inf in batch])
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

    # Setup database connection
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        pipeline = ApifyEnrichmentPipeline(
            db_session=session,
            batch_size=args.batch_size,
            posts_per_user=args.posts_per_user
        )

        await pipeline.run_full_enrichment(
            limit=args.limit,
            dry_run=args.dry_run
        )


if __name__ == "__main__":
    asyncio.run(main())
