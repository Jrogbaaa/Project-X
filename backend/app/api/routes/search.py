from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.services.search_service import SearchService
from app.schemas.search import (
    SearchRequest,
    SearchResponse,
    SaveSearchRequest,
    SavedSearch,
    SearchHistoryItem
)
from app.core.exceptions import SearchError

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def execute_search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Execute an influencer search using natural language query.

    Examples:
    - "5 female influencers for IKEA"
    - "10 lifestyle influencers with high engagement for a beauty brand"
    - "Find 3 micro-influencers in home decor niche"

    The query is parsed by an LLM to extract:
    - Target count (number of influencers)
    - Gender preferences
    - Brand context and category
    - Content themes
    - Audience requirements

    Results are filtered by configurable thresholds (credibility, engagement, Spain audience)
    and ranked using a weighted multi-factor algorithm.
    """
    service = SearchService(db)
    try:
        return await service.execute_search(request)
    except SearchError as e:
        raise HTTPException(status_code=500, detail=str(e.message))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/{search_id}", response_model=SearchResponse)
async def get_search(
    search_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve a previous search by ID with full results."""
    service = SearchService(db)
    search = await service.get_search(search_id)

    if not search:
        raise HTTPException(status_code=404, detail=f"Search {search_id} not found")

    # Reconstruct the search response
    # This would need the full results - for now return basic info
    from app.schemas.llm import ParsedSearchQuery
    from app.schemas.search import FilterConfig

    parsed = ParsedSearchQuery(**search.parsed_query) if search.parsed_query else ParsedSearchQuery()
    filters = FilterConfig(
        min_credibility_score=search.min_credibility_score or 70.0,
        min_engagement_rate=search.min_engagement_rate,
        min_spain_audience_pct=search.min_spain_audience_pct or 60.0,
    )

    # Get results from search_results table
    from sqlalchemy import select
    from app.models.search import SearchResult
    from app.models.influencer import Influencer
    from app.schemas.influencer import RankedInfluencer, ScoreComponents, InfluencerData

    query = (
        select(SearchResult, Influencer)
        .join(Influencer, SearchResult.influencer_id == Influencer.id)
        .where(SearchResult.search_id == search_id)
        .order_by(SearchResult.rank_position)
    )
    result = await db.execute(query)
    rows = result.all()

    results = []
    for sr, inf in rows:
        influencer_data = InfluencerData(
            id=str(inf.id),
            username=inf.username,
            display_name=inf.display_name,
            profile_picture_url=inf.profile_picture_url,
            bio=inf.bio,
            is_verified=inf.is_verified,
            follower_count=inf.follower_count or 0,
            credibility_score=inf.credibility_score,
            engagement_rate=inf.engagement_rate,
            follower_growth_rate_6m=inf.follower_growth_rate_6m,
            avg_likes=inf.avg_likes or 0,
            avg_comments=inf.avg_comments or 0,
            audience_genders=inf.audience_genders or {},
            audience_age_distribution=inf.audience_age_distribution or {},
            audience_geography=inf.audience_geography or {},
        )

        results.append(RankedInfluencer(
            influencer_id=str(inf.id),
            username=inf.username,
            rank_position=sr.rank_position,
            relevance_score=sr.relevance_score or 0,
            scores=ScoreComponents(
                credibility=sr.credibility_score_normalized or 0,
                engagement=sr.engagement_score_normalized or 0,
                audience_match=sr.audience_match_score or 0,
                growth=sr.growth_score_normalized or 0,
                geography=sr.geography_score or 0,
            ),
            raw_data=influencer_data
        ))

    return SearchResponse(
        search_id=str(search.id),
        query=search.raw_query,
        parsed_query=parsed,
        filters_applied=filters,
        results=results,
        total_candidates=search.result_count or len(results),
        total_after_filter=search.result_count or len(results),
        executed_at=search.executed_at
    )


@router.post("/{search_id}/save", response_model=SavedSearch)
async def save_search(
    search_id: UUID,
    request: SaveSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """Save a search for later reference."""
    service = SearchService(db)
    try:
        search = await service.save_search(
            search_id=search_id,
            name=request.name,
            description=request.description
        )
        return SavedSearch(
            id=str(search.id),
            name=search.saved_name,
            description=search.saved_description,
            raw_query=search.raw_query,
            parsed_query=search.parsed_query or {},
            result_count=search.result_count or 0,
            created_at=search.created_at,
            updated_at=search.updated_at
        )
    except SearchError as e:
        raise HTTPException(status_code=404, detail=str(e.message))


@router.get("/saved/list", response_model=List[SavedSearch])
async def list_saved_searches(
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get all saved searches."""
    service = SearchService(db)
    searches = await service.get_saved_searches(limit=limit)
    return [
        SavedSearch(
            id=str(s.id),
            name=s.saved_name or "",
            description=s.saved_description,
            raw_query=s.raw_query,
            parsed_query=s.parsed_query or {},
            result_count=s.result_count or 0,
            created_at=s.created_at,
            updated_at=s.updated_at
        )
        for s in searches
    ]


@router.get("/history/list", response_model=List[SearchHistoryItem])
async def list_search_history(
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get recent search history."""
    service = SearchService(db)
    searches = await service.get_search_history(limit=limit)
    return [
        SearchHistoryItem(
            id=str(s.id),
            raw_query=s.raw_query,
            result_count=s.result_count or 0,
            is_saved=s.is_saved or False,
            saved_name=s.saved_name,
            executed_at=s.executed_at
        )
        for s in searches
    ]
