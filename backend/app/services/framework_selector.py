"""
Framework Selector

Deterministic mapping from brand attributes (growth_goal, archetype) to
the creative advertising frameworks that should guide idea generation.

Based on research from creative_advertising_frameworks_summary.txt:
  - Templates (Goldenberg's 6) → strongest general framework, 89% of award-winning ads
  - Repetition-Break → best for engagement campaigns
  - Visual Metaphor → best for product persuasion (when conceptually coherent)
  - Archetype → best for brand personality communication
  - Schema Congruity → moderate incongruity → highest persuasion

From recommendation_summaries_from_3_pdfs.txt:
  - Retrieval should improve idea quality, not replace reasoning
  - Framework selection is deterministic based on brand attributes
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ── Framework keys ───────────────────────────────────────────────────────────

GOLDENBERG_EXTREME_CONSEQUENCE = "goldenberg_extreme_consequence"
GOLDENBERG_PICTORIAL_ANALOGY = "goldenberg_pictorial_analogy"
GOLDENBERG_COMPETITION = "goldenberg_competition"
GOLDENBERG_INTERACTIVE_EXPERIMENT = "goldenberg_interactive_experiment"
GOLDENBERG_DIMENSIONAL_ALTERATION = "goldenberg_dimensional_alteration"
GOLDENBERG_REPLACEMENT = "goldenberg_replacement"
REPETITION_BREAK = "repetition_break"
VISUAL_METAPHOR = "visual_metaphor"
SCHEMA_CONGRUITY = "schema_congruity"
ARCHETYPE = "archetype"


# ── Framework evidence scores (from research doc) ────────────────────────────
# Indexed by framework key → {awareness, engagement, persuasion, brand_personality}

FRAMEWORK_EVIDENCE_SCORES: dict[str, dict[str, float]] = {
    GOLDENBERG_EXTREME_CONSEQUENCE:    {"awareness": 0.88, "engagement": 0.72, "persuasion": 0.80, "brand_personality": 0.65},
    GOLDENBERG_PICTORIAL_ANALOGY:      {"awareness": 0.82, "engagement": 0.68, "persuasion": 0.75, "brand_personality": 0.78},
    GOLDENBERG_COMPETITION:            {"awareness": 0.85, "engagement": 0.70, "persuasion": 0.80, "brand_personality": 0.60},
    GOLDENBERG_INTERACTIVE_EXPERIMENT: {"awareness": 0.78, "engagement": 0.92, "persuasion": 0.68, "brand_personality": 0.72},
    GOLDENBERG_DIMENSIONAL_ALTERATION: {"awareness": 0.85, "engagement": 0.70, "persuasion": 0.72, "brand_personality": 0.68},
    GOLDENBERG_REPLACEMENT:            {"awareness": 0.80, "engagement": 0.72, "persuasion": 0.82, "brand_personality": 0.70},
    REPETITION_BREAK:                  {"awareness": 0.50, "engagement": 0.90, "persuasion": 0.80, "brand_personality": 0.75},
    VISUAL_METAPHOR:                   {"awareness": 0.65, "engagement": 0.60, "persuasion": 0.85, "brand_personality": 0.70},
    SCHEMA_CONGRUITY:                  {"awareness": 0.60, "engagement": 0.70, "persuasion": 0.85, "brand_personality": 0.65},
    ARCHETYPE:                         {"awareness": 0.70, "engagement": 0.85, "persuasion": 0.65, "brand_personality": 0.92},
}


# ── Primary framework selection by growth goal ────────────────────────────────
# Each goal maps to an ordered list of preferred frameworks.
# The first 3 are "primary" (must be used); any remaining are "secondary" (bonus ideas).

FRAMEWORK_SELECTION_BY_GOAL: dict[str, List[str]] = {
    "awareness": [
        GOLDENBERG_EXTREME_CONSEQUENCE,   # shows high stakes → visceral impact
        GOLDENBERG_DIMENSIONAL_ALTERATION, # magnification of product benefit
        GOLDENBERG_COMPETITION,            # superiority contrast
        REPETITION_BREAK,                  # secondary: pattern surprise aids recall
    ],
    "engagement": [
        REPETITION_BREAK,                  # narrative surprise → highest engagement score
        GOLDENBERG_INTERACTIVE_EXPERIMENT, # audience participation IS the ad
        ARCHETYPE,                         # emotional identity resonance
        GOLDENBERG_EXTREME_CONSEQUENCE,    # secondary: stakes drive action
    ],
    "persuasion": [
        VISUAL_METAPHOR,                   # product benefit = visual concept
        SCHEMA_CONGRUITY,                  # moderate incongruity → highest persuasion
        GOLDENBERG_REPLACEMENT,            # product replaces familiar object logically
        GOLDENBERG_PICTORIAL_ANALOGY,      # secondary: analogy for benefit clarity
    ],
    "brand_personality": [
        ARCHETYPE,                         # identity definition
        GOLDENBERG_PICTORIAL_ANALOGY,      # brand = character/concept
        REPETITION_BREAK,                  # narrative voice
        SCHEMA_CONGRUITY,                  # secondary: moderate incongruity signals personality
    ],
}

# Default fallback if growth_goal is unknown
_DEFAULT_FRAMEWORKS = [
    GOLDENBERG_EXTREME_CONSEQUENCE,
    REPETITION_BREAK,
    ARCHETYPE,
    VISUAL_METAPHOR,
]


# ── Archetype tone modifiers ──────────────────────────────────────────────────
# These don't change which frameworks are used but instruct the LLM on how to
# apply them — the emotional register within each template.

ARCHETYPE_TONE_MODIFIERS: dict[str, str] = {
    "hero":       "Apply each framework through the lens of stakes, triumph, and overcoming obstacles. The product enables peak performance.",
    "explorer":   "Apply each framework through discovery, contrast between ordinary and extraordinary, and transformation. The product opens new worlds.",
    "caregiver":  "Apply each framework through protection, consequence of absence, and emotional warmth. The product keeps people safe or cared for.",
    "everyman":   "Apply each framework with relatability and modest incongruity. Avoid high-gloss aesthetics. The product is for real people.",
    "creator":    "Apply each framework through craft, process, and dimensional alteration. The product enables creation.",
    "ruler":      "Apply each framework through authority, polished execution, and competitive contrast. The product defines the category.",
    "lover":      "Apply each framework through desire, beauty, and sensory experience. The product evokes longing.",
    "jester":     "Apply each framework through humour, surprise, and subverted expectations. The product doesn't take itself seriously.",
    "challenger": "Apply each framework aggressively — extreme consequences against the establishment, replacement of tired conventions. The product disrupts.",
    "sage":       "Apply each framework through insight, clarity, and dimensional alteration of complexity. The product makes the complicated simple.",
    "magician":   "Apply each framework through transformation and before/after contrast. The product creates visible change.",
    "innocent":   "Apply each framework through simplicity, warmth, and schema congruity. The product is pure and wholesome.",
}

_DEFAULT_ARCHETYPE_MODIFIER = "Apply each framework with a clear, authentic voice that matches the brand's category and audience."


# ── Selection result ──────────────────────────────────────────────────────────

@dataclass
class FrameworkSelection:
    frameworks: List[str]               # ordered: primary first, secondary last
    primary_frameworks: List[str]       # first 3 — must all be used
    bold_bet_framework: str             # least-used / most surprising for this brand
    archetype_modifier: str             # tone instruction for the LLM
    rationale: str                      # why these frameworks for this brand


def select_frameworks(
    growth_goal: Optional[str],
    archetype: Optional[str],
    category: Optional[str] = None,
) -> FrameworkSelection:
    """
    Deterministically select creative frameworks for a brand based on its
    growth goal and archetype.

    Args:
        growth_goal: "awareness" | "engagement" | "persuasion" | "brand_personality"
        archetype: "hero" | "explorer" | "caregiver" | "everyman" | "creator" | etc.
        category: optional brand category for rationale text

    Returns:
        FrameworkSelection with ordered frameworks and tone guidance
    """
    goal = (growth_goal or "engagement").lower().strip()

    # Normalise common synonyms
    _goal_aliases = {
        "brand awareness": "awareness",
        "recognition": "awareness",
        "reach": "awareness",
        "engagement": "engagement",
        "interaction": "engagement",
        "viral": "engagement",
        "conversion": "persuasion",
        "sales": "persuasion",
        "purchase": "persuasion",
        "brand identity": "brand_personality",
        "personality": "brand_personality",
        "positioning": "brand_personality",
    }
    goal = _goal_aliases.get(goal, goal)
    if goal not in FRAMEWORK_SELECTION_BY_GOAL:
        goal = "engagement"  # safe default

    frameworks = FRAMEWORK_SELECTION_BY_GOAL[goal]
    primary = frameworks[:3]

    # Bold bet: a framework NOT in the primary set for this goal
    all_frameworks = list(FRAMEWORK_EVIDENCE_SCORES.keys())
    non_primary = [f for f in all_frameworks if f not in primary]
    # Pick the one with highest score for this goal among non-primary
    bold_bet = max(non_primary, key=lambda f: FRAMEWORK_EVIDENCE_SCORES[f].get(goal, 0))

    arch = (archetype or "everyman").lower().strip()
    tone_modifier = ARCHETYPE_TONE_MODIFIERS.get(arch, _DEFAULT_ARCHETYPE_MODIFIER)

    cat_desc = f" for a {category} brand" if category else ""
    rationale = (
        f"Growth goal is '{goal}'{cat_desc}. "
        f"Primary frameworks: {', '.join(primary)}. "
        f"Archetype '{arch}' modifies how each template is applied: {tone_modifier[:80]}..."
    )

    return FrameworkSelection(
        frameworks=frameworks,
        primary_frameworks=primary,
        bold_bet_framework=bold_bet,
        archetype_modifier=tone_modifier,
        rationale=rationale,
    )


def get_engagement_potential(framework: str, growth_goal: str) -> float:
    """
    Return the research-backed engagement potential score for a framework
    given the campaign's growth goal. Used in post-generation ranking.
    """
    scores = FRAMEWORK_EVIDENCE_SCORES.get(framework, {})
    return scores.get(growth_goal, 0.65)  # default to neutral if unknown
