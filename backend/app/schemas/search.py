from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.schemas.llm import ParsedSearchQuery
from app.schemas.influencer import RankedInfluencer


class FilterConfig(BaseModel):
    """Configurable filter settings."""
    min_credibility_score: float = Field(
        default=70.0,
        ge=0,
        le=100,
        description="Minimum credibility score (0-100)"
    )
    min_engagement_rate: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Minimum engagement rate percentage"
    )
    min_spain_audience_pct: float = Field(
        default=60.0,
        ge=0,
        le=100,
        description="Minimum Spain audience percentage"
    )
    min_follower_growth_rate: Optional[float] = Field(
        default=None,
        description="Minimum 6-month follower growth rate"
    )
    min_follower_count: int = Field(
        default=100_000,
        ge=0,
        description="Minimum follower count (default 100K — DB is sourced from 100K+ profiles)"
    )
    max_follower_count: int = Field(
        default=2_500_000,
        ge=0,
        description="Maximum follower count (default 2.5M - excludes mega-celebrities)"
    )

    # Gender audience filter
    target_audience_gender: Optional[str] = Field(
        default=None,
        description="Filter by majority audience gender: 'male', 'female', or None for any"
    )
    min_target_gender_pct: float = Field(
        default=50.0,
        ge=0,
        le=100,
        description="Minimum percentage of target gender in audience"
    )

    # Age bracket filter
    target_age_ranges: List[str] = Field(
        default_factory=list,
        description="Target audience age ranges: ['18-24', '25-34', etc.]"
    )
    min_target_age_pct: float = Field(
        default=30.0,
        ge=0,
        le=100,
        description="Minimum combined percentage in target age ranges"
    )

    # Brand conflict filter
    exclude_competitor_ambassadors: bool = Field(
        default=True,
        description="Hard-exclude known competitor brand ambassadors (e.g., Messi for Nike campaigns)"
    )


class RankingWeights(BaseModel):
    """Configurable ranking weights for influencer scoring.

    When brand/creative info is provided, all 8 factors are used.
    When not provided, brand_affinity, creative_fit, niche_match default to neutral (0.5)
    and their weights are effectively redistributed.
    """
    # PrimeTag-dependent factors (zeroed out until API is restored —
    # these fields have 0-0.4% data coverage without live verification)
    credibility: float = Field(default=0.00, ge=0, le=1)
    audience_match: float = Field(default=0.00, ge=0, le=1)
    growth: float = Field(default=0.00, ge=0, le=1)
    geography: float = Field(default=0.00, ge=0, le=1)

    # Factors with actual data coverage (Starngage + LLM enrichment)
    engagement: float = Field(default=0.15, ge=0, le=1)
    brand_affinity: float = Field(
        default=0.10,
        ge=0,
        le=1,
        description="Weight for audience overlap with target brand"
    )
    creative_fit: float = Field(
        default=0.30,
        ge=0,
        le=1,
        description="Weight for alignment with creative concept"
    )
    niche_match: float = Field(
        default=0.45,
        ge=0,
        le=1,
        description="Weight for content niche alignment"
    )

    def validate_sum(self) -> bool:
        """Check if weights sum to 1.0."""
        total = (
            self.credibility + self.engagement + self.audience_match +
            self.growth + self.geography + self.brand_affinity +
            self.creative_fit + self.niche_match
        )
        return abs(total - 1.0) < 0.01  # Allow small floating point error

    def get_normalized_weights(self) -> "RankingWeights":
        """Return weights normalized to sum to 1.0."""
        total = (
            self.credibility + self.engagement + self.audience_match +
            self.growth + self.geography + self.brand_affinity +
            self.creative_fit + self.niche_match
        )
        if total == 0:
            return self
        return RankingWeights(
            credibility=self.credibility / total,
            engagement=self.engagement / total,
            audience_match=self.audience_match / total,
            growth=self.growth / total,
            geography=self.geography / total,
            brand_affinity=self.brand_affinity / total,
            creative_fit=self.creative_fit / total,
            niche_match=self.niche_match / total,
        )


class SearchRequest(BaseModel):
    """Request to execute an influencer search."""
    query: str = Field(
        ...,
        min_length=3,
        max_length=5000,
        description="Natural language search query or brand brief"
    )
    filters: Optional[FilterConfig] = Field(
        default=None,
        description="Optional filter overrides"
    )
    ranking_weights: Optional[RankingWeights] = Field(
        default=None,
        description="Optional ranking weight overrides"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum number of results to return"
    )


class VerificationStats(BaseModel):
    """Statistics about the Primetag verification process."""
    total_candidates: int = Field(description="Total candidates discovered")
    verified: int = Field(description="Successfully verified via Primetag")
    failed_verification: int = Field(description="Failed to verify (not found or API error)")
    passed_filters: int = Field(description="Passed hard filters after verification")
    rejected_spain_pct: int = Field(default=0, description="Rejected for Spain audience < threshold")
    rejected_credibility: int = Field(default=0, description="Rejected for low credibility")
    rejected_engagement: int = Field(default=0, description="Rejected for low engagement")


class SearchResponse(BaseModel):
    """Response from an influencer search."""
    search_id: str
    query: str
    parsed_query: ParsedSearchQuery
    filters_applied: FilterConfig
    results: List[RankedInfluencer]
    total_candidates: int
    total_after_filter: int
    verification_stats: Optional[VerificationStats] = Field(
        default=None,
        description="Stats about the Primetag verification process"
    )
    executed_at: datetime = Field(default_factory=datetime.utcnow)


class SaveSearchRequest(BaseModel):
    """Request to save a search."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)


class SavedSearch(BaseModel):
    """A saved search record."""
    id: str
    name: str
    description: Optional[str] = None
    raw_query: str
    parsed_query: Dict[str, Any]
    result_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SearchHistoryItem(BaseModel):
    """Search history item."""
    id: str
    raw_query: str
    result_count: int
    is_saved: bool
    saved_name: Optional[str] = None
    executed_at: datetime

    class Config:
        from_attributes = True
