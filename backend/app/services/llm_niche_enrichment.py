"""
LLM Niche + Theme Enrichment Pipeline

Batch-processes influencers where primary_niche is NULL.
For each influencer, sends bio + interests + post_content_aggregated to GPT-4o
and gets back primary_niche, niche_confidence, and content_themes.

Writes results back to DB in batches of 50.

Cost estimate: ~$0.01/influencer (bio + interests + post hashtags as input)

Usage:
    # Dry run - see what would be processed
    cd backend && python -m app.services.llm_niche_enrichment --dry-run

    # Run with default batch size (50)
    cd backend && python -m app.services.llm_niche_enrichment

    # Custom batch size and limit
    cd backend && python -m app.services.llm_niche_enrichment --batch-size 50 --limit 200

    # Re-enrich influencers even if they already have a niche
    cd backend && python -m app.services.llm_niche_enrichment --force
"""

import asyncio
import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from openai import AsyncOpenAI
from sqlalchemy import select, update, and_, or_
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import get_settings
from app.models.influencer import Influencer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Path to niche taxonomy
TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "data" / "niche_taxonomy.yaml"

# Number of influencers to send per individual LLM call (batched within the DB batch)
LLM_CALL_SIZE = 10


def load_valid_niches() -> set[str]:
    """Load valid niche keys from niche_taxonomy.yaml."""
    with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
        taxonomy = yaml.safe_load(f)
    return set(taxonomy.get("niches", {}).keys())


VALID_NICHES: set[str] = load_valid_niches()

# ── LLM prompt ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are a content classification expert specialising in Spanish social media influencers.

For each influencer provided, classify them into a single primary niche and detect their content themes.

## Niche Taxonomy
You MUST pick primary_niche from this exact list (use the exact key):
{json.dumps(sorted(VALID_NICHES), ensure_ascii=False, indent=2)}

If none fit well, pick the closest match. Never invent a new niche.

## Instructions
- Use bio, interests, and post hashtags/keywords to classify.
- Interests are coarse PrimeTag categories (e.g. "Sports", "Soccer"). Use them as signals.
- post_hashtags is the top hashtags used (key=hashtag, value=count). Highly reliable signal.
- caption_keywords is the top caption words (key=word, value=count).
- If data is sparse, assign the best guess with low niche_confidence (0.2-0.4).
- narrative_style: choose from "storytelling", "casual", "minimal", "promotional".
- detected_themes: choose from "behind_the_scenes", "training", "competition", "lifestyle",
  "travel", "family", "motivation", "food", "fashion", "beauty".
- format_preference: list of formats observed, e.g. ["reels", "posts", "stories"].
  Infer from context if not explicit.

## Output Format
Return a JSON object with a "results" array. Each element maps to the input influencer
by its "username". Example:

{{
  "results": [
    {{
      "username": "influencer_handle",
      "primary_niche": "fitness",
      "niche_confidence": 0.87,
      "content_themes": {{
        "detected_themes": ["training", "motivation"],
        "narrative_style": "storytelling",
        "format_preference": ["reels", "posts"]
      }}
    }}
  ]
}}
"""


def build_user_prompt(influencers: List[Dict[str, Any]]) -> str:
    """Build the user message for a sub-batch of influencers."""
    items = []
    for inf in influencers:
        bio = (inf.get("bio") or "").strip()[:300]  # cap at 300 chars
        interests = inf.get("interests") or []
        post_content = inf.get("post_content_aggregated") or {}

        # Extract top hashtags and keywords from post_content_aggregated
        top_hashtags = post_content.get("top_hashtags", {})
        caption_keywords = post_content.get("caption_keywords", {})

        # Trim to top-20 hashtags / top-30 keywords to save tokens
        top_hashtags_trimmed = dict(list(top_hashtags.items())[:20])
        caption_keywords_trimmed = dict(list(caption_keywords.items())[:30])

        items.append({
            "username": inf["username"],
            "bio": bio or None,
            "interests": interests,
            "post_hashtags": top_hashtags_trimmed,
            "caption_keywords": caption_keywords_trimmed,
        })

    return f"Classify these {len(items)} influencers:\n\n{json.dumps(items, ensure_ascii=False, indent=2)}"


# ── Pipeline class ─────────────────────────────────────────────────────────────

class LLMNicheEnrichmentPipeline:
    """LLM-powered niche + theme enrichment for influencers missing primary_niche."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
        batch_size: int = 50,
        force: bool = False,
        progress_file: str = ".tmp/llm_niche_progress.json",
    ):
        self.session_factory = session_factory
        self.batch_size = batch_size
        self.force = force
        self.progress_file = Path(progress_file)
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)

        settings = get_settings()
        self.openai = AsyncOpenAI(api_key=settings.openai_api_key, timeout=120.0)
        self.model = settings.openai_model

        self.stats: Dict[str, Any] = {
            "total": 0,
            "processed": 0,
            "success": 0,
            "failed": 0,
            "skipped_already_classified": 0,
            "llm_calls": 0,
            "estimated_cost_usd": 0.0,
        }

    # ── DB helpers ──────────────────────────────────────────────────────────

    async def get_influencers_to_enrich(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch influencers that need LLM niche enrichment."""
        async with self.session_factory() as session:
            filters = [
                Influencer.username.isnot(None),
            ]
            if not self.force:
                filters.append(Influencer.primary_niche.is_(None))

            query = (
                select(Influencer)
                .where(and_(*filters))
                .order_by(Influencer.follower_count.desc().nullslast())
            )
            if limit:
                query = query.limit(limit)

            result = await session.execute(query)
            rows = list(result.scalars().all())

            return [
                {
                    "id": inf.id,
                    "username": inf.username,
                    "follower_count": inf.follower_count,
                    "bio": inf.bio,
                    "interests": inf.interests,
                    "post_content_aggregated": inf.post_content_aggregated,
                    "existing_niche": inf.primary_niche,
                }
                for inf in rows
            ]

    async def write_batch_to_db(self, updates: List[Dict], retries: int = 3) -> int:
        """
        Write enrichment results using direct UPDATE statements (no SELECT).
        Avoids deadlocks from the SELECT-then-UPDATE pattern.
        Retries up to `retries` times on deadlock with exponential backoff.
        Returns success count.
        """
        if not updates:
            return 0

        for attempt in range(1, retries + 1):
            try:
                async with self.session_factory() as session:
                    for upd in updates:
                        # Merge content_themes via PostgreSQL jsonb concat
                        # We pass the full merged dict; the UPDATE is atomic per row
                        new_themes = upd.get("content_themes") or {}

                        await session.execute(
                            update(Influencer)
                            .where(Influencer.id == upd["id"])
                            .values(
                                primary_niche=upd["primary_niche"],
                                niche_confidence=upd["niche_confidence"],
                                content_themes=new_themes if new_themes else None,
                            )
                        )

                    await session.commit()
                return len(updates)

            except DBAPIError as e:
                if "deadlock" in str(e).lower() and attempt < retries:
                    wait = 2 ** attempt  # 2s, 4s, 8s
                    logger.warning(
                        f"Deadlock on write attempt {attempt}/{retries}, "
                        f"retrying in {wait}s…"
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"DB write failed after {attempt} attempt(s): {e}")
                    return 0

        return 0

    # ── LLM helpers ────────────────────────────────────────────────────────

    async def call_llm(self, influencer_subset: List[Dict]) -> List[Dict]:
        """
        Send a sub-batch of influencers to GPT-4o.
        Returns list of result dicts (may be empty on failure).
        """
        prompt = build_user_prompt(influencer_subset)
        try:
            response = await self.openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=1500,
            )
            self.stats["llm_calls"] += 1

            # Rough token cost estimate (GPT-4o pricing)
            usage = response.usage
            if usage:
                input_cost = (usage.prompt_tokens / 1000) * 0.0025
                output_cost = (usage.completion_tokens / 1000) * 0.010
                self.stats["estimated_cost_usd"] += input_cost + output_cost

            content = response.choices[0].message.content or "{}"
            data = json.loads(content)
            return data.get("results", [])

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error from LLM: {e}")
            return []
        except Exception as e:
            err_str = str(e)
            if "timed out" in err_str.lower() or "timeout" in err_str.lower():
                logger.warning(f"LLM call timed out, skipping sub-batch and continuing")
            else:
                logger.error(f"LLM call failed: {e}")
            return []

    def _validate_and_coerce(self, result: Dict) -> Optional[Dict]:
        """
        Validate a single LLM result dict.
        Coerces niche to a valid taxonomy key; returns None if unusable.
        """
        username = result.get("username", "").strip()
        if not username:
            return None

        primary_niche = (result.get("primary_niche") or "").lower().strip().replace(" ", "_")
        if primary_niche not in VALID_NICHES:
            # Try common aliases
            aliases = {
                "sport": "fitness",
                "health": "wellness",
                "food_drink": "food",
                "home": "home_decor",
                "interior": "home_decor",
                "alcohol": "alcoholic_beverages",
                "drinks": "soft_drinks",
                "cars": "automotive",
                "motor": "motorsport",
            }
            primary_niche = aliases.get(primary_niche, None)
            if not primary_niche:
                logger.debug(f"  {username}: invalid niche '{result.get('primary_niche')}' — skipping")
                return None

        confidence = float(result.get("niche_confidence") or 0.5)
        confidence = max(0.0, min(1.0, confidence))

        themes_raw = result.get("content_themes") or {}
        content_themes = {
            "detected_themes": themes_raw.get("detected_themes") or [],
            "narrative_style": themes_raw.get("narrative_style") or "casual",
            "format_preference": themes_raw.get("format_preference") or [],
        }

        return {
            "username": username,
            "primary_niche": primary_niche,
            "niche_confidence": round(confidence, 3),
            "content_themes": content_themes,
        }

    # ── Main pipeline ───────────────────────────────────────────────────────

    async def process_batch(
        self,
        influencers: List[Dict],
        batch_num: int,
        total_batches: int,
    ) -> int:
        """
        Process one DB batch (up to batch_size influencers).
        Splits into LLM sub-batches of LLM_CALL_SIZE each.
        Returns number of successfully enriched influencers.
        """
        logger.info(
            f"Batch {batch_num}/{total_batches}: "
            f"{len(influencers)} influencers → "
            f"{((len(influencers) - 1) // LLM_CALL_SIZE) + 1} LLM calls"
        )

        # Build username → id mapping for this batch
        username_to_id = {inf["username"]: inf["id"] for inf in influencers}

        # Collect all updates across sub-batches
        updates: List[Dict] = []

        for i in range(0, len(influencers), LLM_CALL_SIZE):
            sub_batch = influencers[i : i + LLM_CALL_SIZE]
            results = await self.call_llm(sub_batch)

            for res in results:
                validated = self._validate_and_coerce(res)
                if not validated:
                    self.stats["failed"] += 1
                    self.stats["processed"] += 1
                    continue

                inf_id = username_to_id.get(validated["username"])
                if not inf_id:
                    logger.warning(f"  Unknown username in LLM response: {validated['username']}")
                    self.stats["failed"] += 1
                    self.stats["processed"] += 1
                    continue

                updates.append({**validated, "id": inf_id})

            # Pause between LLM calls to respect rate limits
            if i + LLM_CALL_SIZE < len(influencers):
                await asyncio.sleep(2)

        # Write this batch to DB
        success_count = await self.write_batch_to_db(updates)
        self.stats["success"] += success_count
        # Any influencer in the batch without an update = failed
        failed_in_batch = len(influencers) - success_count
        self.stats["failed"] += failed_in_batch
        self.stats["processed"] += len(influencers)

        logger.info(
            f"  Batch {batch_num} done — "
            f"enriched: {success_count}, "
            f"failed: {failed_in_batch}, "
            f"LLM calls so far: {self.stats['llm_calls']}, "
            f"est. cost: ${self.stats['estimated_cost_usd']:.3f}"
        )
        return success_count

    def _save_progress(self, processed_ids: List[str]):
        progress = {
            "processed_ids": processed_ids,
            "stats": self.stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(self.progress_file, "w") as f:
            json.dump(progress, f, default=str)

    async def run(self, limit: Optional[int] = None, dry_run: bool = False):
        """Entry point for the enrichment pipeline."""
        influencers = await self.get_influencers_to_enrich(limit=limit)
        self.stats["total"] = len(influencers)

        logger.info("=" * 60)
        logger.info("LLM Niche + Theme Enrichment Pipeline")
        logger.info("=" * 60)
        logger.info(f"Model         : {self.model}")
        logger.info(f"Batch size    : {self.batch_size} influencers / DB write")
        logger.info(f"LLM call size : {LLM_CALL_SIZE} influencers / call")
        logger.info(f"Force mode    : {self.force}")
        logger.info(f"To enrich     : {len(influencers):,}")

        if dry_run:
            est_calls = (len(influencers) + LLM_CALL_SIZE - 1) // LLM_CALL_SIZE
            # Rough: 200 input tokens + 50 output tokens per influencer
            est_input_tokens = len(influencers) * 200
            est_output_tokens = len(influencers) * 50
            est_cost = (est_input_tokens / 1000 * 0.0025) + (est_output_tokens / 1000 * 0.010)
            logger.info("")
            logger.info("DRY RUN — no changes will be written")
            logger.info(f"Estimated LLM calls : {est_calls:,}")
            logger.info(f"Estimated cost      : ${est_cost:.2f}")
            logger.info("")
            logger.info("Fields to populate:")
            logger.info("  - primary_niche (validated against niche_taxonomy.yaml)")
            logger.info("  - niche_confidence (0.0-1.0)")
            logger.info("  - content_themes.detected_themes")
            logger.info("  - content_themes.narrative_style")
            logger.info("  - content_themes.format_preference")
            logger.info("")
            logger.info("Sample influencers (first 10):")
            for inf in influencers[:10]:
                bio_snippet = (inf.get("bio") or "")[:60].replace("\n", " ")
                has_posts = bool(inf.get("post_content_aggregated"))
                logger.info(
                    f"  @{inf['username']:<30} "
                    f"followers={inf['follower_count'] or 0:>8,}  "
                    f"has_posts={'yes' if has_posts else 'no '}  "
                    f"bio=\"{bio_snippet}\""
                )
            return

        if not influencers:
            logger.info("Nothing to enrich — all influencers already have primary_niche set.")
            logger.info("Use --force to re-classify all influencers.")
            return

        total_batches = (len(influencers) + self.batch_size - 1) // self.batch_size
        processed_ids: List[str] = []

        for i in range(0, len(influencers), self.batch_size):
            batch = influencers[i : i + self.batch_size]
            batch_num = (i // self.batch_size) + 1

            await self.process_batch(batch, batch_num, total_batches)

            processed_ids.extend(str(inf["id"]) for inf in batch)
            self._save_progress(processed_ids)

            # Pause between DB batches
            if i + self.batch_size < len(influencers):
                await asyncio.sleep(2)

        # Final summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("Enrichment Complete")
        logger.info("=" * 60)
        logger.info(f"Total influencers : {self.stats['total']:,}")
        logger.info(f"Enriched          : {self.stats['success']:,}")
        logger.info(f"Failed/skipped    : {self.stats['failed']:,}")
        logger.info(f"LLM calls made    : {self.stats['llm_calls']:,}")
        logger.info(f"Estimated cost    : ${self.stats['estimated_cost_usd']:.3f}")


# ── CLI entry point ────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="LLM Niche + Theme Enrichment — classify influencers where primary_niche is NULL"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Influencers per DB write batch (default: 50)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max influencers to process (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without making any changes",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-classify influencers even if primary_niche is already set",
    )
    args = parser.parse_args()

    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    pipeline = LLMNicheEnrichmentPipeline(
        session_factory=session_factory,
        batch_size=args.batch_size,
        force=args.force,
    )

    await pipeline.run(limit=args.limit, dry_run=args.dry_run)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
