"""
Brand Import Service

Handles importing brand data into the PostgreSQL database.
Features:
- Normalization of brand names (lowercase, no accents, etc.)
- Deduplication using normalized names
- Upsert logic (update existing, insert new)
- Batch import support
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert

from app.models.brand import Brand, normalize_brand_name
from app.services.brand_scraper_service import ScrapedBrand, get_brand_scraper_service

logger = logging.getLogger(__name__)


class BrandImportService:
    """
    Service for importing and managing brand data in the database.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def import_brand(self, scraped: ScrapedBrand) -> Tuple[Brand, bool]:
        """
        Import a single brand into the database.
        
        Args:
            scraped: ScrapedBrand object with brand data
        
        Returns:
            Tuple of (Brand object, was_created boolean)
        """
        normalized_name = normalize_brand_name(scraped.name)
        
        # Check if brand exists
        stmt = select(Brand).where(Brand.name_normalized == normalized_name)
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing brand with new data (merge strategy)
            was_created = False
            
            # Only update fields that are not None in scraped data
            if scraped.description:
                existing.description = scraped.description
            if scraped.category:
                existing.category = scraped.category
            if scraped.subcategory:
                existing.subcategory = scraped.subcategory
            if scraped.industry:
                existing.industry = scraped.industry
            if scraped.headquarters:
                existing.headquarters = scraped.headquarters
            if scraped.website:
                existing.website = scraped.website
            if scraped.instagram_handle:
                existing.instagram_handle = scraped.instagram_handle
            if scraped.brand_value_eur:
                existing.brand_value_eur = scraped.brand_value_eur
            
            # Merge extra_data
            if scraped.metadata:
                existing_meta = existing.extra_data or {}
                existing_meta.update(scraped.metadata)
                existing.extra_data = existing_meta
            
            existing.updated_at = datetime.now(timezone.utc)
            brand = existing
            
        else:
            # Create new brand
            was_created = True
            brand = Brand(
                name=scraped.name,
                name_normalized=normalized_name,
                description=scraped.description,
                category=scraped.category,
                subcategory=scraped.subcategory,
                industry=scraped.industry,
                headquarters=scraped.headquarters,
                website=scraped.website,
                instagram_handle=scraped.instagram_handle,
                source=scraped.source,
                source_rank=scraped.source_rank,
                brand_value_eur=scraped.brand_value_eur,
                extra_data=scraped.metadata or {},
            )
            self.db.add(brand)
        
        await self.db.flush()
        return brand, was_created

    async def import_brands_batch(
        self,
        brands: List[ScrapedBrand],
        commit: bool = True
    ) -> Dict[str, int]:
        """
        Import multiple brands in a batch.
        
        Args:
            brands: List of ScrapedBrand objects
            commit: Whether to commit the transaction
        
        Returns:
            Dict with counts: {"created": n, "updated": n, "errors": n}
        """
        stats = {"created": 0, "updated": 0, "errors": 0}
        
        for scraped in brands:
            try:
                _, was_created = await self.import_brand(scraped)
                if was_created:
                    stats["created"] += 1
                else:
                    stats["updated"] += 1
            except Exception as e:
                logger.error(f"Error importing brand '{scraped.name}': {e}")
                stats["errors"] += 1
        
        if commit:
            await self.db.commit()
        
        logger.info(
            f"Brand import complete: {stats['created']} created, "
            f"{stats['updated']} updated, {stats['errors']} errors"
        )
        return stats

    async def upsert_brands_bulk(self, brands: List[ScrapedBrand]) -> Dict[str, int]:
        """
        Bulk upsert brands using PostgreSQL ON CONFLICT.
        More efficient for large imports.
        
        Args:
            brands: List of ScrapedBrand objects
        
        Returns:
            Dict with counts
        """
        if not brands:
            return {"created": 0, "updated": 0, "errors": 0}
        
        # Prepare data for bulk insert
        values = []
        for scraped in brands:
            normalized = normalize_brand_name(scraped.name)
            values.append({
                "name": scraped.name,
                "name_normalized": normalized,
                "description": scraped.description,
                "category": scraped.category,
                "subcategory": scraped.subcategory,
                "industry": scraped.industry,
                "headquarters": scraped.headquarters,
                "website": scraped.website,
                "instagram_handle": scraped.instagram_handle,
                "source": scraped.source,
                "source_rank": scraped.source_rank,
                "brand_value_eur": scraped.brand_value_eur,
                "extra_data": scraped.metadata or {},
            })
        
        # PostgreSQL upsert with ON CONFLICT
        stmt = insert(Brand).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["name_normalized"],
            set_={
                "description": stmt.excluded.description,
                "category": stmt.excluded.category,
                "subcategory": stmt.excluded.subcategory,
                "industry": stmt.excluded.industry,
                "headquarters": stmt.excluded.headquarters,
                "website": stmt.excluded.website,
                "instagram_handle": stmt.excluded.instagram_handle,
                "source": stmt.excluded.source,
                "source_rank": stmt.excluded.source_rank,
                "brand_value_eur": stmt.excluded.brand_value_eur,
                "extra_data": stmt.excluded.extra_data,
                "updated_at": func.now(),
            }
        )
        
        try:
            await self.db.execute(stmt)
            await self.db.commit()
            logger.info(f"Bulk upserted {len(brands)} brands")
            return {"processed": len(brands), "errors": 0}
        except Exception as e:
            logger.error(f"Bulk upsert failed: {e}")
            await self.db.rollback()
            return {"processed": 0, "errors": len(brands)}

    async def get_brand_count(self) -> int:
        """Get total count of brands in database."""
        stmt = select(func.count(Brand.id))
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def get_brands_by_category(self, category: str) -> List[Brand]:
        """Get all brands in a category."""
        stmt = select(Brand).where(Brand.category == category).order_by(Brand.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_brands(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20
    ) -> List[Brand]:
        """
        Search brands by name.
        
        Args:
            query: Search query (partial name match)
            category: Optional category filter
            limit: Maximum results
        
        Returns:
            List of matching Brand objects
        """
        normalized_query = normalize_brand_name(query)
        
        stmt = select(Brand).where(
            Brand.name_normalized.ilike(f"%{normalized_query}%")
        )
        
        if category:
            stmt = stmt.where(Brand.category == category)
        
        stmt = stmt.limit(limit).order_by(Brand.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_all_brands(
        self,
        category: Optional[str] = None,
        limit: int = 1000
    ) -> List[Brand]:
        """
        Get all brands, optionally filtered by category.
        
        Args:
            category: Optional category filter
            limit: Maximum results
        
        Returns:
            List of Brand objects
        """
        stmt = select(Brand).where(Brand.is_active == True)
        
        if category:
            stmt = stmt.where(Brand.category == category)
        
        stmt = stmt.limit(limit).order_by(Brand.source_rank.nulls_last(), Brand.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_brand_categories(self) -> List[Dict[str, Any]]:
        """
        Get all categories with brand counts.
        
        Returns:
            List of dicts: [{"category": "fashion", "count": 50}, ...]
        """
        stmt = (
            select(Brand.category, func.count(Brand.id).label("count"))
            .where(Brand.is_active == True)
            .group_by(Brand.category)
            .order_by(func.count(Brand.id).desc())
        )
        result = await self.db.execute(stmt)
        return [{"category": row[0], "count": row[1]} for row in result.all()]

    async def import_from_scraper(self) -> Dict[str, int]:
        """
        Import brands from the scraper service.
        Collects from all available sources and imports to database.
        
        Returns:
            Import statistics
        """
        scraper = get_brand_scraper_service()
        
        try:
            # Collect all brands
            brands = await scraper.collect_all_brands()
            logger.info(f"Collected {len(brands)} brands from scraper")
            
            # Import to database
            stats = await self.import_brands_batch(brands)
            return stats
            
        finally:
            await scraper.close()


async def import_brands_to_db(db: AsyncSession) -> Dict[str, int]:
    """
    Convenience function to import all brands to database.
    
    Usage:
        async with get_db() as db:
            stats = await import_brands_to_db(db)
    """
    service = BrandImportService(db)
    return await service.import_from_scraper()
