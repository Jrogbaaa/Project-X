import logging
from typing import List, Any, Optional
from app.schemas.llm import ParsedSearchQuery, GenderFilter
from app.schemas.search import FilterConfig
from app.services.brand_intelligence_service import get_brand_intelligence_service

logger = logging.getLogger(__name__)


class FilterService:
    """Service for filtering influencer candidates."""

    def __init__(self, filter_config: FilterConfig = None):
        self.config = filter_config or FilterConfig()

    def apply_filters(
        self,
        influencers: List[Any],
        parsed_query: ParsedSearchQuery,
        custom_config: FilterConfig = None,
        lenient_mode: bool = False
    ) -> List[Any]:
        """
        Apply all configured filters to candidate list.
        
        Args:
            influencers: List of influencer candidates
            parsed_query: Parsed search query from LLM
            custom_config: Optional filter config overrides
            lenient_mode: If True, allow profiles with missing metrics to pass filters.
                         This is useful for imported data without full PrimeTag metrics.
        """
        config = custom_config or self.config
        filtered = list(influencers)
        initial_count = len(filtered)
        
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"🔍 FILTERING {initial_count} candidates")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # Filter by max follower count (exclude mega-celebrities) - HARD FILTER
        max_followers = config.max_follower_count
        before_count = len(filtered)
        filtered = [
            inf for inf in filtered
            if self._passes_max_followers(inf, max_followers)
        ]
        removed = before_count - len(filtered)
        if removed > 0:
            logger.info(f"   ❌ Max followers (<{max_followers:,}): removed {removed} mega-celebrities")
        else:
            logger.info(f"   ✓ Max followers (<{max_followers:,}): all passed")

        # Filter by credibility (allow None in lenient mode)
        min_credibility = parsed_query.min_credibility_score or config.min_credibility_score
        before_count = len(filtered)
        filtered = [
            inf for inf in filtered
            if self._passes_credibility(inf, min_credibility, lenient_mode)
        ]
        removed = before_count - len(filtered)
        if removed > 0:
            logger.info(f"   ❌ Credibility (>={min_credibility}%): removed {removed}")
        else:
            logger.info(f"   ✓ Credibility (>={min_credibility}%): all passed")

        # Filter by Spain audience percentage (allow None in lenient mode)
        min_spain_pct = parsed_query.min_spain_audience_pct or config.min_spain_audience_pct
        before_count = len(filtered)
        filtered = [
            inf for inf in filtered
            if self._passes_spain_pct(inf, min_spain_pct, lenient_mode)
        ]
        removed = before_count - len(filtered)
        if removed > 0:
            logger.info(f"   ❌ Spain audience (>={min_spain_pct}%): removed {removed}")
        else:
            logger.info(f"   ✓ Spain audience (>={min_spain_pct}%): all passed")

        # Filter by engagement rate if specified (allow None in lenient mode)
        min_engagement = parsed_query.min_engagement_rate or config.min_engagement_rate
        if min_engagement:
            # Convert percentage to decimal if needed
            min_er = min_engagement / 100.0 if min_engagement > 1 else min_engagement
            before_count = len(filtered)
            filtered = [
                inf for inf in filtered
                if self._passes_engagement(inf, min_er, lenient_mode)
            ]
            removed = before_count - len(filtered)
            if removed > 0:
                logger.info(f"   ❌ Engagement rate (>={min_er:.2%}): removed {removed}")
            else:
                logger.info(f"   ✓ Engagement rate (>={min_er:.2%}): all passed")

        # Filter by follower growth rate if specified (allow None in lenient mode)
        if config.min_follower_growth_rate is not None:
            before_count = len(filtered)
            filtered = [
                inf for inf in filtered
                if self._passes_growth_rate(inf, config.min_follower_growth_rate, lenient_mode)
            ]
            removed = before_count - len(filtered)
            if removed > 0:
                logger.info(f"   ❌ Growth rate (>={config.min_follower_growth_rate}%): removed {removed}")
            else:
                logger.info(f"   ✓ Growth rate (>={config.min_follower_growth_rate}%): all passed")

        # Filter by audience gender if specified
        if parsed_query.target_audience_gender and parsed_query.target_audience_gender != GenderFilter.ANY:
            before_count = len(filtered)
            filtered = [
                inf for inf in filtered
                if self._matches_audience_gender(inf, parsed_query.target_audience_gender)
            ]
            removed = before_count - len(filtered)
            if removed > 0:
                logger.info(f"   ❌ Audience gender ({parsed_query.target_audience_gender}): removed {removed}")
            else:
                logger.info(f"   ✓ Audience gender ({parsed_query.target_audience_gender}): all passed")

        # Filter out competitor ambassadors if brand context provided
        # This is a hard exclusion - known ambassadors of competitor brands are removed
        if parsed_query.brand_handle or parsed_query.brand_name:
            target_brand = parsed_query.brand_handle or parsed_query.brand_name
            exclude_ambassadors = getattr(config, 'exclude_competitor_ambassadors', True)

            if exclude_ambassadors:
                before_count = len(filtered)
                filtered = [
                    inf for inf in filtered
                    if not self._is_competitor_ambassador(inf, target_brand)
                ]
                removed = before_count - len(filtered)
                if removed > 0:
                    logger.info(f"   ❌ Competitor ambassadors: removed {removed}")

        total_removed = initial_count - len(filtered)
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"📊 FILTER RESULT: {len(filtered)}/{initial_count} passed ({total_removed} removed)")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        return filtered
    
    def _passes_max_followers(self, influencer, max_val: int) -> bool:
        """Check if influencer is under max follower count."""
        count = self._get_follower_count(influencer)
        if count is None:
            return True  # Allow if unknown
        return count <= max_val
    
    def _get_follower_count(self, influencer) -> Optional[int]:
        """Extract follower count from influencer object."""
        if hasattr(influencer, 'follower_count'):
            return influencer.follower_count
        if isinstance(influencer, dict):
            return influencer.get('follower_count')
        return None

    def _passes_credibility(self, influencer, min_val: float, lenient: bool) -> bool:
        """Check if influencer passes credibility filter."""
        score = self._get_credibility(influencer)
        if score is None:
            return lenient  # Allow None values in lenient mode
        return score >= min_val

    def _passes_spain_pct(self, influencer, min_val: float, lenient: bool) -> bool:
        """Check if influencer passes Spain audience filter."""
        pct = self._get_spain_pct(influencer)
        if pct is None or pct == 0:
            # Check country field for imported profiles
            country = self._get_country(influencer)
            if country and country.lower() == "spain":
                return True  # Spanish influencer, assume they have Spanish audience
            return lenient  # Allow if lenient mode
        return pct >= min_val

    def _passes_engagement(self, influencer, min_val: float, lenient: bool) -> bool:
        """Check if influencer passes engagement filter."""
        rate = self._get_engagement_rate(influencer)
        if rate is None:
            return lenient
        return rate >= min_val

    def _passes_growth_rate(self, influencer, min_val: float, lenient: bool) -> bool:
        """Check if influencer passes growth rate filter."""
        rate = self._get_growth_rate(influencer)
        if rate is None:
            return lenient
        return rate >= min_val

    def _get_credibility(self, influencer) -> Optional[float]:
        """Extract credibility score from influencer object."""
        if hasattr(influencer, 'credibility_score'):
            return influencer.credibility_score
        if isinstance(influencer, dict):
            return influencer.get('credibility_score')
        return None

    def _get_spain_pct(self, influencer) -> Optional[float]:
        """Extract Spain percentage from geography data."""
        geography = self._get_geography(influencer)
        if not geography:
            return None
        return geography.get("ES", geography.get("es", 0)) or 0

    def _get_country(self, influencer) -> Optional[str]:
        """Extract country from influencer object."""
        if hasattr(influencer, 'country'):
            return influencer.country
        if isinstance(influencer, dict):
            return influencer.get('country')
        return None

    def _get_geography(self, influencer) -> Optional[dict]:
        """Extract geography data from influencer object."""
        if hasattr(influencer, 'audience_geography'):
            return influencer.audience_geography
        if isinstance(influencer, dict):
            return influencer.get('audience_geography')
        return None

    def _get_engagement_rate(self, influencer) -> Optional[float]:
        """Extract engagement rate from influencer object."""
        if hasattr(influencer, 'engagement_rate'):
            return influencer.engagement_rate
        if isinstance(influencer, dict):
            return influencer.get('engagement_rate')
        return None

    def _get_growth_rate(self, influencer) -> Optional[float]:
        """Extract follower growth rate from influencer object."""
        if hasattr(influencer, 'follower_growth_rate_6m'):
            return influencer.follower_growth_rate_6m
        if isinstance(influencer, dict):
            return influencer.get('follower_growth_rate_6m')
        return None

    def _get_genders(self, influencer) -> Optional[dict]:
        """Extract audience gender data from influencer object."""
        if hasattr(influencer, 'audience_genders'):
            return influencer.audience_genders
        if isinstance(influencer, dict):
            return influencer.get('audience_genders')
        return None

    def _matches_audience_gender(self, influencer, target_gender: GenderFilter) -> bool:
        """Check if influencer's audience matches target gender preference."""
        genders = self._get_genders(influencer)
        if not genders:
            return True  # Allow if no data (lenient for imported profiles)

        if target_gender == GenderFilter.FEMALE:
            female_pct = genders.get("female", genders.get("Female", 50))
            return female_pct >= 50  # Majority female audience

        if target_gender == GenderFilter.MALE:
            male_pct = genders.get("male", genders.get("Male", 50))
            return male_pct >= 50  # Majority male audience

        return True

    def _is_competitor_ambassador(self, influencer, target_brand: str) -> bool:
        """
        Check if influencer is a known ambassador for a competitor brand.

        This is used for HARD EXCLUSION - known competitor ambassadors
        (like Messi for Nike campaigns) are completely removed from results.

        Args:
            influencer: Influencer data
            target_brand: Target brand key or handle

        Returns:
            True if influencer should be EXCLUDED (is competitor ambassador)
        """
        username = self._get_username(influencer)
        if not username:
            return False  # Can't check, allow through

        brand_intel = get_brand_intelligence_service()

        # Check if influencer is a known ambassador for any brand
        ambassador_brands = brand_intel.get_ambassador_brands(username)
        if not ambassador_brands:
            return False  # Not a known ambassador, allow through

        # Get competitor brands for the target
        competitors = brand_intel.get_competitors(target_brand)
        if not competitors:
            return False  # Unknown target brand, allow through

        # Check if any of influencer's ambassador relationships are competitors
        ambassador_brand_keys = {b['brand_key'] for b in ambassador_brands}
        is_competitor = bool(ambassador_brand_keys & competitors)

        return is_competitor

    def _get_username(self, influencer) -> Optional[str]:
        """Extract username from influencer object."""
        if hasattr(influencer, 'username'):
            return influencer.username
        if isinstance(influencer, dict):
            return influencer.get('username')
        return None

    def _get_brand_mentions(self, influencer) -> List[str]:
        """Extract brand mentions from influencer object."""
        if hasattr(influencer, 'brand_mentions'):
            return influencer.brand_mentions or []
        if isinstance(influencer, dict):
            return influencer.get('brand_mentions', []) or []
        return []
