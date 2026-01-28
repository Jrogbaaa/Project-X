from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
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
        limit: int = 100,
        include_partial_data: bool = True
    ) -> List[Influencer]:
        """
        Find cached influencers matching basic criteria.
        
        Args:
            min_credibility: Minimum credibility score (0-100)
            min_spain_pct: Minimum Spain audience percentage
            min_engagement: Minimum engagement rate
            limit: Maximum results
            include_partial_data: If True, include profiles without full metrics
        """
        now = datetime.utcnow()

        # Build query conditions
        conditions = [
            Influencer.cache_expires_at > now,  # Not expired
        ]

        # Handle credibility filter - allow NULL for imported data without metrics
        if include_partial_data:
            conditions.append(
                or_(
                    Influencer.credibility_score >= min_credibility,
                    Influencer.credibility_score.is_(None)
                )
            )
        else:
            conditions.append(Influencer.credibility_score >= min_credibility)

        # Add engagement filter if specified
        if min_engagement is not None:
            if include_partial_data:
                conditions.append(
                    or_(
                        Influencer.engagement_rate >= min_engagement,
                        Influencer.engagement_rate.is_(None)
                    )
                )
            else:
                conditions.append(Influencer.engagement_rate >= min_engagement)

        query = (
            select(Influencer)
            .where(and_(*conditions))
            .limit(limit)
        )

        result = await self.db.execute(query)
        influencers = result.scalars().all()

        # Filter by Spain percentage (requires checking JSONB)
        # For imported data without audience_geography, check country field
        filtered = []
        for inf in influencers:
            spain_pct = (inf.audience_geography or {}).get("ES", 0)
            # If no audience data but country is Spain, assume 100% Spain
            if spain_pct == 0 and inf.country and inf.country.lower() == "spain":
                spain_pct = 100
            if spain_pct >= min_spain_pct or include_partial_data:
                filtered.append(inf)

        return filtered

    async def find_by_interests(
        self,
        interests: List[str],
        exclude_interests: Optional[List[str]] = None,
        country: Optional[str] = None,
        limit: int = 100
    ) -> List[Influencer]:
        """
        Find influencers by matching interests/niches.
        
        Args:
            interests: List of interests to match (e.g., ["Soccer", "Sports"])
            exclude_interests: List of interests to exclude
            country: Filter by country
            limit: Maximum results
        """
        now = datetime.utcnow()
        
        conditions = [
            Influencer.cache_expires_at > now,
            Influencer.interests.isnot(None),
        ]
        
        # Filter by country if specified
        if country:
            conditions.append(
                func.lower(Influencer.country) == country.lower()
            )
        
        query = (
            select(Influencer)
            .where(and_(*conditions))
            .limit(limit * 3)  # Fetch more to filter in Python
        )
        
        result = await self.db.execute(query)
        influencers = list(result.scalars().all())
        
        # Score and filter by interests in Python for flexibility
        scored = []
        for inf in influencers:
            inf_interests = inf.interests or []
            inf_interests_lower = [i.lower() for i in inf_interests]
            inf_bio = (inf.bio or "").lower()
            
            # Calculate match score
            score = 0
            for interest in interests:
                interest_lower = interest.lower()
                if interest_lower in inf_interests_lower:
                    score += 2  # Direct match
                elif interest_lower in inf_bio:
                    score += 1  # Bio mention
            
            # Apply exclusion penalty
            exclude_penalty = 0
            if exclude_interests:
                for exclude in exclude_interests:
                    exclude_lower = exclude.lower()
                    if exclude_lower in inf_interests_lower:
                        exclude_penalty += 3  # Heavy penalty for excluded interest
                    elif exclude_lower in inf_bio:
                        exclude_penalty += 1
            
            final_score = score - exclude_penalty
            
            if final_score > 0:
                scored.append((inf, final_score))
        
        # Sort by score and return top results
        scored.sort(key=lambda x: x[1], reverse=True)
        return [inf for inf, _ in scored[:limit]]

    async def search_by_keywords(
        self,
        keywords: List[str],
        limit: int = 100
    ) -> List[Influencer]:
        """
        Search influencers by keywords in bio and interests.
        
        Args:
            keywords: Keywords to search for
            limit: Maximum results
        """
        now = datetime.utcnow()
        
        conditions = [
            Influencer.cache_expires_at > now,
        ]
        
        # Build keyword search conditions
        keyword_conditions = []
        for keyword in keywords:
            keyword_lower = keyword.lower()
            # Search in bio
            keyword_conditions.append(
                func.lower(Influencer.bio).contains(keyword_lower)
            )
            # Search in interests JSONB (cast to text for LIKE search)
            keyword_conditions.append(
                func.lower(Influencer.interests.cast(sa.Text())).contains(keyword_lower)
            )
        
        if keyword_conditions:
            conditions.append(or_(*keyword_conditions))
        
        query = (
            select(Influencer)
            .where(and_(*conditions))
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_all_active(self, limit: int = 1000) -> List[Influencer]:
        """Get all non-expired influencers."""
        now = datetime.utcnow()
        
        query = (
            select(Influencer)
            .where(Influencer.cache_expires_at > now)
            .order_by(Influencer.follower_count.desc().nullslast())
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

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
            # Update new fields
            existing.interests = metrics.get('interests') or existing.interests
            existing.brand_mentions = metrics.get('brand_mentions') or existing.brand_mentions
            existing.country = metrics.get('country') or existing.country
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
                display_name=metrics.get('display_name'),
                profile_picture_url=metrics.get('profile_picture_url'),
                bio=metrics.get('bio'),
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
                interests=metrics.get('interests'),
                brand_mentions=metrics.get('brand_mentions'),
                country=metrics.get('country'),
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

    async def get_expiring_soon(
        self,
        days_until_expiry: int = 1,
        limit: int = 100
    ) -> List[Influencer]:
        """
        Get influencers whose cache expires within N days.
        Useful for proactive cache warming.
        
        Args:
            days_until_expiry: Find entries expiring within this many days
            limit: Maximum results to return
            
        Returns:
            List of influencers with expiring cache
        """
        now = datetime.utcnow()
        expiry_threshold = now + timedelta(days=days_until_expiry)
        
        query = (
            select(Influencer)
            .where(
                and_(
                    Influencer.cache_expires_at > now,  # Not yet expired
                    Influencer.cache_expires_at <= expiry_threshold,  # But expiring soon
                )
            )
            .order_by(Influencer.cache_expires_at.asc())  # Soonest first
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def upsert_influencers_bulk(
        self,
        influencers_data: List[Dict[str, Any]],
        platform_type: str = "instagram"
    ) -> int:
        """
        Bulk upsert influencers using PostgreSQL ON CONFLICT.
        More efficient than individual upserts for large batches.
        
        Args:
            influencers_data: List of dicts with influencer data
                Each dict should have 'username' and 'metrics' keys
            platform_type: Platform type for all influencers
            
        Returns:
            Number of influencers upserted
        """
        if not influencers_data:
            return 0
        
        now = datetime.utcnow()
        expires_at = now + self.cache_duration
        
        # Prepare values for bulk insert
        values = []
        for data in influencers_data:
            username = data.get('username')
            metrics = data.get('metrics', {})
            
            if not username:
                continue
                
            values.append({
                'platform_type': platform_type,
                'username': username,
                'display_name': metrics.get('display_name'),
                'profile_picture_url': metrics.get('profile_picture_url'),
                'bio': metrics.get('bio'),
                'is_verified': metrics.get('is_verified', False),
                'follower_count': metrics.get('follower_count'),
                'credibility_score': metrics.get('credibility_score'),
                'engagement_rate': metrics.get('engagement_rate'),
                'follower_growth_rate_6m': metrics.get('follower_growth_rate_6m'),
                'avg_likes': metrics.get('avg_likes'),
                'avg_comments': metrics.get('avg_comments'),
                'avg_views': metrics.get('avg_views'),
                'audience_genders': metrics.get('audience_genders'),
                'audience_age_distribution': metrics.get('audience_age_distribution'),
                'audience_geography': metrics.get('audience_geography'),
                'interests': metrics.get('interests'),
                'brand_mentions': metrics.get('brand_mentions'),
                'country': metrics.get('country'),
                'cached_at': now,
                'cache_expires_at': expires_at,
                'updated_at': now,
            })
        
        if not values:
            return 0
        
        # Use PostgreSQL INSERT ... ON CONFLICT for efficient upsert
        stmt = insert(Influencer).values(values)
        
        # On conflict, update all fields except id and created_at
        update_dict = {
            'display_name': stmt.excluded.display_name,
            'profile_picture_url': stmt.excluded.profile_picture_url,
            'bio': stmt.excluded.bio,
            'is_verified': stmt.excluded.is_verified,
            'follower_count': stmt.excluded.follower_count,
            'credibility_score': stmt.excluded.credibility_score,
            'engagement_rate': stmt.excluded.engagement_rate,
            'follower_growth_rate_6m': stmt.excluded.follower_growth_rate_6m,
            'avg_likes': stmt.excluded.avg_likes,
            'avg_comments': stmt.excluded.avg_comments,
            'avg_views': stmt.excluded.avg_views,
            'audience_genders': stmt.excluded.audience_genders,
            'audience_age_distribution': stmt.excluded.audience_age_distribution,
            'audience_geography': stmt.excluded.audience_geography,
            'interests': stmt.excluded.interests,
            'brand_mentions': stmt.excluded.brand_mentions,
            'country': stmt.excluded.country,
            'cached_at': stmt.excluded.cached_at,
            'cache_expires_at': stmt.excluded.cache_expires_at,
            'updated_at': stmt.excluded.updated_at,
        }
        
        stmt = stmt.on_conflict_do_update(
            index_elements=['platform_type', 'username'],
            set_=update_dict
        )
        
        await self.db.execute(stmt)
        await self.db.flush()
        
        return len(values)

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring.
        
        Returns:
            Dict with cache statistics
        """
        now = datetime.utcnow()
        
        # Total cached
        total_query = select(func.count(Influencer.id))
        total_result = await self.db.execute(total_query)
        total_cached = total_result.scalar() or 0
        
        # Active (not expired)
        active_query = select(func.count(Influencer.id)).where(
            Influencer.cache_expires_at > now
        )
        active_result = await self.db.execute(active_query)
        active_count = active_result.scalar() or 0
        
        # Expiring within 24 hours
        expiring_soon_query = select(func.count(Influencer.id)).where(
            and_(
                Influencer.cache_expires_at > now,
                Influencer.cache_expires_at <= now + timedelta(hours=24)
            )
        )
        expiring_soon_result = await self.db.execute(expiring_soon_query)
        expiring_soon = expiring_soon_result.scalar() or 0
        
        # With full metrics (credibility score not null)
        with_metrics_query = select(func.count(Influencer.id)).where(
            and_(
                Influencer.cache_expires_at > now,
                Influencer.credibility_score.isnot(None)
            )
        )
        with_metrics_result = await self.db.execute(with_metrics_query)
        with_full_metrics = with_metrics_result.scalar() or 0
        
        return {
            'total_cached': total_cached,
            'active_count': active_count,
            'expired_count': total_cached - active_count,
            'expiring_within_24h': expiring_soon,
            'with_full_metrics': with_full_metrics,
            'partial_data_only': active_count - with_full_metrics,
            'cache_ttl_hours': self.settings.influencer_cache_hours,
        }
