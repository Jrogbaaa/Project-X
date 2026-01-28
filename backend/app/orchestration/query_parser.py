import json
from openai import AsyncOpenAI
from typing import Optional

from app.config import get_settings
from app.schemas.llm import ParsedSearchQuery, GenderFilter
from app.core.exceptions import LLMParsingError


SYSTEM_PROMPT = """You are a search query parser for an influencer discovery platform focused on the Spanish market.

Your job is to extract structured search parameters from natural language brand briefs and queries. Talent agents paste in campaign briefs containing brand info, creative concepts, and search criteria.

## Extraction Guidelines

### Brand Information
1. Extract brand_name (e.g., "Adidas", "Nike", "IKEA")
2. Infer brand_handle - the brand's social media handle (e.g., "@adidas", "@nike", "@ikea")
3. Infer brand_category from the brand name

Brand category mappings:
- IKEA, furniture stores -> home_furniture
- Zara, H&M, fashion brands -> fashion
- Nike, Adidas, Puma -> sports_apparel
- L'Oreal, beauty brands -> beauty
- Tech companies -> technology
- Food/restaurant brands -> food_lifestyle
- Fitness brands -> health_fitness
- Travel brands -> travel_lifestyle

### Creative Concept Extraction
Extract the creative/campaign concept if described:
1. creative_concept: The full campaign idea or creative brief
2. creative_tone: Style keywords like "authentic", "humorous", "luxury", "edgy", "casual", "documentary", "inspirational", "gritty", "polished", "raw"
3. creative_themes: Key values/themes like "dedication", "family", "adventure", "innovation", "rising stars", "everyday heroes", "transformation"

### Niche/Topic Targeting
1. campaign_topics: Specific niches relevant to the campaign (e.g., "padel", "tennis", "skincare", "cooking")
2. exclude_niches: Niches to AVOID - important for precision (e.g., for a padel campaign, exclude "soccer", "football" to avoid famous soccer players)

### Size Preferences (Anti-Celebrity Bias)
If the brief indicates preference for mid-tier influencers or avoiding mega-celebrities:
- preferred_follower_min: Minimum follower count (e.g., 100000 for "100K+")
- preferred_follower_max: Maximum follower count (e.g., 2000000 to avoid mega-celebrities)

### Gender-Specific Counts
When the brief specifies separate male and female requirements (e.g., "3 male, 3 female influencers" or "we need 5 women and 5 men"):
- target_male_count: Number of male influencers specifically requested
- target_female_count: Number of female influencers specifically requested
- These allow returning a split list (e.g., 10 males + 10 females = 20 results with 3x headroom)
- Only set these if EXPLICIT gender counts are mentioned; do NOT set if just "10 influencers"

### Default Settings
1. Default to Spanish audience focus (min 60% Spain audience)
2. Default credibility threshold is 70%
3. If no count is specified, default to 5 influencers

### Ranking Weight Suggestions
Consider the context when suggesting ranking weights:
- Fashion/beauty brands: higher engagement weight
- B2B/professional brands: higher credibility weight
- Viral campaigns: higher growth weight
- Local businesses: higher geography weight
- When brand_handle is provided: higher brand_affinity weight
- When creative_concept is provided: higher creative_fit weight
- When campaign_topics specified: higher niche_match weight

### Search Keywords
Provide keywords that would help find relevant influencer usernames:
- Niche-specific terms (e.g., "padel", "tenis" for racket sports)
- Spanish terms if relevant (e.g., "decoracion", "hogar")
- Content types (e.g., "lifestyle", "diy")

Always return valid JSON matching the schema."""


RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "parsed_search_query",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "target_count": {
                    "type": "integer",
                    "description": "Number of influencers to find (1-50)"
                },
                "influencer_gender": {
                    "type": "string",
                    "enum": ["male", "female", "any"],
                    "description": "Gender of the influencer"
                },
                "target_audience_gender": {
                    "type": ["string", "null"],
                    "enum": ["male", "female", "any", None],
                    "description": "Desired gender of the influencer's audience"
                },
                # Gender-specific counts
                "target_male_count": {
                    "type": ["integer", "null"],
                    "description": "Number of male influencers specifically requested (e.g., '3 male influencers' -> 3). Only set if explicitly mentioned."
                },
                "target_female_count": {
                    "type": ["integer", "null"],
                    "description": "Number of female influencers specifically requested (e.g., '3 female influencers' -> 3). Only set if explicitly mentioned."
                },
                # Brand context
                "brand_name": {
                    "type": ["string", "null"],
                    "description": "Brand name mentioned in query"
                },
                "brand_handle": {
                    "type": ["string", "null"],
                    "description": "Brand's social media handle (e.g., @nike, @adidas)"
                },
                "brand_category": {
                    "type": ["string", "null"],
                    "description": "Inferred brand category"
                },
                # Creative concept
                "creative_concept": {
                    "type": ["string", "null"],
                    "description": "The campaign creative brief or concept"
                },
                "creative_tone": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tone keywords: authentic, humorous, luxury, edgy, casual, documentary, etc."
                },
                "creative_themes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key themes: dedication, family, adventure, innovation, etc."
                },
                # Niche targeting
                "campaign_topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific niches for the campaign (padel, skincare, cooking)"
                },
                "exclude_niches": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Niches to avoid (e.g., soccer for padel campaign)"
                },
                "content_themes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Relevant content themes"
                },
                # Size preferences
                "preferred_follower_min": {
                    "type": ["integer", "null"],
                    "description": "Minimum preferred follower count"
                },
                "preferred_follower_max": {
                    "type": ["integer", "null"],
                    "description": "Maximum preferred follower count (anti-celebrity)"
                },
                # Audience
                "target_age_ranges": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["13-17", "18-24", "25-34", "35-44", "45-54", "55+"]
                    },
                    "description": "Preferred audience age ranges"
                },
                "min_spain_audience_pct": {
                    "type": "number",
                    "description": "Minimum percentage of Spanish audience (0-100)"
                },
                # Quality
                "min_credibility_score": {
                    "type": "number",
                    "description": "Minimum credibility score (0-100)"
                },
                "min_engagement_rate": {
                    "type": ["number", "null"],
                    "description": "Minimum engagement rate percentage"
                },
                # Ranking
                "suggested_ranking_weights": {
                    "type": ["object", "null"],
                    "properties": {
                        "credibility": {"type": "number"},
                        "engagement": {"type": "number"},
                        "audience_match": {"type": "number"},
                        "growth": {"type": "number"},
                        "geography": {"type": "number"},
                        "brand_affinity": {"type": "number"},
                        "creative_fit": {"type": "number"},
                        "niche_match": {"type": "number"}
                    },
                    "required": ["credibility", "engagement", "audience_match", "growth", "geography", "brand_affinity", "creative_fit", "niche_match"],
                    "additionalProperties": False,
                    "description": "Suggested ranking weight adjustments"
                },
                # Search
                "search_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords for PrimeTag username search"
                },
                # Meta
                "parsing_confidence": {
                    "type": "number",
                    "description": "Confidence in parsing accuracy (0-1)"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of parsing decisions"
                }
            },
            "required": [
                "target_count",
                "influencer_gender",
                "target_audience_gender",
                "target_male_count",
                "target_female_count",
                "brand_name",
                "brand_handle",
                "brand_category",
                "creative_concept",
                "creative_tone",
                "creative_themes",
                "campaign_topics",
                "exclude_niches",
                "content_themes",
                "preferred_follower_min",
                "preferred_follower_max",
                "target_age_ranges",
                "min_spain_audience_pct",
                "min_credibility_score",
                "min_engagement_rate",
                "suggested_ranking_weights",
                "search_keywords",
                "parsing_confidence",
                "reasoning"
            ],
            "additionalProperties": False
        }
    }
}


async def parse_search_query(query: str) -> ParsedSearchQuery:
    """Parse natural language query into structured search parameters using GPT-4o."""
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        completion = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query}
            ],
            response_format=RESPONSE_FORMAT,
            temperature=0.1,  # Low temperature for consistent parsing
            max_tokens=1000,
        )

        response_text = completion.choices[0].message.content
        if not response_text:
            raise LLMParsingError("Empty response from LLM", query)

        # Parse the JSON response
        parsed_data = json.loads(response_text)

        # Convert to Pydantic model with validation
        return ParsedSearchQuery(
            # Count and gender
            target_count=parsed_data.get("target_count", 5),
            influencer_gender=GenderFilter(parsed_data.get("influencer_gender", "any")),
            target_audience_gender=GenderFilter(parsed_data["target_audience_gender"]) if parsed_data.get("target_audience_gender") else None,

            # Gender-specific counts
            target_male_count=parsed_data.get("target_male_count"),
            target_female_count=parsed_data.get("target_female_count"),

            # Brand context
            brand_name=parsed_data.get("brand_name"),
            brand_handle=parsed_data.get("brand_handle"),
            brand_category=parsed_data.get("brand_category"),

            # Creative concept
            creative_concept=parsed_data.get("creative_concept"),
            creative_tone=parsed_data.get("creative_tone", []),
            creative_themes=parsed_data.get("creative_themes", []),

            # Niche targeting
            campaign_topics=parsed_data.get("campaign_topics", []),
            exclude_niches=parsed_data.get("exclude_niches", []),
            content_themes=parsed_data.get("content_themes", []),

            # Size preferences
            preferred_follower_min=parsed_data.get("preferred_follower_min"),
            preferred_follower_max=parsed_data.get("preferred_follower_max"),

            # Audience
            target_age_ranges=parsed_data.get("target_age_ranges", []),
            min_spain_audience_pct=parsed_data.get("min_spain_audience_pct", 60.0),

            # Quality
            min_credibility_score=parsed_data.get("min_credibility_score", 70.0),
            min_engagement_rate=parsed_data.get("min_engagement_rate"),

            # Ranking
            suggested_ranking_weights=parsed_data.get("suggested_ranking_weights"),

            # Search
            search_keywords=parsed_data.get("search_keywords", []),

            # Meta
            parsing_confidence=parsed_data.get("parsing_confidence", 1.0),
            reasoning=parsed_data.get("reasoning", ""),
        )

    except json.JSONDecodeError as e:
        raise LLMParsingError(f"Failed to parse LLM response as JSON: {str(e)}", query)
    except Exception as e:
        # Fallback to basic parsing if LLM fails
        return _fallback_parse(query, str(e))


def _fallback_parse(query: str, error_reason: str) -> ParsedSearchQuery:
    """Fallback parsing when LLM fails - extract basic info from query."""
    query_lower = query.lower()

    # Try to extract count
    target_count = 5
    for word in query.split():
        if word.isdigit():
            count = int(word)
            if 1 <= count <= 50:
                target_count = count
                break

    # Try to extract gender
    influencer_gender = GenderFilter.ANY
    if "female" in query_lower or "woman" in query_lower or "women" in query_lower:
        influencer_gender = GenderFilter.FEMALE
    elif "male" in query_lower or "man" in query_lower or "men" in query_lower:
        influencer_gender = GenderFilter.MALE

    # Extract keywords (non-common words)
    stop_words = {"find", "get", "show", "for", "the", "a", "an", "with", "and", "or", "influencers", "influencer"}
    keywords = [word for word in query.split() if word.lower() not in stop_words and len(word) > 2]

    return ParsedSearchQuery(
        target_count=target_count,
        influencer_gender=influencer_gender,
        search_keywords=keywords[:5],  # Limit to 5 keywords
        parsing_confidence=0.3,
        reasoning=f"Fallback parsing used due to: {error_reason}"
    )
