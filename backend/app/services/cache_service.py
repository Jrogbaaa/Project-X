from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert

from app.models.influencer import Influencer
from app.config import get_settings


class CacheService:
    """Service for managing influencer data cache."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.cache_duration = timedelta(hours=self.settings.influencer_cache_hours)

    async def find_matching(
        self,
        min_credibility: float = 0,
        min_spain_pct: float = 0,
        min_engagement: Optional[float] = None,
        limit: int = 100
    ) -> List[Influencer]:
        """Find cached influencers matching basic criteria."""
        now = datetime.utcnow()

        # Build query conditions
        conditions = [
            Influencer.cache_expires_at > now,  # Not expired
            Influencer.credibility_score >= min_credibility,
        ]

        # Add engagement filter if specified
        if min_engagement is not None:
            conditions.append(Influencer.engagement_rate >= min_engagement)

        query = (
            select(Influencer)
            .where(and_(*conditions))
            .limit(limit)
        )

        result = await self.db.execute(query)
        influencers = result.scalars().all()

        # Filter by Spain percentage (requires checking JSONB)
        filtered = []
        for inf in influencers:
            spain_pct = (inf.audience_geography or {}).get("ES", 0)
            if spain_pct >= min_spain_pct:
                filtered.append(inf)

        return filtered

    async def exists(self, username: str, platform_type: str = "instagram") -> bool:
        """Check if an influencer exists in cache and is not expired."""
        now = datetime.utcnow()

        query = select(Influencer.id).where(
            and_(
                Influencer.username == username,
                Influencer.platform_type == platform_type,
                Influencer.cache_expires_at > now
            )
        )

        result = await self.db.execute(query)
        return result.scalar() is not None

    async def get_by_username(
        self,
        username: str,
        platform_type: str = "instagram"
    ) -> Optional[Influencer]:
        """Get cached influencer by username."""
        query = select(Influencer).where(
            and_(
                Influencer.username == username,
                Influencer.platform_type == platform_type
            )
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, influencer_id: UUID) -> Optional[Influencer]:
        """Get cached influencer by ID."""
        query = select(Influencer).where(Influencer.id == influencer_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_ids(self, influencer_ids: List[UUID]) -> List[Influencer]:
        """Get multiple cached influencers by IDs."""
        query = select(Influencer).where(Influencer.id.in_(influencer_ids))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def upsert_influencer(
        self,
        summary: Any,  # MediaKitSummary or similar
        metrics: Dict[str, Any],
        platform_type: str = "instagram"
    ) -> Influencer:
        """Insert or update an influencer in the cache."""
        now = datetime.utcnow()
        expires_at = now + self.cache_duration

        # Extract username from summary
        username = summary.username if hasattr(summary, 'username') else summary.get('username', '')

        # Check if exists
        existing = await self.get_by_username(username, platform_type)

        if existing:
            # Update existing record
            existing.display_name = metrics.get('display_name') or existing.display_name
            existing.profile_picture_url = metrics.get('profile_picture_url') or existing.profile_picture_url
            existing.bio = metrics.get('bio') or existing.bio
            existing.profile_url = metrics.get('profile_url') or existing.profile_url
            existing.is_verified = metrics.get('is_verified', existing.is_verified)
            existing.follower_count = metrics.get('follower_count') or existing.follower_count
            existing.credibility_score = metrics.get('credibility_score')
            existing.engagement_rate = metrics.get('engagement_rate')
            existing.follower_growth_rate_6m = metrics.get('follower_growth_rate_6m')
            existing.avg_likes = metrics.get('avg_likes') or existing.avg_likes
            existing.avg_comments = metrics.get('avg_comments') or existing.avg_comments
            existing.avg_views = metrics.get('avg_views') or existing.avg_views
            existing.audience_genders = metrics.get('audience_genders') or existing.audience_genders
            existing.audience_age_distribution = metrics.get('audience_age_distribution') or existing.audience_age_distribution
            existing.audience_geography = metrics.get('audience_geography') or existing.audience_geography
            existing.cached_at = now
            existing.cache_expires_at = expires_at
            existing.updated_at = now

            await self.db.flush()
            return existing

        else:
            # Create new record
            influencer = Influencer(
                platform_type=platform_type,
                username=username,
                username_encrypted=getattr(summary, 'external_social_profile_id', None),
                display_name=metrics.get('display_name'),
                profile_picture_url=metrics.get('profile_picture_url'),
                bio=metrics.get('bio'),
                profile_url=metrics.get('profile_url'),
                is_verified=metrics.get('is_verified', False),
                follower_count=metrics.get('follower_count'),
                credibility_score=metrics.get('credibility_score'),
                engagement_rate=metrics.get('engagement_rate'),
                follower_growth_rate_6m=metrics.get('follower_growth_rate_6m'),
                avg_likes=metrics.get('avg_likes'),
                avg_comments=metrics.get('avg_comments'),
                avg_views=metrics.get('avg_views'),
                audience_genders=metrics.get('audience_genders'),
                audience_age_distribution=metrics.get('audience_age_distribution'),
                audience_geography=metrics.get('audience_geography'),
                cached_at=now,
                cache_expires_at=expires_at,
            )

            self.db.add(influencer)
            await self.db.flush()
            return influencer

    async def invalidate(self, username: str, platform_type: str = "instagram"):
        """Invalidate a cached influencer."""
        influencer = await self.get_by_username(username, platform_type)
        if influencer:
            influencer.cache_expires_at = datetime.utcnow() - timedelta(seconds=1)
            await self.db.flush()

    async def cleanup_expired(self, limit: int = 1000):
        """Remove expired cache entries."""
        now = datetime.utcnow()
        # This would be better as a background job
        query = select(Influencer).where(
            Influencer.cache_expires_at < now
        ).limit(limit)

        result = await self.db.execute(query)
        expired = result.scalars().all()

        for inf in expired:
            await self.db.delete(inf)

        await self.db.commit()
        return len(expired)
