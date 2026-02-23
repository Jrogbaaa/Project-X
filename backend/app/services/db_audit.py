"""
DB Coverage Audit — see what % of influencers have each key field populated.

Usage:
    cd backend && python -m app.services.db_audit
"""

import asyncio
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


async def run_audit():
    from app.config import get_settings
    from app.models.influencer import Influencer

    settings = get_settings()

    import ssl
    connect_args = {}
    from app.config import needs_ssl
    if needs_ssl(settings.database_url_raw):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ctx

    engine = create_async_engine(settings.database_url, echo=False, connect_args=connect_args)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Total count
        total = (await session.execute(select(func.count()).select_from(Influencer))).scalar()

        print(f"\n{'='*65}")
        print(f"  INFLUENCER DATABASE AUDIT  —  {total:,} total influencers")
        print(f"{'='*65}")

        # --- Field coverage ---
        fields = [
            ("primary_niche",             "primary_niche IS NOT NULL",             "Niche Match (40% weight)"),
            ("content_themes",            "content_themes IS NOT NULL",            "Creative Fit (35% weight)"),
            ("detected_brands",           "detected_brands IS NOT NULL",           "Brand Affinity (25% weight)"),
            ("credibility_score",         "credibility_score IS NOT NULL",         "Credibility (unused, wt=0)"),
            ("engagement_rate",           "engagement_rate IS NOT NULL",           "Engagement (unused, wt=0)"),
            ("follower_growth_rate_6m",   "follower_growth_rate_6m IS NOT NULL",   "Growth (unused, wt=0)"),
            ("audience_geography",        "audience_geography IS NOT NULL",        "Geography / Spain %"),
            ("audience_genders",          "audience_genders IS NOT NULL",          "Audience gender demo"),
            ("audience_age_distribution", "audience_age_distribution IS NOT NULL", "Audience age demo"),
            ("interests",                 "interests IS NOT NULL",                 "Interests / PrimeTag"),
            ("bio",                       "bio IS NOT NULL AND bio != ''",         "Bio (text for fallback)"),
            ("post_content_aggregated",   "post_content_aggregated IS NOT NULL",   "Post hashtags/keywords"),
            ("follower_count",            "follower_count IS NOT NULL",            "Follower count"),
            ("niche_confidence",          "niche_confidence IS NOT NULL",          "Niche confidence score"),
        ]

        print(f"\n{'Field':<28} {'Populated':>10} {'Null':>8} {'Coverage':>9}   Role")
        print(f"{'-'*28} {'-'*10} {'-'*8} {'-'*9}   {'-'*30}")

        for field, condition, role in fields:
            row = await session.execute(
                text(f"SELECT COUNT(*) FROM influencers WHERE {condition}")
            )
            populated = row.scalar()
            null_count = total - populated
            pct = (populated / total * 100) if total else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            print(f"{field:<28} {populated:>10,} {null_count:>8,} {pct:>8.1f}%   {role}")

        # --- Niche distribution ---
        print(f"\n{'='*65}")
        print("  NICHE DISTRIBUTION  (primary_niche column)")
        print(f"{'='*65}")

        niche_rows = await session.execute(
            text("""
                SELECT primary_niche, COUNT(*) as cnt
                FROM influencers
                WHERE primary_niche IS NOT NULL
                GROUP BY primary_niche
                ORDER BY cnt DESC
                LIMIT 30
            """)
        )
        niches = niche_rows.fetchall()

        if niches:
            print(f"\n  {'Niche':<25} {'Count':>8}   Bar")
            print(f"  {'-'*25} {'-'*8}   {'-'*25}")
            max_count = niches[0][1]
            for niche, cnt in niches:
                bar_len = int(cnt / max_count * 25)
                bar = "█" * bar_len
                print(f"  {niche:<25} {cnt:>8,}   {bar}")
        else:
            print("  No primary_niche values set yet.")

        # --- Interests distribution ---
        print(f"\n{'='*65}")
        print("  TOP INTERESTS  (interests JSONB array)")
        print(f"{'='*65}")

        interest_rows = await session.execute(
            text("""
                SELECT interest, COUNT(*) as cnt
                FROM influencers, jsonb_array_elements_text(interests) AS interest
                WHERE interests IS NOT NULL AND jsonb_typeof(interests) = 'array'
                GROUP BY interest
                ORDER BY cnt DESC
                LIMIT 20
            """)
        )
        interests = interest_rows.fetchall()

        if interests:
            print(f"\n  {'Interest':<25} {'Count':>8}")
            print(f"  {'-'*25} {'-'*8}")
            for interest, cnt in interests:
                print(f"  {interest:<25} {cnt:>8,}")
        else:
            print("  No interests data found.")

        # --- Follower tier breakdown ---
        print(f"\n{'='*65}")
        print("  FOLLOWER TIER BREAKDOWN")
        print(f"{'='*65}")

        tier_rows = await session.execute(
            text("""
                SELECT
                    CASE
                        WHEN follower_count < 50000 THEN 'micro   (<50K)'
                        WHEN follower_count < 500000 THEN 'mid     (50K-500K)'
                        WHEN follower_count < 2000000 THEN 'macro   (500K-2M)'
                        ELSE 'mega    (>2M)'
                    END AS tier,
                    COUNT(*) as cnt
                FROM influencers
                WHERE follower_count IS NOT NULL
                GROUP BY tier
                ORDER BY MIN(follower_count)
            """)
        )
        tiers = tier_rows.fetchall()

        no_follower = (await session.execute(
            text("SELECT COUNT(*) FROM influencers WHERE follower_count IS NULL")
        )).scalar()

        print(f"\n  {'Tier':<22} {'Count':>8}")
        print(f"  {'-'*22} {'-'*8}")
        for tier, cnt in tiers:
            print(f"  {tier:<22} {cnt:>8,}")
        if no_follower:
            print(f"  {'(no follower count)':<22} {no_follower:>8,}")

        # --- Quick health summary ---
        print(f"\n{'='*65}")
        print("  HEALTH SUMMARY")
        print(f"{'='*65}\n")

        has_niche = (await session.execute(
            text("SELECT COUNT(*) FROM influencers WHERE primary_niche IS NOT NULL")
        )).scalar()
        has_all_apify = (await session.execute(
            text("SELECT COUNT(*) FROM influencers WHERE primary_niche IS NOT NULL AND content_themes IS NOT NULL AND detected_brands IS NOT NULL")
        )).scalar()
        has_primetag = (await session.execute(
            text("SELECT COUNT(*) FROM influencers WHERE credibility_score IS NOT NULL AND engagement_rate IS NOT NULL")
        )).scalar()
        has_nothing = (await session.execute(
            text("SELECT COUNT(*) FROM influencers WHERE primary_niche IS NULL AND interests IS NULL AND bio IS NULL")
        )).scalar()

        def pct(n): return f"{n/total*100:.1f}%" if total else "0%"

        print(f"  Full Apify data (niche + themes + brands): {has_all_apify:,} ({pct(has_all_apify)})")
        print(f"  Has primary_niche only:                    {has_niche:,} ({pct(has_niche)})")
        print(f"  Has PrimeTag metrics:                      {has_primetag:,} ({pct(has_primetag)})")
        print(f"  Completely empty (no niche/interests/bio): {has_nothing:,} ({pct(has_nothing)})")
        print(f"\n  Ranking quality estimate:")
        print(f"    High confidence matches:   {has_all_apify:,} ({pct(has_all_apify)}) — uses all 3 top factors")
        print(f"    Medium confidence matches: {has_niche - has_all_apify:,} — has niche, missing themes/brands")
        print(f"    Fallback matches:          {total - has_niche:,} ({pct(total - has_niche)}) — bio/interests keyword matching only")
        print(f"\n{'='*65}\n")

    await engine.dispose()


def main():
    asyncio.run(run_audit())


if __name__ == "__main__":
    main()
