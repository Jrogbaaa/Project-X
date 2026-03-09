"""
Idea Match Service

Orchestrates the full pipeline for generating structured creative advertising ideas:

  Layer 1 — Brand Understanding: extract structured brand attributes via LLM
  Layer 2 — Framework Selection: deterministic mapping from growth_goal + archetype
  Layer 3 — Retrieval: content-based filtering of campaign_examples knowledge base
  Layer 4 — Prompt Construction: assemble brand attrs + frameworks + retrieved examples
  Layer 5 — Idea Generation: GPT-5.4 generates structured creative brief
  Layer 6 — Ranking: score each idea and sort by weighted composite

Design notes:
  - retrieval improves idea quality; it does not replace LLM reasoning
  - frameworks guide ideation through proven Goldenberg templates + narrative structures
  - the LLM must reason through named templates, not brainstorm freely
  - outputs are persisted in idea_briefs table for history
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_session_maker
from app.services.framework_selector import (
    FrameworkSelection,
    get_engagement_potential,
    select_frameworks,
    GOLDENBERG_EXTREME_CONSEQUENCE,
    GOLDENBERG_PICTORIAL_ANALOGY,
    GOLDENBERG_COMPETITION,
    GOLDENBERG_INTERACTIVE_EXPERIMENT,
    GOLDENBERG_DIMENSIONAL_ALTERATION,
    GOLDENBERG_REPLACEMENT,
    REPETITION_BREAK,
    VISUAL_METAPHOR,
    SCHEMA_CONGRUITY,
    ARCHETYPE,
)

logger = logging.getLogger(__name__)


# ── Brand attribute extraction prompt ────────────────────────────────────────

_BRAND_EXTRACTION_SYSTEM = """You are a brand analyst. Given a brand name (and optional brief context), extract structured brand attributes.

Return valid JSON with these fields:
- brand_name: Official brand name
- category: Business category — one of: sports_apparel, fashion, beauty, skincare, food, beverage, alcoholic_beverages, tech, gaming, home_decor, automotive, travel, fitness, wellness, luxury, retail, finance, entertainment, media, pet, other
- audience: Primary audience descriptor — one of: young_male, young_female, young_broad, gen_z, millennial, family, professional, broad, luxury_consumer, mass_market
- positioning: Brand positioning — one of: challenger, premium, mass, lifestyle, purpose_driven, performance, luxury, accessible_luxury, heritage, innovation
- tone: Array of 2-4 tone words from: authentic, inspirational, bold, gritty, humorous, luxury, edgy, casual, polished, raw, warm, playful, rebellious, sophisticated, empowering
- visual_style: One of: high_contrast_cinematic, clean_minimal, warm_lifestyle, dark_editorial, bright_playful, documentary_raw, luxury_glossy, ugc_authentic
- price_tier: One of: budget, mid, premium, luxury
- platform_focus: Array of platforms from: instagram, tiktok, youtube, twitter, tv, ooh, digital
- product_benefit: Core product/service benefit in 3-5 words (e.g. "peak athletic performance", "effortless home style")
- growth_goal: Primary marketing goal — one of: awareness, engagement, persuasion, brand_personality
- archetype: Brand archetype — one of: hero, explorer, caregiver, everyman, creator, ruler, lover, jester, challenger, sage, magician, innocent
- description: One-sentence brand description
- competitors: Array of 3-5 competitor brand names
- confidence: 0.0-1.0

If you don't know the brand well, make your best inference from the name and set confidence accordingly."""

_BRAND_EXTRACTION_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "brand_attributes",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "brand_name": {"type": "string"},
                "category": {"type": "string"},
                "audience": {"type": "string"},
                "positioning": {"type": "string"},
                "tone": {"type": "array", "items": {"type": "string"}},
                "visual_style": {"type": "string"},
                "price_tier": {"type": "string"},
                "platform_focus": {"type": "array", "items": {"type": "string"}},
                "product_benefit": {"type": "string"},
                "growth_goal": {"type": "string"},
                "archetype": {"type": "string"},
                "description": {"type": "string"},
                "competitors": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "number"},
            },
            "required": [
                "brand_name", "category", "audience", "positioning", "tone",
                "visual_style", "price_tier", "platform_focus", "product_benefit",
                "growth_goal", "archetype", "description", "competitors", "confidence"
            ],
            "additionalProperties": False,
        }
    }
}


# ── Goldenberg template definitions (encoded for LLM) ────────────────────────

_GOLDENBERG_BLOCK = """
GOLDENBERG CREATIVITY TEMPLATES — USE THESE TO STRUCTURE IDEAS:

These templates are found in 89% of award-winning advertisements. Every idea you generate MUST be traceable to one named template.

1. EXTREME CONSEQUENCE (goldenberg_extreme_consequence)
   Show what happens when the product is absent, or what extreme outcome the product enables.
   Exaggerate the consequence to make the benefit visceral and undeniable.
   Example: absence of running shoes → athlete's feet leave cracks in pavement; deodorant → office spontaneously evacuates.

2. PICTORIAL ANALOGY (goldenberg_pictorial_analogy)
   Replace the product or its key attribute with a visual metaphor that communicates
   the core benefit without literally showing the product.
   Example: battery life shown as a marathon runner mid-stride; insurance shown as a literal safety net.

3. COMPETITION (goldenberg_competition)
   Directly or indirectly contrast the brand against an alternative.
   Show the inferiority of the alternative through visual or narrative contrast.
   Example: only the brand's product survives an extreme scenario; comparison leaves competitor unnamed but obvious.

4. INTERACTIVE EXPERIMENT (goldenberg_interactive_experiment)
   Invite the audience to participate, test, or try something.
   The audience action IS the ad. The engagement is the message itself.
   Example: "pour it on yourself" waterproofing challenge; a map challenge where runners unlock zones.

5. DIMENSIONAL ALTERATION (goldenberg_dimensional_alteration)
   Magnify, shrink, multiply, or distort a product dimension to dramatize its significance.
   Example: a filter shown 1000x magnified to show what it catches; mattress springs shown as full city buildings.

6. REPLACEMENT (goldenberg_replacement)
   The product replaces a familiar object in an unexpected but logically coherent way.
   Example: deodorant replaces a fire extinguisher in a locker room; headphones replace a concert venue.

ADDITIONAL FRAMEWORKS:

7. REPETITION-BREAK (repetition_break)
   Narrative structure: establish a repeating pattern → repeat it → break it with a surprising twist.
   Best for engagement campaigns. Higher brand attitudes and purchase intentions but lower recall.
   Example: three athletes fail, get up, fail — twist: they were training, not competing.

8. VISUAL METAPHOR (visual_metaphor)
   Synthesize the product with a conceptually SIMILAR (not dissimilar) object to communicate benefit.
   Only works when the objects are conceptually close. Dissimilar synthesis causes confusion.
   Example: protein powder + iron weights fused into one; car tyres drawn as city roads.

9. SCHEMA CONGRUITY (schema_congruity)
   Slightly violate audience expectations — enough to surprise but not confuse.
   Too predictable → boring. Too incongruent → confusing. Moderate incongruity = highest persuasion.
   Example: an athlete shown doing nothing (rest day positioning); luxury brand using lo-fi UGC.

10. ARCHETYPE (archetype)
    Position the brand through a classic narrative archetype that resonates with audience identity.
    Hero, Explorer, Caregiver, Everyman, Creator, Ruler, Lover, Jester, Challenger, Sage, Magician, Innocent.
    Example: Nike = Hero; Patagonia = Explorer; Dove = Caregiver; Old Spice = Jester.

RULES:
- EVERY idea must name one template and explain WHY it fits this specific brand.
- Do NOT combine templates in one idea unless they reinforce each other naturally.
- Do NOT generate generic "brand awareness campaigns" — every idea needs a specific structural logic.
- The "bold bet" idea should use the least-obvious template for this brand category.
"""


# ── Idea generation prompt ────────────────────────────────────────────────────

def _build_generation_system_prompt(selection: FrameworkSelection) -> str:
    return f"""You are a senior creative strategist and art director with 20 years of award-winning advertising experience.

You generate advertising ideas using structured creative frameworks — not free brainstorming.
Every idea must trace back to a named template with a clear structural logic.

{_GOLDENBERG_BLOCK}

SOCIAL MEDIA CONSTRAINT — THIS IS NON-NEGOTIABLE:
ALL ideas must be designed for social media or YouTube. Think:
- TikTok / Instagram Reels (15-60 seconds)
- YouTube Shorts (up to 60 seconds) or YouTube mid-roll (30-90 seconds max)
- Instagram carousels (swipeable images/frames)
- Stories (vertical, ephemeral)
- UGC / creator briefs

Do NOT generate TV commercials, brand films, documentaries, or long-form productions.
These are influencer/social campaigns. Every concept should be describable in one vertical video or one swipe-through carousel.

FRAMEWORK SELECTION FOR THIS BRIEF:
The following frameworks have been selected based on the brand's growth goal and archetype.
{selection.rationale}

ARCHETYPE TONE MODIFIER:
{selection.archetype_modifier}

PRIMARY FRAMEWORKS (you MUST generate at least one idea using each of these):
{', '.join(selection.primary_frameworks)}

BOLD BET FRAMEWORK (use for the final "bold bet" idea — higher risk, higher originality):
{selection.bold_bet_framework}

OUTPUT FORMAT: Return valid JSON matching the IdeaBrief schema exactly."""


def _build_generation_user_prompt(
    brand_attrs: Dict[str, Any],
    retrieved_examples: List[Dict[str, Any]],
) -> str:
    examples_text = ""
    if retrieved_examples:
        examples_text = "\n\nRETRIEVED INSPIRATION (analogous real campaigns — do NOT copy, use as creative reference only):\n"
        for i, ex in enumerate(retrieved_examples, 1):
            examples_text += (
                f"\n{i}. {ex['brand_name']} — \"{ex.get('campaign_title', 'Campaign')}\"\n"
                f"   Category: {ex['category']} | Framework: {ex['framework_used']}\n"
                f"   What worked: {ex.get('creative_angle', '')}\n"
                f"   Success signal: {ex.get('success_signals', '')}\n"
            )

    return f"""BRAND INPUT:
Brand: {brand_attrs['brand_name']}
Category: {brand_attrs['category']}
Audience: {brand_attrs['audience']}
Positioning: {brand_attrs['positioning']}
Tone: {', '.join(brand_attrs.get('tone', []))}
Visual style: {brand_attrs.get('visual_style', 'unspecified')}
Price tier: {brand_attrs['price_tier']}
Platforms: {', '.join(brand_attrs.get('platform_focus', []))}
Core product benefit: {brand_attrs['product_benefit']}
Growth goal: {brand_attrs['growth_goal']}
Brand archetype: {brand_attrs['archetype']}
Competitors: {', '.join(brand_attrs.get('competitors', [])[:3])}
{examples_text}

Generate a structured creative brief with:

1. brand_vertical: 2-sentence description of the brand's market position and what makes it distinctive
2. brand_summary: 1-sentence core brand truth (the insight that all ideas should stem from)
3. archetype: the brand archetype name
4. archetype_rationale: 2-3 sentences on why this archetype fits and what it unlocks creatively
5. ideas: array of 4-5 campaign ideas. Each idea MUST use one of the primary frameworks and include:
   - title: punchy campaign name (3-7 words)
   - concept: 4-5 sentences — specific enough to brief a social media creator or content studio. Describe: (1) what happens in the first 3 seconds to stop the scroll, (2) the visual mechanics of the template in action, (3) the CTA or ending beat. Think vertical video or swipeable carousel, not a film narrative.
   - format: one of reel | tiktok_video | youtube_short | carousel | ugc | challenge | story | social_experiment | stunt | interactive
   - platforms: array of best platforms for this idea
   - tone: array of 2-3 tone descriptors for this specific idea
   - framework_used: the exact framework key (e.g. "goldenberg_extreme_consequence")
   - framework_rationale: 1-2 sentences on why THIS template is the right structure for THIS brand
   - avoid: what would make this idea fail (1-2 sentences — be specific)
   - engagement_type: one of awareness | engagement | persuasion | brand_personality
   IMPORTANT: Each idea must demonstrate a specific, non-obvious application of its template to THIS brand. Generic "show the product being used" is NOT a valid template application. The template's structural logic must be clearly visible in the concept.
6. bold_bet: one additional idea that is higher risk, higher originality — uses {brand_attrs.get('archetype', 'an unexpected')} archetype in a subversive way or applies a template in a non-obvious category application. Same structure as ideas array items.

The concepts should feel like they came from a real creative pitch — specific, visual, and grounded in a strategic truth about the brand."""


# ── Ranking ───────────────────────────────────────────────────────────────────

_FORMAT_FEASIBILITY: dict[str, float] = {
    "reel": 0.95,
    "ugc": 0.95,
    "tiktok_video": 0.93,
    "youtube_short": 0.90,
    "story": 0.90,
    "carousel": 0.88,
    "challenge": 0.88,
    "testimonial": 0.85,
    "social_experiment": 0.80,
    "stunt": 0.65,
    "interactive": 0.65,
    # Legacy fallback — penalise if LLM ignores the social media constraint
    "short_film": 0.35,
    "documentary": 0.25,
    "ooh": 0.30,
}


def _score_idea(
    idea: Dict[str, Any],
    brand_attrs: Dict[str, Any],
    all_ideas: List[Dict[str, Any]],
) -> Dict[str, float]:
    """Score a single idea on 5 dimensions. Returns dict with scores + weighted total."""
    growth_goal = brand_attrs.get("growth_goal", "engagement")
    framework = idea.get("framework_used", "")
    fmt = idea.get("format", "")
    engagement_type = idea.get("engagement_type", "")

    # 1. Brand fit: does the idea's engagement_type match the brand's growth_goal?
    brand_fit = 8.5 if engagement_type == growth_goal else 6.5
    # Bonus if the idea's tone overlaps with the brand's tone
    idea_tone = set(t.lower() for t in idea.get("tone", []))
    brand_tone = set(t.lower() for t in brand_attrs.get("tone", []))
    if idea_tone & brand_tone:
        brand_fit = min(10.0, brand_fit + 0.8)

    # 2. Originality: penalise if another idea uses the same framework
    framework_counts = {}
    for other in all_ideas:
        fw = other.get("framework_used", "")
        framework_counts[fw] = framework_counts.get(fw, 0) + 1
    usage_count = framework_counts.get(framework, 1)
    originality = max(4.0, 9.5 - (usage_count - 1) * 2.0)

    # 3. Strategic relevance: framework research score for this growth goal
    strategic_relevance = get_engagement_potential(framework, growth_goal) * 10

    # 4. Feasibility: based on production format
    feasibility = _FORMAT_FEASIBILITY.get(fmt, 0.70) * 10

    # 5. Engagement potential: framework evidence score for the idea's own engagement_type
    engagement_potential = get_engagement_potential(framework, engagement_type) * 10

    # Weighted composite (weights from plan)
    total = (
        brand_fit * 0.30
        + strategic_relevance * 0.25
        + originality * 0.20
        + engagement_potential * 0.15
        + feasibility * 0.10
    )

    return {
        "brand_fit": round(brand_fit, 1),
        "originality": round(originality, 1),
        "strategic_relevance": round(strategic_relevance, 1),
        "feasibility": round(feasibility, 1),
        "engagement_potential": round(engagement_potential, 1),
        "total": round(total, 1),
    }


def _rank_brief(raw: Dict[str, Any], brand_attrs: Dict[str, Any]) -> Dict[str, Any]:
    """Attach scores to all ideas and sort main ideas by total score descending."""
    all_ideas = raw.get("ideas", []) + ([raw["bold_bet"]] if raw.get("bold_bet") else [])

    scored_ideas = []
    for idea in raw.get("ideas", []):
        idea["score"] = _score_idea(idea, brand_attrs, all_ideas)
        scored_ideas.append(idea)

    # Sort main ideas by score descending
    scored_ideas.sort(key=lambda x: x["score"]["total"], reverse=True)
    raw["ideas"] = scored_ideas

    # Score bold bet separately (don't include in sort pool)
    if raw.get("bold_bet"):
        raw["bold_bet"]["score"] = _score_idea(raw["bold_bet"], brand_attrs, all_ideas)

    return raw


# ── Retrieval (content-based filtering) ──────────────────────────────────────

async def _retrieve_similar_campaigns(
    brand_attrs: Dict[str, Any],
    session: AsyncSession,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Content-based filtering: retrieve campaign_examples that best match brand attributes.
    Scoring: category (+3), growth_goal (+3), archetype (+2), positioning (+2), tone (+1 each), platform (+1 each).
    Returns top-N with framework diversity enforced (max 2 per framework).
    """
    result = await session.execute(
        text("""
            SELECT id, brand_name, campaign_title, category, audience, positioning,
                   price_tier, platform, format, tone, archetype, growth_goal,
                   framework_used, creative_angle, success_signals, tags
            FROM campaign_examples
            ORDER BY id
        """)
    )
    rows = result.mappings().all()

    if not rows:
        return []

    category = brand_attrs.get("category", "")
    growth_goal = brand_attrs.get("growth_goal", "")
    archetype = brand_attrs.get("archetype", "")
    positioning = brand_attrs.get("positioning", "")
    brand_tone = set(t.lower() for t in brand_attrs.get("tone", []))
    brand_platforms = set(p.lower() for p in brand_attrs.get("platform_focus", []))

    scored: List[tuple[int, dict]] = []
    for row in rows:
        score = 0
        r = dict(row)

        if r.get("category", "").lower() == category.lower():
            score += 3
        if r.get("growth_goal", "").lower() == growth_goal.lower():
            score += 3
        if r.get("archetype", "").lower() == archetype.lower():
            score += 2
        if r.get("positioning", "").lower() == positioning.lower():
            score += 2

        row_tone = set(t.lower() for t in (r.get("tone") or []))
        score += len(row_tone & brand_tone)

        row_platforms = set(p.lower() for p in (r.get("platform") or []))
        if row_platforms & brand_platforms:
            score += 1

        scored.append((score, r))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Enforce framework diversity: max 2 examples per framework
    results: List[Dict[str, Any]] = []
    framework_seen: Dict[str, int] = {}
    for _score, row in scored:
        fw = row.get("framework_used", "")
        if framework_seen.get(fw, 0) >= 2:
            continue
        framework_seen[fw] = framework_seen.get(fw, 0) + 1
        results.append(row)
        if len(results) >= limit:
            break

    return results


# ── Main service ──────────────────────────────────────────────────────────────

class IdeaMatchService:
    def __init__(self):
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    async def generate(
        self,
        brand_input: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Full pipeline: brand input → structured creative brief with scored ideas.

        Args:
            brand_input: Raw brand name or brief text from user
            db: Async DB session for retrieval + persistence

        Returns:
            Dict matching IdeaBrief schema
        """
        logger.info(f"[IdeaMatch] Starting generation for: '{brand_input}'")

        # ── Layer 1: Extract brand attributes ─────────────────────────────────
        logger.info("[IdeaMatch] Layer 1: Extracting brand attributes...")
        brand_attrs = await self._extract_brand_attributes(brand_input)
        logger.info(
            f"[IdeaMatch] Brand: {brand_attrs['brand_name']} | "
            f"Category: {brand_attrs['category']} | "
            f"Archetype: {brand_attrs['archetype']} | "
            f"Goal: {brand_attrs['growth_goal']}"
        )

        # ── Layer 2: Select frameworks ────────────────────────────────────────
        logger.info("[IdeaMatch] Layer 2: Selecting frameworks...")
        selection = select_frameworks(
            growth_goal=brand_attrs.get("growth_goal"),
            archetype=brand_attrs.get("archetype"),
            category=brand_attrs.get("category"),
        )
        logger.info(f"[IdeaMatch] Frameworks: {selection.primary_frameworks} | Bold bet: {selection.bold_bet_framework}")

        # ── Layer 3: Retrieve similar campaigns ───────────────────────────────
        logger.info("[IdeaMatch] Layer 3: Retrieving similar campaigns...")
        retrieved = await _retrieve_similar_campaigns(brand_attrs, db)
        logger.info(f"[IdeaMatch] Retrieved {len(retrieved)} campaign examples")

        # ── Layer 4 + 5: Build prompt + generate ideas ────────────────────────
        logger.info("[IdeaMatch] Layers 4-5: Generating creative brief via LLM...")
        system_prompt = _build_generation_system_prompt(selection)
        user_prompt = _build_generation_user_prompt(brand_attrs, retrieved)

        raw_brief = await self._call_llm_generation(system_prompt, user_prompt)

        # ── Layer 6: Rank ideas ───────────────────────────────────────────────
        logger.info("[IdeaMatch] Layer 6: Ranking ideas...")
        ranked_brief = _rank_brief(raw_brief, brand_attrs)

        # Attach metadata
        ranked_brief["brand_attributes"] = brand_attrs
        ranked_brief["frameworks_selected"] = selection.frameworks
        ranked_brief["retrieved_examples_count"] = len(retrieved)

        # ── Persist ───────────────────────────────────────────────────────────
        brief_id = str(uuid.uuid4())
        ranked_brief["id"] = brief_id
        retrieved_ids = [str(r.get("id", "")) for r in retrieved]

        await self._persist_brief(
            brief_id=brief_id,
            brand_input=brand_input,
            brand_attrs=brand_attrs,
            frameworks=selection.frameworks,
            retrieved_ids=retrieved_ids,
            brief=ranked_brief,
            db=db,
        )

        logger.info(f"[IdeaMatch] Done. Brief ID: {brief_id}")
        return ranked_brief

    async def _extract_brand_attributes(self, brand_input: str) -> Dict[str, Any]:
        """Call LLM to extract structured brand attributes from raw input."""
        try:
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": _BRAND_EXTRACTION_SYSTEM},
                    {"role": "user", "content": f"Extract brand attributes for: {brand_input}"},
                ],
                response_format=_BRAND_EXTRACTION_RESPONSE_FORMAT,
                temperature=0.2,
                max_completion_tokens=600,
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception as e:
            logger.error(f"[IdeaMatch] Brand extraction failed: {e}")
            # Minimal fallback
            return {
                "brand_name": brand_input,
                "category": "other",
                "audience": "broad",
                "positioning": "mass",
                "tone": ["authentic"],
                "visual_style": "clean_minimal",
                "price_tier": "mid",
                "platform_focus": ["instagram"],
                "product_benefit": "quality products",
                "growth_goal": "engagement",
                "archetype": "everyman",
                "description": f"{brand_input} brand",
                "competitors": [],
                "confidence": 0.2,
            }

    async def _call_llm_generation(
        self, system_prompt: str, user_prompt: str
    ) -> Dict[str, Any]:
        """Call LLM to generate the structured creative brief."""
        response_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "idea_brief",
                "strict": False,  # Allow flexible idea counts
                "schema": {
                    "type": "object",
                    "properties": {
                        "brand_vertical": {"type": "string"},
                        "brand_summary": {"type": "string"},
                        "archetype": {"type": "string"},
                        "archetype_rationale": {"type": "string"},
                        "ideas": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "concept": {"type": "string"},
                                    "format": {"type": "string"},
                                    "platforms": {"type": "array", "items": {"type": "string"}},
                                    "tone": {"type": "array", "items": {"type": "string"}},
                                    "framework_used": {"type": "string"},
                                    "framework_rationale": {"type": "string"},
                                    "avoid": {"type": "string"},
                                    "engagement_type": {"type": "string"},
                                },
                            }
                        },
                        "bold_bet": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "concept": {"type": "string"},
                                "format": {"type": "string"},
                                "platforms": {"type": "array", "items": {"type": "string"}},
                                "tone": {"type": "array", "items": {"type": "string"}},
                                "framework_used": {"type": "string"},
                                "framework_rationale": {"type": "string"},
                                "avoid": {"type": "string"},
                                "engagement_type": {"type": "string"},
                            }
                        },
                    },
                    "required": ["brand_vertical", "brand_summary", "archetype", "archetype_rationale", "ideas", "bold_bet"],
                }
            }
        }

        response = await self.client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=response_schema,
            temperature=0.75,  # Slightly higher for creative generation
            max_completion_tokens=3000,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    async def _persist_brief(
        self,
        brief_id: str,
        brand_input: str,
        brand_attrs: Dict[str, Any],
        frameworks: List[str],
        retrieved_ids: List[str],
        brief: Dict[str, Any],
        db: AsyncSession,
    ) -> None:
        """Persist the generated brief to idea_briefs table."""
        try:
            await db.execute(
                text("""
                    INSERT INTO idea_briefs
                        (id, brand_input, brand_attributes, frameworks_selected, retrieved_example_ids, brief, created_at)
                    VALUES
                        (:id, :brand_input, :brand_attributes::jsonb, :frameworks_selected, :retrieved_example_ids, :brief::jsonb, now())
                """),
                {
                    "id": brief_id,
                    "brand_input": brand_input,
                    "brand_attributes": json.dumps(brand_attrs),
                    "frameworks_selected": frameworks,
                    "retrieved_example_ids": retrieved_ids,
                    "brief": json.dumps(brief),
                },
            )
            await db.commit()
        except Exception as e:
            logger.error(f"[IdeaMatch] Failed to persist brief: {e}")
            # Don't raise — generation succeeded, persistence is best-effort


# ── Singleton ─────────────────────────────────────────────────────────────────

_service: Optional[IdeaMatchService] = None


def get_idea_match_service() -> IdeaMatchService:
    global _service
    if _service is None:
        _service = IdeaMatchService()
    return _service
