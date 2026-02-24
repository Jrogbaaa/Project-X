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
    'authentic': ['real', 'genuine', 'honest', 'raw', 'unfiltered', 'natural', 'auténtico', 'verdadero'],
    'luxury': ['premium', 'exclusive', 'elegant', 'sophisticated', 'high-end', 'lujo', 'exclusivo'],
    'humorous': ['funny', 'comedy', 'laugh', 'humor', 'fun', 'divertido', 'risa', 'comedia'],
    'casual': ['everyday', 'relax', 'chill', 'lifestyle', 'daily', 'cotidiano', 'relajado'],
    'documentary': ['story', 'journey', 'behind', 'real', 'making of', 'documental'],
    'inspirational': ['inspire', 'motivate', 'dream', 'achieve', 'success', 'inspirar', 'motivar'],
    'edgy': ['bold', 'daring', 'provocative', 'rebel', 'alternative', 'atrevido'],
    'gritty': ['raw', 'intense', 'real', 'street', 'urban', 'hardcore'],
    'polished': ['professional', 'clean', 'refined', 'quality', 'premium', 'profesional'],
    'creative': ['creative', 'art', 'artist', 'design', 'creativo', 'artista', 'diseño', 'original'],
    'artistic': ['art', 'artist', 'creative', 'gallery', 'arte', 'artista', 'museo', 'pintura'],
    'warm': ['warm', 'cozy', 'heart', 'love', 'cariño', 'hogar', 'familia', 'acogedor'],
    'fun': ['fun', 'funny', 'enjoy', 'laugh', 'divertido', 'humor', 'entretenimiento', 'fiesta'],
    'approachable': ['friendly', 'close', 'relatable', 'everyday', 'cercano', 'accesible', 'normal'],
    'heartwarming': ['heart', 'love', 'family', 'cute', 'adorable', 'corazón', 'amor', 'ternura'],
    'playful': ['play', 'fun', 'game', 'colorful', 'juego', 'divertido', 'color', 'alegre'],
    'bold': ['bold', 'daring', 'strong', 'powerful', 'atrevido', 'fuerte', 'valiente'],
    'natural': ['natural', 'organic', 'real', 'eco', 'nature', 'naturaleza', 'sostenible'],
    'professional': ['professional', 'business', 'expert', 'credible', 'profesional', 'experto'],
    'colorful': ['color', 'colorful', 'vibrant', 'bright', 'colorido', 'vibrante', 'alegre'],
    'urban': ['urban', 'city', 'street', 'metropolitan', 'urbano', 'ciudad', 'callejero'],
    'dynamic': ['dynamic', 'energy', 'active', 'fast', 'dinámico', 'energía', 'activo'],
    'modern': ['modern', 'contemporary', 'trendy', 'current', 'moderno', 'actual', 'tendencia'],
    'sophisticated': ['sophisticated', 'elegant', 'refined', 'chic', 'sofisticado', 'elegante'],
    'elegant': ['elegant', 'classy', 'refined', 'grace', 'elegante', 'refinado', 'clase'],
    'cercano': ['cercano', 'close', 'relatable', 'friendly', 'accesible', 'familiar'],
    'aspiracional': ['aspirational', 'dream', 'luxury', 'goal', 'aspiracional', 'lujo', 'premium'],
    'divertido': ['divertido', 'fun', 'funny', 'humor', 'risa', 'entretenimiento'],
    'social': ['social', 'friends', 'together', 'community', 'amigos', 'juntos', 'comunidad'],
    'adventurous': ['adventure', 'explore', 'discover', 'travel', 'aventura', 'explorar', 'descubrir', 'viaje'],
    'luxurious': ['luxury', 'premium', 'exclusive', 'elegant', 'lujo', 'premium', 'exclusivo', 'elegante'],
    'romantic': ['romantic', 'love', 'couple', 'romance', 'romántico', 'amor', 'pareja', 'corazón'],
    'feminine': ['feminine', 'woman', 'girl', 'beauty', 'femenino', 'mujer', 'chica', 'belleza'],
    'masculine': ['masculine', 'man', 'strong', 'power', 'masculino', 'hombre', 'fuerza'],
    'trendy': ['trendy', 'trend', 'viral', 'hot', 'tendencia', 'moda', 'viral'],
    'minimalist': ['minimal', 'minimalist', 'simple', 'clean', 'minimalista', 'sencillo', 'limpio'],
    'sporty': ['sport', 'athletic', 'active', 'fitness', 'deportivo', 'atlético', 'activo'],
    'rebellious': ['rebel', 'alternative', 'punk', 'counter-culture', 'rebelde', 'alternativo'],
    'cozy': ['cozy', 'warm', 'home', 'comfort', 'acogedor', 'cálido', 'hogar', 'confort'],
    'auténtico': ['auténtico', 'real', 'genuine', 'natural', 'verdadero', 'honesto'],
    'eco-conscious': ['eco', 'sustainable', 'green', 'environment', 'sostenible', 'ecológico', 'reciclaje'],
    'sustainable': ['sustainable', 'eco', 'green', 'recycl', 'sostenible', 'ecológico', 'reciclaje'],
    'funny': ['funny', 'comedy', 'humor', 'laugh', 'fun', 'divertido', 'risa', 'comedia', 'gracioso'],
}


class RankingService:
    """Service for ranking influencer candidates with brand affinity and creative fit.
    
    Simplified ranking focuses on 3 main factors using data from Apify scraping:
    - niche_match (40%): Uses primary_niche column for exact/related niche matching
    - creative_fit (35%): Uses content_themes column for format/style matching  
    - brand_affinity (25%): Uses detected_brands column for brand mention matching
    
    Other factors (credibility, engagement, demographics) come from PrimeTag verification
    AFTER initial matching and are used for display/filtering, not ranking.
    """

    # Balanced weights: niche/creative remain dominant, PrimeTag signals now active
    # PrimeTag factors (credibility, engagement, geography) contribute where data exists;
    # their scores default to neutral (0.5) when not yet fetched, so they don't harm
    # influencers that haven't been verified yet.
    # Weights tuned for current data reality (no PrimeTag API).
    # When PrimeTag is restored, rebalance credibility/geography/audience_match.
    DEFAULT_WEIGHTS = RankingWeights(
        credibility=0.00,      # PrimeTag: 0.4% coverage — zeroed until API restored
        engagement=0.10,       # Starngage: 98.6% coverage — reduced to prevent ER outliers dominating
        audience_match=0.00,   # PrimeTag: 0.4% coverage — zeroed until API restored
        growth=0.00,           # PrimeTag: 0.4% coverage — zeroed until API restored
        geography=0.00,        # PrimeTag: 0.0% coverage — zeroed until API restored
        brand_affinity=0.10,   # Apify: 3.4% coverage — mostly neutral, helps when present
        creative_fit=0.30,     # Apify+LLM: 50.3% coverage — key differentiator
        niche_match=0.50,      # LLM+keyword: 98.6% coverage — dominant signal (boosted from 0.45)
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
            else:
                # Even without a range preference, penalize profiles with
                # unknown (0/null) follower counts — we can't verify their reach.
                followers = self._get_value(inf, 'follower_count', 0)
                if not followers or followers == 0:
                    relevance_score *= 0.4

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
                # Niche detection data from Apify scrape
                primary_niche=raw_data.get('primary_niche'),
                niche_confidence=raw_data.get('niche_confidence'),
                detected_brands=raw_data.get('detected_brands') or [],
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

            # If the LLM suggests equal (or near-equal) weights for all factors,
            # it has no meaningful preference — fall back to system defaults.
            # This happens when the LLM hedges (e.g. all 1.0 or all 0.5), and
            # applying equal weights collapses niche_match's 0.50 dominance.
            _weight_keys = ['credibility', 'engagement', 'audience_match', 'growth',
                            'geography', 'brand_affinity', 'creative_fit', 'niche_match']
            _vals = [suggested.get(k) for k in _weight_keys if suggested.get(k) is not None]
            if _vals and (max(_vals) - min(_vals)) < 0.15:
                return self.weights  # Equal-ish weights → ignore, use defaults

            def clamp(key, default):
                # If the default weight is zero (data source unavailable),
                # keep it zero regardless of LLM suggestion
                if default == 0.0:
                    return 0.0
                v = suggested.get(key, default)
                result = max(0, min(1, v)) if v is not None else default
                # niche_match is the primary quality signal — never let the LLM reduce it
                # below the system default. It can be boosted but not weakened.
                if key == 'niche_match':
                    result = max(result, default)
                return result

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
        # Now uses content_themes column from Apify scrape
        creative_fit = self._calculate_creative_fit(
            influencer,
            parsed_query.creative_tone,
            parsed_query.creative_themes,
            getattr(parsed_query, 'creative_format', None)
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
                     'post_content_aggregated',
                     # New niche detection columns from Apify scrape
                     'primary_niche', 'niche_confidence', 'detected_brands',
                     'sponsored_ratio', 'content_language', 'content_themes']:
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

        USES NEW COLUMN FROM APIFY SCRAPE:
        - detected_brands: Brands mentioned in posts (more accurate than bio-based brand_mentions)

        Logic:
        - Check for competitor ambassador conflicts (Messi for Nike = 0.05)
        - Check for competitor brand mentions (0.25-0.45 depending on severity)
        - Check for brand saturation (already ambassador = 0.35-0.45)
        - Boost if target brand is in detected_brands

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

        # Get influencer data - prefer detected_brands from scrape over brand_mentions
        username = self._get_value(influencer, 'username', '').lower()
        detected_brands = self._get_value(influencer, 'detected_brands', []) or []
        brand_mentions = self._get_value(influencer, 'brand_mentions', []) or []
        
        # Combine both sources, preferring detected_brands (from actual posts)
        all_brand_mentions = list(set(
            [b.lower() for b in detected_brands] + 
            [b.lower() for b in brand_mentions]
        ))

        # Get influencer overlap data if available
        influencer_overlap = None
        if overlap_data:
            influencer_overlap = overlap_data.get(username, {})

        # Use brand intelligence service for comprehensive scoring
        brand_intel = get_brand_intelligence_service()
        score, warning_type, warning_message = brand_intel.calculate_brand_affinity_score(
            influencer_username=username,
            influencer_brand_mentions=all_brand_mentions,
            target_brand=brand_handle,
            overlap_data=influencer_overlap
        )
        
        # Boost score if target brand is directly mentioned in detected_brands
        brand_handle_clean = brand_handle.lower().lstrip('@')
        if brand_handle_clean in [b.lower() for b in detected_brands]:
            # Direct mention of target brand - strong positive signal
            score = min(score + 0.25, 1.0)

        return score, warning_type, warning_message

    def _calculate_creative_fit(
        self,
        influencer: Any,
        creative_tone: List[str],
        creative_themes: List[str],
        creative_format: Optional[str] = None
    ) -> float:
        """
        Calculate how well influencer matches the creative concept.

        USES NEW COLUMNS FROM APIFY SCRAPE:
        - content_themes: Detected themes like "training", "behind_the_scenes", etc.
        - content_themes.narrative_style: "storytelling", "casual", "promotional"
        - content_themes.format_preference: Post formats used (Reel, Sidecar, etc.)

        Returns:
            Score from 0-1 (0.5 = neutral/no creative context)
        """
        # Return neutral if no creative context
        if not creative_tone and not creative_themes and not creative_format:
            return 0.5

        score_components = []

        # Get new content_themes column from scrape
        content_themes = self._get_value(influencer, 'content_themes', None)
        
        # Fallback data
        interests = self._get_value(influencer, 'interests', [])
        bio = self._get_value(influencer, 'bio', '') or ''
        bio_lower = bio.lower()
        brand_mentions = self._get_value(influencer, 'brand_mentions', [])
        detected_brands = self._get_value(influencer, 'detected_brands', []) or []

        # Normalize interests to lowercase strings
        interests_lower = [str(i).lower() for i in interests]
        interests_text = ' '.join(interests_lower)

        # 1. Theme alignment - USE content_themes.detected_themes if available
        if creative_themes:
            theme_matches = 0
            
            if content_themes and content_themes.get('detected_themes'):
                # Use scraped content themes for matching
                detected = [t.lower() for t in content_themes.get('detected_themes', [])]
                for theme in creative_themes:
                    theme_lower = theme.lower()
                    # Check for exact or partial match in detected themes
                    if theme_lower in detected or any(theme_lower in d for d in detected):
                        theme_matches += 1
                    # Also check bio/interests as fallback
                    elif theme_lower in bio_lower or theme_lower in interests_text:
                        theme_matches += 0.5
            else:
                # Fallback to bio/interests matching
                for theme in creative_themes:
                    theme_lower = theme.lower()
                    if theme_lower in bio_lower or theme_lower in interests_text:
                        theme_matches += 1
                        
            theme_score = theme_matches / len(creative_themes) if creative_themes else 0
            score_components.append(('theme', theme_score, 0.35))

        # 2. Narrative style / format alignment - USE content_themes.narrative_style
        format_score = 0.5  # Neutral default
        if content_themes:
            narrative_style = content_themes.get('narrative_style', '')
            format_preference = content_themes.get('format_preference', [])
            
            # Match creative format to narrative style
            if creative_format:
                format_map = {
                    'documentary': 'storytelling',
                    'day_in_the_life': 'storytelling',
                    'storytelling': 'storytelling',
                    'tutorial': 'casual',
                    'challenge': 'casual',
                    'lifestyle': 'casual',
                    'testimonial': 'promotional',
                }
                expected_style = format_map.get(creative_format, '')
                if narrative_style == expected_style:
                    format_score = 0.9
                elif narrative_style == 'storytelling' and creative_format in ['documentary', 'day_in_the_life']:
                    format_score = 0.85
                elif narrative_style != 'promotional' and creative_format != 'testimonial':
                    format_score = 0.6
            
            # Boost for Reels if challenge/tutorial format
            if creative_format in ['challenge', 'tutorial'] and 'Reel' in format_preference:
                format_score = min(format_score + 0.15, 1.0)
                
        score_components.append(('format', format_score, 0.30))

        # 3. Tone alignment using keyword matching
        if creative_tone:
            tone_matches = 0
            for tone in creative_tone:
                tone_lower = tone.lower()
                keywords = TONE_KEYWORDS.get(tone_lower, [tone_lower])
                if any(kw in bio_lower or kw in interests_text for kw in keywords):
                    tone_matches += 1
                # Also check if narrative style aligns with tone
                if content_themes:
                    narrative = content_themes.get('narrative_style', '')
                    if tone_lower in ['authentic', 'raw', 'documentary'] and narrative == 'storytelling':
                        tone_matches += 0.5
                    elif tone_lower in ['polished', 'luxury'] and narrative == 'promotional':
                        tone_matches += 0.3
            tone_score = min(tone_matches / len(creative_tone), 1.0) if creative_tone else 0
            score_components.append(('tone', tone_score, 0.20))

        # 4. Past brand experience - USE detected_brands
        has_experience = len(brand_mentions) > 0 or len(detected_brands) > 0
        experience_score = 0.7 if has_experience else 0.5
        score_components.append(('experience', experience_score, 0.10))

        # 5. Engagement as creative quality proxy — high engagement indicates
        # content that resonates with audiences, a signal of creative competence
        engagement_raw = self._get_value(influencer, 'engagement_rate', 0)
        if engagement_raw and engagement_raw < 1:
            engagement_raw = engagement_raw * 100
        if engagement_raw and engagement_raw > 0:
            engagement_quality = min(engagement_raw / 8.0, 1.0)
        else:
            engagement_quality = 0.3
        score_components.append(('engagement_quality', engagement_quality, 0.15))

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

        USES NEW COLUMNS FROM APIFY SCRAPE:
        - primary_niche: Directly compare influencer's detected niche to campaign niche
        - niche_confidence: Weight the score by detection confidence
        - Falls back to brand intelligence service for taxonomy matching

        Returns:
            Tuple of (score, warning_message):
            - score: 0.15-0.95 based on niche relevance
            - warning: Human-readable warning if mismatch detected
        """
        # Get new niche columns from scrape
        primary_niche = self._get_value(influencer, 'primary_niche', None)
        niche_confidence = self._get_value(influencer, 'niche_confidence', 0.5) or 0.5
        
        # Fallback data
        interests = self._get_value(influencer, 'interests', [])
        bio = self._get_value(influencer, 'bio', '') or ''
        follower_count = self._get_value(influencer, 'follower_count', 0)
        post_content = self._get_value(influencer, 'post_content_aggregated', None)

        warning = None

        # If we have a campaign niche, try direct matching first
        if campaign_niche:
            campaign_niche_lower = campaign_niche.lower()
            
            # FAST PATH: Use primary_niche column if available
            if primary_niche:
                primary_niche_lower = primary_niche.lower()
                
                # Exact match - highest score
                if primary_niche_lower == campaign_niche_lower:
                    final_score = 0.95 * niche_confidence
                    return min(final_score, 1.0), None
                
                # Check for related/conflicting niches via taxonomy
                brand_intel = get_brand_intelligence_service()
                niche_info = brand_intel.get_niche(campaign_niche_lower)
                
                if niche_info:
                    # Check for alias (scored same as exact match)
                    if primary_niche_lower in [n.lower() for n in niche_info.aliases]:
                        final_score = 0.95 * niche_confidence
                        return min(final_score, 1.0), None

                    # Check for related niche
                    if primary_niche_lower in [n.lower() for n in niche_info.related_niches]:
                        final_score = 0.70 * niche_confidence
                        return final_score, None

                    # Check for conflicting niche
                    if primary_niche_lower in [n.lower() for n in niche_info.conflicting_niches]:
                        warning = f"Conflicting niche: {primary_niche} conflicts with {campaign_niche}"
                        # Apply celebrity penalty for large accounts in wrong niche
                        if follower_count and follower_count > 5_000_000:
                            return 0.05, warning
                        return 0.20, warning
                
                # No direct relationship - neutral with some penalty
                final_score = 0.40 * niche_confidence
                
                # Apply exclude_niches penalty
                if exclude_niches:
                    if primary_niche_lower in [n.lower() for n in exclude_niches]:
                        warning = f"Excluded niche: {primary_niche}"
                        return 0.10, warning
                
                return final_score, warning
            
            # SLOW PATH: No primary_niche, use full taxonomy matching
            brand_intel = get_brand_intelligence_service()
            relevance = brand_intel.check_niche_relevance(
                influencer_interests=interests,
                influencer_bio=bio,
                campaign_niche=campaign_niche,
                follower_count=follower_count,
                post_content=post_content
            )

            if relevance.match_type == "conflicting" or relevance.is_celebrity_mismatch:
                warning = relevance.details

            niche_score = relevance.score

            # If also have campaign_topics, blend the scores
            if campaign_topics:
                topic_score = self._calculate_topic_match(influencer, campaign_topics)
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
        Profiles with 0/null follower counts are heavily penalized (0.3x) since
        we can't verify they match the brief's size requirements.

        Args:
            influencer: Influencer data
            preferred_range: (min_followers, max_followers)

        Returns:
            Multiplier from 0.3-1.0 (1.0 = in range, <1.0 = penalty)
        """
        followers = self._get_value(influencer, 'follower_count', 0)
        min_f, max_f = preferred_range

        if not followers or followers == 0:
            return 0.3  # Unknown follower count — can't verify size match

        if min_f <= followers <= max_f:
            return 1.0  # Perfect range

        if followers < min_f:
            if min_f == 0:
                return 1.0
            return max(0.5, followers / min_f)

        # Too large (anti-celebrity bias)
        if max_f == 0:
            return 1.0
        overage_ratio = followers / max_f
        return max(0.3, 1.0 / overage_ratio)
