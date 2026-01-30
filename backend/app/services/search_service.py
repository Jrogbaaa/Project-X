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
from app.services.brand_lookup_service import get_brand_lookup_service, BrandLookupResult
from app.schemas.search import SearchRequest, SearchResponse, FilterConfig, RankingWeights, VerificationStats
from app.schemas.llm import ParsedSearchQuery
from app.schemas.influencer import RankedInfluencer
from app.models.search import Search, SearchResult
from app.models.influencer import Influencer
from app.core.exceptions import SearchError

logger = logging.getLogger(__name__)

# Configuration constants for batch verification approach
CANDIDATE_POOL_SIZE = 200  # Fixed pool size for predictable performance
MAX_CANDIDATES_TO_VERIFY = 15  # Max candidates to verify via API (controls cost, caps at 15-30 calls)
MAX_CONCURRENT_VERIFICATION = 5  # Parallel API calls for verification

# Influencer tier follower ranges
TIER_MICRO = (1_000, 49_999)      # Micro: 1K - 50K followers
TIER_MID = (50_000, 499_999)      # Mid: 50K - 500K followers
TIER_MACRO = (500_000, 2_500_000) # Macro: 500K - 2.5M followers


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
            logger.info(f"")
            logger.info(f"╔══════════════════════════════════════════════════════════════════════════╗")
            logger.info(f"║  🔎 NEW SEARCH REQUEST                                                   ║")
            logger.info(f"╚══════════════════════════════════════════════════════════════════════════╝")
            logger.info(f"")
            logger.info(f"📝 Query: \"{request.query[:80]}{'...' if len(request.query) > 80 else ''}\"")
            logger.info(f"")
            logger.info(f"⏳ Step 1/6: Parsing query with AI...")
            parsed_query = await parse_search_query(request.query)
            logger.info(f"   ✓ Brand: {parsed_query.brand_name or 'Not specified'}")
            logger.info(f"   ✓ Topics: {parsed_query.campaign_topics or 'None'}")
            logger.info(f"   ✓ Keywords: {parsed_query.search_keywords[:5] if parsed_query.search_keywords else 'None'}")
            logger.info(f"   ✓ Target count: {parsed_query.target_count or 'Default'}")
            
            # Log tier distribution if specified
            tier_dist = parsed_query.get_tier_distribution()
            if tier_dist:
                logger.info(f"   ✓ Tier counts: micro={tier_dist['micro']}, mid={tier_dist['mid']}, macro={tier_dist['macro']}")
            else:
                logger.info(f"   ✓ Tier distribution: balanced (no specific counts)")

            # Step 1b: Enrich with brand context from database (or LLM lookup)
            brand_context = await self._get_brand_context(parsed_query.brand_name)
            if brand_context:
                parsed_query = self._enrich_with_brand_context(parsed_query, brand_context)
                logger.info(f"   ✓ Brand context found: {brand_context.name} ({brand_context.category})")
            
            # Log the campaign niche (critical for influencer discovery)
            if parsed_query.campaign_niche:
                logger.info(f"   ✓ Campaign niche: {parsed_query.campaign_niche}")
            else:
                logger.warning(f"   ⚠ No campaign niche - will use fallback matching")
            logger.info(f"")

            # Merge with request filters if provided
            filters_applied = self._merge_filters(parsed_query, request.filters)

            # Track candidates - use fixed pool size for predictable performance
            candidates: List[Influencer] = []
            seen_usernames: Set[str] = set()

            # Step 2: Discover candidates from local DB (get large pool)
            logger.info(f"⏳ Step 2/6: Discovering candidates from database...")
            
            # PRIORITY: Use taxonomy-aware niche matching if campaign_niche is set
            # This applies hard exclusion of conflicting niches (e.g., soccer players excluded from padel)
            if parsed_query.campaign_niche:
                logger.info(f"   → Searching by niche (taxonomy-aware): {parsed_query.campaign_niche}")
                if parsed_query.exclude_niches:
                    logger.info(f"   → Explicit exclusions: {parsed_query.exclude_niches}")
                
                primary_matches, fallback_matches = await self.cache_service.find_by_niche(
                    campaign_niche=parsed_query.campaign_niche,
                    exclude_niches=parsed_query.exclude_niches,
                    country="Spain",
                    limit=CANDIDATE_POOL_SIZE
                )
                
                # Add primary niche matches first (higher confidence)
                for inf in primary_matches:
                    if inf.username not in seen_usernames:
                        seen_usernames.add(inf.username)
                        candidates.append(inf)
                
                # Add fallback matches (interest-based, lower confidence)
                for inf in fallback_matches:
                    if inf.username not in seen_usernames:
                        seen_usernames.add(inf.username)
                        candidates.append(inf)
                
                logger.info(f"   ✓ Found {len(primary_matches)} by primary_niche, {len(fallback_matches)} by interests")
                
                # CREATIVE DISCOVERY: If niche matches are sparse, use discovery_interests
                if len(candidates) < 20 and parsed_query.discovery_interests:
                    logger.info(f"   → Expanding via creative matching: {parsed_query.discovery_interests}")
                    if parsed_query.influencer_reasoning:
                        logger.info(f"   💡 Reasoning: {parsed_query.influencer_reasoning[:100]}...")
                    
                    creative_matches = await self.cache_service.find_by_interests(
                        interests=parsed_query.discovery_interests,
                        exclude_interests=parsed_query.exclude_interests,
                        country="Spain",
                        limit=CANDIDATE_POOL_SIZE
                    )
                    creative_added = 0
                    for inf in creative_matches:
                        if inf.username not in seen_usernames:
                            seen_usernames.add(inf.username)
                            candidates.append(inf)
                            creative_added += 1
                    logger.info(f"   ✓ Added {creative_added} via creative discovery (interest-based)")
            
            # Fallback: Use interest-based matching if no campaign_niche
            elif parsed_query.campaign_topics:
                logger.info(f"   → Searching by interests: {parsed_query.campaign_topics}")
                interest_matches = await self.cache_service.find_by_interests(
                    interests=parsed_query.campaign_topics,
                    exclude_interests=parsed_query.exclude_niches,
                    country="Spain",
                    limit=CANDIDATE_POOL_SIZE
                )
                for inf in interest_matches:
                    if inf.username not in seen_usernames:
                        seen_usernames.add(inf.username)
                        candidates.append(inf)
                logger.info(f"   ✓ Found {len(interest_matches)} matches by interests")
            
            # CREATIVE DISCOVERY FALLBACK: Use discovery_interests if available
            elif parsed_query.discovery_interests:
                logger.info(f"   → Creative discovery via interests: {parsed_query.discovery_interests}")
                if parsed_query.influencer_reasoning:
                    logger.info(f"   💡 Reasoning: {parsed_query.influencer_reasoning[:100]}...")
                
                creative_matches = await self.cache_service.find_by_interests(
                    interests=parsed_query.discovery_interests,
                    exclude_interests=parsed_query.exclude_interests,
                    country="Spain",
                    limit=CANDIDATE_POOL_SIZE
                )
                for inf in creative_matches:
                    if inf.username not in seen_usernames:
                        seen_usernames.add(inf.username)
                        candidates.append(inf)
                logger.info(f"   ✓ Found {len(creative_matches)} via creative discovery")

            # Step 3: Search by keywords in bio
            if len(candidates) < CANDIDATE_POOL_SIZE and parsed_query.search_keywords:
                logger.info(f"   → Searching by keywords: {parsed_query.search_keywords[:5]}")
                keyword_matches = await self.cache_service.search_by_keywords(
                    keywords=parsed_query.search_keywords[:5],
                    limit=CANDIDATE_POOL_SIZE
                )
                for inf in keyword_matches:
                    if inf.username not in seen_usernames:
                        seen_usernames.add(inf.username)
                        candidates.append(inf)
                logger.info(f"   ✓ Found {len(keyword_matches)} matches by keywords")

            # Step 4: Fall back to generic cache search
            if len(candidates) < CANDIDATE_POOL_SIZE:
                logger.info("   → Expanding search to full database...")
                cached_influencers = await self.cache_service.find_matching(
                    min_credibility=0,  # Don't pre-filter, let verification handle it
                    min_spain_pct=0,
                    min_engagement=None,
                    limit=CANDIDATE_POOL_SIZE,
                    include_partial_data=True
                )
                for inf in cached_influencers:
                    if inf.username not in seen_usernames:
                        seen_usernames.add(inf.username)
                        candidates.append(inf)
                logger.info(f"   ✓ Added {len(cached_influencers)} from expanded search")

            total_candidates = len(candidates)
            logger.info(f"   📊 Total candidates discovered: {total_candidates}")
            logger.info(f"")

            # ============================================================
            # Step 5: SOFT PRE-FILTER - Score candidates using cached data
            # Ranks candidates by likelihood of being a good match
            # ============================================================
            logger.info(f"⏳ Step 3/6: Pre-filtering candidates by relevance...")
            # Use larger pool since we're not making API calls for now
            prefilter_limit = min(100, total_candidates)  # Up to 100 candidates for ranking
            prefiltered = self._soft_prefilter_candidates(
                candidates,
                filters_applied,
                parsed_query,
                limit=prefilter_limit
            )
            logger.info(f"   ✓ Selected top {len(prefiltered)} most relevant candidates")
            logger.info(f"")

            # ============================================================
            # Step 6: SKIP API VERIFICATION (temporarily disabled)
            # Using imported data directly - will re-enable PrimeTag API later
            # ============================================================
            # For now, use prefiltered candidates directly without API verification
            # This allows imported influencers to pass through based on cached data
            verified_candidates = prefiltered
            failed_count = 0

            # ============================================================
            # Step 7: Apply filters with lenient mode for imported data
            # Allows profiles without full metrics (credibility, etc.) to pass
            # Uses country fallback for Spain filter when audience_geography is missing
            # ============================================================
            logger.info(f"⏳ Step 4/6: Applying hard filters...")
            filtered = self.filter_service.apply_filters(
                verified_candidates,
                parsed_query,
                filters_applied,
                lenient_mode=True  # LENIENT: Allow imported profiles without full metrics
            )
            total_after_filter = len(filtered)
            logger.info(f"")

            # Calculate rejection stats
            rejected_count = len(verified_candidates) - total_after_filter

            # Step 8: Rank survivors using 8-factor scoring
            # Enrich campaign_topics with search_keywords if empty (for niche matching)
            logger.info(f"⏳ Step 5/6: Ranking {total_after_filter} candidates...")
            ranking_query = self._enrich_campaign_topics(parsed_query)
            ranked = self.ranking_service.rank_influencers(
                filtered,
                ranking_query,
                request.ranking_weights
            )
            logger.info(f"   ✓ Scored using 8-factor algorithm")
            logger.info(f"")

            # Step 9: Limit to requested count with tier and gender split logic
            # First apply tier distribution (explicit or balanced)
            tier_distributed = self._apply_tier_split_limit(
                ranked,
                parsed_query,
                request.limit
            )
            
            # Then apply gender split if specified
            final_results = self._apply_gender_split_limit(
                tier_distributed,
                parsed_query,
                request.limit
            )
            
            # Log top results
            logger.info(f"⏳ Step 6/6: Selecting final results...")
            logger.info(f"")
            logger.info(f"╔══════════════════════════════════════════════════════════════════════════╗")
            logger.info(f"║  🏆 TOP RESULTS                                                          ║")
            logger.info(f"╚══════════════════════════════════════════════════════════════════════════╝")
            for i, result in enumerate(final_results[:10], 1):
                followers = result.raw_data.follower_count if result.raw_data else 0
                followers_str = f"{followers/1_000_000:.1f}M" if followers >= 1_000_000 else f"{followers/1_000:.0f}K"
                score = result.relevance_score
                logger.info(f"   {i:2}. @{result.username:<20} | {followers_str:>6} followers | Score: {score:.2f}")
            if len(final_results) > 10:
                logger.info(f"   ... and {len(final_results) - 10} more")
            logger.info(f"")
            logger.info(f"═══════════════════════════════════════════════════════════════════════════")
            logger.info(f"✅ SEARCH COMPLETE: Returning {len(final_results)} influencers")
            logger.info(f"═══════════════════════════════════════════════════════════════════════════")
            logger.info(f"")

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

    def _soft_prefilter_candidates(
        self,
        candidates: List[Influencer],
        filters: FilterConfig,
        parsed_query: ParsedSearchQuery,
        limit: int = MAX_CANDIDATES_TO_VERIFY
    ) -> List[Influencer]:
        """
        Apply soft filters using cached data BEFORE expensive API verification.
        
        This reduces API calls by scoring candidates based on available cached metrics
        and selecting only the most promising ones for verification.
        
        Scoring logic:
        - Candidates with full cached metrics that meet filters score highest
        - Candidates with partial metrics score medium (need verification)
        - Candidates that clearly fail filters are deprioritized
        
        Args:
            candidates: All candidates from local DB
            filters: Filter config with thresholds
            parsed_query: Parsed query with preferences
            limit: Max candidates to return for verification
            
        Returns:
            Top N candidates sorted by likelihood of passing filters
        """
        scored: List[tuple[Influencer, float, bool]] = []
        
        for c in candidates:
            score = 0.0
            has_full_metrics = self._has_full_metrics(c)
            
            # Score based on credibility (if available)
            min_cred = filters.min_credibility_score or 70.0
            if c.credibility_score is not None:
                if c.credibility_score >= min_cred:
                    score += 3.0  # Meets threshold
                    # Bonus for exceeding threshold
                    score += min(1.0, (c.credibility_score - min_cred) / 20.0)
                else:
                    score -= 2.0  # Below threshold - likely to fail
            else:
                score += 0.5  # Unknown - might pass after verification
            
            # Score based on engagement rate (if available)
            min_er = filters.min_engagement_rate or 0.0
            if c.engagement_rate is not None:
                if c.engagement_rate >= min_er:
                    score += 2.0  # Meets threshold
                else:
                    score -= 1.0  # Below threshold
            else:
                score += 0.5  # Unknown
            
            # Score based on Spain audience % (if available)
            min_spain = filters.min_spain_audience_pct or 60.0
            spain_pct = 0.0
            if c.audience_geography:
                spain_pct = c.audience_geography.get("ES", c.audience_geography.get("es", 0))
            # Fallback to country field
            if spain_pct == 0 and c.country and c.country.lower() == "spain":
                spain_pct = 80.0  # Assume Spanish influencers have ~80% Spain audience
            
            if spain_pct >= min_spain:
                score += 3.0  # Meets threshold
            elif spain_pct > 0:
                score -= 1.0  # Below threshold
            else:
                score += 0.5  # Unknown
            
            # Bonus for candidates with full metrics (saves API calls)
            if has_full_metrics:
                score += 2.0
            
            # Bonus for interest/niche match
            if c.interests and parsed_query.campaign_topics:
                c_interests_lower = [i.lower() for i in c.interests]
                for topic in parsed_query.campaign_topics:
                    if topic.lower() in c_interests_lower:
                        score += 1.0
            
            # Penalty for excluded niches
            if c.interests and parsed_query.exclude_niches:
                c_interests_lower = [i.lower() for i in c.interests]
                for exclude in parsed_query.exclude_niches:
                    if exclude.lower() in c_interests_lower:
                        score -= 3.0
            
            # Slight preference for larger accounts (more reliable data)
            if c.follower_count:
                if c.follower_count >= 100000:
                    score += 0.5
                elif c.follower_count >= 50000:
                    score += 0.25
            
            scored.append((c, score, has_full_metrics))
        
        # Sort by score descending, then by has_full_metrics (True first to save API calls)
        scored.sort(key=lambda x: (-x[1], not x[2], -(x[0].follower_count or 0)))
        
        # Return top N candidates
        return [c for c, _, _ in scored[:limit]]

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
        
        Optimization: If we have cached primetag_encrypted_username, we can skip
        the search step and directly call the detail endpoint (1 API call instead of 2).
        """
        username = influencer.username

        # Check if already has full metrics and cache is fresh
        if self._has_full_metrics(influencer) and influencer.cache_expires_at > datetime.utcnow():
            logger.debug(f"Candidate {username} already has full metrics (cache hit)")
            return influencer

        try:
            username_encrypted = None
            search_summary = None  # Will be populated if we need to search
            
            # OPTIMIZATION: Use cached encrypted username if available (saves 1 API call)
            if influencer.primetag_encrypted_username:
                username_encrypted = influencer.primetag_encrypted_username
                logger.debug(f"Using cached encrypted username for {username}")
            else:
                # Need to search Primetag to get the encrypted username
                logger.debug(f"Searching Primetag for {username} (no cached encrypted username)")
                search_results = await self.primetag.search_media_kits(
                    username,
                    platform_type=PrimeTagClient.PLATFORM_INSTAGRAM,
                    limit=5
                )

                # Find exact match
                for result in search_results:
                    if result.username.lower() == username.lower():
                        search_summary = result
                        break

                if not search_summary:
                    logger.warning(f"Verification failed: {username} not found in Primetag")
                    return None

                # Extract encrypted username from mediakit_url
                username_encrypted = PrimeTagClient.extract_encrypted_username(search_summary.mediakit_url)
                if not username_encrypted:
                    username_encrypted = search_summary.external_social_profile_id or username

            # Fetch FULL metrics from detail endpoint
            detail = await self.primetag.get_media_kit_detail(
                username_encrypted,
                PrimeTagClient.PLATFORM_INSTAGRAM
            )
            metrics = self.primetag.extract_metrics(detail)

            # Add follower count from search result or existing data if not in detail
            if not metrics.get('follower_count'):
                if search_summary:
                    metrics['follower_count'] = search_summary.audience_size
                elif influencer.follower_count:
                    metrics['follower_count'] = influencer.follower_count

            # Update cache with verified data
            # Use search_summary if we have it, otherwise create a minimal summary object
            summary_for_cache = search_summary if search_summary else type('Summary', (), {
                'username': username,
                'external_social_profile_id': influencer.external_social_profile_id,
                'mediakit_url': f"https://mediakit.primetag.com/instagram/{username_encrypted}" if username_encrypted else None
            })()
            
            verified = await self.cache_service.upsert_influencer(summary_for_cache, metrics)
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

    def _apply_gender_split_limit(
        self,
        ranked: List[RankedInfluencer],
        parsed_query: ParsedSearchQuery,
        request_limit: int
    ) -> List[RankedInfluencer]:
        """
        Apply result limiting with gender-split logic.

        If parsed_query has target_male_count and/or target_female_count,
        return separate counts for each gender (with 3x headroom).
        Otherwise, return up to request_limit results (default 20).

        Falls back gracefully when gender cannot be determined for influencers
        (e.g., missing audience_genders data) by including unclassified influencers.

        Args:
            ranked: Ranked list of influencers
            parsed_query: Parsed query with potential gender counts
            request_limit: Maximum results from request

        Returns:
            Final list of influencers respecting gender split
        """
        male_count = parsed_query.target_male_count
        female_count = parsed_query.target_female_count

        # If gender-specific counts are set, split results
        if male_count is not None or female_count is not None:
            males = []
            females = []
            others = []

            for inf in ranked:
                # Determine gender from audience_genders or influencer data
                gender = self._infer_influencer_gender(inf)
                if gender == "male":
                    males.append(inf)
                elif gender == "female":
                    females.append(inf)
                else:
                    others.append(inf)

            # Apply 3x headroom to requested counts
            male_limit = (male_count or 0) * 3 if male_count else 0
            female_limit = (female_count or 0) * 3 if female_count else 0

            # Take up to the limit for each gender
            selected_males = males[:male_limit] if male_limit > 0 else []
            selected_females = females[:female_limit] if female_limit > 0 else []

            # Combine classified results
            combined = selected_males + selected_females

            logger.info(f"Gender split: {len(selected_males)} males, {len(selected_females)} females")

            # FALLBACK: If we couldn't classify enough by gender, include unclassified
            # This ensures we return results even when audience_genders data is missing
            total_target = (male_limit + female_limit) or request_limit
            if len(combined) < total_target and others:
                remaining_slots = total_target - len(combined)
                combined.extend(others[:remaining_slots])
                logger.info(f"   → Added {min(len(others), remaining_slots)} unclassified influencers (gender data unavailable)")

            # Sort by relevance score to maintain overall ranking
            combined.sort(key=lambda x: x.relevance_score, reverse=True)

            # Re-assign rank positions
            for i, inf in enumerate(combined):
                inf.rank_position = i + 1

            return combined

        # Default: return up to request_limit
        return ranked[:request_limit]

    def _infer_influencer_gender(self, influencer: RankedInfluencer) -> Optional[str]:
        """
        Infer influencer's gender from available data.

        Uses audience_genders as a heuristic - influencers typically have
        opposite-gender audience majority (e.g., female influencer -> male audience).
        Falls back to None if cannot determine.
        """
        if not influencer.raw_data:
            return None

        # Check if we have audience gender data
        audience_genders = influencer.raw_data.audience_genders
        if not audience_genders:
            return None

        male_pct = audience_genders.get("male", 0)
        female_pct = audience_genders.get("female", 0)

        # Heuristic: influencers often have opposite-gender audience majority
        # Female influencers typically have majority male audience
        # Male influencers typically have majority female audience
        if male_pct > 60:
            return "female"  # Likely female influencer with male audience
        elif female_pct > 60:
            return "male"  # Likely male influencer with female audience

        # If audience is balanced, cannot determine
        return None

    def _get_follower_count(self, influencer: RankedInfluencer) -> Optional[int]:
        """Extract follower count from influencer."""
        if influencer.raw_data:
            return influencer.raw_data.follower_count
        return None

    def _get_influencer_tier(self, influencer: RankedInfluencer) -> Optional[str]:
        """
        Determine influencer's tier based on follower count.
        
        Returns:
            'micro', 'mid', 'macro', or None if cannot determine
        """
        followers = self._get_follower_count(influencer)
        if followers is None:
            return None
        if TIER_MICRO[0] <= followers <= TIER_MICRO[1]:
            return "micro"
        elif TIER_MID[0] <= followers <= TIER_MID[1]:
            return "mid"
        elif TIER_MACRO[0] <= followers <= TIER_MACRO[1]:
            return "macro"
        return None

    def _apply_tier_split_limit(
        self,
        ranked: List[RankedInfluencer],
        parsed_query: ParsedSearchQuery,
        request_limit: int
    ) -> List[RankedInfluencer]:
        """
        Apply result limiting with tier-split logic.

        If tier counts specified: return requested distribution (with 3x headroom)
        If no tier specified: return balanced mix across all 3 tiers

        Falls back gracefully when tier cannot be determined for influencers
        (e.g., missing follower_count data) by including unclassified influencers.

        Args:
            ranked: Ranked list of influencers
            parsed_query: Parsed query with potential tier counts
            request_limit: Maximum results from request

        Returns:
            Final list of influencers respecting tier split
        """
        tier_dist = parsed_query.get_tier_distribution()

        # Bucket influencers by tier
        micros = []
        mids = []
        macros = []
        others = []

        for inf in ranked:
            tier = self._get_influencer_tier(inf)
            if tier == "micro":
                micros.append(inf)
            elif tier == "mid":
                mids.append(inf)
            elif tier == "macro":
                macros.append(inf)
            else:
                others.append(inf)

        if tier_dist:
            # Explicit tier counts requested - apply 3x headroom
            micro_limit = tier_dist["micro"] * 3
            mid_limit = tier_dist["mid"] * 3
            macro_limit = tier_dist["macro"] * 3

            selected_micros = micros[:micro_limit] if micro_limit > 0 else []
            selected_mids = mids[:mid_limit] if mid_limit > 0 else []
            selected_macros = macros[:macro_limit] if macro_limit > 0 else []

            combined = selected_micros + selected_mids + selected_macros

            logger.info(
                f"Tier split: {len(selected_micros)} micro, "
                f"{len(selected_mids)} mid, {len(selected_macros)} macro"
            )

            # Fallback: add unclassified if needed
            total_target = micro_limit + mid_limit + macro_limit
            if len(combined) < total_target and others:
                remaining_slots = total_target - len(combined)
                combined.extend(others[:remaining_slots])
                logger.info(
                    f"   → Added {min(len(others), remaining_slots)} unclassified "
                    f"influencers (tier data unavailable)"
                )
        else:
            # Default: balanced distribution (1/3 each tier)
            per_tier = max(request_limit // 3, 1)
            combined = micros[:per_tier] + mids[:per_tier] + macros[:per_tier]

            logger.info(
                f"Balanced tier distribution: {min(len(micros), per_tier)} micro, "
                f"{min(len(mids), per_tier)} mid, {min(len(macros), per_tier)} macro"
            )

            # If we don't have enough in balanced mode, fill with remaining from any tier
            if len(combined) < request_limit:
                # Get remaining influencers not yet selected
                remaining = [inf for inf in ranked if inf not in combined]
                slots_needed = request_limit - len(combined)
                combined.extend(remaining[:slots_needed])

        # Re-sort by relevance score to maintain overall ranking
        combined.sort(key=lambda x: x.relevance_score, reverse=True)

        # Re-assign rank positions
        for i, inf in enumerate(combined):
            inf.rank_position = i + 1

        return combined

    async def _get_brand_context(self, brand_name: Optional[str]) -> Optional[BrandContext]:
        """
        Look up brand context from the database, falling back to LLM lookup.
        
        Flow:
        1. Try database lookup first (fast, reliable for known brands)
        2. If not found, use LLM to understand the brand (handles unknown brands)
        
        Args:
            brand_name: Brand name from parsed query
            
        Returns:
            BrandContext if found, None otherwise
        """
        if not brand_name:
            return None
        
        try:
            # Try database lookup first
            context = await self.brand_context_service.find_brand_context(brand_name)
            if context:
                return context
            
            # Fall back to LLM lookup for unknown brands
            logger.info(f"Brand '{brand_name}' not in database, using LLM lookup...")
            brand_lookup = get_brand_lookup_service()
            lookup_result = await brand_lookup.lookup_brand(brand_name)
            
            if lookup_result and lookup_result.confidence >= 0.5:
                # Convert LLM result to BrandContext
                context = BrandContext(
                    name=lookup_result.brand_name,
                    category=lookup_result.category,
                    description=lookup_result.description,
                    suggested_keywords=lookup_result.suggested_keywords,
                    related_brands=lookup_result.competitors[:3],  # Use competitors as related brands
                )
                # Store the niche for later use (attach to context as extra attribute)
                context._llm_niche = lookup_result.niche
                context._llm_confidence = lookup_result.confidence
                
                logger.info(
                    f"   ✓ LLM brand lookup: {lookup_result.brand_name} -> "
                    f"category={lookup_result.category}, niche={lookup_result.niche}"
                )
                return context
            else:
                logger.info(f"   ⚠ LLM could not identify brand: {brand_name}")
                return None
                
        except Exception as e:
            logger.warning(f"Failed to get brand context for '{brand_name}': {e}")
            return None

    def _enrich_with_brand_context(
        self,
        parsed_query: ParsedSearchQuery,
        brand_context: BrandContext
    ) -> ParsedSearchQuery:
        """
        Enrich parsed query with brand context from database or LLM lookup.
        
        Adds:
        - Category-based keywords to search_keywords
        - Category info to brand_category if not set
        - campaign_niche from brand context (critical for influencer discovery)
        
        Args:
            parsed_query: The parsed search query
            brand_context: Brand context from database or LLM lookup
            
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
        
        # IMPORTANT: Set campaign_niche from brand context if not already set
        # This is critical for niche-based influencer discovery (find_by_niche)
        campaign_niche = parsed_query.campaign_niche
        if not campaign_niche:
            # Check if LLM lookup provided a niche
            if hasattr(brand_context, '_llm_niche') and brand_context._llm_niche:
                campaign_niche = brand_context._llm_niche
                logger.info(f"   ✓ Setting campaign_niche from LLM lookup: {campaign_niche}")
            # Fall back to mapping category to niche
            elif brand_context.category:
                brand_lookup = get_brand_lookup_service()
                campaign_niche = brand_lookup.get_niche_for_category(brand_context.category)
                logger.info(f"   ✓ Setting campaign_niche from category mapping: {brand_context.category} -> {campaign_niche}")
        
        # Create updated query with enriched data
        # Note: ParsedSearchQuery is a Pydantic model, so we create a new instance
        return ParsedSearchQuery(
            target_count=parsed_query.target_count,
            influencer_gender=parsed_query.influencer_gender,
            target_audience_gender=parsed_query.target_audience_gender,
            target_male_count=parsed_query.target_male_count,
            target_female_count=parsed_query.target_female_count,
            target_micro_count=parsed_query.target_micro_count,
            target_mid_count=parsed_query.target_mid_count,
            target_macro_count=parsed_query.target_macro_count,
            brand_name=parsed_query.brand_name,
            brand_handle=parsed_query.brand_handle,
            brand_category=brand_category,
            creative_concept=parsed_query.creative_concept,
            creative_format=parsed_query.creative_format,
            creative_tone=parsed_query.creative_tone,
            creative_themes=parsed_query.creative_themes,
            campaign_niche=campaign_niche,  # Now enriched from brand context
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

    def _enrich_campaign_topics(self, parsed_query: ParsedSearchQuery) -> ParsedSearchQuery:
        """
        Enrich campaign_topics with search_keywords if empty.
        
        This ensures niche matching works even when the LLM extracts
        keywords but not explicit campaign_topics. For example, for
        "IKEA home furniture campaign", search_keywords might include
        ["home", "furniture", "decoracion"] which should boost influencers
        with matching interests.
        """
        # If campaign_topics already has values, use as-is
        if parsed_query.campaign_topics:
            return parsed_query
        
        # If no search_keywords either, return as-is
        if not parsed_query.search_keywords:
            return parsed_query
        
        # Filter search_keywords to likely niche-relevant terms
        # Exclude brand names and very generic terms
        brand_terms = {
            parsed_query.brand_name.lower() if parsed_query.brand_name else "",
            parsed_query.brand_handle.lower().lstrip("@") if parsed_query.brand_handle else "",
        }
        generic_terms = {"influencer", "campaign", "spain", "spanish", "espana"}
        
        niche_keywords = [
            kw for kw in parsed_query.search_keywords
            if kw.lower() not in brand_terms 
            and kw.lower() not in generic_terms
            and len(kw) > 2
        ]
        
        if not niche_keywords:
            return parsed_query
        
        # Create enriched query with campaign_topics from keywords
        logger.info(f"Enriching campaign_topics with search_keywords: {niche_keywords[:5]}")
        
        return ParsedSearchQuery(
            target_count=parsed_query.target_count,
            influencer_gender=parsed_query.influencer_gender,
            target_audience_gender=parsed_query.target_audience_gender,
            target_male_count=parsed_query.target_male_count,
            target_female_count=parsed_query.target_female_count,
            target_micro_count=parsed_query.target_micro_count,
            target_mid_count=parsed_query.target_mid_count,
            target_macro_count=parsed_query.target_macro_count,
            brand_name=parsed_query.brand_name,
            brand_handle=parsed_query.brand_handle,
            brand_category=parsed_query.brand_category,
            creative_concept=parsed_query.creative_concept,
            creative_format=parsed_query.creative_format,
            creative_tone=parsed_query.creative_tone,
            creative_themes=parsed_query.creative_themes,
            campaign_niche=parsed_query.campaign_niche,
            campaign_topics=niche_keywords[:5],  # Use top 5 keywords as topics
            exclude_niches=parsed_query.exclude_niches,
            content_themes=parsed_query.content_themes,
            preferred_follower_min=parsed_query.preferred_follower_min,
            preferred_follower_max=parsed_query.preferred_follower_max,
            target_age_ranges=parsed_query.target_age_ranges,
            min_spain_audience_pct=parsed_query.min_spain_audience_pct,
            min_credibility_score=parsed_query.min_credibility_score,
            min_engagement_rate=parsed_query.min_engagement_rate,
            suggested_ranking_weights=parsed_query.suggested_ranking_weights,
            search_keywords=parsed_query.search_keywords,
            parsing_confidence=parsed_query.parsing_confidence,
            reasoning=parsed_query.reasoning,
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
