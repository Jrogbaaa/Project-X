from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Tuple
from enum import Enum


class GenderFilter(str, Enum):
    """Gender filter options."""
    MALE = "male"
    FEMALE = "female"
    ANY = "any"


class AudienceAgeRange(str, Enum):
    """Audience age range categories."""
    TEEN = "13-17"
    YOUNG_ADULT = "18-24"
    ADULT = "25-34"
    MATURE_ADULT = "35-44"
    MIDDLE_AGE = "45-54"
    SENIOR = "55+"


class ParsedSearchQuery(BaseModel):
    """Structured output from LLM query parsing.

    Extracts brand info, creative concept, and search criteria from natural language briefs.
    """

    # Extracted count
    target_count: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of influencers to find"
    )

    # Gender targeting
    influencer_gender: GenderFilter = Field(
        default=GenderFilter.ANY,
        description="Gender of the influencer themselves"
    )

    target_audience_gender: Optional[GenderFilter] = Field(
        default=None,
        description="Desired gender of the influencer's audience"
    )

    # Gender-specific result counts (when brief requests e.g. "3 male, 3 female")
    target_male_count: Optional[int] = Field(
        default=None,
        ge=1,
        le=50,
        description="Number of male influencers requested (e.g., '3 male influencers' -> 3)"
    )

    target_female_count: Optional[int] = Field(
        default=None,
        ge=1,
        le=50,
        description="Number of female influencers requested (e.g., '3 female influencers' -> 3)"
    )

    # ========== Brand Context ==========
    brand_name: Optional[str] = Field(
        default=None,
        description="Brand name mentioned in query"
    )

    brand_handle: Optional[str] = Field(
        default=None,
        description="Brand's social media handle (e.g., '@nike', '@adidas') for audience overlap analysis"
    )

    brand_category: Optional[str] = Field(
        default=None,
        description="Inferred brand category (e.g., 'home_furniture', 'fashion', 'sports', 'tech')"
    )

    # ========== Creative Concept ==========
    creative_concept: Optional[str] = Field(
        default=None,
        description="The campaign creative brief or concept description"
    )

    creative_format: Optional[str] = Field(
        default=None,
        description="Content format requested: documentary, day_in_the_life, tutorial, challenge, testimonial, storytelling, lifestyle"
    )

    creative_tone: List[str] = Field(
        default_factory=list,
        description="Tone/style keywords: authentic, humorous, luxury, edgy, casual, inspirational, gritty, polished, raw"
    )

    creative_themes: List[str] = Field(
        default_factory=list,
        description="Key themes in the creative concept: dedication, family, adventure, innovation, rising stars, etc."
    )

    # ========== Niche/Topic Targeting ==========
    campaign_niche: Optional[str] = Field(
        default=None,
        description="Primary campaign niche for relevance scoring (e.g., 'padel', 'tennis', 'fitness'). Used for niche taxonomy matching."
    )

    campaign_topics: List[str] = Field(
        default_factory=list,
        description="Specific topics/niches for the campaign (e.g., 'padel', 'tennis', 'skincare')"
    )

    exclude_niches: List[str] = Field(
        default_factory=list,
        description="Niches to avoid (e.g., for padel campaign, exclude 'soccer', 'football')"
    )

    content_themes: List[str] = Field(
        default_factory=list,
        description="Relevant content themes (e.g., 'interior_design', 'lifestyle')"
    )

    # ========== Creative Discovery (PrimeTag Interest Mapping) ==========
    discovery_interests: List[str] = Field(
        default_factory=list,
        description="PrimeTag interest categories to search for (e.g., 'Sports', 'Tennis', 'Fitness'). Used when exact niche matches are sparse."
    )

    exclude_interests: List[str] = Field(
        default_factory=list,
        description="PrimeTag interest categories to avoid (e.g., 'Soccer' for a padel campaign)"
    )

    influencer_reasoning: str = Field(
        default="",
        description="Brief reasoning about what types of influencers would authentically represent this brand"
    )

    # ========== Size Preferences ==========
    preferred_follower_min: Optional[int] = Field(
        default=None,
        description="Minimum preferred follower count (anti-celebrity bias)"
    )

    preferred_follower_max: Optional[int] = Field(
        default=None,
        description="Maximum preferred follower count (anti-celebrity bias)"
    )

    # ========== Audience Requirements ==========
    target_age_ranges: List[AudienceAgeRange] = Field(
        default_factory=list,
        description="Preferred audience age ranges"
    )

    min_spain_audience_pct: float = Field(
        default=60.0,
        ge=0,
        le=100,
        description="Minimum percentage of Spanish audience"
    )

    # ========== Quality Filters ==========
    min_credibility_score: float = Field(
        default=70.0,
        ge=0,
        le=100,
        description="Minimum credibility score"
    )

    min_engagement_rate: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Minimum engagement rate percentage"
    )

    # ========== Ranking ==========
    suggested_ranking_weights: Optional[Dict[str, float]] = Field(
        default=None,
        description="Suggested ranking weight adjustments based on query context"
    )

    # ========== Search ==========
    search_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords to use for PrimeTag username search"
    )

    # ========== Meta ==========
    parsing_confidence: float = Field(
        default=1.0,
        ge=0,
        le=1,
        description="LLM confidence in parsing accuracy"
    )

    reasoning: str = Field(
        default="",
        description="Brief explanation of parsing decisions"
    )

    def has_brand_context(self) -> bool:
        """Check if brand info was provided for affinity scoring."""
        return bool(self.brand_name or self.brand_handle)

    def has_creative_context(self) -> bool:
        """Check if creative concept was provided for fit scoring."""
        return bool(self.creative_concept or self.creative_format or self.creative_tone or self.creative_themes)

    def has_niche_context(self) -> bool:
        """Check if niche targeting was specified."""
        return bool(self.campaign_niche or self.campaign_topics or self.exclude_niches)

    def get_follower_range(self) -> Optional[Tuple[int, int]]:
        """Get preferred follower range if specified."""
        if self.preferred_follower_min is not None or self.preferred_follower_max is not None:
            return (
                self.preferred_follower_min or 0,
                self.preferred_follower_max or 999_999_999
            )
        return None
