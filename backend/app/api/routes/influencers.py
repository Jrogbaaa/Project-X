from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.services.cache_service import CacheService
from app.schemas.influencer import InfluencerData

router = APIRouter(prefix="/influencers", tags=["influencers"])


@router.get("/{influencer_id}", response_model=InfluencerData)
async def get_influencer(
    influencer_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed influencer data by ID."""
    cache_service = CacheService(db)
    influencer = await cache_service.get_by_id(influencer_id)

    if not influencer:
        raise HTTPException(status_code=404, detail=f"Influencer {influencer_id} not found")

    return InfluencerData(
        id=str(influencer.id),
        username=influencer.username,
        display_name=influencer.display_name,
        profile_picture_url=influencer.profile_picture_url,
        bio=influencer.bio,
        is_verified=influencer.is_verified or False,
        follower_count=influencer.follower_count or 0,
        credibility_score=influencer.credibility_score,
        engagement_rate=influencer.engagement_rate,
        follower_growth_rate_6m=influencer.follower_growth_rate_6m,
        avg_likes=influencer.avg_likes or 0,
        avg_comments=influencer.avg_comments or 0,
        avg_views=influencer.avg_views,
        audience_genders=influencer.audience_genders or {},
        audience_age_distribution=influencer.audience_age_distribution or {},
        audience_geography=influencer.audience_geography or {},
        interests=influencer.interests or [],
        brand_mentions=influencer.brand_mentions or [],
        platform_type=influencer.platform_type or "instagram",
        cached_at=influencer.cached_at
    )


@router.get("/username/{username}", response_model=InfluencerData)
async def get_influencer_by_username(
    username: str,
    platform: str = "instagram",
    db: AsyncSession = Depends(get_db)
):
    """Get detailed influencer data by username."""
    cache_service = CacheService(db)
    influencer = await cache_service.get_by_username(username, platform)

    if not influencer:
        raise HTTPException(
            status_code=404,
            detail=f"Influencer @{username} not found. Try searching first."
        )

    return InfluencerData(
        id=str(influencer.id),
        username=influencer.username,
        display_name=influencer.display_name,
        profile_picture_url=influencer.profile_picture_url,
        bio=influencer.bio,
        is_verified=influencer.is_verified or False,
        follower_count=influencer.follower_count or 0,
        credibility_score=influencer.credibility_score,
        engagement_rate=influencer.engagement_rate,
        follower_growth_rate_6m=influencer.follower_growth_rate_6m,
        avg_likes=influencer.avg_likes or 0,
        avg_comments=influencer.avg_comments or 0,
        avg_views=influencer.avg_views,
        audience_genders=influencer.audience_genders or {},
        audience_age_distribution=influencer.audience_age_distribution or {},
        audience_geography=influencer.audience_geography or {},
        interests=influencer.interests or [],
        brand_mentions=influencer.brand_mentions or [],
        platform_type=influencer.platform_type or "instagram",
        cached_at=influencer.cached_at
    )
