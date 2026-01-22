import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Set
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestration.query_parser import parse_search_query
from app.services.primetag_client import PrimeTagClient
from app.services.filter_service import FilterService
from app.services.ranking_service import RankingService
from app.services.cache_service import CacheService
from app.schemas.search import SearchRequest, SearchResponse, FilterConfig, RankingWeights
from app.schemas.llm import ParsedSearchQuery
from app.schemas.influencer import RankedInfluencer
from app.models.search import Search, SearchResult
from app.models.influencer import Influencer
from app.core.exceptions import SearchError

logger = logging.getLogger(__name__)


class SearchService:
    """Main service for orchestrating influencer searches."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.primetag = PrimeTagClient()
        self.filter_service = FilterService()
        self.ranking_service = RankingService()
        self.cache_service = CacheService(db)

    async def execute_search(self, request: SearchRequest) -> SearchResponse:
        """
        Main search orchestration flow (local-first):
        1. Parse natural language query with LLM
        2. Search local database by interests/niche
        3. Fall back to generic cache search
        4. Search PrimeTag API only if local results insufficient
        5. Apply filters (lenient for partial data)
        6. Rank results using 8-factor scoring
        7. Save search and return
        """
        try:
            # Step 1: Parse query with LLM
            logger.info(f"Parsing query: {request.query[:100]}...")
            parsed_query = await parse_search_query(request.query)
            logger.info(f"Parsed query - topics: {parsed_query.campaign_topics}, keywords: {parsed_query.search_keywords}")

            # Merge with request filters if provided
            filters_applied = self._merge_filters(parsed_query, request.filters)

            # Track candidates
            candidates: List[Influencer] = []
            seen_usernames: Set[str] = set()
            target_candidates = parsed_query.target_count * 5  # Get 5x for filtering headroom

            # Step 2: Search local DB by interests/niche (PRIMARY SOURCE)
            if parsed_query.campaign_topics:
                logger.info(f"Searching by interests: {parsed_query.campaign_topics}")
                interest_matches = await self.cache_service.find_by_interests(
                    interests=parsed_query.campaign_topics,
                    exclude_interests=parsed_query.exclude_niches,
                    country="Spain",  # Default to Spain
                    limit=target_candidates
                )
                for inf in interest_matches:
                    if inf.username not in seen_usernames:
                        seen_usernames.add(inf.username)
                        candidates.append(inf)
                logger.info(f"Found {len(interest_matches)} matches by interests")

            # Step 3: Search by keywords in bio
            if len(candidates) < target_candidates and parsed_query.search_keywords:
                logger.info(f"Searching by keywords: {parsed_query.search_keywords}")
                keyword_matches = await self.cache_service.search_by_keywords(
                    keywords=parsed_query.search_keywords[:5],
                    limit=target_candidates
                )
                for inf in keyword_matches:
                    if inf.username not in seen_usernames:
                        seen_usernames.add(inf.username)
                        candidates.append(inf)
                logger.info(f"Found {len(keyword_matches)} matches by keywords")

            # Step 4: Fall back to generic cache search (includes partial data)
            if len(candidates) < target_candidates:
                logger.info("Falling back to generic cache search")
                cached_influencers = await self.cache_service.find_matching(
                    min_credibility=filters_applied.min_credibility_score,
                    min_spain_pct=filters_applied.min_spain_audience_pct,
                    min_engagement=filters_applied.min_engagement_rate,
                    limit=target_candidates,
                    include_partial_data=True  # Include imported profiles without full metrics
                )
                for inf in cached_influencers:
                    if inf.username not in seen_usernames:
                        seen_usernames.add(inf.username)
                        candidates.append(inf)
                logger.info(f"Total candidates after cache: {len(candidates)}")

            # Step 5: Search PrimeTag API ONLY if local results still insufficient
            if len(candidates) < target_candidates and parsed_query.search_keywords:
                logger.info(f"Local results insufficient ({len(candidates)}), trying PrimeTag API")
                await self._search_primetag_api(
                    parsed_query=parsed_query,
                    candidates=candidates,
                    seen_usernames=seen_usernames,
                    target_candidates=target_candidates
                )
                logger.info(f"Total candidates after PrimeTag: {len(candidates)}")

            total_candidates = len(candidates)

            # Step 6: Apply filters (lenient for partial data)
            filtered = self.filter_service.apply_filters(
                candidates,
                parsed_query,
                filters_applied,
                lenient_mode=True  # Don't filter out profiles missing metrics
            )
            total_after_filter = len(filtered)
            logger.info(f"After filtering: {total_after_filter} candidates")

            # Step 7: Rank results using 8-factor scoring
            ranked = self.ranking_service.rank_influencers(
                filtered,
                parsed_query,
                request.ranking_weights
            )

            # Step 8: Limit to requested count
            final_results = ranked[:request.limit]
            logger.info(f"Final results: {len(final_results)}")

            # Step 9: Save search to database
            search = await self._save_search(
                request=request,
                parsed_query=parsed_query,
                filters_applied=filters_applied,
                results=final_results,
                total_candidates=total_candidates,
                total_after_filter=total_after_filter
            )

            return SearchResponse(
                search_id=str(search.id),
                query=request.query,
                parsed_query=parsed_query,
                filters_applied=filters_applied,
                results=final_results,
                total_candidates=total_candidates,
                total_after_filter=total_after_filter,
                executed_at=search.executed_at
            )

        except Exception as e:
            logger.error(f"Search failed: {str(e)}", exc_info=True)
            raise SearchError(f"Search failed: {str(e)}")

    async def _search_primetag_api(
        self,
        parsed_query: ParsedSearchQuery,
        candidates: List[Influencer],
        seen_usernames: Set[str],
        target_candidates: int
    ):
        """Search PrimeTag API for additional candidates."""
        try:
            # Search for more candidates using keywords
            search_tasks = []
            for keyword in parsed_query.search_keywords[:5]:  # Limit API calls
                search_tasks.append(self._search_keyword(keyword))

            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

            # Collect unique usernames
            new_summaries = []
            for result in search_results:
                if isinstance(result, Exception):
                    continue
                for summary in result:
                    if summary.username not in seen_usernames:
                        seen_usernames.add(summary.username)
                        new_summaries.append(summary)

            # Fetch detailed metrics for new candidates
            if new_summaries:
                detail_tasks = []
                for summary in new_summaries[:30]:  # Limit detail fetches
                    detail_tasks.append(self._fetch_and_cache(summary))

                detail_results = await asyncio.gather(*detail_tasks, return_exceptions=True)

                for result in detail_results:
                    if isinstance(result, Influencer):
                        candidates.append(result)
        except Exception as e:
            logger.warning(f"PrimeTag API search failed: {e}")

    async def _search_keyword(self, keyword: str) -> List:
        """Search PrimeTag for a keyword."""
        try:
            return await self.primetag.search_media_kits(keyword)
        except Exception:
            return []

    async def _fetch_and_cache(self, summary) -> Optional[Influencer]:
        """Fetch detailed metrics and cache the influencer."""
        try:
            # Extract encrypted username from mediakit_url
            username_encrypted = None
            if hasattr(summary, 'mediakit_url') and summary.mediakit_url:
                username_encrypted = PrimeTagClient.extract_encrypted_username(summary.mediakit_url)

            # Fallback to external_social_profile_id if URL extraction failed
            if not username_encrypted:
                username_encrypted = summary.external_social_profile_id or summary.username

            # Get platform type from summary
            platform_type = getattr(summary, 'platform_type', PrimeTagClient.PLATFORM_INSTAGRAM)

            # Fetch detailed metrics
            detail = await self.primetag.get_media_kit_detail(username_encrypted, platform_type)
            metrics = self.primetag.extract_metrics(detail)

            # Add follower count from summary if not in metrics
            if not metrics.get('follower_count'):
                metrics['follower_count'] = summary.audience_size

            # Cache the result
            influencer = await self.cache_service.upsert_influencer(summary, metrics)
            return influencer

        except Exception:
            return None

    def _merge_filters(
        self,
        parsed_query: ParsedSearchQuery,
        request_filters: Optional[FilterConfig]
    ) -> FilterConfig:
        """Merge parsed query filters with request overrides."""
        # Start with parsed query values
        base = FilterConfig(
            min_credibility_score=parsed_query.min_credibility_score,
            min_engagement_rate=parsed_query.min_engagement_rate,
            min_spain_audience_pct=parsed_query.min_spain_audience_pct,
        )

        # Override with request filters if provided
        if request_filters:
            if request_filters.min_credibility_score is not None:
                base.min_credibility_score = request_filters.min_credibility_score
            if request_filters.min_engagement_rate is not None:
                base.min_engagement_rate = request_filters.min_engagement_rate
            if request_filters.min_spain_audience_pct is not None:
                base.min_spain_audience_pct = request_filters.min_spain_audience_pct
            if request_filters.min_follower_growth_rate is not None:
                base.min_follower_growth_rate = request_filters.min_follower_growth_rate

        return base

    async def _save_search(
        self,
        request: SearchRequest,
        parsed_query: ParsedSearchQuery,
        filters_applied: FilterConfig,
        results: List[RankedInfluencer],
        total_candidates: int,
        total_after_filter: int
    ) -> Search:
        """Persist search and results to database."""
        # Create search record
        search = Search(
            raw_query=request.query,
            parsed_query=parsed_query.model_dump(),
            target_count=parsed_query.target_count,
            gender_filter=parsed_query.influencer_gender.value if parsed_query.influencer_gender else None,
            brand_context=parsed_query.brand_name,
            min_credibility_score=filters_applied.min_credibility_score,
            min_engagement_rate=filters_applied.min_engagement_rate,
            min_spain_audience_pct=filters_applied.min_spain_audience_pct,
            min_follower_growth_rate=filters_applied.min_follower_growth_rate,
            ranking_weights=request.ranking_weights.model_dump() if request.ranking_weights else None,
            result_count=len(results),
            result_influencer_ids=[UUID(r.influencer_id) for r in results if r.influencer_id],
        )
        self.db.add(search)
        await self.db.flush()

        # Create search result records
        for result in results:
            if not result.influencer_id:
                continue

            search_result = SearchResult(
                search_id=search.id,
                influencer_id=UUID(result.influencer_id),
                rank_position=result.rank_position,
                relevance_score=result.relevance_score,
                credibility_score_normalized=result.scores.credibility,
                engagement_score_normalized=result.scores.engagement,
                audience_match_score=result.scores.audience_match,
                growth_score_normalized=result.scores.growth,
                geography_score=result.scores.geography,
                metrics_snapshot=result.raw_data.model_dump() if result.raw_data else None
            )
            self.db.add(search_result)

        await self.db.commit()
        await self.db.refresh(search)
        return search

    async def get_search(self, search_id: UUID) -> Optional[Search]:
        """Retrieve a search by ID."""
        from sqlalchemy import select
        query = select(Search).where(Search.id == search_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def save_search(
        self,
        search_id: UUID,
        name: str,
        description: Optional[str] = None
    ) -> Search:
        """Mark a search as saved."""
        search = await self.get_search(search_id)
        if not search:
            raise SearchError(f"Search {search_id} not found")

        search.is_saved = True
        search.saved_name = name
        search.saved_description = description
        search.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(search)
        return search

    async def get_saved_searches(self, limit: int = 50) -> List[Search]:
        """Get all saved searches."""
        from sqlalchemy import select
        query = (
            select(Search)
            .where(Search.is_saved == True)
            .order_by(Search.updated_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_search_history(self, limit: int = 50) -> List[Search]:
        """Get recent search history."""
        from sqlalchemy import select
        query = (
            select(Search)
            .order_by(Search.executed_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
