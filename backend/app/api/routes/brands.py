"""
Brand API Routes

Endpoints for managing and querying the Spanish brand knowledge base.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.services.brand_import_service import BrandImportService

router = APIRouter(prefix="/brands", tags=["Brands"])


# ==================== SCHEMAS ====================

class BrandResponse(BaseModel):
    """Brand API response schema."""
    id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    industry: Optional[str] = None
    headquarters: Optional[str] = None
    website: Optional[str] = None
    instagram_handle: Optional[str] = None
    source: Optional[str] = None
    source_rank: Optional[int] = None
    brand_value_eur: Optional[int] = None


class BrandCategoryCount(BaseModel):
    """Brand category with count."""
    category: str
    count: int


class BrandImportResponse(BaseModel):
    """Response from brand import operation."""
    created: int
    updated: int
    errors: int
    total_brands: int


class BrandSearchRequest(BaseModel):
    """Search request for brands."""
    query: str
    category: Optional[str] = None
    limit: int = 20


# ==================== ENDPOINTS ====================

@router.get("/", response_model=List[BrandResponse])
async def list_brands(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(100, le=1000, description="Maximum results"),
    db: AsyncSession = Depends(get_db)
):
    """
    List all brands in the knowledge base.
    
    Optionally filter by category.
    """
    service = BrandImportService(db)
    brands = await service.get_all_brands(category=category, limit=limit)
    return [BrandResponse(**b.to_dict()) for b in brands]


@router.get("/categories", response_model=List[BrandCategoryCount])
async def list_categories(
    db: AsyncSession = Depends(get_db)
):
    """
    Get all brand categories with counts.
    """
    service = BrandImportService(db)
    categories = await service.get_brand_categories()
    return [BrandCategoryCount(**c) for c in categories]


@router.get("/search", response_model=List[BrandResponse])
async def search_brands(
    q: str = Query(..., min_length=1, description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, le=100, description="Maximum results"),
    db: AsyncSession = Depends(get_db)
):
    """
    Search brands by name.
    
    Performs partial matching on normalized brand names.
    """
    service = BrandImportService(db)
    brands = await service.search_brands(query=q, category=category, limit=limit)
    return [BrandResponse(**b.to_dict()) for b in brands]


@router.get("/count")
async def get_brand_count(
    db: AsyncSession = Depends(get_db)
):
    """
    Get total count of brands in the database.
    """
    service = BrandImportService(db)
    count = await service.get_brand_count()
    return {"count": count}


@router.post("/import", response_model=BrandImportResponse)
async def import_brands(
    db: AsyncSession = Depends(get_db)
):
    """
    Import brands from all configured sources.
    
    This will:
    1. Collect brands from manual curated lists
    2. Attempt web scraping of IBEX 35
    3. Import all unique brands to database
    
    Existing brands will be updated, new brands will be created.
    """
    service = BrandImportService(db)
    
    # Run import
    stats = await service.import_from_scraper()
    
    # Get total count
    total = await service.get_brand_count()
    
    return BrandImportResponse(
        created=stats.get("created", 0),
        updated=stats.get("updated", 0),
        errors=stats.get("errors", 0),
        total_brands=total
    )


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(
    brand_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific brand by ID.
    """
    from sqlalchemy import select
    from app.models.brand import Brand
    import uuid
    
    try:
        brand_uuid = uuid.UUID(brand_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid brand ID format")
    
    stmt = select(Brand).where(Brand.id == brand_uuid)
    result = await db.execute(stmt)
    brand = result.scalar_one_or_none()
    
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    return BrandResponse(**brand.to_dict())
