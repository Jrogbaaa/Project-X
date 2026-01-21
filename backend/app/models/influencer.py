from sqlalchemy import Column, String, Integer, BigInteger, Float, Boolean, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class Influencer(Base):
    """Cached influencer data from PrimeTag."""

    __tablename__ = "influencers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # PrimeTag identifiers
    platform_type = Column(String(20), nullable=False, default="instagram")
    username = Column(String(100), nullable=False)
    username_encrypted = Column(String(255), nullable=True)

    # Basic profile info
    display_name = Column(String(255), nullable=True)
    profile_picture_url = Column(Text, nullable=True)
    bio = Column(Text, nullable=True)
    profile_url = Column(Text, nullable=True)
    is_verified = Column(Boolean, default=False)

    # Core metrics
    follower_count = Column(BigInteger, nullable=True)
    following_count = Column(Integer, nullable=True)
    post_count = Column(Integer, nullable=True)

    # Quality metrics
    credibility_score = Column(Float, nullable=True)  # audience_credibility_percentage
    engagement_rate = Column(Float, nullable=True)  # avg_engagement_rate (as decimal, e.g., 0.0345)
    follower_growth_rate_6m = Column(Float, nullable=True)  # followers_last_6_month_evolution

    # Engagement stats
    avg_likes = Column(Integer, nullable=True)
    avg_comments = Column(Integer, nullable=True)
    avg_views = Column(Integer, nullable=True)

    # Audience demographics (stored as JSONB for flexibility)
    audience_genders = Column(JSONB, nullable=True)  # {"male": 45.2, "female": 54.8}
    audience_age_distribution = Column(JSONB, nullable=True)  # {"13-17": 5, "18-24": 30, ...}
    audience_geography = Column(JSONB, nullable=True)  # {"ES": 65, "MX": 10, ...}
    female_audience_age_distribution = Column(JSONB, nullable=True)

    # Full API response for debugging
    primetag_raw_response = Column(JSONB, nullable=True)

    # Cache metadata
    cached_at = Column(DateTime(timezone=True), server_default=func.now())
    cache_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_influencers_platform_username", "platform_type", "username", unique=True),
        Index("idx_influencers_credibility", "credibility_score"),
        Index("idx_influencers_engagement", "engagement_rate"),
        Index("idx_influencers_growth", "follower_growth_rate_6m"),
        Index("idx_influencers_cache_expiry", "cache_expires_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "platform_type": self.platform_type,
            "username": self.username,
            "display_name": self.display_name,
            "profile_picture_url": self.profile_picture_url,
            "bio": self.bio,
            "profile_url": self.profile_url,
            "is_verified": self.is_verified,
            "follower_count": self.follower_count,
            "following_count": self.following_count,
            "post_count": self.post_count,
            "credibility_score": self.credibility_score,
            "engagement_rate": self.engagement_rate,
            "follower_growth_rate_6m": self.follower_growth_rate_6m,
            "avg_likes": self.avg_likes,
            "avg_comments": self.avg_comments,
            "avg_views": self.avg_views,
            "audience_genders": self.audience_genders or {},
            "audience_age_distribution": self.audience_age_distribution or {},
            "audience_geography": self.audience_geography or {},
            "cached_at": self.cached_at.isoformat() if self.cached_at else None,
        }
