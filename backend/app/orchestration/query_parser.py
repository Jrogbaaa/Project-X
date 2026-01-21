import json
from openai import AsyncOpenAI
from typing import Optional

from app.config import get_settings
from app.schemas.llm import ParsedSearchQuery, GenderFilter
from app.core.exceptions import LLMParsingError


SYSTEM_PROMPT = """You are a search query parser for an influencer discovery platform focused on the Spanish market.

Your job is to extract structured search parameters from natural language queries from talent agents looking for influencers for brand partnerships.

Key guidelines:
1. Default to Spanish audience focus (min 60% Spain audience)
2. Default credibility threshold is 70%
3. If a brand is mentioned, infer the category and relevant content themes
4. If no count is specified, default to 5 influencers
5. Consider the brand context when suggesting ranking weights:
   - Fashion/beauty brands: higher engagement weight
   - B2B/professional brands: higher credibility weight
   - Viral campaigns: higher growth weight
   - Local businesses: higher geography weight

Brand category mappings:
- IKEA, furniture stores -> home_furniture
- Zara, H&M, fashion brands -> fashion
- L'Oreal, beauty brands -> beauty
- Tech companies -> technology
- Food/restaurant brands -> food_lifestyle
- Fitness brands -> health_fitness
- Travel brands -> travel_lifestyle

For the search_keywords field, provide keywords that would help find relevant influencer usernames or content themes. Think about:
- Related niches (e.g., "interior" for IKEA, "moda" for fashion)
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
                "brand_name": {
                    "type": ["string", "null"],
                    "description": "Brand name mentioned in query"
                },
                "brand_category": {
                    "type": ["string", "null"],
                    "description": "Inferred brand category"
                },
                "content_themes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Relevant content themes"
                },
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
                "min_credibility_score": {
                    "type": "number",
                    "description": "Minimum credibility score (0-100)"
                },
                "min_engagement_rate": {
                    "type": ["number", "null"],
                    "description": "Minimum engagement rate percentage"
                },
                "suggested_ranking_weights": {
                    "type": ["object", "null"],
                    "properties": {
                        "credibility": {"type": "number"},
                        "engagement": {"type": "number"},
                        "audience_match": {"type": "number"},
                        "growth": {"type": "number"},
                        "geography": {"type": "number"}
                    },
                    "additionalProperties": False,
                    "description": "Suggested ranking weight adjustments"
                },
                "search_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords for PrimeTag username search"
                },
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
                "brand_name",
                "brand_category",
                "content_themes",
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
            target_count=parsed_data.get("target_count", 5),
            influencer_gender=GenderFilter(parsed_data.get("influencer_gender", "any")),
            target_audience_gender=GenderFilter(parsed_data["target_audience_gender"]) if parsed_data.get("target_audience_gender") else None,
            brand_name=parsed_data.get("brand_name"),
            brand_category=parsed_data.get("brand_category"),
            content_themes=parsed_data.get("content_themes", []),
            target_age_ranges=parsed_data.get("target_age_ranges", []),
            min_spain_audience_pct=parsed_data.get("min_spain_audience_pct", 60.0),
            min_credibility_score=parsed_data.get("min_credibility_score", 70.0),
            min_engagement_rate=parsed_data.get("min_engagement_rate"),
            suggested_ranking_weights=parsed_data.get("suggested_ranking_weights"),
            search_keywords=parsed_data.get("search_keywords", []),
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
