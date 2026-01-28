#!/usr/bin/env python3
"""
Script to import Spanish brands into the database.

Usage:
    cd backend && source ../venv/bin/activate
    python scripts/import_brands.py
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db, init_db
from app.services.brand_import_service import BrandImportService


async def main():
    """Run the brand import."""
    print("=" * 60)
    print("Spanish Brand Knowledge Base Import")
    print("=" * 60)
    
    # Initialize database
    print("\n1. Initializing database connection...")
    await init_db()
    
    # Get database session
    async for db in get_db():
        service = BrandImportService(db)
        
        # Get current count
        current_count = await service.get_brand_count()
        print(f"\n2. Current brand count: {current_count}")
        
        # Run import
        print("\n3. Importing brands from all sources...")
        stats = await service.import_from_scraper()
        
        print(f"\n4. Import complete!")
        print(f"   - Created: {stats.get('created', 0)}")
        print(f"   - Updated: {stats.get('updated', 0)}")
        print(f"   - Errors: {stats.get('errors', 0)}")
        
        # Get new count
        new_count = await service.get_brand_count()
        print(f"\n5. Total brands in database: {new_count}")
        
        # Show categories
        print("\n6. Brands by category:")
        categories = await service.get_brand_categories()
        for cat in categories:
            print(f"   - {cat['category'] or 'uncategorized'}: {cat['count']}")
        
        break
    
    print("\n" + "=" * 60)
    print("Import finished!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
