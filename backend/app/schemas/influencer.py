from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class AudienceGenders(BaseModel):
    """Audience gender distribution."""
    male: float = 0.0
    female: float = 0.0


class AudienceGeography(BaseModel):
    """Audience geography distribution."""
    ES: float = Field(default=0.0, description="Spain percentage")
    # Additional countries stored dynamically


class ScoreComponents(BaseModel):
    """Individual score components for ranking transparency."""
    # Original 5 factors
    credibility: float = Field(ge=0, le=1)
    engagement: float = Field(ge=0, le=1)
    audience_match: float = Field(ge=0, le=1)
    growth: float = Field(ge=0, le=1)
    geography: float = Field(ge=0, le=1)

    # New brand/creative matching factors
    brand_affinity: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Audience overlap with target brand (0.5 = neutral/no brand specified)"
    )
    creative_fit: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Alignment with campaign creative concept (0.5 = neutral/no concept specified)"
    )
    niche_match: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Content niche alignment with campaign topics (0.5 = neutral)"
    )


class InfluencerData(BaseModel):
    """Complete influencer data from PrimeTag."""
    id: Optional[str] = None
    username: str
    display_name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    bio: Optional[str] = None
    profile_url: Optional[str] = None
    is_verified: bool = False

    # Metrics
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0

    # Quality metrics
    credibility_score: Optional[float] = None
    engagement_rate: Optional[float] = None
    follower_growth_rate_6m: Optional[float] = None

    # Engagement stats
    avg_likes: int = 0
    avg_comments: int = 0
    avg_views: Optional[int] = None

    # Audience demographics
    audience_genders: Dict[str, float] = Field(default_factory=dict)
    audience_age_distribution: Dict[str, float] = Field(default_factory=dict)
    audience_geography: Dict[str, float] = Field(default_factory=dict)
    female_audience_age_distribution: Optional[Dict[str, float]] = None

    # Content/niche data (for creative matching)
    interests: List[str] = Field(
        default_factory=list,
        description="Influencer's stated interests/categories"
    )
    brand_mentions: List[str] = Field(
        default_factory=list,
        description="Brands the influencer has mentioned/partnered with"
    )

    # Metadata
    platform_type: str = "instagram"
    username_encrypted: Optional[str] = None
    cached_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RankedInfluencer(BaseModel):
    """Influencer with ranking information."""
    influencer_id: str
    username: str
    rank_position: int
    relevance_score: float = Field(ge=0, le=1)
    scores: ScoreComponents
    raw_data: InfluencerData

    class Config:
        from_attributes = True


class InfluencerSummary(BaseModel):
    """Brief influencer summary for search results."""
    external_social_profile_id: Optional[str] = None
    username: str
    display_name: Optional[str] = None
    avatar: Optional[str] = None
    audience_size: int = 0
    is_verified: Optional[bool] = None
    platform_type: int = 1
    mediakit_url: Optional[str] = None
