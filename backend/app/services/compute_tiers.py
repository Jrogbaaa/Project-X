"""compute_tiers.py — Populate influencer_tier from follower_count.

Tier definitions
----------------
  micro  — follower_count < 50_000
  mid    — 50_000 ≤ follower_count < 500_000
  macro  — 500_000 ≤ follower_count < 2_000_000
  mega   — follower_count ≥ 2_000_000

Usage
-----
    cd backend && python -m app.services.compute_tiers

Safe to re-run — each tier is a single bulk UPDATE, so it's idempotent.
"""
import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# (label, min_inclusive, max_exclusive)  — max=None means no upper bound
TIER_RULES = [
    ("micro",  0,          50_000),
    ("mid",    50_000,     500_000),
    ("macro",  500_000,    2_000_000),
    ("mega",   2_000_000,  None),
]


async def compute_tiers() -> None:
    from app.config import get_settings
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("Computing influencer tiers…")
    async with async_session() as session:
        for tier, low, high in TIER_RULES:
            if high is None:
                sql = text(
                    "UPDATE influencers SET influencer_tier = :tier "
                    "WHERE follower_count >= :low"
                )
                params: dict = {"tier": tier, "low": low}
            else:
                sql = text(
                    "UPDATE influencers SET influencer_tier = :tier "
                    "WHERE follower_count >= :low AND follower_count < :high"
                )
                params = {"tier": tier, "low": low, "high": high}

            result = await session.execute(sql, params)
            print(f"  {tier:<6}  {result.rowcount:>6} influencers")

        # Clear tier for rows without follower_count (unclassifiable)
        null_result = await session.execute(
            text("UPDATE influencers SET influencer_tier = NULL WHERE follower_count IS NULL")
        )
        if null_result.rowcount:
            print(f"  (null)  {null_result.rowcount:>6} influencers — tier cleared (no follower_count)")

        await session.commit()

    await engine.dispose()
    print("Done — influencer_tier populated and indexed.")


if __name__ == "__main__":
    asyncio.run(compute_tiers())
