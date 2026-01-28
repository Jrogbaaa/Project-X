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
from app.services.brand_context_service import BrandContextService, BrandContext
from app.schemas.search import SearchRequest, SearchResponse, FilterConfig, RankingWeights, VerificationStats
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
        self.brand_context_service = BrandContextService(db)

    async def execute_search(self, request: SearchRequest) -> SearchResponse:
        """
        Main search orchestration flow with verification gate:
        1. Parse natural language query with LLM
        2. Discover candidates from local DB + PrimeTag API
        3. VERIFY each candidate via Primetag API (fetch full metrics)
        4. Apply STRICT hard filters (Spain %, credibility, ER)
        5. Rank survivors using 8-factor scoring
        6. Save search and return
        """
        try:
            # Step 1: Parse query with LLM
            logger.info(f"Parsing query: {request.query[:100]}...")
            parsed_query = await parse_search_query(request.query)
            logger.info(f"Parsed query - topics: {parsed_query.campaign_topics}, keywords: {parsed_query.search_keywords}")

            # Step 1b: Enrich with brand context from database
            brand_context = await self._get_brand_context(parsed_query.brand_name)
            if brand_context:
                parsed_query = self._enrich_with_brand_context(parsed_query, brand_context)
                logger.info(f"Enriched with brand context: {brand_context.name} ({brand_context.category})")

            # Merge with request filters if provided
            filters_applied = self._merge_filters(parsed_query, request.filters)

            # Track candidates
            candidates: List[Influencer] = []
            seen_usernames: Set[str] = set()
            target_candidates = parsed_query.target_count * 5  # Get 5x for filtering headroom

            # Step 2: Discover candidates from local DB
            if parsed_query.campaign_topics:
                logger.info(f"Searching by interests: {parsed_query.campaign_topics}")
                interest_matches = await self.cache_service.find_by_interests(
                    interests=parsed_query.campaign_topics,
                    exclude_interests=parsed_query.exclude_niches,
                    country="Spain",
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

            # Step 4: Fall back to generic cache search
            if len(candidates) < target_candidates:
                logger.info("Falling back to generic cache search")
                cached_influencers = await self.cache_service.find_matching(
                    min_credibility=0,  # Don't pre-filter, let verification handle it
                    min_spain_pct=0,
                    min_engagement=None,
                    limit=target_candidates,
                    include_partial_data=True
                )
                for inf in cached_influencers:
                    if inf.username not in seen_usernames:
                        seen_usernames.add(inf.username)
                        candidates.append(inf)
                logger.info(f"Total candidates after cache: {len(candidates)}")

            # Step 5: Search PrimeTag API if still insufficient
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

            # ============================================================
            # Step 6: VERIFICATION GATE - Verify ALL candidates via Primetag
            # ============================================================
            logger.info(f"Verifying {len(candidates)} candidates via Primetag API...")
            verified_candidates, failed_count = await self._verify_candidates_batch(
                candidates,
                max_concurrent=5
            )
            logger.info(f"Verification complete: {len(verified_candidates)} verified, {failed_count} failed")

            # ============================================================
            # Step 7: Apply STRICT hard filters (no lenient mode)
            # Only verified candidates with real metrics pass through
            # ============================================================
            filtered = self.filter_service.apply_filters(
                verified_candidates,
                parsed_query,
                filters_applied,
                lenient_mode=False  # STRICT: Must have real data to pass
            )
            total_after_filter = len(filtered)
            logger.info(f"After strict filtering: {total_after_filter} candidates")

            # Calculate rejection stats
            rejected_count = len(verified_candidates) - total_after_filter

            # Step 8: Rank survivors using 8-factor scoring
            ranked = self.ranking_service.rank_influencers(
                filtered,
                parsed_query,
                request.ranking_weights
            )

            # Step 9: Limit to requested count
            final_results = ranked[:request.limit]
            logger.info(f"Final results: {len(final_results)}")

            # Step 10: Save search to database
            search = await self._save_search(
                request=request,
                parsed_query=parsed_query,
                filters_applied=filters_applied,
                results=final_results,
                total_candidates=total_candidates,
                total_after_filter=total_after_filter
            )

            # Build verification stats
            verification_stats = VerificationStats(
                total_candidates=total_candidates,
                verified=len(verified_candidates),
                failed_verification=failed_count,
                passed_filters=total_after_filter,
            )

            return SearchResponse(
                search_id=str(search.id),
                query=request.query,
                parsed_query=parsed_query,
                filters_applied=filters_applied,
                results=final_results,
                total_candidates=total_candidates,
                total_after_filter=total_after_filter,
                verification_stats=verification_stats,
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

    def _has_full_metrics(self, influencer: Influencer) -> bool:
        """
        Check if an influencer has the full metrics required for verification.
        Required: audience_geography, credibility_score (for IG), engagement_rate
        """
        # Must have audience geography data with Spain percentage
        if not influencer.audience_geography:
            return False
        spain_pct = influencer.audience_geography.get("ES", influencer.audience_geography.get("es", 0))
        if spain_pct == 0:
            return False

        # Must have engagement rate
        if influencer.engagement_rate is None:
            return False

        # Credibility score is required for Instagram
        if influencer.platform_type == "instagram" and influencer.credibility_score is None:
            return False

        return True

    async def _verify_candidate(self, influencer: Influencer) -> Optional[Influencer]:
        """
        Verify a candidate by fetching full metrics from Primetag API.

        Returns the influencer with full metrics, or None if verification fails.
        This ensures we have real data for:
        - % España (audience_geography)
        - % Hombres/Mujeres (audience_genders)
        - % Edades (audience_age_distribution)
        - % Credibilidad (credibility_score) - Instagram only
        - % ER (engagement_rate)
        """
        username = influencer.username

        # Check if already has full metrics and cache is fresh
        if self._has_full_metrics(influencer) and influencer.cache_expires_at > datetime.utcnow():
            logger.debug(f"Candidate {username} already has full metrics")
            return influencer

        try:
            # Search Primetag to get the encrypted username
            search_results = await self.primetag.search_media_kits(
                username,
                platform_type=PrimeTagClient.PLATFORM_INSTAGRAM,
                limit=5
            )

            # Find exact match
            exact_match = None
            for result in search_results:
                if result.username.lower() == username.lower():
                    exact_match = result
                    break

            if not exact_match:
                logger.warning(f"Verification failed: {username} not found in Primetag")
                return None

            # Extract encrypted username from mediakit_url
            username_encrypted = PrimeTagClient.extract_encrypted_username(exact_match.mediakit_url)
            if not username_encrypted:
                username_encrypted = exact_match.external_social_profile_id or username

            # Fetch FULL metrics from detail endpoint
            detail = await self.primetag.get_media_kit_detail(
                username_encrypted,
                PrimeTagClient.PLATFORM_INSTAGRAM
            )
            metrics = self.primetag.extract_metrics(detail)

            # Add follower count from search result if not in detail
            if not metrics.get('follower_count'):
                metrics['follower_count'] = exact_match.audience_size

            # Update cache with verified data
            verified = await self.cache_service.upsert_influencer(exact_match, metrics)
            logger.info(f"Verified {username}: Spain={metrics.get('audience_geography', {}).get('ES', 0)}%, "
                       f"Cred={metrics.get('credibility_score')}, ER={metrics.get('engagement_rate')}")
            return verified

        except Exception as e:
            logger.warning(f"Verification failed for {username}: {e}")
            return None

    async def _verify_candidates_batch(
        self,
        candidates: List[Influencer],
        max_concurrent: int = 5
    ) -> tuple[List[Influencer], int]:
        """
        Verify multiple candidates in parallel with bounded concurrency.

        Returns (verified_candidates, failed_count)
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def verify_one(candidate: Influencer) -> Optional[Influencer]:
            async with semaphore:
                return await self._verify_candidate(candidate)

        tasks = [verify_one(c) for c in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        verified = []
        failed = 0
        for result in results:
            if isinstance(result, Influencer):
                verified.append(result)
            else:
                failed += 1

        return verified, failed

    async def _get_brand_context(self, brand_name: Optional[str]) -> Optional[BrandContext]:
        """
        Look up brand context from the database.
        
        Args:
            brand_name: Brand name from parsed query
            
        Returns:
            BrandContext if found, None otherwise
        """
        if not brand_name:
            return None
        
        try:
            return await self.brand_context_service.find_brand_context(brand_name)
        except Exception as e:
            logger.warning(f"Failed to get brand context for '{brand_name}': {e}")
            return None

    def _enrich_with_brand_context(
        self,
        parsed_query: ParsedSearchQuery,
        brand_context: BrandContext
    ) -> ParsedSearchQuery:
        """
        Enrich parsed query with brand context from database.
        
        Adds:
        - Category-based keywords to search_keywords
        - Category info to brand_category if not set
        
        Args:
            parsed_query: The parsed search query
            brand_context: Brand context from database
            
        Returns:
            Enriched ParsedSearchQuery
        """
        # Create a copy of the keywords to avoid modifying the original
        enriched_keywords = list(parsed_query.search_keywords)
        
        # Add brand-specific keywords
        if brand_context.suggested_keywords:
            for kw in brand_context.suggested_keywords:
                if kw.lower() not in [k.lower() for k in enriched_keywords]:
                    enriched_keywords.append(kw)
        
        # Limit to 10 keywords
        enriched_keywords = enriched_keywords[:10]
        
        # Update brand category if not set
        brand_category = parsed_query.brand_category or brand_context.category
        
        # Create updated query with enriched data
        # Note: ParsedSearchQuery is a Pydantic model, so we create a new instance
        return ParsedSearchQuery(
            target_count=parsed_query.target_count,
            influencer_gender=parsed_query.influencer_gender,
            target_audience_gender=parsed_query.target_audience_gender,
            brand_name=parsed_query.brand_name,
            brand_handle=parsed_query.brand_handle,
            brand_category=brand_category,
            creative_concept=parsed_query.creative_concept,
            creative_tone=parsed_query.creative_tone,
            creative_themes=parsed_query.creative_themes,
            campaign_topics=parsed_query.campaign_topics,
            exclude_niches=parsed_query.exclude_niches,
            content_themes=parsed_query.content_themes,
            preferred_follower_min=parsed_query.preferred_follower_min,
            preferred_follower_max=parsed_query.preferred_follower_max,
            target_age_ranges=parsed_query.target_age_ranges,
            min_spain_audience_pct=parsed_query.min_spain_audience_pct,
            min_credibility_score=parsed_query.min_credibility_score,
            min_engagement_rate=parsed_query.min_engagement_rate,
            suggested_ranking_weights=parsed_query.suggested_ranking_weights,
            search_keywords=enriched_keywords,
            parsing_confidence=parsed_query.parsing_confidence,
            reasoning=parsed_query.reasoning + f" [Brand context: {brand_context.category}]" if brand_context.category else parsed_query.reasoning,
        )

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
                # All 8 score components
                credibility_score_normalized=result.scores.credibility,
                engagement_score_normalized=result.scores.engagement,
                audience_match_score=result.scores.audience_match,
                growth_score_normalized=result.scores.growth,
                geography_score=result.scores.geography,
                brand_affinity_score=result.scores.brand_affinity,
                creative_fit_score=result.scores.creative_fit,
                niche_match_score=result.scores.niche_match,
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
