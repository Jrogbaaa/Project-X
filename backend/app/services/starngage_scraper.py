#!/usr/bin/env python3
"""
Starngage Spain Influencer Scraper — Helper Utilities

The actual scraping is done interactively via Cursor's Playwright MCP browser.
See directives/starngage-scraper.md for the full process.

This module provides:
  - parse_follower_count(): Convert '209.6K' / '1.2M' to numeric
  - extract_page(): Parse one page of Starngage HTML into dicts
  - combine_and_write_csv(): Merge batch JSON files, filter by threshold, write CSV
  - import_to_db(): Upsert Starngage CSV data into the influencers table

Usage:
    # Combine batch extracts into CSV
    cd backend && python -m app.services.starngage_scraper combine \\
        --batch-files file1.txt file2.txt \\
        --min-followers 100000

    # Import CSV into database (upsert: updates existing, adds new, preserves enrichment)
    cd backend && python -m app.services.starngage_scraper import \\
        --csv ../starngage_spain_influencers_2026.csv

    # Dry run import (see what would change)
    cd backend && python -m app.services.starngage_scraper import \\
        --csv ../starngage_spain_influencers_2026.csv --dry-run
"""

import argparse
import asyncio
import csv
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

BASE_URL = "https://starngage.com/plus/en-us/influencer/ranking/instagram/spain"
DEFAULT_MIN_FOLLOWERS = 100_000
DEFAULT_OUTPUT = "../starngage_spain_influencers_{year}.csv"


def parse_follower_count(text: str) -> float:
    """Convert '209.6K' or '1.2M' to a numeric value."""
    text = text.strip()
    if not text:
        return 0.0
    if text.endswith("M"):
        return float(text[:-1]) * 1_000_000
    if text.endswith("K"):
        return float(text[:-1]) * 1_000
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return 0.0


def parse_engagement_rate(text: str) -> Optional[float]:
    """Convert '2.61%' to 0.0261."""
    text = text.strip().rstrip("%")
    if not text:
        return None
    try:
        return float(text) / 100.0
    except ValueError:
        return None


def parse_topics_to_interests(topics_str: str) -> list[str]:
    """Split 'Fashion, Entertainment and Music, Travel' into a list."""
    if not topics_str or not topics_str.strip():
        return []
    return [t.strip() for t in topics_str.split(",") if t.strip()]


def clean_handle(handle: str) -> str:
    """Strip @ prefix and lowercase."""
    if not handle:
        return ""
    return handle.lstrip("@").strip().lower()


def extract_page(html: str) -> list[dict]:
    """Parse one page of Starngage HTML and return influencer dicts."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table tbody")
    if not table:
        return []

    rows = table.select("tr")
    results = []
    for row in rows:
        cells = row.select("td")
        if len(cells) < 4:
            continue

        rank = cells[0].get_text(strip=True)

        name_cell = cells[1]
        handle_link = name_cell.select_one("a")
        handle = handle_link.get_text(strip=True) if handle_link else ""
        name_container = name_cell.select_one("div > div:last-child")
        name = ""
        if name_container:
            first_div = name_container.select_one("div:first-child")
            name = first_div.get_text(strip=True) if first_div else ""

        followers = cells[2].get_text(strip=True)
        er = cells[3].get_text(strip=True) if len(cells) > 3 else ""

        topics = ""
        if len(cells) > 5:
            topic_links = cells[5].select("a")
            topics = ", ".join(
                a.get_text(strip=True) for a in topic_links if a.get_text(strip=True)
            )

        results.append({
            "rank": rank,
            "name": name,
            "handle": handle,
            "followers": followers,
            "er": er,
            "topics": topics,
        })

    return results


def load_batch_file(path: str) -> list[dict]:
    """Load influencer data from a Playwright MCP agent-tools output file."""
    with open(path, "r") as f:
        content = f.read()

    start = content.index('"{')
    end = content.index('}"', start) + 2
    json_str = content[start:end]
    parsed = json.loads(json_str)
    data = json.loads(parsed) if isinstance(parsed, str) else parsed
    return data["data"]


def combine_and_write_csv(
    batch_files: list[str],
    min_followers: int = DEFAULT_MIN_FOLLOWERS,
    output_path: str | None = None,
    existing_csv: str | None = None,
) -> list[dict]:
    """Combine batch JSON files, filter by follower threshold, write CSV."""
    if output_path is None:
        output_path = DEFAULT_OUTPUT.format(year=datetime.now().year)

    all_data: list[dict] = []

    if existing_csv:
        with open(existing_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            all_data.extend(reader)
        logger.info("Loaded %d existing rows from %s", len(all_data), existing_csv)

    for bf in batch_files:
        batch = load_batch_file(bf)
        logger.info(
            "Batch %s: %d rows, ranks %s-%s, last followers: %s",
            Path(bf).name,
            len(batch),
            batch[0]["rank"],
            batch[-1]["rank"],
            batch[-1]["followers"],
        )
        all_data.extend(batch)

    logger.info("Combined total: %d rows", len(all_data))

    filtered = [
        row for row in all_data
        if parse_follower_count(row["followers"]) >= min_followers
    ]
    logger.info("After %s filter: %d influencers", f"{min_followers:,}", len(filtered))

    if filtered:
        logger.info("First: rank %s %s (%s)", filtered[0]["rank"], filtered[0]["name"], filtered[0]["followers"])
        logger.info("Last:  rank %s %s (%s)", filtered[-1]["rank"], filtered[-1]["name"], filtered[-1]["followers"])

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["rank", "name", "handle", "followers", "er", "topics"]
        )
        writer.writeheader()
        writer.writerows(filtered)

    logger.info("Wrote %d rows to %s", len(filtered), output)
    return filtered


# ---------------------------------------------------------------------------
# Database import
# ---------------------------------------------------------------------------

async def import_to_db(
    csv_path: str,
    dry_run: bool = False,
    batch_size: int = 200,
) -> dict:
    """
    Upsert Starngage CSV into the influencers table.

    For EXISTING influencers (matched by username):
        - ALWAYS updates: follower_count, display_name, interests, engagement_rate
        - NEVER touches: primary_niche, niche_confidence, content_themes,
          credibility_score, audience_*, bio, post_content_aggregated,
          detected_brands, PrimeTag IDs, etc.

    For NEW influencers:
        - Creates a new record with Starngage data
        - Sets country='Spain', platform_type='instagram'

    Returns stats dict with counts.
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import get_settings
    from app.models.influencer import Influencer

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        content = f.read()
        if content.startswith("\ufeff"):
            content = content[1:]
        reader = csv.DictReader(content.splitlines())
        rows = list(reader)

    logger.info("Loaded %d rows from %s", len(rows), csv_path)

    stats = {"total": len(rows), "updated": 0, "created": 0, "skipped": 0, "errors": 0}

    async with async_session() as session:
        # Pre-load all existing usernames in one query for fast lookups
        logger.info("Loading existing influencers from database...")
        result = await session.execute(
            select(Influencer.username, Influencer.id).where(
                Influencer.platform_type == "instagram"
            )
        )
        existing_map = {row.username: row.id for row in result.all()}
        logger.info("Found %d existing influencers in DB", len(existing_map))

        if dry_run:
            csv_usernames = set()
            for row in rows:
                username = clean_handle(row.get("handle", ""))
                if not username:
                    stats["skipped"] += 1
                    continue
                csv_usernames.add(username)
                if username in existing_map:
                    stats["updated"] += 1
                else:
                    stats["created"] += 1

            logger.info("=" * 60)
            logger.info("DRY RUN SUMMARY")
            logger.info("  Total CSV rows:  %d", stats["total"])
            logger.info("  Would update:    %d  (existing influencers)", stats["updated"])
            logger.info("  Would create:    %d  (new influencers)", stats["created"])
            logger.info("  Would skip:      %d  (no handle)", stats["skipped"])
            logger.info("=" * 60)
            await engine.dispose()
            return stats

        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            batch_usernames = []

            for row in batch:
                username = clean_handle(row.get("handle", ""))
                if username:
                    batch_usernames.append(username)

            # Batch-load all influencer objects we need to update
            if batch_usernames:
                result = await session.execute(
                    select(Influencer).where(
                        Influencer.platform_type == "instagram",
                        Influencer.username.in_(batch_usernames),
                    )
                )
                existing_batch = {inf.username: inf for inf in result.scalars().all()}
            else:
                existing_batch = {}

            now = datetime.now(timezone.utc)
            far_future = now + timedelta(days=365 * 10)

            for row in batch:
                try:
                    username = clean_handle(row.get("handle", ""))
                    if not username:
                        stats["skipped"] += 1
                        continue

                    follower_count = int(parse_follower_count(row.get("followers", "")))
                    display_name = row.get("name", "").strip() or None
                    interests = parse_topics_to_interests(row.get("topics", ""))
                    er = parse_engagement_rate(row.get("er", ""))

                    existing = existing_batch.get(username)

                    if existing:
                        existing.follower_count = follower_count
                        existing.display_name = display_name or existing.display_name
                        existing.interests = interests if interests else existing.interests
                        existing.engagement_rate = er if er is not None else existing.engagement_rate
                        existing.country = "Spain"
                        existing.updated_at = now
                        existing.cache_expires_at = far_future
                        stats["updated"] += 1
                    else:
                        influencer = Influencer(
                            platform_type="instagram",
                            username=username,
                            display_name=display_name,
                            follower_count=follower_count,
                            interests=interests if interests else None,
                            engagement_rate=er,
                            country="Spain",
                            cache_expires_at=far_future,
                        )
                        session.add(influencer)
                        stats["created"] += 1

                except Exception as e:
                    logger.error("Error processing %s: %s", row.get("handle", "?"), e)
                    stats["errors"] += 1

            await session.commit()

            processed = min(i + batch_size, len(rows))
            logger.info(
                "Processed %d/%d (updated=%d, created=%d)",
                processed, len(rows), stats["updated"], stats["created"],
            )

    await engine.dispose()

    logger.info("=" * 60)
    logger.info("IMPORT SUMMARY")
    logger.info("  Total CSV rows:  %d", stats["total"])
    logger.info("  Updated:         %d  (existing influencers refreshed)", stats["updated"])
    logger.info("  Created:         %d  (new influencers added)", stats["created"])
    logger.info("  Skipped:         %d  (no handle)", stats["skipped"])
    logger.info("  Errors:          %d", stats["errors"])
    logger.info("=" * 60)

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Starngage scraper utilities",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- combine subcommand ---
    combine_parser = subparsers.add_parser(
        "combine", help="Combine batch extracts into a single CSV",
    )
    combine_parser.add_argument(
        "--batch-files", nargs="+", required=True,
        help="Paths to agent-tools output files",
    )
    combine_parser.add_argument(
        "--min-followers", type=int, default=DEFAULT_MIN_FOLLOWERS,
        help=f"Min followers (default: {DEFAULT_MIN_FOLLOWERS:,})",
    )
    combine_parser.add_argument("--output", type=str, default=None)
    combine_parser.add_argument("--existing-csv", type=str, default=None)

    # --- import subcommand ---
    import_parser = subparsers.add_parser(
        "import", help="Import Starngage CSV into database (upsert)",
    )
    import_parser.add_argument(
        "--csv", required=True,
        help="Path to starngage_spain_influencers CSV",
    )
    import_parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without writing to DB",
    )
    import_parser.add_argument(
        "--batch-size", type=int, default=100,
        help="Records per DB commit batch (default: 100)",
    )

    args = parser.parse_args()

    if args.command == "combine":
        combine_and_write_csv(
            batch_files=args.batch_files,
            min_followers=args.min_followers,
            output_path=args.output,
            existing_csv=args.existing_csv,
        )
    elif args.command == "import":
        asyncio.run(import_to_db(
            csv_path=args.csv,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
        ))


if __name__ == "__main__":
    main()
