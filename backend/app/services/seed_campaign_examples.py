"""
Seed script for campaign_examples knowledge base.

These are ~30 curated, real-world-inspired examples tagged with the Goldenberg
creativity template or other framework they exemplify. They are used as
content-based retrieval context for Idea Match generation.

Run with:
    cd backend && python -m app.services.seed_campaign_examples

Use --clear to wipe existing rows first.
"""

import asyncio
import argparse
import logging
import sys
import os

# Ensure backend package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from app.core.database import get_session_maker

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


CAMPAIGN_EXAMPLES = [
    # ── GOLDENBERG: EXTREME CONSEQUENCE ────────────────────────────────────────
    {
        "brand_name": "Nike",
        "campaign_title": "Just Do It — Limits",
        "category": "sports_apparel",
        "audience": "young_broad",
        "positioning": "performance",
        "price_tier": "premium",
        "platform": ["tv", "youtube", "instagram"],
        "format": "short_film",
        "tone": ["inspirational", "bold", "gritty"],
        "archetype": "hero",
        "growth_goal": "awareness",
        "framework_used": "goldenberg_extreme_consequence",
        "creative_angle": "Athletes at the extreme edge of failure — what happens when you stop? The product is the only thing standing between them and collapse.",
        "success_signals": "Consequence of absence dramatised through physical stakes. High emotional impact. 89% recall in award-winning ad category.",
        "tags": ["sports", "motivation", "athlete", "stakes", "running"],
    },
    {
        "brand_name": "Duracell",
        "campaign_title": "The Bunny Never Stops",
        "category": "electronics",
        "audience": "broad",
        "positioning": "mass",
        "price_tier": "mid",
        "platform": ["tv", "youtube"],
        "format": "short_film",
        "tone": ["humorous", "playful"],
        "archetype": "everyman",
        "growth_goal": "awareness",
        "framework_used": "goldenberg_extreme_consequence",
        "creative_angle": "What happens when all other batteries die? The Duracell bunny keeps going long after everything else has stopped.",
        "success_signals": "Extended consequence (competitors dead, brand still running) made the benefit visceral and memorable. Iconic campaign.",
        "tags": ["battery", "longevity", "humour", "comparison"],
    },
    {
        "brand_name": "Volkswagen",
        "campaign_title": "Think Small",
        "category": "automotive",
        "audience": "young_broad",
        "positioning": "challenger",
        "price_tier": "mid",
        "platform": ["ooh", "print"],
        "format": "ooh",
        "tone": ["bold", "authentic", "playful"],
        "archetype": "everyman",
        "growth_goal": "brand_personality",
        "framework_used": "goldenberg_extreme_consequence",
        "creative_angle": "The extreme consequence of American car culture: bloated, expensive, impractical. VW is the antidote. The small car becomes a brave stance.",
        "success_signals": "Consequence of the alternative (big car culture) made VW's smallness a feature, not a flaw. Cultural moment ad.",
        "tags": ["automotive", "challenger", "simplicity", "culture"],
    },

    # ── GOLDENBERG: PICTORIAL ANALOGY ─────────────────────────────────────────
    {
        "brand_name": "The Economist",
        "campaign_title": "Ideas",
        "category": "media",
        "audience": "professional",
        "positioning": "premium",
        "price_tier": "premium",
        "platform": ["ooh"],
        "format": "ooh",
        "tone": ["sophisticated", "bold"],
        "archetype": "sage",
        "growth_goal": "brand_personality",
        "framework_used": "goldenberg_pictorial_analogy",
        "creative_angle": "A lightbulb made of a brain. The product benefit (illuminating ideas) shown as a visual metaphor without words. The analogy IS the concept.",
        "success_signals": "Pure pictorial analogy — no headline needed. Brand personality communicated entirely through image. D&AD winner.",
        "tags": ["media", "intelligence", "simplicity", "visual"],
    },
    {
        "brand_name": "FedEx",
        "campaign_title": "Speed",
        "category": "logistics",
        "audience": "professional",
        "positioning": "performance",
        "price_tier": "premium",
        "platform": ["ooh", "print"],
        "format": "ooh",
        "tone": ["bold", "polished"],
        "archetype": "ruler",
        "growth_goal": "persuasion",
        "framework_used": "goldenberg_pictorial_analogy",
        "creative_angle": "A package with a cheetah's legs underneath it. Speed is shown through analogy — no claim needed. The visual makes the argument.",
        "success_signals": "Pictorial analogy with high conceptual similarity (cheetah = fast delivery). Immediately legible. No copy needed.",
        "tags": ["logistics", "speed", "b2b", "visual"],
    },

    # ── GOLDENBERG: COMPETITION ────────────────────────────────────────────────
    {
        "brand_name": "Apple",
        "campaign_title": "Mac vs PC",
        "category": "tech",
        "audience": "young_broad",
        "positioning": "premium",
        "price_tier": "premium",
        "platform": ["tv", "youtube"],
        "format": "short_film",
        "tone": ["humorous", "bold", "sophisticated"],
        "archetype": "creator",
        "growth_goal": "persuasion",
        "framework_used": "goldenberg_competition",
        "creative_angle": "Two characters represent the products. The contrast is the argument. No specs — just personality difference made human.",
        "success_signals": "Competitive frame made abstract product differences visceral through character. Cannes winner. Drove significant market share shift.",
        "tags": ["tech", "comparison", "humour", "character"],
    },
    {
        "brand_name": "Pepsi",
        "campaign_title": "Pepsi Challenge",
        "category": "beverage",
        "audience": "young_broad",
        "positioning": "challenger",
        "price_tier": "mid",
        "platform": ["tv"],
        "format": "documentary",
        "tone": ["bold", "authentic", "playful"],
        "archetype": "challenger",
        "growth_goal": "awareness",
        "framework_used": "goldenberg_competition",
        "creative_angle": "Real consumers blind-taste-tested in public. The result — Pepsi wins — is revealed on camera. Competitor made to lose by their own audience.",
        "success_signals": "Competitive template with authentic proof. The competition IS the ad. Real people made it credible.",
        "tags": ["beverage", "challenger", "ugc", "proof"],
    },

    # ── GOLDENBERG: INTERACTIVE EXPERIMENT ────────────────────────────────────
    {
        "brand_name": "Red Bull",
        "campaign_title": "Stratos",
        "category": "beverage",
        "audience": "young_male",
        "positioning": "challenger",
        "price_tier": "mid",
        "platform": ["youtube", "tv", "instagram"],
        "format": "stunt",
        "tone": ["bold", "rebellious", "inspirational"],
        "archetype": "explorer",
        "growth_goal": "engagement",
        "framework_used": "goldenberg_interactive_experiment",
        "creative_angle": "Felix Baumgartner jumps from space. The world watches live. The ad IS the event. Audience participation (watching, sharing) is the metric.",
        "success_signals": "8 million simultaneous YouTube viewers. Interactive experiment at global scale. Audience action was the campaign.",
        "tags": ["energy_drink", "stunt", "live_event", "extreme"],
    },
    {
        "brand_name": "Dove",
        "campaign_title": "Real Beauty Sketches",
        "category": "beauty",
        "audience": "broad_female",
        "positioning": "purpose_driven",
        "price_tier": "mid",
        "platform": ["youtube", "instagram"],
        "format": "social_experiment",
        "tone": ["authentic", "warm", "empowering"],
        "archetype": "caregiver",
        "growth_goal": "engagement",
        "framework_used": "goldenberg_interactive_experiment",
        "creative_angle": "Women describe themselves to a forensic artist. The sketch differs from one done by a stranger. The experiment reveals that women see themselves more harshly than others do.",
        "success_signals": "Most watched ad of all time (2013). The experiment IS the insight. Audience participation through sharing made it a cultural moment.",
        "tags": ["beauty", "self-image", "women", "social_experiment"],
    },
    {
        "brand_name": "IKEA",
        "campaign_title": "Cook This Page",
        "category": "home_decor",
        "audience": "millennial",
        "positioning": "accessible_luxury",
        "price_tier": "mid",
        "platform": ["instagram", "digital"],
        "format": "interactive",
        "tone": ["playful", "warm", "authentic"],
        "archetype": "creator",
        "growth_goal": "engagement",
        "framework_used": "goldenberg_interactive_experiment",
        "creative_angle": "A magazine spread you cook on. Lay it flat on a baking tray, add ingredients shown on the page, bake. The ad becomes the recipe.",
        "success_signals": "The audience action IS the ad. Interactive print that worked as a real cooking guide. High social sharing.",
        "tags": ["home", "cooking", "interactive", "print"],
    },

    # ── GOLDENBERG: DIMENSIONAL ALTERATION ────────────────────────────────────
    {
        "brand_name": "Bose",
        "campaign_title": "Quiet Comfort",
        "category": "tech",
        "audience": "professional",
        "positioning": "premium",
        "price_tier": "premium",
        "platform": ["ooh", "instagram"],
        "format": "ooh",
        "tone": ["sophisticated", "bold"],
        "archetype": "ruler",
        "growth_goal": "persuasion",
        "framework_used": "goldenberg_dimensional_alteration",
        "creative_angle": "The noise being cancelled is shown magnified to enormous scale — a visual representation of what the headphones remove. Dimension (sound) shown as physical mass.",
        "success_signals": "Product benefit made tangible through scale distortion. Dimensional alteration of an invisible attribute (noise) into something visible.",
        "tags": ["tech", "audio", "noise_cancellation", "visual"],
    },
    {
        "brand_name": "Colgate",
        "campaign_title": "Net Effect",
        "category": "beauty",
        "audience": "broad",
        "positioning": "mass",
        "price_tier": "budget",
        "platform": ["ooh"],
        "format": "ooh",
        "tone": ["bold", "clean"],
        "archetype": "caregiver",
        "growth_goal": "persuasion",
        "framework_used": "goldenberg_dimensional_alteration",
        "creative_angle": "The toothbrush bristles magnified to reveal a net that catches bacteria. Product dimension (bristles) enlarged to communicate the mechanism of benefit.",
        "success_signals": "Dimensional magnification of the product mechanism. Made an invisible benefit (bacteria-catching) visually obvious.",
        "tags": ["health", "dental", "magnification", "benefit"],
    },

    # ── GOLDENBERG: REPLACEMENT ────────────────────────────────────────────────
    {
        "brand_name": "Old Spice",
        "campaign_title": "The Man Your Man Could Smell Like",
        "category": "beauty",
        "audience": "broad",
        "positioning": "challenger",
        "price_tier": "mid",
        "platform": ["tv", "youtube"],
        "format": "short_film",
        "tone": ["humorous", "bold", "playful"],
        "archetype": "jester",
        "growth_goal": "brand_personality",
        "framework_used": "goldenberg_replacement",
        "creative_angle": "One product replaces everything: the boat, the horse, the diamonds. Old Spice replaces the entire concept of masculinity — and does it absurdly.",
        "success_signals": "Replacement template applied to brand archetype. The product literally replaced aspirational objects. Campaign reversed years of decline.",
        "tags": ["grooming", "humour", "masculine", "absurdist"],
    },
    {
        "brand_name": "Burger King",
        "campaign_title": "Mouldy Whopper",
        "category": "food",
        "audience": "young_broad",
        "positioning": "challenger",
        "price_tier": "budget",
        "platform": ["instagram", "youtube", "tv"],
        "format": "short_film",
        "tone": ["bold", "rebellious", "authentic"],
        "archetype": "challenger",
        "growth_goal": "brand_personality",
        "framework_used": "goldenberg_replacement",
        "creative_angle": "A Whopper aged 34 days, shown in full decay. Mould replaces the idea of 'appetising food'. The decay proves the lack of preservatives. Repulsion IS the message.",
        "success_signals": "Replacement of visual appeal with evidence of authenticity. Cannes Grand Prix. Drove significant conversation about food quality.",
        "tags": ["food", "authenticity", "challenger", "bold"],
    },

    # ── REPETITION-BREAK ───────────────────────────────────────────────────────
    {
        "brand_name": "Guinness",
        "campaign_title": "Surfer",
        "category": "alcoholic_beverages",
        "audience": "young_male",
        "positioning": "heritage",
        "price_tier": "mid",
        "platform": ["tv"],
        "format": "short_film",
        "tone": ["bold", "gritty", "inspirational"],
        "archetype": "hero",
        "growth_goal": "engagement",
        "framework_used": "repetition_break",
        "creative_angle": "Surfers wait. Surfers wait. Surfers wait. The wave comes. They ride. 'Good things come to those who wait.' Pattern of waiting broken by the moment of action.",
        "success_signals": "Classic repetition-break structure. Pattern (waiting) repeated 3 times. Break (the ride) is the reward. 'Best ad of all time' in many polls.",
        "tags": ["beer", "patience", "storytelling", "narrative"],
    },
    {
        "brand_name": "John Lewis",
        "campaign_title": "The Long Wait",
        "category": "retail",
        "audience": "family",
        "positioning": "heritage",
        "price_tier": "premium",
        "platform": ["tv", "youtube"],
        "format": "short_film",
        "tone": ["warm", "inspirational", "polished"],
        "archetype": "caregiver",
        "growth_goal": "engagement",
        "framework_used": "repetition_break",
        "creative_angle": "A boy waits impatiently for Christmas — we assume it's to get gifts. Break: he wakes early to give a gift to his parents. The expectation (getting) is broken by the reveal (giving).",
        "success_signals": "Repetition-break with emotional misdirection. The audience's assumption is the pattern; the break recontextualises everything.",
        "tags": ["retail", "christmas", "emotion", "storytelling"],
    },
    {
        "brand_name": "Always",
        "campaign_title": "#LikeAGirl",
        "category": "beauty",
        "audience": "young_female",
        "positioning": "purpose_driven",
        "price_tier": "mid",
        "platform": ["youtube", "tv"],
        "format": "social_experiment",
        "tone": ["empowering", "authentic", "bold"],
        "archetype": "caregiver",
        "growth_goal": "engagement",
        "framework_used": "repetition_break",
        "creative_angle": "Adults and boys act out 'like a girl' (mocking). Break: young girls show what it actually looks like. The pattern of the phrase is broken by its reclamation.",
        "success_signals": "The repeated assumption (like a girl = weakness) is broken by the reveal. Cultural reframing through repetition-break narrative.",
        "tags": ["femcare", "empowerment", "social_experiment", "gender"],
    },

    # ── VISUAL METAPHOR ────────────────────────────────────────────────────────
    {
        "brand_name": "WWF",
        "campaign_title": "Endangered Species",
        "category": "nonprofit",
        "audience": "broad",
        "positioning": "purpose_driven",
        "price_tier": "budget",
        "platform": ["ooh"],
        "format": "ooh",
        "tone": ["bold", "raw"],
        "archetype": "caregiver",
        "growth_goal": "persuasion",
        "framework_used": "visual_metaphor",
        "creative_angle": "An endangered animal's silhouette made from the shape of human footprints. The cause (human impact on animals) expressed through a single visual metaphor.",
        "success_signals": "High conceptual similarity between elements (human prints = habitat destruction). Metaphor legible instantly. No copy needed.",
        "tags": ["nonprofit", "environment", "visual", "impact"],
    },
    {
        "brand_name": "Adidas",
        "campaign_title": "Impossible is Nothing",
        "category": "sports_apparel",
        "audience": "young_broad",
        "positioning": "performance",
        "price_tier": "premium",
        "platform": ["tv", "instagram"],
        "format": "documentary",
        "tone": ["inspirational", "authentic", "gritty"],
        "archetype": "hero",
        "growth_goal": "persuasion",
        "framework_used": "visual_metaphor",
        "creative_angle": "Athletes' greatest achievements visualised as impossible physical feats — a runner carrying the weight of doubt, a boxer fighting their past self.",
        "success_signals": "Visual metaphor connects abstract values (overcoming impossible) to physical athletic imagery. Conceptually coherent — both involve physical striving.",
        "tags": ["sports", "motivation", "athlete", "achievement"],
    },

    # ── SCHEMA CONGRUITY ───────────────────────────────────────────────────────
    {
        "brand_name": "Liquid Death",
        "campaign_title": "Murder Your Thirst",
        "category": "beverage",
        "audience": "gen_z",
        "positioning": "challenger",
        "price_tier": "mid",
        "platform": ["tiktok", "instagram", "youtube"],
        "format": "ugc",
        "tone": ["rebellious", "humorous", "bold", "edgy"],
        "archetype": "jester",
        "growth_goal": "brand_personality",
        "framework_used": "schema_congruity",
        "creative_angle": "Water packaged and marketed like heavy metal beer. The schema (premium canned water) violates the expected (boring health product). Moderate incongruity = highly shareable.",
        "success_signals": "Classic schema congruity — health product with death metal branding. Incongruent enough to be interesting, coherent enough to still sell water.",
        "tags": ["water", "challenger", "gen_z", "subversive"],
    },
    {
        "brand_name": "Patagonia",
        "campaign_title": "Don't Buy This Jacket",
        "category": "fashion",
        "audience": "millennial",
        "positioning": "purpose_driven",
        "price_tier": "premium",
        "platform": ["ooh", "digital"],
        "format": "ooh",
        "tone": ["authentic", "bold", "rebellious"],
        "archetype": "explorer",
        "growth_goal": "brand_personality",
        "framework_used": "schema_congruity",
        "creative_angle": "A full-page ad in the NYT: 'Don't Buy This Jacket.' The schema (brands want you to buy things) is violated by a brand telling you not to buy. Incongruity IS the message.",
        "success_signals": "Schema violation (brand anti-consumerism) perfectly aligned with brand values. Paradox makes it irresistible. Black Friday ad that went viral organically.",
        "tags": ["fashion", "sustainability", "anti-advertising", "bold"],
    },
    {
        "brand_name": "Dollar Shave Club",
        "campaign_title": "Our Blades Are F***ing Great",
        "category": "beauty",
        "audience": "young_male",
        "positioning": "challenger",
        "price_tier": "budget",
        "platform": ["youtube"],
        "format": "short_film",
        "tone": ["humorous", "authentic", "bold", "casual"],
        "archetype": "jester",
        "growth_goal": "awareness",
        "framework_used": "schema_congruity",
        "creative_angle": "CEO walks through warehouse making absurd claims. Violates the expected polished brand video with raw, low-budget honesty. The incongruity is the budget itself.",
        "success_signals": "Schema violation (cheap video for brand launch). Moderate incongruity — too low-fi to be taken seriously, but too well-written to be ignored. 27M views, $1B acquisition.",
        "tags": ["grooming", "challenger", "humour", "ugc_style"],
    },

    # ── ARCHETYPE ──────────────────────────────────────────────────────────────
    {
        "brand_name": "Dove",
        "campaign_title": "Real Beauty",
        "category": "beauty",
        "audience": "broad_female",
        "positioning": "purpose_driven",
        "price_tier": "mid",
        "platform": ["tv", "youtube", "instagram"],
        "format": "documentary",
        "tone": ["authentic", "warm", "empowering"],
        "archetype": "caregiver",
        "growth_goal": "engagement",
        "framework_used": "archetype",
        "creative_angle": "Real women (not models) shown in beauty contexts. The caregiver archetype made the brand a champion of authentic beauty rather than aspirational beauty.",
        "success_signals": "Archetype perfectly aligned with audience identity. Caregiver brand became the anti-beauty standard beauty brand. Sales tripled over a decade.",
        "tags": ["beauty", "authenticity", "women", "self-image"],
    },
    {
        "brand_name": "Harley-Davidson",
        "campaign_title": "Live to Ride",
        "category": "automotive",
        "audience": "young_male",
        "positioning": "heritage",
        "price_tier": "premium",
        "platform": ["tv", "ooh"],
        "format": "short_film",
        "tone": ["bold", "rebellious", "authentic"],
        "archetype": "explorer",
        "growth_goal": "brand_personality",
        "framework_used": "archetype",
        "creative_angle": "The Explorer archetype frames the motorcycle not as transport but as freedom. Every ad shows roads less travelled, sunsets, escape. The brand is identity, not vehicle.",
        "success_signals": "Archetype alignment created a cult brand identity. Harley owners identify as explorers/outlaws. Brand personality stronger than any product claim.",
        "tags": ["automotive", "freedom", "identity", "lifestyle"],
    },
    {
        "brand_name": "Red Bull",
        "campaign_title": "Gives You Wings",
        "category": "beverage",
        "audience": "young_male",
        "positioning": "challenger",
        "price_tier": "mid",
        "platform": ["tv", "instagram", "youtube"],
        "format": "challenge",
        "tone": ["bold", "playful", "inspirational"],
        "archetype": "explorer",
        "growth_goal": "brand_personality",
        "framework_used": "archetype",
        "creative_angle": "Explorer archetype applied to energy. Every sponsored event (cliff diving, F1, skydiving) is an act of exploration. The brand doesn't sell energy — it sells the world of extreme exploration.",
        "success_signals": "Archetype → content strategy → brand category ownership. Red Bull owns 'extreme' completely through consistent archetype expression.",
        "tags": ["energy_drink", "extreme", "explorer", "sports"],
    },

    # ── CROSS-CATEGORY EXAMPLES ────────────────────────────────────────────────
    {
        "brand_name": "Spotify",
        "campaign_title": "Wrapped",
        "category": "tech",
        "audience": "gen_z",
        "positioning": "lifestyle",
        "price_tier": "mid",
        "platform": ["instagram", "tiktok"],
        "format": "ugc",
        "tone": ["playful", "authentic", "bold"],
        "archetype": "creator",
        "growth_goal": "engagement",
        "framework_used": "goldenberg_interactive_experiment",
        "creative_angle": "Each user's year in data becomes their own personalised campaign. They share it. The audience IS the creative. The data experiment creates mass UGC.",
        "success_signals": "Interactive experiment at global scale — every user gets their own version of the ad. Created cultural moment every December.",
        "tags": ["music", "data", "ugc", "personalized"],
    },
    {
        "brand_name": "Airbnb",
        "campaign_title": "Live There",
        "category": "travel",
        "audience": "millennial",
        "positioning": "lifestyle",
        "price_tier": "mid",
        "platform": ["instagram", "youtube"],
        "format": "documentary",
        "tone": ["authentic", "warm", "inspirational"],
        "archetype": "explorer",
        "growth_goal": "persuasion",
        "framework_used": "schema_congruity",
        "creative_angle": "Hotels vs Airbnb: tourists visit, locals live. The schema (travel means sightseeing) is broken by showing what actually living in a place looks like. Moderate incongruity — familiar enough to understand, different enough to want.",
        "success_signals": "Schema congruity against hotel category. The alternative (tourist experience) made to look limiting by contrast.",
        "tags": ["travel", "authentic", "local", "lifestyle"],
    },
    {
        "brand_name": "Gillette",
        "campaign_title": "The Best a Man Can Be",
        "category": "beauty",
        "audience": "broad_male",
        "positioning": "purpose_driven",
        "price_tier": "mid",
        "platform": ["youtube", "tv"],
        "format": "short_film",
        "tone": ["bold", "authentic", "empowering"],
        "archetype": "hero",
        "growth_goal": "brand_personality",
        "framework_used": "repetition_break",
        "creative_angle": "Repeated pattern of toxic male behaviour. Break: men stepping in, doing better. 'The best a man can be' recontextualised from aspirational to behavioural.",
        "success_signals": "Repetition-break with cultural reframing. Controversial (intentionally) — pattern break violated male archetype expectations. Generated enormous conversation.",
        "tags": ["grooming", "masculinity", "purpose_driven", "controversial"],
    },
    {
        "brand_name": "Cadbury",
        "campaign_title": "Gorilla",
        "category": "food",
        "audience": "broad",
        "positioning": "mass",
        "price_tier": "budget",
        "platform": ["tv", "youtube"],
        "format": "short_film",
        "tone": ["playful", "bold", "warm"],
        "archetype": "jester",
        "growth_goal": "engagement",
        "framework_used": "schema_congruity",
        "creative_angle": "A gorilla plays drums to Phil Collins. No product shown for 90 seconds. Schema violation (chocolate ad with no chocolate) creates pure entertainment. The joy IS the brand.",
        "success_signals": "Extreme schema violation (no product, no claim). Worked because moderate incongruity resolved into joy = chocolate's core emotion. Cannes Grand Prix.",
        "tags": ["food", "chocolate", "humour", "entertainment"],
    },
]


async def seed(clear_existing: bool = False) -> None:
    session_maker = get_session_maker()
    async with session_maker() as db:
        if clear_existing:
            logger.info("Clearing existing campaign_examples...")
            await db.execute(text("DELETE FROM campaign_examples"))
            await db.commit()
            logger.info("Cleared.")

        # Check existing count
        result = await db.execute(text("SELECT COUNT(*) FROM campaign_examples"))
        existing = result.scalar()
        logger.info(f"Existing rows: {existing}")

        if existing and not clear_existing:
            logger.info("Examples already seeded. Use --clear to re-seed.")
            return

        logger.info(f"Seeding {len(CAMPAIGN_EXAMPLES)} campaign examples...")

        for i, ex in enumerate(CAMPAIGN_EXAMPLES, 1):
            await db.execute(
                text("""
                    INSERT INTO campaign_examples
                        (brand_name, campaign_title, category, audience, positioning,
                         price_tier, platform, format, tone, archetype, growth_goal,
                         framework_used, creative_angle, success_signals, tags)
                    VALUES
                        (:brand_name, :campaign_title, :category, :audience, :positioning,
                         :price_tier, :platform, :format, :tone, :archetype, :growth_goal,
                         :framework_used, :creative_angle, :success_signals, :tags)
                """),
                {
                    **ex,
                    "platform": ex.get("platform"),
                    "tone": ex.get("tone"),
                    "tags": ex.get("tags"),
                }
            )
            logger.info(f"  [{i}/{len(CAMPAIGN_EXAMPLES)}] {ex['brand_name']} — {ex.get('campaign_title', '')} ({ex['framework_used']})")

        await db.commit()
        logger.info(f"Done. Seeded {len(CAMPAIGN_EXAMPLES)} campaign examples.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed campaign_examples knowledge base")
    parser.add_argument("--clear", action="store_true", help="Clear existing rows before seeding")
    args = parser.parse_args()
    asyncio.run(seed(clear_existing=args.clear))
