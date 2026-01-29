from sqlalchemy import Column, String, Integer, BigInteger, Float, Boolean, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class Influencer(Base):
    """Cached influencer data from PrimeTag.
    
    Stores discovery data (interests, brand_mentions, country) for matching briefs,
    plus cached PrimeTag metrics for verification and display.
    """

    __tablename__ = "influencers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # PrimeTag identifiers
    platform_type = Column(String(20), nullable=False, default="instagram")
    username = Column(String(100), nullable=False)
    external_social_profile_id = Column(String(100), nullable=True)  # PrimeTag's external ID
    primetag_encrypted_username = Column(Text, nullable=True)  # Encrypted username for direct API calls

    # Basic profile info (cached from PrimeTag)
    display_name = Column(String(255), nullable=True)
    profile_picture_url = Column(Text, nullable=True)
    bio = Column(Text, nullable=True)
    is_verified = Column(Boolean, default=False)

    # Core metrics (cached from PrimeTag)
    follower_count = Column(BigInteger, nullable=True)

    # Quality metrics (cached from PrimeTag) - used for verification
    credibility_score = Column(Float, nullable=True)  # audience_credibility_percentage
    engagement_rate = Column(Float, nullable=True)  # avg_engagement_rate (as decimal, e.g., 0.0345)
    follower_growth_rate_6m = Column(Float, nullable=True)  # followers_last_6_month_evolution

    # Engagement stats (cached from PrimeTag)
    avg_likes = Column(Integer, nullable=True)
    avg_comments = Column(Integer, nullable=True)
    avg_views = Column(Integer, nullable=True)

    # Audience demographics (cached from PrimeTag) - used for verification
    audience_genders = Column(JSONB, nullable=True)  # {"male": 45.2, "female": 54.8}
    audience_age_distribution = Column(JSONB, nullable=True)  # {"13-17": 5, "18-24": 30, ...}
    audience_geography = Column(JSONB, nullable=True)  # {"ES": 65, "MX": 10, ...}
    female_audience_age_distribution = Column(JSONB, nullable=True)

    # Discovery data (for matching briefs to influencers)
    interests = Column(JSONB, nullable=True)  # ["Sports", "Soccer", "Tennis"]
    brand_mentions = Column(JSONB, nullable=True)  # ["nike", "adidas"]
    country = Column(String(100), nullable=True)  # "Spain"

    # Post content aggregated (from Apify scraping)
    # Structure: {"top_hashtags": {...}, "caption_keywords": {...}, "scrape_status": "complete"}
    post_content_aggregated = Column(JSONB, nullable=True)

    # Niche detection (from Apify scrape analysis)
    primary_niche = Column(String(50), nullable=True)  # "padel", "football", "fitness"
    niche_confidence = Column(Float, nullable=True)  # 0.0-1.0 confidence score
    detected_brands = Column(JSONB, nullable=True)  # ["bullpadel", "nike", "adidas"]
    sponsored_ratio = Column(Float, nullable=True)  # 0.0-1.0 (% of sponsored posts)
    content_language = Column(String(10), nullable=True)  # "es", "en", "ca"

    # Content themes for creative matching (from Apify scrape analysis)
    # Structure: {"detected_themes": [...], "narrative_style": "...", "format_preference": [...], "avg_caption_length": N}
    content_themes = Column(JSONB, nullable=True)

    # Relationship to posts
    posts = relationship("InfluencerPost", back_populates="influencer", cascade="all, delete-orphan")

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
        Index("idx_influencers_country", "country"),
        Index("idx_influencers_interests", "interests", postgresql_using="gin"),
        Index("idx_influencers_brand_mentions", "brand_mentions", postgresql_using="gin"),
        # Niche detection indexes
        Index("idx_influencers_primary_niche", "primary_niche"),
        Index("idx_influencers_niche_confidence", "niche_confidence"),
        Index("idx_influencers_detected_brands", "detected_brands", postgresql_using="gin"),
        Index("idx_influencers_content_language", "content_language"),
        Index("idx_influencers_content_themes", "content_themes", postgresql_using="gin"),
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
            "is_verified": self.is_verified,
            "follower_count": self.follower_count,
            "credibility_score": self.credibility_score,
            "engagement_rate": self.engagement_rate,
            "follower_growth_rate_6m": self.follower_growth_rate_6m,
            "avg_likes": self.avg_likes,
            "avg_comments": self.avg_comments,
            "avg_views": self.avg_views,
            "audience_genders": self.audience_genders or {},
            "audience_age_distribution": self.audience_age_distribution or {},
            "audience_geography": self.audience_geography or {},
            "interests": self.interests or [],
            "brand_mentions": self.brand_mentions or [],
            "country": self.country,
            "post_content_aggregated": self.post_content_aggregated,
            # Niche detection fields
            "primary_niche": self.primary_niche,
            "niche_confidence": self.niche_confidence,
            "detected_brands": self.detected_brands or [],
            "sponsored_ratio": self.sponsored_ratio,
            "content_language": self.content_language,
            "content_themes": self.content_themes,
            "cached_at": self.cached_at.isoformat() if self.cached_at else None,
        }
