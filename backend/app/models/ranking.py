from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class RankingPreset(Base):
    """Configurable ranking weight presets for 8-factor scoring."""

    __tablename__ = "ranking_presets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    # Weight configuration (8 factors)
    credibility_weight = Column(Float, default=0.15)
    engagement_weight = Column(Float, default=0.20)
    audience_match_weight = Column(Float, default=0.15)
    growth_weight = Column(Float, default=0.10)
    geography_weight = Column(Float, default=0.10)
    brand_affinity_weight = Column(Float, default=0.10)
    creative_fit_weight = Column(Float, default=0.10)
    niche_match_weight = Column(Float, default=0.10)

    # Metadata
    is_default = Column(Boolean, default=False)
    is_system = Column(Boolean, default=False)  # System presets cannot be deleted

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "credibility_weight + engagement_weight + audience_match_weight + growth_weight + "
            "geography_weight + brand_affinity_weight + creative_fit_weight + niche_match_weight "
            "BETWEEN 0.99 AND 1.01",
            name="weights_sum_check"
        ),
    )
