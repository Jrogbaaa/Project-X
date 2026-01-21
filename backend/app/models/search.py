from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class Search(Base):
    """Search history and saved searches."""

    __tablename__ = "searches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Search input
    raw_query = Column(Text, nullable=False)
    parsed_query = Column(JSONB, nullable=True)  # LLM-parsed structured query

    # Search parameters
    target_count = Column(Integer, nullable=True)
    gender_filter = Column(String(20), nullable=True)
    brand_context = Column(String(255), nullable=True)

    # Filter criteria used
    min_credibility_score = Column(Float, nullable=True)
    min_engagement_rate = Column(Float, nullable=True)
    min_spain_audience_pct = Column(Float, nullable=True)
    min_follower_growth_rate = Column(Float, nullable=True)

    # Ranking weights used
    ranking_weights = Column(JSONB, nullable=True)

    # Results
    result_count = Column(Integer, nullable=True)
    result_influencer_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)

    # Saved search metadata
    is_saved = Column(Boolean, default=False)
    saved_name = Column(String(255), nullable=True)
    saved_description = Column(Text, nullable=True)

    # User tracking (for future multi-user support)
    user_identifier = Column(String(255), nullable=True)

    # Timestamps
    executed_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    results = relationship("SearchResult", back_populates="search", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_searches_saved", "is_saved"),
        Index("idx_searches_user", "user_identifier"),
        Index("idx_searches_executed", "executed_at"),
    )


class SearchResult(Base):
    """Links searches to influencers with ranking data."""

    __tablename__ = "search_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_id = Column(UUID(as_uuid=True), ForeignKey("searches.id", ondelete="CASCADE"), nullable=False)
    influencer_id = Column(UUID(as_uuid=True), ForeignKey("influencers.id", ondelete="CASCADE"), nullable=False)

    # Ranking data at time of search
    rank_position = Column(Integer, nullable=False)
    relevance_score = Column(Float, nullable=True)

    # Individual score components (for transparency)
    credibility_score_normalized = Column(Float, nullable=True)
    engagement_score_normalized = Column(Float, nullable=True)
    audience_match_score = Column(Float, nullable=True)
    growth_score_normalized = Column(Float, nullable=True)
    geography_score = Column(Float, nullable=True)

    # Snapshot of key metrics at search time
    metrics_snapshot = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    search = relationship("Search", back_populates="results")
    influencer = relationship("Influencer")

    __table_args__ = (
        Index("idx_search_results_search", "search_id"),
        Index("idx_search_results_rank", "search_id", "rank_position"),
    )
