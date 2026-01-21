from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class MediaKitSummary(BaseModel):
    """Summary from PrimeTag search endpoint."""
    external_social_profile_id: Optional[str] = None
    username: str
    display_name: Optional[str] = None
    avatar: Optional[str] = None
    audience_size: int = 0
    is_verified: Optional[bool] = None
    platform_type: int = 1
    mediakit_url: Optional[str] = None


class MediaKitSearchResponse(BaseModel):
    """Response from GET /media-kits search."""
    response: List[MediaKitSummary]
    metadata: Optional[Dict[str, Any]] = None


class AudienceDataSection(BaseModel):
    """Audience data from media kit detail."""
    audience_credibility_percentage: Optional[float] = None
    audience_credibility_label: Optional[str] = None
    audience_credibility_emoji: Optional[str] = None
    audience_reachability: Optional[List[Any]] = None
    follow_for_follow: Optional[Dict[str, Any]] = None
    genders: Optional[Dict[str, float]] = None
    average_age: Optional[List[Any]] = None
    location_by_country: Optional[List[Any]] = None
    location_by_city: Optional[List[Any]] = None


class AudienceData(BaseModel):
    """Container for followers/likes audience data."""
    followers: Optional[AudienceDataSection] = None
    likes: Optional[AudienceDataSection] = None


class EngagementsInfo(BaseModel):
    """Engagement information section."""
    engagement_rate_consistency_percentage: Optional[float] = None
    engagement_rate_consistency_label: Optional[str] = None
    engagement_rate_consistency_emoji: Optional[str] = None
    likes_evolution: Optional[Dict[str, Any]] = None
    engagement_spread_last_posts: Optional[List[Any]] = None
    engagement_spread_last_posts_formatted: Optional[Dict[str, Any]] = None
    engagement_rate_in_comparison_with_others: Optional[Dict[str, Any]] = None


class Post(BaseModel):
    """Post data."""
    type: str = ""
    thumbnail: Optional[str] = None
    link: Optional[str] = None


class BrandMention(BaseModel):
    """Brand mention data."""
    user_id: str = ""
    username: str = ""
    thumbnail: Optional[str] = None


class FollowerEvolution(BaseModel):
    """Follower evolution data point."""
    month: str = ""
    followers: int = 0
    year: int = 0
    month_str: str = ""
    month_int: int = 0
    date: Optional[str] = None


class MediaKit(BaseModel):
    """Full media kit data from PrimeTag."""
    platform_type: int = 1
    profile_pic: Optional[str] = None
    cover_photo: Optional[str] = None
    profile_url: Optional[str] = None
    fullname: str = ""
    is_verified: bool = False
    username: str
    is_official_api_connected: bool = False
    description: Optional[str] = None
    interests: Optional[List[str]] = None
    location: str = ""
    contacts: Optional[List[str]] = None

    # Followers & growth
    followers: int = 0
    followers_evolution: List[FollowerEvolution] = Field(default_factory=list)
    followers_last_month_evolution: float = 0.0
    followers_last_6_month_evolution: float = 0.0

    # Engagement metrics
    avg_likes: int = 0
    avg_comments: int = 0
    avg_views: Optional[int] = None
    avg_reels_plays: Optional[int] = None
    avg_shares: Optional[int] = None
    avg_saves: Optional[int] = None
    avg_reach: Optional[float] = None
    avg_engagements: int = 0
    avg_engagement_rate: float = 0.0

    # Content
    top_posts: List[Post] = Field(default_factory=list)

    # Paid content metrics
    paid_avg_likes: Optional[int] = None
    paid_avg_comments: Optional[int] = None
    paid_avg_engagements: Optional[int] = None
    paid_avg_reels_plays: Optional[int] = None
    paid_avg_engagement_rate: Optional[float] = None
    paid_followers: Optional[int] = None
    paid_evolution_last_month: Optional[float] = None

    # Brand mentions & paid posts
    brand_mentions: List[BrandMention] = Field(default_factory=list)
    paid_posts: List[Post] = Field(default_factory=list)

    # Audience data
    audience_data: Optional[AudienceData] = None
    engagements_info: Optional[EngagementsInfo] = None


class MediaKitDetailResponse(BaseModel):
    """Response from GET /media-kits/{platform}/{username} detail endpoint."""
    response: MediaKit
    metadata: Optional[Dict[str, Any]] = None
