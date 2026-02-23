"""
Match Quality Review — repeatable human review of influencer matching quality.

Runs N random briefs (default 4) from a diverse pool through the full search
pipeline and prints matched influencer results for manual evaluation. No
assertions, no pass/fail — purely diagnostic.

Usage:
    cd backend && python -m app.services.match_quality_review
    cd backend && python -m app.services.match_quality_review --seed 42
    cd backend && python -m app.services.match_quality_review --count 6
    cd backend && python -m app.services.match_quality_review --brief "Find me padel influencers"
    cd backend && python -m app.services.match_quality_review --all
"""
import argparse
import asyncio
import logging
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure backend is on path when run as module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.config import get_settings
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)

# ============================================================
# Brief pool — deliberately diverse and unpredictable
# ============================================================

REVIEW_BRIEF_POOL: List[str] = [
    # --- Messy Spanish agency emails ---
    (
        "Hola equipo!! Os paso el brief de Desigual. Necesitamos 5 perfiles lifestyle/moda "
        "para la campaña de primavera. Chicas entre 25-35 años, audiencia España mínimo 65%. "
        "Que sean auténticas y coloridas, nada de lujo frío. Presupuesto limitado así que "
        "mejor micro o mid (50K-300K). Gracias!!"
    ),
    (
        "Buenas, reenvío el brief de Bimbo. Buscan 4 influencers de comida/recetas para "
        "una campaña de pan de molde integral. Perfil: madres jóvenes que comparten recetas "
        "fáciles y saludables. Audiencia femenina >70%, España >60%. Engagement mínimo 2%. "
        "IMPORTANTE: nada de fitness extremo ni gym bros, es pan de molde no proteína jajaja"
    ),
    (
        "FW: Brief Cupra\n\nNecesitamos 5 perfiles para Cupra Born (coche eléctrico). "
        "Buscamos creadores de contenido de lifestyle urbano, tecnología o motor que hablen "
        "de movilidad sostenible. Hombres 25-40, audiencia España. Tono: moderno, dinámico, "
        "un poco premium pero accesible. Nada de influencers de coches clásicos ni tuning."
    ),
    (
        "Hola! Para la campaña de Camper necesitamos 3 mujeres y 2 hombres. Moda sostenible "
        "y slow fashion. Perfiles creativos, artísticos. Mallorca o Barcelona si es posible. "
        "Seguidores entre 20K-200K. Que no sean los típicos de fast fashion."
    ),
    # --- Casual English ---
    (
        "find me 5 fashion girls for Mango, want them to look effortlessly cool, "
        "like street style bloggers not runway models. Spanish audience obviously. "
        "mid-tier followers, nothing crazy"
    ),
    (
        "Need 4 travel influencers for Iberia airlines summer campaign. People who "
        "actually travel a lot and post about it, not just pose at airports. Mix of "
        "adventure and luxury travel. Spain-based audience but international appeal."
    ),
    (
        "Looking for gaming/tech influencers for a new Razer headset launch in Spain. "
        "3-4 profiles, male-heavy audience, 18-30 age range. Twitch or YouTube crossover "
        "preferred. High engagement, doesn't need to be huge following."
    ),
    (
        "Hey, we need 5 beauty/skincare influencers for Freshly Cosmetics. Natural, "
        "organic vibe. NO heavy makeup looks — we're natural skincare, not glam. "
        "Female audience 80%+, Spain 60%+. Prefer people who actually talk about "
        "ingredients and routines, not just pretty photos."
    ),
    # --- Niche industries ---
    (
        "Buscamos influencers de padel para Head Padel. 4-5 perfiles que realmente "
        "jueguen y hablen de padel. NO futbolistas que juegan padel de vez en cuando. "
        "Audiencia España. Credibilidad alta."
    ),
    (
        "Craft beer campaign for Alhambra Reserva. Need 4 influencers — food, gastro, "
        "or lifestyle. People who appreciate artisan products. NOT fitness or health "
        "accounts. Think: foodies, restaurant reviewers, tapas lovers. 30-45 age demo."
    ),
    (
        "Campaign for Tiendanimal (pet store chain). Need 5 pet influencers — dogs and "
        "cats. Real pet owners who post daily about their animals. Funny, heartwarming "
        "content. Spain-based audience. Micro or mid-tier preferred."
    ),
    (
        "Electric scooter brand Silence needs 3 influencers for urban mobility campaign. "
        "Eco-conscious lifestyle creators. City-based, Madrid or Barcelona preferred. "
        "Sustainability angle. NOT car enthusiasts or petrolheads."
    ),
    # --- Vague / minimal asks ---
    (
        "influencers for a new fintech app launching in Spain"
    ),
    (
        "We need some people for a Coca-Cola Christmas campaign. The usual — happy, "
        "family vibes. Big names if possible."
    ),
    (
        "yoga influencers spain"
    ),
    # --- Overly specific ---
    (
        "3 male micro-influencers in Barcelona who post about sustainable fashion and "
        "have >3% engagement rate. Must have worked with eco brands before. Audience: "
        "70% Spain, 60% male, predominantly 25-34. Credibility above 80%. Absolutely "
        "no fast fashion, no Shein, no Primark collabs."
    ),
    (
        "Necesitamos exactamente 2 macro influencers (500K-1.5M) y 3 mid (100K-400K) "
        "para Decathlon España. Deporte variado: running, senderismo, natación, ciclismo. "
        "Nada de fútbol ni baloncesto. Audiencia 70% España, credibilidad >75%, "
        "engagement >1.5%. Perfil: deportistas reales, no modelos fitness."
    ),
    # --- Edge cases ---
    (
        "Find influencers for a brand called 'Aire'. I won't tell you what they sell — "
        "the system should figure it out. Just search for Aire Spain influencers."
    ),
    (
        "Necesitamos perfiles para una marca de colchones (Flex). Sí, colchones. "
        "Buscamos influencers de lifestyle, hogar, bienestar o incluso humor. "
        "Que puedan hablar de descanso de forma natural. Nada de deporte."
    ),
    (
        "Campaign for Tous jewelry. Need 5 female influencers with a romantic, "
        "feminine aesthetic. Fashion or lifestyle niche. EXCLUDE anyone who posts "
        "about competing jewelry brands like Pandora or Swarovski. Audience: "
        "women 20-40, Spain 65%+."
    ),
    (
        "Hola, para la campaña de Wallapop necesitamos 6 perfiles — 3 chicos y 3 chicas. "
        "Temática: segunda mano, reciclaje, DIY, decoración low cost. Tono divertido y "
        "cercano. Micro-influencers (10K-80K) con mucho engagement. España obviously."
    ),
    (
        "Buscamos 4 influencers de running para Asics. Corredores de verdad — maratones, "
        "trails, media maratón. NO gym, NO crossfit, NO fitness genérico. "
        "Audiencia España >60%, engagement >2%. Entre 30K y 500K seguidores."
    ),
    (
        "Samsung Spain wants 5 tech/lifestyle creators for the new Galaxy phone launch. "
        "Mix of tech reviewers and lifestyle people who use phones creatively "
        "(photography, content creation). NO Apple fanboys obviously. 50K-1M followers."
    ),
]


# ============================================================
# Execution infrastructure
# ============================================================

@dataclass
class BriefResult:
    brief_text: str
    brief_index: int
    response: Optional[SearchResponse] = None
    error: Optional[str] = None
    elapsed_s: float = 0.0


async def _create_session() -> tuple[AsyncSession, any]:
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return factory(), engine


async def _run_brief(brief_text: str, brief_index: int, limit: int = 10) -> BriefResult:
    """Run a single brief through the full search pipeline with its own DB session."""
    session, engine = await _create_session()
    t0 = time.time()
    try:
        svc = SearchService(session)
        request = SearchRequest(query=brief_text, limit=limit)
        response = await svc.execute_search(request)
        return BriefResult(
            brief_text=brief_text,
            brief_index=brief_index,
            response=response,
            elapsed_s=time.time() - t0,
        )
    except Exception as exc:
        logger.error(f"Brief {brief_index} failed: {exc}", exc_info=True)
        return BriefResult(
            brief_text=brief_text,
            brief_index=brief_index,
            error=str(exc),
            elapsed_s=time.time() - t0,
        )
    finally:
        await session.close()
        await engine.dispose()


# ============================================================
# Display helpers
# ============================================================

def _fmt_followers(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n // 1_000}K"
    return str(n)


def _truncate(text: str, length: int = 80) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    return text[:length] + ("..." if len(text) > length else "")


def _print_brief_result(result: BriefResult, total: int) -> None:
    """Print rich output for a single brief result."""
    idx = result.brief_index
    W = 80

    print(f"\n{'=' * W}")
    print(f"  BRIEF {idx}/{total}")
    print(f"{'=' * W}")
    print(f"  \"{_truncate(result.brief_text, 120)}\"")
    print(f"  (elapsed: {result.elapsed_s:.1f}s)")

    if result.error:
        print(f"\n  ERROR: {result.error}")
        print(f"{'=' * W}")
        return

    resp = result.response
    if not resp:
        print(f"\n  No response returned.")
        print(f"{'=' * W}")
        return

    pq = resp.parsed_query

    # -- LLM extraction --
    print(f"\n  LLM EXTRACTION:")
    print(f"    Brand:            {pq.brand_name or '(none)'}")
    print(f"    Brand category:   {pq.brand_category or '(none)'}")
    print(f"    Niche:            {pq.campaign_niche or '(none)'}")
    print(f"    Topics:           {pq.campaign_topics or []}")
    print(f"    Exclude niches:   {pq.exclude_niches or []}")
    print(f"    Target count:     {pq.target_count}")
    fmin = pq.preferred_follower_min
    fmax = pq.preferred_follower_max
    if fmin or fmax:
        print(f"    Followers:        {_fmt_followers(fmin or 0)} – {_fmt_followers(fmax or 0)}")
    print(f"    Gender:           {pq.influencer_gender.value}")
    if pq.target_male_count or pq.target_female_count:
        print(f"    Gender split:     {pq.target_male_count or 0}M / {pq.target_female_count or 0}F")
    tier_dist = pq.get_tier_distribution()
    if tier_dist:
        print(f"    Tier split:       micro={tier_dist['micro']} mid={tier_dist['mid']} macro={tier_dist['macro']}")
    print(f"    Spain min:        {pq.min_spain_audience_pct}%")
    print(f"    Credibility min:  {pq.min_credibility_score}%")
    if pq.min_engagement_rate:
        print(f"    ER min:           {pq.min_engagement_rate}%")
    if pq.creative_tone:
        print(f"    Tone:             {pq.creative_tone}")
    disc = getattr(pq, "discovery_interests", [])
    if disc:
        print(f"    Discovery ints:   {disc}")
    excl = getattr(pq, "exclude_interests", [])
    if excl:
        print(f"    Excl. interests:  {excl}")
    reasoning = getattr(pq, "influencer_reasoning", "") or ""
    if reasoning:
        print(f"    Reasoning:        {_truncate(reasoning, 140)}")

    # -- Discovery funnel --
    print(f"\n  DISCOVERY FUNNEL:")
    print(f"    DB candidates:    {resp.total_candidates}")
    print(f"    After filters:    {resp.total_after_filter}")
    if resp.verification_stats:
        vs = resp.verification_stats
        print(f"    Verified (PT):    {vs.verified}")
        print(f"    Failed verify:    {vs.failed_verification}")
        if vs.rejected_spain_pct:
            print(f"    Rejected (ES%):   {vs.rejected_spain_pct}")
        if vs.rejected_credibility:
            print(f"    Rejected (cred):  {vs.rejected_credibility}")
        if vs.rejected_engagement:
            print(f"    Rejected (ER):    {vs.rejected_engagement}")
    print(f"    Returned:         {len(resp.results)}")

    # -- Influencer table --
    results = resp.results
    if not results:
        print(f"\n  NO INFLUENCERS MATCHED.")
    else:
        print(f"\n  MATCHED INFLUENCERS ({len(results)}):")
        hdr = (
            f"  {'#':<3} {'Username':<24} {'Followers':>10} {'Niche':<18} "
            f"{'ES%':>5} {'Cred':>5} {'ER%':>5} {'Score':>6}  Warnings"
        )
        print(hdr)
        print(f"  {'─' * (len(hdr) - 2)}")

        for i, r in enumerate(results, 1):
            raw = r.raw_data
            fol = _fmt_followers(raw.follower_count or 0)
            niche = (raw.primary_niche or "?")[:17]
            es_pct = raw.audience_geography.get("ES", 0.0) if raw.audience_geography else 0.0
            cred = raw.credibility_score
            er = raw.engagement_rate
            score = f"{r.relevance_score:.2f}"

            warnings = []
            if raw.brand_warning_message:
                warnings.append(raw.brand_warning_message)
            if raw.niche_warning:
                warnings.append(raw.niche_warning)
            warn_str = " | ".join(warnings) if warnings else ""

            es_str = f"{es_pct:.0f}%" if es_pct else "  -"
            cred_str = f"{cred:.0f}%" if cred is not None else "  -"
            er_str = f"{er:.1f}%" if er is not None else "  -"

            print(
                f"  {i:<3} @{r.username:<23} {fol:>10} {niche:<18} "
                f"{es_str:>5} {cred_str:>5} {er_str:>5} {score:>6}  {warn_str}"
            )

        # Score component breakdown for top 3
        print(f"\n  SCORE BREAKDOWN (top 3):")
        print(
            f"  {'Username':<24} {'Cred':>5} {'Eng':>5} {'Aud':>5} "
            f"{'Grow':>5} {'Geo':>5} {'BrAf':>5} {'CrFt':>5} {'Nich':>5}"
        )
        print(f"  {'─' * 69}")
        for r in results[:3]:
            s = r.scores
            print(
                f"  @{r.username:<23} {s.credibility:.2f} {s.engagement:.2f} "
                f"{s.audience_match:.2f} {s.growth:.2f} {s.geography:.2f} "
                f"{s.brand_affinity:.2f} {s.creative_fit:.2f} {s.niche_match:.2f}"
            )

    print(f"\n{'=' * W}")


def _print_summary(results: List[BriefResult]) -> None:
    """Print a compact summary table across all briefs."""
    W = 100
    print(f"\n\n{'━' * W}")
    print(f"  MATCH QUALITY REVIEW — SUMMARY")
    print(f"{'━' * W}")

    hdr = f"  {'#':<3} {'Brand':<18} {'Niche':<16} {'Cands':>6} {'Filt':>6} {'Ret':>4} {'Time':>6}  Status"
    print(hdr)
    print(f"  {'─' * (W - 2)}")

    for r in results:
        idx = r.brief_index
        if r.error:
            print(f"  {idx:<3} {'ERROR':<18} {'':<16} {'':>6} {'':>6} {'':>4} {r.elapsed_s:>5.1f}s  {r.error[:40]}")
            continue
        if not r.response:
            print(f"  {idx:<3} {'NO RESPONSE':<18}")
            continue

        resp = r.response
        pq = resp.parsed_query
        brand = (pq.brand_name or "?")[:17]
        niche = (pq.campaign_niche or "?")[:15]
        cands = resp.total_candidates
        filt = resp.total_after_filter
        ret = len(resp.results)
        status = "OK" if ret > 0 else "EMPTY"

        print(
            f"  {idx:<3} {brand:<18} {niche:<16} {cands:>6} {filt:>6} {ret:>4} "
            f"{r.elapsed_s:>5.1f}s  {status}"
        )

    total_time = sum(r.elapsed_s for r in results)
    ok_count = sum(1 for r in results if r.response and len(r.response.results) > 0)
    print(f"\n  Briefs with results: {ok_count}/{len(results)}")
    print(f"  Total wall time:    {total_time:.1f}s (parallel, so actual ~{max(r.elapsed_s for r in results):.1f}s)")
    print(f"{'━' * W}\n")


# ============================================================
# Main entry point
# ============================================================

async def run_review(
    briefs: List[str],
    limit: int = 10,
) -> List[BriefResult]:
    """Run all briefs in parallel and print results."""
    total = len(briefs)
    print(f"\n{'━' * 80}")
    print(f"  MATCH QUALITY REVIEW — {total} briefs")
    print(f"{'━' * 80}\n")
    for i, b in enumerate(briefs, 1):
        print(f"  [{i}] {_truncate(b, 90)}")
    print()

    tasks = [_run_brief(b, i, limit=limit) for i, b in enumerate(briefs, 1)]
    results = await asyncio.gather(*tasks)

    for r in results:
        _print_brief_result(r, total)

    _print_summary(results)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Match Quality Review — run diverse briefs through the search pipeline for human review"
    )
    parser.add_argument(
        "--count", "-n", type=int, default=4,
        help="Number of random briefs to run (default: 4)",
    )
    parser.add_argument(
        "--seed", "-s", type=int, default=None,
        help="Random seed for reproducible brief selection",
    )
    parser.add_argument(
        "--brief", "-b", type=str, default=None,
        help="Run a single custom brief instead of random selection",
    )
    parser.add_argument(
        "--all", "-a", action="store_true",
        help="Run ALL briefs in the pool",
    )
    parser.add_argument(
        "--limit", "-l", type=int, default=10,
        help="Max influencers to return per brief (default: 10)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.brief:
        briefs = [args.brief]
    elif args.all:
        briefs = list(REVIEW_BRIEF_POOL)
    else:
        if args.seed is not None:
            random.seed(args.seed)
        count = min(args.count, len(REVIEW_BRIEF_POOL))
        briefs = random.sample(REVIEW_BRIEF_POOL, count)

    asyncio.run(run_review(briefs, limit=args.limit))


if __name__ == "__main__":
    main()
