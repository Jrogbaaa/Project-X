from typing import List, Any, Optional
from app.schemas.llm import ParsedSearchQuery, GenderFilter
from app.schemas.search import FilterConfig


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

        # Filter by credibility (allow None in lenient mode)
        min_credibility = parsed_query.min_credibility_score or config.min_credibility_score
        filtered = [
            inf for inf in filtered
            if self._passes_credibility(inf, min_credibility, lenient_mode)
        ]

        # Filter by Spain audience percentage (allow None in lenient mode)
        min_spain_pct = parsed_query.min_spain_audience_pct or config.min_spain_audience_pct
        filtered = [
            inf for inf in filtered
            if self._passes_spain_pct(inf, min_spain_pct, lenient_mode)
        ]

        # Filter by engagement rate if specified (allow None in lenient mode)
        min_engagement = parsed_query.min_engagement_rate or config.min_engagement_rate
        if min_engagement:
            # Convert percentage to decimal if needed
            min_er = min_engagement / 100.0 if min_engagement > 1 else min_engagement
            filtered = [
                inf for inf in filtered
                if self._passes_engagement(inf, min_er, lenient_mode)
            ]

        # Filter by follower growth rate if specified (allow None in lenient mode)
        if config.min_follower_growth_rate is not None:
            filtered = [
                inf for inf in filtered
                if self._passes_growth_rate(inf, config.min_follower_growth_rate, lenient_mode)
            ]

        # Filter by audience gender if specified
        if parsed_query.target_audience_gender and parsed_query.target_audience_gender != GenderFilter.ANY:
            filtered = [
                inf for inf in filtered
                if self._matches_audience_gender(inf, parsed_query.target_audience_gender)
            ]

        return filtered

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
