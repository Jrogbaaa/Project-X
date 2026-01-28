"""
Import influencers from enriched CSV into database.

Usage:
    cd backend && source ../venv/bin/activate
    python -m app.services.import_influencers \
        --csv "../influencers_enriched.csv" \
        --cache "../.tmp/ig_cache.json"
"""

import argparse
import asyncio
import csv
import json
import logging
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Known niche/interest categories for parsing concatenated strings
# These represent the content niches that influencers create content about
KNOWN_NICHES = [
    "Entertainment and Music",
    "Fashion and Accessories",
    "Food and Drink",
    "Sports",
    "Soccer",
    "Tennis",
    "Basketball",
    "Golf",
    "Motorsport",
    "F1",
    "MotoGP",
    "Padel",
    "Books",
    "Lifestyle",
    "Modeling",
    "Actors",
    "Celebrity",
    "Music",
    "Singer",
    "Dance",
    "Education",
    "Journalists",
    "Travel",
    "Beauty",
    "Fitness",
    "Gaming",
    "Technology",
    "Comedy",
    "Photography",
    "Art",
    "Food",
    "Cooking",
    "Family",
    "Parenting",
    "Business",
    "Entrepreneur",
    "Health",
    "Wellness",
    "Home",
    "Decor",
    "DIY",
]

# Lowercase version for matching
KNOWN_NICHES_LOWER = {niche.lower(): niche for niche in KNOWN_NICHES}


def parse_niche_string(niche_str: str) -> List[str]:
    """
    Parse concatenated niche strings like 'SportsSoccer' or 'BooksLifestyleModeling'
    into a list of individual niches/interests.
    
    Niches represent the content categories that influencers create content about.
    This is one of the most important factors for matching influencers to brands.
    """
    if not niche_str or niche_str.strip() == "":
        return []
    
    # Handle known multi-word niches first
    remaining = niche_str
    found = []
    
    # Sort niches by length (longest first) to match "Entertainment and Music" before "Music"
    sorted_niches = sorted(KNOWN_NICHES, key=len, reverse=True)
    
    for niche in sorted_niches:
        # Case-insensitive search
        pattern = re.compile(re.escape(niche), re.IGNORECASE)
        if pattern.search(remaining):
            found.append(niche)
            remaining = pattern.sub('', remaining, count=1)
    
    # Handle remaining text - try to split on capital letters
    if remaining.strip():
        # Split camelCase: "SomethingElse" -> ["Something", "Else"]
        words = re.findall(r'[A-Z][a-z]*|[a-z]+', remaining)
        for word in words:
            if len(word) > 2:  # Skip very short fragments
                # Check if it matches a known niche
                if word.lower() in KNOWN_NICHES_LOWER:
                    canonical = KNOWN_NICHES_LOWER[word.lower()]
                    if canonical not in found:
                        found.append(canonical)
                elif word.lower() not in ['and', 'the', 'of']:
                    # Add as-is if it's a meaningful word
                    if word.capitalize() not in found:
                        found.append(word.capitalize())
    
    return found


def clean_handle(handle: str) -> str:
    """Clean Instagram handle by removing @ prefix."""
    if not handle:
        return ""
    return handle.lstrip('@').strip().lower()


def load_ig_cache(cache_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load Instagram cache data."""
    if not cache_path.exists():
        logger.warning(f"Cache file not found: {cache_path}")
        return {}
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data)} profiles from Instagram cache")
        return data
    except Exception as e:
        logger.error(f"Error loading cache: {e}")
        return {}


def read_csv_rows(csv_path: Path) -> List[Dict[str, str]]:
    """Read CSV and return list of row dicts."""
    rows = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        # Handle potential BOM
        content = f.read()
        if content.startswith('\ufeff'):
            content = content[1:]
        
        reader = csv.DictReader(content.splitlines())
        for row in reader:
            rows.append(row)
    
    logger.info(f"Read {len(rows)} rows from CSV")
    return rows


async def import_influencers(
    csv_path: Path,
    cache_path: Optional[Path] = None,
    database_url: Optional[str] = None,
    batch_size: int = 100,
    dry_run: bool = False
):
    """
    Import influencers from CSV into database.
    
    Args:
        csv_path: Path to the enriched CSV file
        cache_path: Optional path to ig_cache.json for additional data
        database_url: Database connection string (uses env if not provided)
        batch_size: Number of records to insert per batch
        dry_run: If True, don't actually insert, just log what would be done
    """
    # Import here to avoid circular imports
    from app.config import get_settings
    from app.models.influencer import Influencer
    from app.core.database import Base
    
    # Get database URL - use app settings which handles URL cleaning
    settings = get_settings()
    if not database_url:
        database_url = settings.database_url
    
    logger.info(f"Connecting to database...")
    
    # Create async engine and session
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Load data
    ig_cache = load_ig_cache(cache_path) if cache_path else {}
    csv_rows = read_csv_rows(csv_path)
    
    # Track stats
    stats = {
        "total": len(csv_rows),
        "imported": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0
    }
    
    async with async_session() as session:
        for i in range(0, len(csv_rows), batch_size):
            batch = csv_rows[i:i + batch_size]
            
            for row in batch:
                try:
                    # Extract and clean handle
                    handle_raw = row.get('Instagram Handle', '')
                    username = clean_handle(handle_raw)
                    
                    if not username:
                        stats["skipped"] += 1
                        continue
                    
                    # Get additional data from Instagram cache
                    ig_data = ig_cache.get(username, {})
                    
                    # Parse niche into interests
                    # GENRE column contains the influencer's content niche (e.g., "SportsSoccer", "LifestyleHome")
                    niche_raw = row.get('GENRE', '')
                    interests = parse_niche_string(niche_raw)
                    
                    # Get bio from Details column or Instagram cache
                    bio = row.get('Details', '') or ig_data.get('biography', '')
                    
                    # Build profile data
                    profile_data = {
                        "platform_type": "instagram",
                        "username": username,
                        "display_name": row.get('Name ', '').strip() or ig_data.get('full_name'),
                        "bio": bio[:2000] if bio else None,  # Truncate long bios
                        "country": row.get('Country', 'Spain'),
                        "interests": interests if interests else None,
                        "is_verified": ig_data.get('is_verified', False),
                        "follower_count": ig_data.get('follower_count'),
                        # Set cache_expires_at to far future for imported data (don't expire)
                        "cache_expires_at": datetime.now(timezone.utc) + timedelta(days=365 * 10),
                    }
                    
                    if dry_run:
                        logger.debug(f"Would import: {username} with interests: {interests}")
                        stats["imported"] += 1
                        continue
                    
                    # Check if exists
                    query = select(Influencer).where(
                        Influencer.platform_type == "instagram",
                        Influencer.username == username
                    )
                    result = await session.execute(query)
                    existing = result.scalar_one_or_none()
                    
                    if existing:
                        # Update existing record with new fields
                        existing.interests = profile_data["interests"]
                        existing.country = profile_data["country"]
                        if not existing.bio and profile_data["bio"]:
                            existing.bio = profile_data["bio"]
                        if not existing.follower_count and profile_data["follower_count"]:
                            existing.follower_count = profile_data["follower_count"]
                        if not existing.display_name and profile_data["display_name"]:
                            existing.display_name = profile_data["display_name"]
                        existing.cache_expires_at = profile_data["cache_expires_at"]
                        existing.updated_at = datetime.now(timezone.utc)
                        stats["updated"] += 1
                    else:
                        # Create new record
                        influencer = Influencer(**profile_data)
                        session.add(influencer)
                        stats["imported"] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing row: {row.get('Instagram Handle', 'unknown')} - {e}")
                    stats["errors"] += 1
            
            # Commit batch
            if not dry_run:
                await session.commit()
            
            logger.info(f"Processed {min(i + batch_size, len(csv_rows))}/{len(csv_rows)} rows")
    
    # Print summary
    logger.info("=" * 50)
    logger.info("Import Summary:")
    logger.info(f"  Total rows: {stats['total']}")
    logger.info(f"  Imported: {stats['imported']}")
    logger.info(f"  Updated: {stats['updated']}")
    logger.info(f"  Skipped: {stats['skipped']}")
    logger.info(f"  Errors: {stats['errors']}")
    logger.info("=" * 50)
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Import influencers from CSV to database")
    parser.add_argument(
        "--csv", "-c",
        required=True,
        help="Path to the enriched CSV file"
    )
    parser.add_argument(
        "--cache",
        help="Path to ig_cache.json for additional data"
    )
    parser.add_argument(
        "--database-url",
        help="Database URL (uses DATABASE_URL env var if not provided)"
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=100,
        help="Number of records per batch (default: 100)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually insert, just log what would be done"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    csv_path = Path(args.csv)
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        sys.exit(1)
    
    cache_path = Path(args.cache) if args.cache else None
    
    # Run async import
    asyncio.run(import_influencers(
        csv_path=csv_path,
        cache_path=cache_path,
        database_url=args.database_url,
        batch_size=args.batch_size,
        dry_run=args.dry_run
    ))


if __name__ == "__main__":
    main()
