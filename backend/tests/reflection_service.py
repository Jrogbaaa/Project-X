"""
LLM Reflection Service for validating search results against brand briefs.

Uses GPT-4o to analyze whether returned influencers actually match the 
original brief's requirements (niche, brand fit, creative concept).
"""
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal
from openai import AsyncOpenAI

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.schemas.llm import ParsedSearchQuery
from app.schemas.influencer import RankedInfluencer

logger = logging.getLogger(__name__)


@dataclass
class InfluencerEvaluation:
    """Evaluation of a single influencer against the brief."""
    username: str
    rank: int
    niche_match: float  # 0-1 scale
    brand_fit: float  # 0-1 scale
    creative_fit: float  # 0-1 scale
    overall_match: float  # 0-1 scale
    verdict: Literal["excellent", "good", "acceptable", "poor", "fail"]
    issues: List[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class ReflectionVerdict:
    """Overall evaluation of search results against the brief."""
    overall_quality: Literal["excellent", "good", "acceptable", "poor", "fail"]
    niche_alignment: float  # 0-1 average across results
    brand_fit: float  # 0-1 average
    creative_fit: float  # 0-1 average
    coverage_score: float  # 0-1 how well results cover the request
    
    evaluations: List[InfluencerEvaluation] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    # Specific failure checks
    niche_violations: List[str] = field(default_factory=list)  # e.g., football influencer for padel
    excluded_niche_violations: List[str] = field(default_factory=list)  # influencers in excluded niches
    brand_conflicts: List[str] = field(default_factory=list)  # competitor ambassadors
    
    reasoning: str = ""


REFLECTION_SYSTEM_PROMPT = """You are an expert evaluator for influencer marketing campaigns. Your job is to analyze whether the search results match the original campaign brief.

## Evaluation Criteria

### 1. Niche Alignment (0-1 scale)
IMPORTANT: Use "Interests" field when "Primary Niche" is Unknown. Many influencers have interests like "Sports", "Tennis", "Fitness" but no explicit niche.

- 1.0: Perfect match (influencer's niche matches campaign niche exactly)
- 0.7-0.9: Related niche (e.g., tennis influencer for padel campaign)
- 0.5-0.7: Creative match (e.g., fitness influencer for sports brand - they share athletic audience)
- 0.4-0.5: Loosely related (e.g., general lifestyle for specific niche)
- 0.1-0.3: Poor match (e.g., fashion-only influencer for sports campaign)
- 0.0: Conflicting niche (e.g., football player for a padel campaign that explicitly excludes football)

**Creative Matching Logic:**
- Padel brand → Tennis, Fitness, Sports influencers are GOOD matches (score 0.6-0.8)
- Healthy food brand → Fitness, Health, Wellness influencers are GOOD matches
- Home furniture → Lifestyle, Family, Parenting influencers are GOOD matches
- Use the "Interests" field to determine fit when "Primary Niche" is Unknown

### 2. Brand Fit (0-1 scale)
- 1.0: Perfect fit (no conflicts, aligns with brand values)
- 0.7-0.9: Good fit (minor concerns)
- 0.4-0.6: Neutral (no obvious conflicts)
- 0.1-0.3: Potential conflict (competitor association)
- 0.0: Direct conflict (known competitor ambassador)

### 3. Creative Fit (0-1 scale)
- 1.0: Perfect match to creative concept/tone
- 0.7-0.9: Good alignment
- 0.4-0.6: Neutral/unknown
- 0.1-0.3: Misaligned tone/style
- 0.0: Opposite of requested creative direction

### 4. Coverage Score (0-1 scale)
- How well does the result set fulfill the request?
- Did we get the requested count?
- Did we respect gender splits if requested?
- Are results diverse enough?

## CRITICAL CHECKS

1. **Excluded Niche Violations**: If the brief says "no football influencers" and a result is a football player, this is a MAJOR failure.

2. **Competitor Conflicts**: If the brief is for Nike and an influencer is an Adidas ambassador, flag this.

3. **Niche Mismatches**: A home decor campaign should NOT return fitness influencers as top results.

## Output Format

Provide a JSON response with:
- overall_quality: "excellent", "good", "acceptable", "poor", or "fail"
- niche_alignment: 0-1 average
- brand_fit: 0-1 average  
- creative_fit: 0-1 average
- coverage_score: 0-1
- evaluations: Array of per-influencer evaluations
- issues: List of problems found
- suggestions: How to improve results
- niche_violations: Specific niche mismatches
- excluded_niche_violations: Influencers in explicitly excluded niches
- brand_conflicts: Competitor or conflict issues
- reasoning: Brief explanation

Be STRICT. If a padel campaign returns soccer players, that's a FAIL."""


REFLECTION_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "reflection_verdict",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "overall_quality": {
                    "type": "string",
                    "enum": ["excellent", "good", "acceptable", "poor", "fail"],
                    "description": "Overall quality rating"
                },
                "niche_alignment": {
                    "type": "number",
                    "description": "Average niche alignment score (0-1)"
                },
                "brand_fit": {
                    "type": "number",
                    "description": "Average brand fit score (0-1)"
                },
                "creative_fit": {
                    "type": "number",
                    "description": "Average creative fit score (0-1)"
                },
                "coverage_score": {
                    "type": "number",
                    "description": "How well results cover the request (0-1)"
                },
                "evaluations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string"},
                            "rank": {"type": "integer"},
                            "niche_match": {"type": "number"},
                            "brand_fit": {"type": "number"},
                            "creative_fit": {"type": "number"},
                            "overall_match": {"type": "number"},
                            "verdict": {
                                "type": "string",
                                "enum": ["excellent", "good", "acceptable", "poor", "fail"]
                            },
                            "issues": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "reasoning": {"type": "string"}
                        },
                        "required": ["username", "rank", "niche_match", "brand_fit", "creative_fit", "overall_match", "verdict", "issues", "reasoning"],
                        "additionalProperties": False
                    },
                    "description": "Per-influencer evaluations"
                },
                "issues": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Overall issues found"
                },
                "suggestions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Suggestions for improvement"
                },
                "niche_violations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific niche mismatches"
                },
                "excluded_niche_violations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Influencers in explicitly excluded niches"
                },
                "brand_conflicts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Competitor or brand conflict issues"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of the evaluation"
                }
            },
            "required": [
                "overall_quality",
                "niche_alignment",
                "brand_fit",
                "creative_fit",
                "coverage_score",
                "evaluations",
                "issues",
                "suggestions",
                "niche_violations",
                "excluded_niche_violations",
                "brand_conflicts",
                "reasoning"
            ],
            "additionalProperties": False
        }
    }
}


class ReflectionService:
    """Service for validating search results using LLM reflection."""
    
    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
    
    async def reflect_on_results(
        self,
        original_brief: str,
        parsed_query: ParsedSearchQuery,
        results: List[RankedInfluencer],
        max_results_to_evaluate: int = 10
    ) -> ReflectionVerdict:
        """
        Analyze search results against the original brief using GPT-4o.
        
        Args:
            original_brief: The raw natural language brief
            parsed_query: The parsed query structure
            results: The ranked influencer results
            max_results_to_evaluate: Maximum results to send to LLM (cost control)
            
        Returns:
            ReflectionVerdict with detailed evaluation
        """
        # Prepare context for LLM
        results_to_eval = results[:max_results_to_evaluate]
        
        context = self._build_evaluation_context(
            original_brief, parsed_query, results_to_eval
        )
        
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": REFLECTION_SYSTEM_PROMPT},
                    {"role": "user", "content": context}
                ],
                response_format=REFLECTION_RESPONSE_FORMAT,
                temperature=0.2,  # Slightly higher for nuanced evaluation
                max_tokens=2000,
            )
            
            response_text = completion.choices[0].message.content
            if not response_text:
                return self._create_error_verdict("Empty response from LLM")
            
            parsed_data = json.loads(response_text)
            return self._parse_verdict(parsed_data)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse reflection response: {e}")
            return self._create_error_verdict(f"JSON parse error: {e}")
        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return self._create_error_verdict(str(e))
    
    def _build_evaluation_context(
        self,
        brief: str,
        parsed_query: ParsedSearchQuery,
        results: List[RankedInfluencer]
    ) -> str:
        """Build the context string for LLM evaluation."""
        
        # Get discovery interests if available
        discovery_interests = getattr(parsed_query, 'discovery_interests', []) or []
        exclude_interests = getattr(parsed_query, 'exclude_interests', []) or []
        influencer_reasoning = getattr(parsed_query, 'influencer_reasoning', '') or ''
        
        # Build parsed query summary
        query_summary = f"""
## Parsed Query
- Brand: {parsed_query.brand_name or 'Not specified'}
- Campaign Niche: {parsed_query.campaign_niche or 'Not specified'}
- Campaign Topics: {', '.join(parsed_query.campaign_topics) if parsed_query.campaign_topics else 'None'}
- Excluded Niches: {', '.join(parsed_query.exclude_niches) if parsed_query.exclude_niches else 'None'}
- Creative Concept: {parsed_query.creative_concept or 'Not specified'}
- Creative Format: {parsed_query.creative_format or 'Not specified'}
- Creative Tone: {', '.join(parsed_query.creative_tone) if parsed_query.creative_tone else 'None'}
- Creative Themes: {', '.join(parsed_query.creative_themes) if parsed_query.creative_themes else 'None'}
- Target Count: {parsed_query.target_count}
- Target Male Count: {parsed_query.target_male_count or 'Not specified'}
- Target Female Count: {parsed_query.target_female_count or 'Not specified'}

## Creative Discovery Strategy
- Discovery Interests: {', '.join(discovery_interests) if discovery_interests else 'Not specified'}
- Exclude Interests: {', '.join(exclude_interests) if exclude_interests else 'None'}
- Influencer Reasoning: {influencer_reasoning or 'Not specified'}

NOTE: Influencers matching the "Discovery Interests" above are VALID matches even if their primary niche differs from campaign niche. For example, if campaign_niche is "padel" but discovery_interests includes ["Sports", "Tennis", "Fitness"], then fitness influencers are GOOD matches.
"""
        
        # Build results summary
        results_lines = []
        for i, r in enumerate(results, 1):
            raw = r.raw_data
            if raw:
                niche = getattr(raw, 'primary_niche', None) or "Unknown"
                interests_list = getattr(raw, 'interests', []) or []
                interests = ", ".join(interests_list[:3]) if interests_list else "Unknown"
                followers = getattr(raw, 'follower_count', 0) or 0
                bio = (getattr(raw, 'bio', '') or "")[:100]
                detected_brands_list = getattr(raw, 'detected_brands', []) or []
                detected_brands = ", ".join(detected_brands_list[:3]) if detected_brands_list else "None"
            else:
                niche = "Unknown"
                interests = "Unknown"
                followers = 0
                bio = ""
                detected_brands = "None"
            
            results_lines.append(f"""
### Result {i}: @{r.username}
- Rank: {r.rank_position}
- Relevance Score: {r.relevance_score:.3f}
- Primary Niche: {niche}
- Interests: {interests}
- Followers: {followers:,}
- Bio: {bio}
- Detected Brands: {detected_brands}
- Score Breakdown:
  - Niche Match: {r.scores.niche_match:.2f}
  - Brand Affinity: {r.scores.brand_affinity:.2f}
  - Creative Fit: {r.scores.creative_fit:.2f}
  - Engagement: {r.scores.engagement:.2f}
  - Credibility: {r.scores.credibility:.2f}
""")
        
        results_section = "\n".join(results_lines)
        
        return f"""## Original Brief
{brief}

{query_summary}

## Search Results ({len(results)} results returned)
{results_section}

## Your Task
Evaluate each result against the original brief. Consider:
1. Niche alignment - does the influencer match via primary_niche OR interests? Check "Discovery Interests" above.
2. Excluded niches - are any influencers in niches that should be EXCLUDED? (e.g., Soccer for padel campaign)
3. Brand fit - are there any competitor conflicts?
4. Creative fit - does the influencer's style match the requested tone?

CRITICAL: If "Discovery Interests" are specified, influencers matching those interests are VALID matches. For example:
- Padel campaign with Discovery Interests ["Sports", "Tennis", "Fitness"] → Fitness influencers are GOOD (score 0.6-0.7)
- Only flag as FAIL if influencer is in an EXCLUDED interest category (e.g., Soccer for padel)

If primary_niche is Unknown, use the Interests field to determine fit.
"""
    
    def _parse_verdict(self, data: Dict[str, Any]) -> ReflectionVerdict:
        """Parse LLM response into ReflectionVerdict."""
        evaluations = []
        for eval_data in data.get("evaluations", []):
            evaluations.append(InfluencerEvaluation(
                username=eval_data["username"],
                rank=eval_data["rank"],
                niche_match=eval_data["niche_match"],
                brand_fit=eval_data["brand_fit"],
                creative_fit=eval_data["creative_fit"],
                overall_match=eval_data["overall_match"],
                verdict=eval_data["verdict"],
                issues=eval_data.get("issues", []),
                reasoning=eval_data.get("reasoning", ""),
            ))
        
        return ReflectionVerdict(
            overall_quality=data["overall_quality"],
            niche_alignment=data["niche_alignment"],
            brand_fit=data["brand_fit"],
            creative_fit=data["creative_fit"],
            coverage_score=data["coverage_score"],
            evaluations=evaluations,
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            niche_violations=data.get("niche_violations", []),
            excluded_niche_violations=data.get("excluded_niche_violations", []),
            brand_conflicts=data.get("brand_conflicts", []),
            reasoning=data.get("reasoning", ""),
        )
    
    def _create_error_verdict(self, error: str) -> ReflectionVerdict:
        """Create a verdict for error cases."""
        return ReflectionVerdict(
            overall_quality="fail",
            niche_alignment=0.0,
            brand_fit=0.0,
            creative_fit=0.0,
            coverage_score=0.0,
            issues=[f"Reflection failed: {error}"],
            suggestions=["Fix the reflection service error"],
            reasoning=f"Could not complete reflection: {error}",
        )


# Convenience function
async def reflect_on_results(
    original_brief: str,
    parsed_query: ParsedSearchQuery,
    results: List[RankedInfluencer],
    max_results: int = 10
) -> ReflectionVerdict:
    """Convenience function to create service and reflect."""
    service = ReflectionService()
    return await service.reflect_on_results(
        original_brief, parsed_query, results, max_results
    )


def print_reflection_report(verdict: ReflectionVerdict) -> str:
    """Generate a human-readable report from a reflection verdict."""
    lines = [
        "",
        "=" * 70,
        "  REFLECTION REPORT",
        "=" * 70,
        "",
        f"Overall Quality: {verdict.overall_quality.upper()}",
        "",
        "Scores (0-1 scale):",
        f"  - Niche Alignment: {verdict.niche_alignment:.2f}",
        f"  - Brand Fit:       {verdict.brand_fit:.2f}",
        f"  - Creative Fit:    {verdict.creative_fit:.2f}",
        f"  - Coverage:        {verdict.coverage_score:.2f}",
        "",
    ]
    
    if verdict.niche_violations:
        lines.append("⚠️  NICHE VIOLATIONS:")
        for v in verdict.niche_violations:
            lines.append(f"    - {v}")
        lines.append("")
    
    if verdict.excluded_niche_violations:
        lines.append("🚫 EXCLUDED NICHE VIOLATIONS:")
        for v in verdict.excluded_niche_violations:
            lines.append(f"    - {v}")
        lines.append("")
    
    if verdict.brand_conflicts:
        lines.append("❌ BRAND CONFLICTS:")
        for c in verdict.brand_conflicts:
            lines.append(f"    - {c}")
        lines.append("")
    
    if verdict.issues:
        lines.append("Issues Found:")
        for issue in verdict.issues:
            lines.append(f"  - {issue}")
        lines.append("")
    
    if verdict.suggestions:
        lines.append("Suggestions:")
        for sug in verdict.suggestions:
            lines.append(f"  - {sug}")
        lines.append("")
    
    lines.append("-" * 70)
    lines.append("Per-Influencer Evaluations:")
    lines.append("-" * 70)
    
    for eval in verdict.evaluations:
        status_emoji = {
            "excellent": "✅",
            "good": "👍",
            "acceptable": "⚪",
            "poor": "⚠️",
            "fail": "❌",
        }.get(eval.verdict, "❓")
        
        lines.append(f"\n{status_emoji} @{eval.username} (Rank #{eval.rank}) - {eval.verdict.upper()}")
        lines.append(f"   Scores: Niche={eval.niche_match:.2f}, Brand={eval.brand_fit:.2f}, Creative={eval.creative_fit:.2f}")
        lines.append(f"   Overall: {eval.overall_match:.2f}")
        if eval.issues:
            for issue in eval.issues:
                lines.append(f"   ⚠️  {issue}")
        if eval.reasoning:
            lines.append(f"   📝 {eval.reasoning}")
    
    lines.append("")
    lines.append("=" * 70)
    lines.append(f"Reasoning: {verdict.reasoning}")
    lines.append("=" * 70)
    
    return "\n".join(lines)
