from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from app.schemas.llm import ParsedSearchQuery, GenderFilter, AudienceAgeRange
from app.schemas.influencer import ScoreComponents, RankedInfluencer, InfluencerData
from app.schemas.search import RankingWeights


@dataclass
class RankingResult:
    """Internal ranking result before conversion to response schema."""
    influencer_id: str
    username: str
    relevance_score: float
    scores: ScoreComponents
    raw_data: dict


class RankingService:
    """Service for ranking influencer candidates."""

    DEFAULT_WEIGHTS = RankingWeights(
        credibility=0.25,
        engagement=0.30,
        audience_match=0.25,
        growth=0.10,
        geography=0.10
    )

    def __init__(self, weights: RankingWeights = None):
        self.weights = weights or self.DEFAULT_WEIGHTS

    def rank_influencers(
        self,
        influencers: List[Any],
        parsed_query: ParsedSearchQuery,
        custom_weights: RankingWeights = None
    ) -> List[RankedInfluencer]:
        """
        Rank influencers using weighted multi-factor scoring.
        Returns ranked list with score components for transparency.
        """
        # Use LLM-suggested weights, custom weights, or defaults
        weights = self._resolve_weights(parsed_query, custom_weights)

        ranked = []
        for inf in influencers:
            scores = self._calculate_scores(inf, parsed_query)

            relevance_score = (
                weights.credibility * scores.credibility +
                weights.engagement * scores.engagement +
                weights.audience_match * scores.audience_match +
                weights.growth * scores.growth +
                weights.geography * scores.geography
            )

            # Get raw data dict
            if hasattr(inf, 'to_dict'):
                raw_data = inf.to_dict()
            elif isinstance(inf, dict):
                raw_data = inf
            else:
                raw_data = self._extract_raw_data(inf)

            # Convert to InfluencerData
            influencer_data = InfluencerData(
                id=raw_data.get('id', ''),
                username=raw_data.get('username', ''),
                display_name=raw_data.get('display_name'),
                profile_picture_url=raw_data.get('profile_picture_url'),
                bio=raw_data.get('bio'),
                is_verified=raw_data.get('is_verified', False),
                follower_count=raw_data.get('follower_count', 0),
                credibility_score=raw_data.get('credibility_score'),
                engagement_rate=raw_data.get('engagement_rate'),
                follower_growth_rate_6m=raw_data.get('follower_growth_rate_6m'),
                avg_likes=raw_data.get('avg_likes', 0),
                avg_comments=raw_data.get('avg_comments', 0),
                audience_genders=raw_data.get('audience_genders', {}),
                audience_age_distribution=raw_data.get('audience_age_distribution', {}),
                audience_geography=raw_data.get('audience_geography', {}),
            )

            ranked.append(RankedInfluencer(
                influencer_id=str(raw_data.get('id', '')),
                username=raw_data.get('username', ''),
                rank_position=0,  # Will be set after sorting
                relevance_score=round(relevance_score, 4),
                scores=scores,
                raw_data=influencer_data
            ))

        # Sort by relevance score descending
        ranked.sort(key=lambda x: x.relevance_score, reverse=True)

        # Set rank positions
        for i, item in enumerate(ranked, 1):
            item.rank_position = i

        return ranked

    def _resolve_weights(
        self,
        parsed_query: ParsedSearchQuery,
        custom_weights: RankingWeights = None
    ) -> RankingWeights:
        """Resolve which weights to use based on available inputs."""
        if custom_weights:
            return custom_weights

        if parsed_query.suggested_ranking_weights:
            suggested = parsed_query.suggested_ranking_weights
            return RankingWeights(
                credibility=suggested.get('credibility', self.DEFAULT_WEIGHTS.credibility),
                engagement=suggested.get('engagement', self.DEFAULT_WEIGHTS.engagement),
                audience_match=suggested.get('audience_match', self.DEFAULT_WEIGHTS.audience_match),
                growth=suggested.get('growth', self.DEFAULT_WEIGHTS.growth),
                geography=suggested.get('geography', self.DEFAULT_WEIGHTS.geography),
            )

        return self.weights

    def _calculate_scores(
        self,
        influencer: Any,
        parsed_query: ParsedSearchQuery
    ) -> ScoreComponents:
        """Calculate normalized scores for each factor (0-1 scale)."""

        # Credibility: normalize from 0-100 to 0-1
        credibility_raw = self._get_value(influencer, 'credibility_score', 0)
        credibility = credibility_raw / 100.0 if credibility_raw else 0

        # Engagement: normalize (typical range 0-10%, cap at 15%)
        engagement_raw = self._get_value(influencer, 'engagement_rate', 0)
        # If stored as decimal (0.035), convert to percentage equivalent
        if engagement_raw and engagement_raw < 1:
            engagement_raw = engagement_raw * 100
        engagement = min(engagement_raw / 15.0, 1.0) if engagement_raw else 0

        # Audience match: based on gender and age targeting
        audience_match = self._calculate_audience_match(influencer, parsed_query)

        # Growth: normalize (typical range -20% to +50%, stored as decimal)
        growth_raw = self._get_value(influencer, 'follower_growth_rate_6m', 0)
        # If stored as decimal, convert
        if growth_raw and -1 < growth_raw < 1:
            growth_raw = growth_raw * 100
        growth = max(0, min((growth_raw + 20) / 70.0, 1.0)) if growth_raw is not None else 0.5

        # Geography: Spain percentage / 100
        geography_data = self._get_value(influencer, 'audience_geography', {})
        spain_pct = geography_data.get("ES", geography_data.get("es", 0)) or 0
        geography = spain_pct / 100.0

        return ScoreComponents(
            credibility=round(credibility, 4),
            engagement=round(engagement, 4),
            audience_match=round(audience_match, 4),
            growth=round(growth, 4),
            geography=round(geography, 4)
        )

    def _calculate_audience_match(
        self,
        influencer: Any,
        parsed_query: ParsedSearchQuery
    ) -> float:
        """Calculate audience demographic match score."""
        score = 0.5  # Neutral starting point

        genders = self._get_value(influencer, 'audience_genders', {})
        age_distribution = self._get_value(influencer, 'audience_age_distribution', {})

        # Gender match
        if parsed_query.target_audience_gender and parsed_query.target_audience_gender != GenderFilter.ANY:
            target_gender = parsed_query.target_audience_gender.value
            if target_gender == "female":
                female_pct = genders.get("female", genders.get("Female", 50))
                score = female_pct / 100.0 if female_pct else 0.5
            elif target_gender == "male":
                male_pct = genders.get("male", genders.get("Male", 50))
                score = male_pct / 100.0 if male_pct else 0.5

        # Age range match (boost if overlaps with target)
        if parsed_query.target_age_ranges and age_distribution:
            target_ranges = [r.value if isinstance(r, AudienceAgeRange) else r for r in parsed_query.target_age_ranges]
            overlap_pct = sum(
                age_distribution.get(r, 0)
                for r in target_ranges
            )
            # Blend with gender score
            if overlap_pct > 0:
                score = (score + overlap_pct / 100.0) / 2

        return min(max(score, 0), 1.0)

    def _get_value(self, obj: Any, key: str, default: Any = None) -> Any:
        """Extract value from object or dict."""
        if hasattr(obj, key):
            return getattr(obj, key, default) or default
        if isinstance(obj, dict):
            return obj.get(key, default) or default
        return default

    def _extract_raw_data(self, obj: Any) -> dict:
        """Extract raw data dictionary from an object."""
        data = {}
        for attr in ['id', 'username', 'display_name', 'profile_picture_url', 'bio',
                     'is_verified', 'follower_count', 'credibility_score', 'engagement_rate',
                     'follower_growth_rate_6m', 'avg_likes', 'avg_comments',
                     'audience_genders', 'audience_age_distribution', 'audience_geography']:
            if hasattr(obj, attr):
                data[attr] = getattr(obj, attr)
        return data
