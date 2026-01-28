"""
Brand Context Service

Provides brand context during search operations to enhance matching.
Uses the brand database to:
1. Recognize brands mentioned in queries
2. Provide category/industry context
3. Suggest relevant search keywords
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.brand import Brand, normalize_brand_name

logger = logging.getLogger(__name__)


@dataclass
class BrandContext:
    """Context about a brand extracted from the database."""
    name: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    industry: Optional[str] = None
    headquarters: Optional[str] = None
    description: Optional[str] = None
    source_rank: Optional[int] = None
    related_brands: List[str] = field(default_factory=list)
    suggested_keywords: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "subcategory": self.subcategory,
            "industry": self.industry,
            "headquarters": self.headquarters,
            "description": self.description,
            "source_rank": self.source_rank,
            "related_brands": self.related_brands,
            "suggested_keywords": self.suggested_keywords,
        }


class BrandContextService:
    """
    Service for providing brand context during search operations.
    """

    # Category to keywords mapping for search enhancement
    CATEGORY_KEYWORDS = {
        "fashion": ["moda", "style", "outfit", "fashion", "ropa", "estilo"],
        "food_beverage": ["comida", "food", "recetas", "cocina", "gastronomia", "foodie"],
        "sports": ["deporte", "sports", "fitness", "entrenar", "athlete"],
        "beauty": ["belleza", "beauty", "makeup", "skincare", "cosmetics"],
        "travel": ["viajes", "travel", "turismo", "vacation", "wanderlust"],
        "technology": ["tech", "tecnologia", "gadgets", "digital", "innovation"],
        "automotive": ["coches", "cars", "auto", "motor", "driving"],
        "retail": ["shopping", "compras", "tienda", "store"],
        "banking": ["finanzas", "finance", "ahorro", "inversión"],
        "telecom": ["movil", "mobile", "telefono", "internet"],
        "healthcare": ["salud", "health", "bienestar", "wellness"],
        "entertainment": ["entretenimiento", "entertainment", "cine", "musica"],
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_brand_context(self, brand_name: str) -> Optional[BrandContext]:
        """
        Find brand in database and return context.
        
        Args:
            brand_name: Brand name from search query
            
        Returns:
            BrandContext if found, None otherwise
        """
        if not brand_name:
            return None
            
        normalized = normalize_brand_name(brand_name)
        
        # Search by exact normalized match
        stmt = select(Brand).where(Brand.name_normalized == normalized)
        result = await self.db.execute(stmt)
        brand = result.scalar_one_or_none()
        
        # If not found, try partial match
        if not brand:
            stmt = select(Brand).where(
                Brand.name_normalized.ilike(f"%{normalized}%")
            ).limit(1)
            result = await self.db.execute(stmt)
            brand = result.scalar_one_or_none()
        
        if not brand:
            logger.debug(f"Brand not found in database: {brand_name}")
            return None
        
        # Build context
        context = BrandContext(
            name=brand.name,
            category=brand.category,
            subcategory=brand.subcategory,
            industry=brand.industry,
            headquarters=brand.headquarters,
            description=brand.description,
            source_rank=brand.source_rank,
        )
        
        # Add suggested keywords based on category
        if brand.category and brand.category in self.CATEGORY_KEYWORDS:
            context.suggested_keywords = self.CATEGORY_KEYWORDS[brand.category].copy()
        
        # Add subcategory as keyword if available
        if brand.subcategory:
            context.suggested_keywords.append(brand.subcategory.replace("_", " "))
        
        # Find related brands in same category
        if brand.category:
            context.related_brands = await self._find_related_brands(
                category=brand.category,
                exclude_name=brand.name_normalized,
                limit=5
            )
        
        logger.info(f"Found brand context: {brand.name} ({brand.category})")
        return context

    async def _find_related_brands(
        self,
        category: str,
        exclude_name: str,
        limit: int = 5
    ) -> List[str]:
        """Find related brands in the same category."""
        stmt = (
            select(Brand.name)
            .where(Brand.category == category)
            .where(Brand.name_normalized != exclude_name)
            .where(Brand.is_active == True)
            .order_by(Brand.source_rank.nulls_last())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def search_brands_by_category(
        self,
        category: str,
        limit: int = 20
    ) -> List[Brand]:
        """Get all brands in a category."""
        stmt = (
            select(Brand)
            .where(Brand.category == category)
            .where(Brand.is_active == True)
            .order_by(Brand.source_rank.nulls_last(), Brand.name)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_category_summary(self) -> Dict[str, int]:
        """Get brand count by category."""
        from sqlalchemy import func
        
        stmt = (
            select(Brand.category, func.count(Brand.id))
            .where(Brand.is_active == True)
            .group_by(Brand.category)
            .order_by(func.count(Brand.id).desc())
        )
        result = await self.db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def enrich_search_keywords(
        self,
        brand_name: Optional[str],
        existing_keywords: List[str]
    ) -> List[str]:
        """
        Enrich search keywords with brand context.
        
        If a brand is mentioned, add relevant keywords based on:
        - Brand category
        - Brand subcategory  
        - Related terms
        
        Returns enriched keyword list (deduplicated).
        """
        enriched = list(existing_keywords)
        
        if brand_name:
            context = await self.find_brand_context(brand_name)
            if context and context.suggested_keywords:
                for kw in context.suggested_keywords:
                    if kw.lower() not in [k.lower() for k in enriched]:
                        enriched.append(kw)
        
        return enriched[:10]  # Limit to 10 keywords

    async def get_brands_for_llm_context(
        self,
        categories: Optional[List[str]] = None,
        limit_per_category: int = 5
    ) -> str:
        """
        Generate brand list text for LLM context/system prompt.
        
        Useful for helping the LLM recognize Spanish brands.
        """
        from sqlalchemy import func
        
        if categories is None:
            # Get top categories
            stmt = (
                select(Brand.category)
                .where(Brand.is_active == True)
                .where(Brand.category.isnot(None))
                .group_by(Brand.category)
                .order_by(func.count(Brand.id).desc())
                .limit(10)
            )
            result = await self.db.execute(stmt)
            categories = [row[0] for row in result.all()]
        
        lines = ["## Spanish Brands Reference\n"]
        
        for category in categories:
            brands = await self.search_brands_by_category(category, limit_per_category)
            if brands:
                brand_names = ", ".join(b.name for b in brands)
                lines.append(f"- **{category}**: {brand_names}")
        
        return "\n".join(lines)


async def get_brand_context_for_search(
    db: AsyncSession,
    brand_name: Optional[str]
) -> Optional[BrandContext]:
    """
    Convenience function to get brand context for a search.
    
    Usage:
        brand_context = await get_brand_context_for_search(db, "Zara")
        if brand_context:
            # Use brand_context.category, brand_context.suggested_keywords, etc.
    """
    if not brand_name:
        return None
    
    service = BrandContextService(db)
    return await service.find_brand_context(brand_name)
