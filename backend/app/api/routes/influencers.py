from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional
from pydantic import BaseModel
import logging

from app.core.database import get_db
from app.services.cache_service import CacheService
from app.services.primetag_client import PrimeTagClient
from app.schemas.influencer import InfluencerData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/influencers", tags=["influencers"])


class CacheWarmRequest(BaseModel):
    """Request body for cache warming."""
    limit: int = 100
    days_until_expiry: int = 1


class CacheWarmResponse(BaseModel):
    """Response for cache warming."""
    message: str
    influencers_queued: int
    refreshed_count: int
    failed_count: int


class CacheStatsResponse(BaseModel):
    """Response for cache statistics."""
    total_cached: int
    active_count: int
    expired_count: int
    expiring_within_24h: int
    with_full_metrics: int
    partial_data_only: int
    cache_ttl_hours: int


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


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    db: AsyncSession = Depends(get_db)
):
    """
    Get cache statistics for monitoring.
    
    Returns counts of total cached, active, expiring soon, etc.
    """
    cache_service = CacheService(db)
    stats = await cache_service.get_cache_stats()
    return CacheStatsResponse(**stats)


@router.post("/cache/warm", response_model=CacheWarmResponse)
async def warm_cache(
    request: CacheWarmRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Pre-emptively refresh cache entries close to expiration.
    
    This endpoint finds influencers whose cache expires within the specified
    number of days and refreshes their data from PrimeTag API.
    
    Args:
        limit: Maximum number of influencers to refresh (default: 100)
        days_until_expiry: Refresh entries expiring within N days (default: 1)
    
    Returns:
        Count of influencers queued and refreshed
    """
    cache_service = CacheService(db)
    primetag_client = PrimeTagClient()
    
    # Find expiring influencers
    expiring = await cache_service.get_expiring_soon(
        days_until_expiry=request.days_until_expiry,
        limit=request.limit
    )
    
    if not expiring:
        return CacheWarmResponse(
            message="No influencers found expiring soon",
            influencers_queued=0,
            refreshed_count=0,
            failed_count=0
        )
    
    refreshed_count = 0
    failed_count = 0
    
    # Refresh each expiring influencer
    for influencer in expiring:
        try:
            # Get mediakit URL to extract encrypted username
            # If we don't have the encrypted username, we need to search first
            if not influencer.profile_url:
                logger.warning(f"No profile URL for {influencer.username}, skipping")
                failed_count += 1
                continue
            
            # Extract encrypted username from mediakit URL
            encrypted_username = PrimeTagClient.extract_encrypted_username(
                influencer.profile_url
            )
            
            if not encrypted_username:
                # Try searching by username
                logger.info(f"Searching for {influencer.username} to refresh cache")
                search_results = await primetag_client.search_media_kits(
                    influencer.username,
                    limit=1
                )
                
                if not search_results:
                    logger.warning(f"Could not find {influencer.username} in PrimeTag")
                    failed_count += 1
                    continue
                
                encrypted_username = PrimeTagClient.extract_encrypted_username(
                    search_results[0].mediakit_url
                )
            
            if not encrypted_username:
                logger.warning(f"Could not extract encrypted username for {influencer.username}")
                failed_count += 1
                continue
            
            # Fetch fresh data from PrimeTag
            detail = await primetag_client.get_media_kit_detail(encrypted_username)
            metrics = primetag_client.extract_metrics(detail)
            
            # Update the cache with fresh data
            # Create a minimal summary object for upsert
            summary = type('Summary', (), {'username': influencer.username})()
            await cache_service.upsert_influencer(summary, metrics, influencer.platform_type)
            
            refreshed_count += 1
            logger.info(f"Refreshed cache for {influencer.username}")
            
        except Exception as e:
            logger.error(f"Failed to refresh {influencer.username}: {str(e)}")
            failed_count += 1
    
    # Commit all changes
    await db.commit()
    
    return CacheWarmResponse(
        message=f"Cache warming completed for {refreshed_count} influencers",
        influencers_queued=len(expiring),
        refreshed_count=refreshed_count,
        failed_count=failed_count
    )


@router.delete("/cache/expired")
async def cleanup_expired_cache(
    limit: int = 1000,
    db: AsyncSession = Depends(get_db)
):
    """
    Remove expired cache entries.
    
    This is a maintenance endpoint to clean up stale data.
    
    Args:
        limit: Maximum number of entries to delete (default: 1000)
    
    Returns:
        Count of deleted entries
    """
    cache_service = CacheService(db)
    deleted_count = await cache_service.cleanup_expired(limit=limit)
    
    return {
        "message": f"Deleted {deleted_count} expired cache entries",
        "deleted_count": deleted_count
    }
