from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class InfluencerPost(Base):
    """Scraped Instagram post content from Apify.

    Stores post captions, hashtags, and mentions for enhanced niche detection.
    Each post belongs to an influencer and contains content analysis data.
    """

    __tablename__ = "influencer_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    influencer_id = Column(
        UUID(as_uuid=True),
        ForeignKey('influencers.id', ondelete='CASCADE'),
        nullable=False
    )

    # Post identifiers
    instagram_post_id = Column(String(100), nullable=False)
    shortcode = Column(String(50), nullable=True)
    post_url = Column(Text, nullable=True)

    # Content
    caption = Column(Text, nullable=True)
    hashtags = Column(JSONB, nullable=True)  # ["padel", "fitness", "worldpadeltour"]
    mentions = Column(JSONB, nullable=True)  # ["nike", "bullpadel"]

    # Post metadata
    post_type = Column(String(20), nullable=True)  # Image, Video, Sidecar, Reel
    posted_at = Column(DateTime(timezone=True), nullable=True)

    # Engagement metrics
    likes_count = Column(Integer, nullable=True)
    comments_count = Column(Integer, nullable=True)
    views_count = Column(Integer, nullable=True)

    # Media
    thumbnail_url = Column(Text, nullable=True)
    is_sponsored = Column(Boolean, default=False)

    # Apify metadata
    apify_scraped_at = Column(DateTime(timezone=True), nullable=True)
    apify_run_id = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship back to influencer
    influencer = relationship("Influencer", back_populates="posts")

    __table_args__ = (
        UniqueConstraint('influencer_id', 'instagram_post_id', name='uq_influencer_post'),
        Index('idx_posts_influencer', 'influencer_id'),
        Index('idx_posts_posted_at', 'posted_at'),
        Index('idx_posts_hashtags', 'hashtags', postgresql_using='gin'),
        Index('idx_posts_mentions', 'mentions', postgresql_using='gin'),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "influencer_id": str(self.influencer_id),
            "instagram_post_id": self.instagram_post_id,
            "shortcode": self.shortcode,
            "post_url": self.post_url,
            "caption": self.caption,
            "hashtags": self.hashtags or [],
            "mentions": self.mentions or [],
            "post_type": self.post_type,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "likes_count": self.likes_count,
            "comments_count": self.comments_count,
            "views_count": self.views_count,
            "is_sponsored": self.is_sponsored,
            "apify_scraped_at": self.apify_scraped_at.isoformat() if self.apify_scraped_at else None,
        }
