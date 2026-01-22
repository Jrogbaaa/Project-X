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


class RankingWeights(BaseModel):
    """Configurable ranking weights for influencer scoring.

    When brand/creative info is provided, all 8 factors are used.
    When not provided, brand_affinity, creative_fit, niche_match default to neutral (0.5)
    and their weights are effectively redistributed.
    """
    # Original factors
    credibility: float = Field(default=0.15, ge=0, le=1)
    engagement: float = Field(default=0.20, ge=0, le=1)
    audience_match: float = Field(default=0.15, ge=0, le=1)
    growth: float = Field(default=0.05, ge=0, le=1)
    geography: float = Field(default=0.10, ge=0, le=1)

    # New brand/creative matching factors
    brand_affinity: float = Field(
        default=0.15,
        ge=0,
        le=1,
        description="Weight for audience overlap with target brand"
    )
    creative_fit: float = Field(
        default=0.15,
        ge=0,
        le=1,
        description="Weight for alignment with creative concept"
    )
    niche_match: float = Field(
        default=0.05,
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
        max_length=500,
        description="Natural language search query"
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
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results to return"
    )


class SearchResponse(BaseModel):
    """Response from an influencer search."""
    search_id: str
    query: str
    parsed_query: ParsedSearchQuery
    filters_applied: FilterConfig
    results: List[RankedInfluencer]
    total_candidates: int
    total_after_filter: int
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
