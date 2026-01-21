from pydantic import BaseModel, Field
from typing import Optional, List, Dict
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
    """Structured output from LLM query parsing."""

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

    # Brand context
    brand_name: Optional[str] = Field(
        default=None,
        description="Brand name mentioned in query"
    )

    brand_category: Optional[str] = Field(
        default=None,
        description="Inferred brand category (e.g., 'home_furniture', 'fashion', 'tech')"
    )

    # Content preferences
    content_themes: List[str] = Field(
        default_factory=list,
        description="Relevant content themes (e.g., 'interior_design', 'lifestyle')"
    )

    # Audience requirements
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

    # Quality filters
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

    # Ranking weight adjustments
    suggested_ranking_weights: Optional[Dict[str, float]] = Field(
        default=None,
        description="Suggested ranking weight adjustments based on query context"
    )

    # Search keywords for PrimeTag API
    search_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords to use for PrimeTag username search"
    )

    # Confidence
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
