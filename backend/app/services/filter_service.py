from typing import List, Any
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
        custom_config: FilterConfig = None
    ) -> List[Any]:
        """Apply all configured filters to candidate list."""
        config = custom_config or self.config
        filtered = list(influencers)

        # Filter by credibility
        min_credibility = parsed_query.min_credibility_score or config.min_credibility_score
        filtered = [
            inf for inf in filtered
            if self._get_credibility(inf) >= min_credibility
        ]

        # Filter by Spain audience percentage
        min_spain_pct = parsed_query.min_spain_audience_pct or config.min_spain_audience_pct
        filtered = [
            inf for inf in filtered
            if self._get_spain_pct(inf) >= min_spain_pct
        ]

        # Filter by engagement rate if specified
        min_engagement = parsed_query.min_engagement_rate or config.min_engagement_rate
        if min_engagement:
            # Convert percentage to decimal if needed
            min_er = min_engagement / 100.0 if min_engagement > 1 else min_engagement
            filtered = [
                inf for inf in filtered
                if self._get_engagement_rate(inf) >= min_er
            ]

        # Filter by follower growth rate if specified
        if config.min_follower_growth_rate is not None:
            filtered = [
                inf for inf in filtered
                if self._get_growth_rate(inf) >= config.min_follower_growth_rate
            ]

        # Filter by audience gender if specified
        if parsed_query.target_audience_gender and parsed_query.target_audience_gender != GenderFilter.ANY:
            filtered = [
                inf for inf in filtered
                if self._matches_audience_gender(inf, parsed_query.target_audience_gender)
            ]

        return filtered

    def _get_credibility(self, influencer) -> float:
        """Extract credibility score from influencer object."""
        if hasattr(influencer, 'credibility_score'):
            return influencer.credibility_score or 0
        if isinstance(influencer, dict):
            return influencer.get('credibility_score', 0) or 0
        return 0

    def _get_spain_pct(self, influencer) -> float:
        """Extract Spain percentage from geography data."""
        geography = self._get_geography(influencer)
        return geography.get("ES", geography.get("es", 0)) or 0

    def _get_geography(self, influencer) -> dict:
        """Extract geography data from influencer object."""
        if hasattr(influencer, 'audience_geography'):
            return influencer.audience_geography or {}
        if isinstance(influencer, dict):
            return influencer.get('audience_geography', {}) or {}
        return {}

    def _get_engagement_rate(self, influencer) -> float:
        """Extract engagement rate from influencer object."""
        if hasattr(influencer, 'engagement_rate'):
            return influencer.engagement_rate or 0
        if isinstance(influencer, dict):
            return influencer.get('engagement_rate', 0) or 0
        return 0

    def _get_growth_rate(self, influencer) -> float:
        """Extract follower growth rate from influencer object."""
        if hasattr(influencer, 'follower_growth_rate_6m'):
            return influencer.follower_growth_rate_6m or 0
        if isinstance(influencer, dict):
            return influencer.get('follower_growth_rate_6m', 0) or 0
        return 0

    def _get_genders(self, influencer) -> dict:
        """Extract audience gender data from influencer object."""
        if hasattr(influencer, 'audience_genders'):
            return influencer.audience_genders or {}
        if isinstance(influencer, dict):
            return influencer.get('audience_genders', {}) or {}
        return {}

    def _matches_audience_gender(self, influencer, target_gender: GenderFilter) -> bool:
        """Check if influencer's audience matches target gender preference."""
        genders = self._get_genders(influencer)
        if not genders:
            return True  # Allow if no data

        if target_gender == GenderFilter.FEMALE:
            female_pct = genders.get("female", genders.get("Female", 50))
            return female_pct >= 50  # Majority female audience

        if target_gender == GenderFilter.MALE:
            male_pct = genders.get("male", genders.get("Male", 50))
            return male_pct >= 50  # Majority male audience

        return True
