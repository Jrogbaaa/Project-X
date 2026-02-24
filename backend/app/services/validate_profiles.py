"""validate_profiles.py — Batch-check Instagram handles and mark dead accounts.

For each influencer where profile_active IS TRUE, makes a lightweight HEAD
request to instagram.com/{username}. If the response is 404 (account deleted
or renamed) it sets profile_active=False so the profile is excluded from all
future search results.

Rate-limiting: 1 request per second by default (configurable with --delay).
Run time: ~77 minutes for 4,645 profiles at 1 req/s.

Usage
-----
    # Dry run — print what would be marked inactive (no DB writes)
    cd backend && python -m app.services.validate_profiles --dry-run

    # Live run — update DB
    cd backend && python -m app.services.validate_profiles

    # Faster run (risk of rate-limiting by Instagram)
    cd backend && python -m app.services.validate_profiles --delay 0.3

    # Only check profiles not validated in the last N days
    cd backend && python -m app.services.validate_profiles --since-days 30

Notes
-----
- Instagram returns 200 for public profiles, 404 for deleted/renamed.
- Private profiles still return 200 (the page exists, just locked).
- Bot detection may return 429 — the script backs off automatically.
- Always run with --dry-run first to sanity-check the result set.
"""

import argparse
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.influencer import Influencer

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

INSTAGRAM_URL = "https://www.instagram.com/{}/"
BATCH_SIZE = 50  # Commit every N updates


async def check_handle(client: httpx.AsyncClient, username: str) -> Optional[bool]:
    """Return True if the handle resolves, False if 404, None on error."""
    url = INSTAGRAM_URL.format(username)
    try:
        resp = await client.head(url, follow_redirects=True, timeout=10)
        if resp.status_code == 200:
            return True
        if resp.status_code == 404:
            return False
        if resp.status_code == 429:
            logger.warning(f"  429 rate-limited on @{username} — sleeping 30s")
            await asyncio.sleep(30)
            return None
        # 301/302/other — treat as exists
        return True
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        logger.warning(f"  Request error for @{username}: {exc}")
        return None


async def validate_profiles(dry_run: bool, delay: float, since_days: Optional[int]) -> None:
    from app.config import get_settings
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Build query — only active profiles, optionally limited to unvalidated ones
        stmt = select(Influencer).where(Influencer.profile_active.isnot(False))

        if since_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
            # Only profiles not updated recently (use updated_at as proxy)
            stmt = stmt.where(Influencer.updated_at < cutoff)

        stmt = stmt.order_by(Influencer.username)
        result = await session.execute(stmt)
        influencers = list(result.scalars().all())

    await engine.dispose()

    total = len(influencers)
    logger.info(f"Checking {total} profiles{'  [DRY RUN]' if dry_run else ''}")

    inactive_count = 0
    error_count = 0
    batch_updates: list[tuple[str, bool]] = []  # (username, profile_active)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(headers=headers) as client:
        engine2 = create_async_engine(
            __import__("app.config", fromlist=["get_settings"]).get_settings().database_url,
            echo=False,
        )
        async_session2 = sessionmaker(engine2, class_=AsyncSession, expire_on_commit=False)

        for i, inf in enumerate(influencers, 1):
            exists = await check_handle(client, inf.username)

            if exists is False:
                status = "INACTIVE"
                inactive_count += 1
                batch_updates.append((str(inf.id), False))
            elif exists is True:
                status = "ok"
            else:
                status = "error"
                error_count += 1

            if i % 100 == 0 or i == total:
                logger.info(f"  [{i}/{total}] @{inf.username} → {status}   ({inactive_count} inactive so far)")
            elif exists is False:
                logger.info(f"  [{i}/{total}] @{inf.username} → {status}")

            # Commit in batches
            if not dry_run and len(batch_updates) >= BATCH_SIZE:
                async with async_session2() as session:
                    for uid, active in batch_updates:
                        await session.execute(
                            text("UPDATE influencers SET profile_active = :active WHERE id = :id"),
                            {"active": active, "id": uid},
                        )
                    await session.commit()
                batch_updates.clear()

            await asyncio.sleep(delay)

        # Final batch
        if not dry_run and batch_updates:
            async with async_session2() as session:
                for uid, active in batch_updates:
                    await session.execute(
                        text("UPDATE influencers SET profile_active = :active WHERE id = :id"),
                        {"active": active, "id": uid},
                    )
                await session.commit()

        await engine2.dispose()

    logger.info("")
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}Summary:")
    logger.info(f"  Checked  : {total}")
    logger.info(f"  Inactive : {inactive_count}  (would be{'  excluded from searches' if dry_run else ' marked profile_active=False'})")
    logger.info(f"  Errors   : {error_count}  (skipped — handle treated as active)")
    if dry_run:
        logger.info("Re-run without --dry-run to apply changes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate Instagram handles in DB")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing to DB")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between requests (default: 1.0)")
    parser.add_argument("--since-days", type=int, default=None, help="Only check profiles not updated in N days")
    args = parser.parse_args()

    asyncio.run(validate_profiles(
        dry_run=args.dry_run,
        delay=args.delay,
        since_days=args.since_days,
    ))
