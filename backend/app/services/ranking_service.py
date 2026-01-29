from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

from app.schemas.llm import ParsedSearchQuery, GenderFilter, AudienceAgeRange
from app.schemas.influencer import ScoreComponents, RankedInfluencer, InfluencerData
from app.schemas.search import RankingWeights
from app.services.brand_intelligence_service import get_brand_intelligence_service


@dataclass
class RankingResult:
    """Internal ranking result before conversion to response schema."""
    influencer_id: str
    username: str
    relevance_score: float
    scores: ScoreComponents
    raw_data: dict
    # Warning fields for brand conflicts/saturation
    brand_warning_type: Optional[str] = None  # "competitor_conflict", "saturation"
    brand_warning_message: Optional[str] = None
    niche_warning: Optional[str] = None  # For celebrity/niche mismatch


# Tone keywords for creative fit matching
TONE_KEYWORDS = {
    'authentic': ['real', 'genuine', 'honest', 'raw', 'unfiltered', 'natural'],
    'luxury': ['premium', 'exclusive', 'elegant', 'sophisticated', 'high-end', 'lujo'],
    'humorous': ['funny', 'comedy', 'laugh', 'humor', 'fun', 'divertido'],
    'casual': ['everyday', 'relax', 'chill', 'lifestyle', 'daily', 'cotidiano'],
    'documentary': ['story', 'journey', 'behind', 'real', 'making of', 'documental'],
    'inspirational': ['inspire', 'motivate', 'dream', 'achieve', 'success', 'inspirar'],
    'edgy': ['bold', 'daring', 'provocative', 'rebel', 'alternative', 'atrevido'],
    'gritty': ['raw', 'intense', 'real', 'street', 'urban', 'hardcore'],
    'polished': ['professional', 'clean', 'refined', 'quality', 'premium'],
}


class RankingService:
    """Service for ranking influencer candidates with brand affinity and creative fit."""

    # Updated default weights including new factors
    DEFAULT_WEIGHTS = RankingWeights(
        credibility=0.15,
        engagement=0.20,
        audience_match=0.15,
        growth=0.05,
        geography=0.10,
        brand_affinity=0.15,
        creative_fit=0.15,
        niche_match=0.05
    )

    def __init__(self, weights: RankingWeights = None):
        self.weights = weights or self.DEFAULT_WEIGHTS

    def rank_influencers(
        self,
        influencers: List[Any],
        parsed_query: ParsedSearchQuery,
        custom_weights: RankingWeights = None,
        brand_overlap_data: Optional[Dict[str, Dict[str, float]]] = None
    ) -> List[RankedInfluencer]:
        """
        Rank influencers using weighted multi-factor scoring.
        Returns ranked list with score components for transparency.

        Args:
            influencers: List of influencer data
            parsed_query: Parsed search query with brand/creative context
            custom_weights: Optional weight overrides
            brand_overlap_data: Optional pre-fetched audience overlap data
                Format: {"influencer_username": {"brand_handle": overlap_pct}}
        """
        # Use LLM-suggested weights, custom weights, or defaults
        weights = self._resolve_weights(parsed_query, custom_weights)

        ranked = []
        for inf in influencers:
            # Calculate scores - now returns tuple with warnings
            scores, brand_warning_type, brand_warning_message, niche_warning = \
                self._calculate_scores(inf, parsed_query, brand_overlap_data)

            # Calculate weighted relevance score with all 8 factors
            relevance_score = (
                weights.credibility * scores.credibility +
                weights.engagement * scores.engagement +
                weights.audience_match * scores.audience_match +
                weights.growth * scores.growth +
                weights.geography * scores.geography +
                weights.brand_affinity * scores.brand_affinity +
                weights.creative_fit * scores.creative_fit +
                weights.niche_match * scores.niche_match
            )

            # Apply size penalty if follower range preference specified
            follower_range = parsed_query.get_follower_range()
            if follower_range:
                size_multiplier = self._calculate_size_penalty(inf, follower_range)
                relevance_score *= size_multiplier

            # Get raw data dict
            if hasattr(inf, 'to_dict'):
                raw_data = inf.to_dict()
            elif isinstance(inf, dict):
                raw_data = inf
            else:
                raw_data = self._extract_raw_data(inf)

            # Construct mediakit_url from encrypted username if available
            encrypted_username = raw_data.get('primetag_encrypted_username')
            mediakit_url = f"https://mediakit.primetag.com/instagram/{encrypted_username}" if encrypted_username else None

            # Convert to InfluencerData - handle None values from database
            influencer_data = InfluencerData(
                id=raw_data.get('id', ''),
                username=raw_data.get('username', ''),
                display_name=raw_data.get('display_name'),
                profile_picture_url=raw_data.get('profile_picture_url'),
                bio=raw_data.get('bio'),
                is_verified=raw_data.get('is_verified') or False,
                follower_count=raw_data.get('follower_count') or 0,
                credibility_score=raw_data.get('credibility_score'),
                engagement_rate=raw_data.get('engagement_rate'),
                follower_growth_rate_6m=raw_data.get('follower_growth_rate_6m'),
                avg_likes=raw_data.get('avg_likes') or 0,
                avg_comments=raw_data.get('avg_comments') or 0,
                audience_genders=raw_data.get('audience_genders') or {},
                audience_age_distribution=raw_data.get('audience_age_distribution') or {},
                audience_geography=raw_data.get('audience_geography') or {},
                interests=raw_data.get('interests') or [],
                brand_mentions=raw_data.get('brand_mentions') or [],
                # Add warning fields
                brand_warning_type=brand_warning_type,
                brand_warning_message=brand_warning_message,
                niche_warning=niche_warning,
                # MediaKit URL for PrimeTag data
                mediakit_url=mediakit_url,
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
            return custom_weights.get_normalized_weights()

        if parsed_query.suggested_ranking_weights:
            suggested = parsed_query.suggested_ranking_weights
            # Clamp values to [0, 1] before creating RankingWeights
            # The LLM may return relative weights > 1, which will be normalized
            def clamp(val, default):
                v = suggested.get(val, default)
                return max(0, min(1, v)) if v is not None else default

            weights = RankingWeights(
                credibility=clamp('credibility', self.DEFAULT_WEIGHTS.credibility),
                engagement=clamp('engagement', self.DEFAULT_WEIGHTS.engagement),
                audience_match=clamp('audience_match', self.DEFAULT_WEIGHTS.audience_match),
                growth=clamp('growth', self.DEFAULT_WEIGHTS.growth),
                geography=clamp('geography', self.DEFAULT_WEIGHTS.geography),
                brand_affinity=clamp('brand_affinity', self.DEFAULT_WEIGHTS.brand_affinity),
                creative_fit=clamp('creative_fit', self.DEFAULT_WEIGHTS.creative_fit),
                niche_match=clamp('niche_match', self.DEFAULT_WEIGHTS.niche_match),
            )
            return weights.get_normalized_weights()

        return self.weights

    def _calculate_scores(
        self,
        influencer: Any,
        parsed_query: ParsedSearchQuery,
        brand_overlap_data: Optional[Dict[str, Dict[str, float]]] = None
    ) -> Tuple[ScoreComponents, Optional[str], Optional[str], Optional[str]]:
        """
        Calculate normalized scores for each factor (0-1 scale).

        Returns:
            Tuple of (ScoreComponents, brand_warning_type, brand_warning_message, niche_warning)
        """

        # ===== ORIGINAL 5 FACTORS =====

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

        # ===== NEW BRAND/CREATIVE FACTORS =====

        # Brand Affinity: audience overlap with target brand + conflict detection
        brand_affinity, brand_warning_type, brand_warning_message = self._calculate_brand_affinity(
            influencer,
            parsed_query.brand_handle,
            brand_overlap_data
        )

        # Creative Fit: alignment with campaign creative concept
        creative_fit = self._calculate_creative_fit(
            influencer,
            parsed_query.creative_tone,
            parsed_query.creative_themes
        )

        # Niche Match: content niche alignment with campaign topics
        # Now uses brand intelligence service for better matching
        niche_match, niche_warning = self._calculate_niche_match(
            influencer,
            parsed_query.campaign_topics,
            parsed_query.exclude_niches,
            parsed_query.campaign_niche if hasattr(parsed_query, 'campaign_niche') else None
        )

        scores = ScoreComponents(
            credibility=round(credibility, 4),
            engagement=round(engagement, 4),
            audience_match=round(audience_match, 4),
            growth=round(growth, 4),
            geography=round(geography, 4),
            brand_affinity=round(brand_affinity, 4),
            creative_fit=round(creative_fit, 4),
            niche_match=round(niche_match, 4)
        )

        return scores, brand_warning_type, brand_warning_message, niche_warning

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
                     'audience_genders', 'audience_age_distribution', 'audience_geography',
                     'interests', 'brand_mentions', 'primetag_encrypted_username',
                     'post_content_aggregated']:
            if hasattr(obj, attr):
                data[attr] = getattr(obj, attr)
        return data

    # ===== NEW SCORING METHODS =====

    def _calculate_brand_affinity(
        self,
        influencer: Any,
        brand_handle: Optional[str],
        overlap_data: Optional[Dict[str, Dict[str, float]]]
    ) -> Tuple[float, Optional[str], Optional[str]]:
        """
        Calculate brand affinity score with conflict detection and saturation warnings.

        NEW LOGIC:
        - Check for competitor ambassador conflicts (Messi for Nike = 0.05)
        - Check for competitor brand mentions (0.25-0.45 depending on severity)
        - Check for brand saturation (already ambassador = 0.35-0.45)
        - Then apply original boost logic for positive signals

        Args:
            influencer: Influencer data
            brand_handle: Brand's social handle (e.g., "@nike" or "nike")
            overlap_data: Pre-fetched overlap data {username: {brand: overlap_pct}}

        Returns:
            Tuple of (score, warning_type, warning_message):
            - score: 0.05-1.0 (lower = worse fit)
            - warning_type: "competitor_conflict", "saturation", or None
            - warning_message: Human-readable warning or None
        """
        # Return neutral if no brand context provided
        if not brand_handle:
            return 0.5, None, None

        # Get influencer data
        username = self._get_value(influencer, 'username', '').lower()
        brand_mentions = self._get_value(influencer, 'brand_mentions', [])

        # Get influencer overlap data if available
        influencer_overlap = None
        if overlap_data:
            influencer_overlap = overlap_data.get(username, {})

        # Use brand intelligence service for comprehensive scoring
        brand_intel = get_brand_intelligence_service()
        score, warning_type, warning_message = brand_intel.calculate_brand_affinity_score(
            influencer_username=username,
            influencer_brand_mentions=brand_mentions,
            target_brand=brand_handle,
            overlap_data=influencer_overlap
        )

        return score, warning_type, warning_message

    def _calculate_creative_fit(
        self,
        influencer: Any,
        creative_tone: List[str],
        creative_themes: List[str]
    ) -> float:
        """
        Calculate how well influencer matches the creative concept.

        Analyzes:
        - Content style alignment from bio/interests
        - Past campaign relevance from brand_mentions
        - Theme alignment

        Returns:
            Score from 0-1 (0.5 = neutral/no creative context)
        """
        # Return neutral if no creative context
        if not creative_tone and not creative_themes:
            return 0.5

        score_components = []

        # Get influencer data
        interests = self._get_value(influencer, 'interests', [])
        bio = self._get_value(influencer, 'bio', '') or ''
        bio_lower = bio.lower()
        brand_mentions = self._get_value(influencer, 'brand_mentions', [])

        # Normalize interests to lowercase strings
        interests_lower = [str(i).lower() for i in interests]
        interests_text = ' '.join(interests_lower)

        # 1. Theme alignment from interests/bio
        if creative_themes:
            theme_matches = 0
            for theme in creative_themes:
                theme_lower = theme.lower()
                if theme_lower in bio_lower or theme_lower in interests_text:
                    theme_matches += 1
            theme_score = theme_matches / len(creative_themes) if creative_themes else 0
            score_components.append(('theme', theme_score, 0.4))

        # 2. Tone alignment using keyword matching
        if creative_tone:
            tone_matches = 0
            for tone in creative_tone:
                tone_lower = tone.lower()
                keywords = TONE_KEYWORDS.get(tone_lower, [tone_lower])
                if any(kw in bio_lower or kw in interests_text for kw in keywords):
                    tone_matches += 1
            tone_score = tone_matches / len(creative_tone) if creative_tone else 0
            score_components.append(('tone', tone_score, 0.3))

        # 3. Past campaign experience
        has_experience = len(brand_mentions) > 0
        experience_score = 0.7 if has_experience else 0.5
        score_components.append(('experience', experience_score, 0.3))

        # Calculate weighted score
        if not score_components:
            return 0.5

        total_weight = sum(w for _, _, w in score_components)
        weighted_score = sum(s * w for _, s, w in score_components) / total_weight

        return min(max(weighted_score, 0), 1.0)

    def _calculate_niche_match(
        self,
        influencer: Any,
        campaign_topics: List[str],
        exclude_niches: List[str],
        campaign_niche: Optional[str] = None
    ) -> Tuple[float, Optional[str]]:
        """
        Calculate content niche alignment with campaign topics.

        NEW LOGIC (Messi/Padel problem):
        - Uses brand intelligence service for niche taxonomy
        - Detects conflicting niches (football influencer for padel campaign)
        - Applies celebrity penalty for large accounts in wrong niche
        - Uses post content (hashtags, captions) from Apify for enhanced detection

        Returns:
            Tuple of (score, warning_message):
            - score: 0.15-0.95 based on niche relevance
            - warning: Human-readable warning if mismatch detected
        """
        interests = self._get_value(influencer, 'interests', [])
        bio = self._get_value(influencer, 'bio', '') or ''
        follower_count = self._get_value(influencer, 'follower_count', 0)
        post_content = self._get_value(influencer, 'post_content_aggregated', None)

        warning = None

        # If we have a campaign niche, use the brand intelligence service
        if campaign_niche:
            brand_intel = get_brand_intelligence_service()
            relevance = brand_intel.check_niche_relevance(
                influencer_interests=interests,
                influencer_bio=bio,
                campaign_niche=campaign_niche,
                follower_count=follower_count,
                post_content=post_content  # Pass post content for enhanced detection
            )

            if relevance.match_type == "conflicting" or relevance.is_celebrity_mismatch:
                warning = relevance.details

            # Blend with topic matching for comprehensive score
            niche_score = relevance.score

            # If also have campaign_topics, blend the scores
            if campaign_topics:
                topic_score = self._calculate_topic_match(influencer, campaign_topics)
                # Weight niche matching more heavily (70/30)
                final_score = (niche_score * 0.7) + (topic_score * 0.3)
            else:
                final_score = niche_score

            # Apply exclude_niches penalty
            if exclude_niches:
                exclusion_penalty = self._calculate_exclusion_penalty(influencer, exclude_niches)
                final_score = max(0.1, final_score - exclusion_penalty)

            return min(max(final_score, 0), 1.0), warning

        # Fallback to original topic-based matching if no campaign_niche
        if not campaign_topics and not exclude_niches:
            return 0.5, None

        score = self._calculate_topic_match(influencer, campaign_topics) if campaign_topics else 0.5

        # Penalty for excluded niches
        if exclude_niches:
            exclusion_penalty = self._calculate_exclusion_penalty(influencer, exclude_niches)
            score = max(0.1, score - exclusion_penalty)

        return min(max(score, 0), 1.0), warning

    def _calculate_topic_match(
        self,
        influencer: Any,
        campaign_topics: List[str]
    ) -> float:
        """Calculate simple topic keyword matching score."""
        if not campaign_topics:
            return 0.5

        interests = self._get_value(influencer, 'interests', [])
        bio = self._get_value(influencer, 'bio', '') or ''

        interests_lower = [str(i).lower() for i in interests]
        searchable_text = f"{bio.lower()} {' '.join(interests_lower)}"

        matches = sum(
            1 for topic in campaign_topics
            if topic.lower() in searchable_text
        )
        topic_score = matches / len(campaign_topics)
        return 0.5 + (topic_score * 0.5)  # Scale to 0.5-1.0

    def _calculate_exclusion_penalty(
        self,
        influencer: Any,
        exclude_niches: List[str]
    ) -> float:
        """Calculate penalty for excluded niches."""
        if not exclude_niches:
            return 0.0

        interests = self._get_value(influencer, 'interests', [])
        bio = self._get_value(influencer, 'bio', '') or ''

        interests_lower = [str(i).lower() for i in interests]
        searchable_text = f"{bio.lower()} {' '.join(interests_lower)}"

        exclusions = sum(
            1 for niche in exclude_niches
            if niche.lower() in searchable_text
        )

        if exclusions > 0:
            return (exclusions / len(exclude_niches)) * 0.4

        return 0.0

    def _calculate_size_penalty(
        self,
        influencer: Any,
        preferred_range: Tuple[int, int]
    ) -> float:
        """
        Calculate size multiplier based on preferred follower range.

        For anti-celebrity bias - penalize influencers outside the preferred range.

        Args:
            influencer: Influencer data
            preferred_range: (min_followers, max_followers)

        Returns:
            Multiplier from 0.3-1.0 (1.0 = in range, <1.0 = penalty)
        """
        followers = self._get_value(influencer, 'follower_count', 0)
        min_f, max_f = preferred_range

        if min_f <= followers <= max_f:
            return 1.0  # Perfect range

        if followers < min_f:
            # Too small - scale down
            if min_f == 0:
                return 1.0
            return max(0.5, followers / min_f)

        # Too large (anti-celebrity bias)
        if max_f == 0:
            return 1.0
        overage_ratio = followers / max_f
        # Diminishing returns - larger = worse
        return max(0.3, 1.0 / overage_ratio)
