"""
Keyword-based niche detector for influencers missing primary_niche.

Uses niche_taxonomy.yaml keyword lists to pattern-match against each influencer's
bio, interests, and post_content_aggregated. Scores each taxonomy niche by weighted
keyword hit count and assigns primary_niche + niche_confidence if the top-scoring
niche clears the confidence threshold.

Scoring weights:
  bio           → 3x  (most reliable signal — user-written description)
  interests     → 2x  (PrimeTag-assigned categories)
  post content  → 1x  (hashtags + caption keywords from Apify scrape)

Confidence = top_niche_score / sum_of_all_niche_scores
This is a relative dominance metric: 1.0 means 100% of keyword evidence points
to one niche; 0.5 means the top niche accounts for half the evidence.

Only influencers where primary_niche IS NULL are processed. Existing assignments
are never overwritten (run Option B afterwards to upgrade with LLM if needed).

Usage:
    cd backend && python -m app.services.keyword_niche_detector
    cd backend && python -m app.services.keyword_niche_detector --confidence-threshold 0.4
    cd backend && python -m app.services.keyword_niche_detector --dry-run --limit 200
"""

import argparse
import asyncio
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Weights ─────────────────────────────────────────────────────────────────
WEIGHT_BIO = 3
WEIGHT_INTERESTS = 2
WEIGHT_POST_CONTENT = 1

# Cap keyword occurrences per field so a single spammy keyword can't dominate
MAX_KW_HITS_PER_FIELD = 3


# ── Taxonomy loading ─────────────────────────────────────────────────────────

def load_niche_taxonomy(data_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Return the `niches` dict from niche_taxonomy.yaml."""
    if data_dir is None:
        data_dir = Path(__file__).parent.parent / "data"

    niche_file = data_dir / "niche_taxonomy.yaml"
    if not niche_file.exists():
        raise FileNotFoundError(f"niche_taxonomy.yaml not found at: {niche_file}")

    with open(niche_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    niches = data.get("niches", {})
    logger.info(f"Loaded {len(niches)} niches from taxonomy")
    return niches


# ── Scoring logic ─────────────────────────────────────────────────────────────

def _score_text(text: str, niches: Dict[str, Any], weight: float) -> Dict[str, float]:
    """
    Score a text blob against every niche using substring matching.

    Returns {niche_key: weighted_score}.
    Multi-word keywords (e.g. "padel player") match as a whole phrase,
    giving them an advantage over single-word keywords.
    """
    if not text:
        return {}

    text_lower = text.lower()
    scores: Dict[str, float] = defaultdict(float)

    for niche_key, niche_data in niches.items():
        for kw in niche_data.get("keywords", []):
            kw_lower = kw.lower()
            hits = min(text_lower.count(kw_lower), MAX_KW_HITS_PER_FIELD)
            if hits:
                # Multi-word keywords get a length bonus so "padel player"
                # outweighs plain "padel" when both match.
                word_count = len(kw_lower.split())
                scores[niche_key] += hits * weight * word_count

    return dict(scores)


def detect_niche(
    bio: Optional[str],
    interests: Optional[Any],
    post_content: Optional[Dict[str, Any]],
    niches: Dict[str, Any],
    confidence_threshold: float,
) -> Tuple[Optional[str], float]:
    """
    Detect primary niche from available text sources.

    Returns:
        (niche_key, confidence)  — niche_key is None if confidence < threshold
                                    or no keywords matched at all.
    """
    combined: Dict[str, float] = defaultdict(float)

    # ── bio ──────────────────────────────────────────────────────────────────
    if bio:
        for k, v in _score_text(bio, niches, WEIGHT_BIO).items():
            combined[k] += v

    # ── interests (JSONB list → join to string) ───────────────────────────────
    if interests:
        if isinstance(interests, list):
            interests_text = " ".join(str(i) for i in interests)
        else:
            interests_text = str(interests)
        for k, v in _score_text(interests_text, niches, WEIGHT_INTERESTS).items():
            combined[k] += v

    # ── post_content_aggregated ───────────────────────────────────────────────
    if post_content and isinstance(post_content, dict):
        # top_hashtags: {"#padel": 12, "#fitness": 8, ...}
        hashtags = post_content.get("top_hashtags", {})
        if isinstance(hashtags, dict) and hashtags:
            # Strip leading # so keyword "padel" matches "#padel"
            hashtag_text = " ".join(k.lstrip("#") for k in hashtags)
            for k, v in _score_text(hashtag_text, niches, WEIGHT_POST_CONTENT).items():
                combined[k] += v

        # caption_keywords: {"padel": 5, "fit": 3, ...}
        caption_kws = post_content.get("caption_keywords", {})
        if isinstance(caption_kws, dict) and caption_kws:
            caption_text = " ".join(caption_kws)
            for k, v in _score_text(caption_text, niches, WEIGHT_POST_CONTENT).items():
                combined[k] += v

    if not combined:
        return None, 0.0

    total_score = sum(combined.values())
    top_niche = max(combined, key=combined.__getitem__)
    top_score = combined[top_niche]
    confidence = top_score / total_score if total_score > 0 else 0.0

    if confidence < confidence_threshold:
        return None, confidence

    return top_niche, round(confidence, 4)


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def run_detection(
    confidence_threshold: float = 0.5,
    batch_size: int = 500,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    Scan all influencers missing primary_niche, run keyword detection,
    and write results back to the database.
    """
    # Late imports to avoid circular-import issues
    from app.config import get_settings
    from app.models.influencer import Influencer  # noqa: F401 — needed for SQLAlchemy metadata

    niches = load_niche_taxonomy()

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats = {
        "processed": 0,
        "assigned": 0,
        "skipped_no_data": 0,
        "skipped_low_confidence": 0,
    }

    # ── Fetch candidates ──────────────────────────────────────────────────────
    async with Session() as session:
        query = (
            select(Influencer)
            .where(Influencer.primary_niche.is_(None))
            .order_by(Influencer.id)
        )
        if limit:
            query = query.limit(limit)

        result = await session.execute(query)
        influencers = list(result.scalars().all())

    logger.info(f"Found {len(influencers)} influencers missing primary_niche")

    # ── Score each influencer ─────────────────────────────────────────────────
    pending_updates: List[Tuple[Any, str, float]] = []  # (id, niche, confidence)

    for inf in influencers:
        stats["processed"] += 1

        has_data = inf.bio or inf.interests or inf.post_content_aggregated
        if not has_data:
            stats["skipped_no_data"] += 1
            logger.debug(f"  {inf.username}: no data — skip")
            continue

        niche, confidence = detect_niche(
            bio=inf.bio,
            interests=inf.interests,
            post_content=inf.post_content_aggregated,
            niches=niches,
            confidence_threshold=confidence_threshold,
        )

        if niche is None:
            stats["skipped_low_confidence"] += 1
            logger.debug(f"  {inf.username}: below threshold (conf={confidence:.3f})")
        else:
            logger.info(f"  {inf.username}: → {niche} (conf={confidence:.3f})")
            pending_updates.append((inf.id, niche, confidence))
            stats["assigned"] += 1

    # ── Summary before write ──────────────────────────────────────────────────
    logger.info(
        f"\n{'[DRY RUN] ' if dry_run else ''}Summary:\n"
        f"  Processed            : {stats['processed']}\n"
        f"  Will assign          : {stats['assigned']}\n"
        f"  Below threshold      : {stats['skipped_low_confidence']}\n"
        f"  No text data         : {stats['skipped_no_data']}\n"
    )

    if dry_run:
        logger.info("[DRY RUN] No changes written to database.")
        await engine.dispose()
        return stats

    if not pending_updates:
        logger.info("Nothing to update.")
        await engine.dispose()
        return stats

    # ── Write in batches ──────────────────────────────────────────────────────
    async with Session() as session:
        for i in range(0, len(pending_updates), batch_size):
            batch = pending_updates[i : i + batch_size]
            for inf_id, niche, confidence in batch:
                await session.execute(
                    update(Influencer)
                    .where(Influencer.id == inf_id)
                    .values(primary_niche=niche, niche_confidence=confidence)
                )
            await session.commit()
            end = min(i + batch_size, len(pending_updates))
            logger.info(f"  Committed records {i + 1}–{end} of {len(pending_updates)}")

    logger.info(f"\nDone. Assigned primary_niche to {stats['assigned']} influencers.")
    await engine.dispose()
    return stats


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Keyword-based niche detection for influencers missing primary_niche. "
            "Free, fast, no LLM — uses niche_taxonomy.yaml keyword lists."
        )
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.5,
        metavar="FLOAT",
        help="Minimum relative confidence to assign a niche (default: 0.5). "
             "Lower values = more assignments but noisier results.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        metavar="N",
        help="Number of DB rows to commit per transaction (default: 500).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Cap the number of influencers to process (useful for testing).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect niches and log assignments without writing to the database.",
    )
    args = parser.parse_args()

    asyncio.run(
        run_detection(
            confidence_threshold=args.confidence_threshold,
            batch_size=args.batch_size,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
