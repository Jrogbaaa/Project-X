"""Brand model for Spanish brand knowledge base."""

from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
import unicodedata
import re

from app.core.database import Base


def normalize_brand_name(name: str) -> str:
    """
    Normalize brand name for deduplication.
    
    - Converts to lowercase
    - Removes accents/diacritics
    - Removes special characters except spaces
    - Collapses multiple spaces
    """
    if not name:
        return ""
    
    # Convert to lowercase
    normalized = name.lower()
    
    # Remove accents/diacritics (NFD decomposes, then we remove combining characters)
    normalized = unicodedata.normalize('NFD', normalized)
    normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    
    # Remove special characters except alphanumeric and spaces
    normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
    
    # Collapse multiple spaces and strip
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


class Brand(Base):
    """
    Spanish brand knowledge base entry.
    
    Stores basic brand information for context matching during influencer searches.
    """

    __tablename__ = "brands"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Core brand identity
    name = Column(String(255), nullable=False)
    name_normalized = Column(String(255), nullable=False)  # For deduplication
    description = Column(Text, nullable=True)

    # Classification
    category = Column(String(100), nullable=True)  # e.g., "fashion", "food_beverage", "banking"
    subcategory = Column(String(100), nullable=True)  # e.g., "fast_fashion", "beer", "retail_banking"
    industry = Column(String(100), nullable=True)  # Broader sector

    # Location
    headquarters = Column(String(100), nullable=True)  # City/region in Spain

    # Online presence
    website = Column(String(255), nullable=True)
    instagram_handle = Column(String(100), nullable=True)

    # Data provenance
    source = Column(String(100), nullable=True)  # e.g., "kantar_brandz", "ibex35", "manual"
    source_rank = Column(Integer, nullable=True)  # Ranking in source list if applicable

    # Value metrics
    brand_value_eur = Column(BigInteger, nullable=True)  # Brand value in euros if available

    # Status
    is_active = Column(Boolean, default=True)

    # Flexible storage for additional data
    extra_data = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_brands_name_normalized", "name_normalized", unique=True),
        Index("idx_brands_category", "category"),
        Index("idx_brands_industry", "industry"),
        Index("idx_brands_source", "source"),
        Index("idx_brands_extra_data", "extra_data", postgresql_using="gin"),
    )

    def __init__(self, **kwargs):
        """Initialize brand with auto-normalized name."""
        if 'name' in kwargs and 'name_normalized' not in kwargs:
            kwargs['name_normalized'] = normalize_brand_name(kwargs['name'])
        super().__init__(**kwargs)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "name": self.name,
            "name_normalized": self.name_normalized,
            "description": self.description,
            "category": self.category,
            "subcategory": self.subcategory,
            "industry": self.industry,
            "headquarters": self.headquarters,
            "website": self.website,
            "instagram_handle": self.instagram_handle,
            "source": self.source,
            "source_rank": self.source_rank,
            "brand_value_eur": self.brand_value_eur,
            "is_active": self.is_active,
            "extra_data": self.extra_data or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_summary(self) -> dict:
        """Return a brief summary for search context."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
        }

    def __repr__(self) -> str:
        return f"<Brand(name='{self.name}', category='{self.category}')>"
