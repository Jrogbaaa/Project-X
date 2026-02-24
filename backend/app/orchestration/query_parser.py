import json
from openai import AsyncOpenAI
from typing import Optional

from app.config import get_settings
from app.schemas.llm import ParsedSearchQuery, GenderFilter
from app.core.exceptions import LLMParsingError


SYSTEM_PROMPT = """You are a search query parser for an influencer discovery platform focused on the Spanish market.

Your job is to extract structured search parameters from natural language brand briefs and queries. Talent agents paste in campaign briefs containing brand info, creative concepts, and search criteria.

Queries may be in English or Spanish, and often arrive as messy forwarded email chains with budget figures (€), CPM constraints, "oleada" (campaign wave/round), "contrastado" (confirmed/verified), or other agency shorthand. Extract structured fields regardless of format or language.

## Extraction Guidelines

### Brand Information
1. Extract brand_name (e.g., "Adidas", "Nike", "IKEA")
2. Infer brand_handle - the brand's social media handle (e.g., "@adidas", "@nike", "@ikea")
3. Infer brand_category from the brand name

Brand category mappings:
- IKEA, furniture stores -> home_furniture
- Zara, H&M, fashion brands -> fashion
- Nike, Adidas, Puma -> sports_apparel
- L'Oreal, general beauty/makeup brands -> beauty
- Skincare brands (CeraVe, The Ordinary, La Roche-Posay, vitamin C serums, natural skincare) -> skincare
- Perfume, fragrance brands (Halloween, Loewe Perfumes, Carolina Herrera) -> beauty
- Tech companies -> technology
- Food/restaurant brands -> food_lifestyle
- Fitness brands -> health_fitness
- Travel brands -> travel_lifestyle
- Spirits, gin, whisky, beer brands (Puerto de Indias, Mahou, Estrella, Hendrick's) -> alcoholic_beverages
- Fintech, payment technology brands (Square, iZettle, SumUp) -> fintech
- Banking apps, digital finance (imagin, BBVA, Revolut) -> fintech
- Pet stores, animal brands (Tiendanimal, Royal Canin, Purina) -> pets

### Creative Concept Extraction
Extract the creative/campaign concept if described:
1. creative_concept: The full campaign idea or creative brief
2. creative_format: The content format being requested. Choose from:
   - "documentary" - Behind-the-scenes, journey, making-of style
   - "day_in_the_life" - Daily routine, lifestyle focused
   - "tutorial" - How-to, educational content
   - "challenge" - Viral challenge, user participation
   - "testimonial" - Review, endorsement style
   - "storytelling" - Narrative, emotional arc
   - "lifestyle" - Casual, everyday moments
   - null if not specified
3. creative_tone: Style keywords like "authentic", "humorous", "luxury", "edgy", "casual", "inspirational", "gritty", "polished", "raw"
4. creative_themes: Key values/themes like "dedication", "family", "adventure", "innovation", "rising stars", "everyday heroes", "transformation"

### Niche/Topic Targeting
1. campaign_niche: The PRIMARY niche for this campaign (SINGLE value, most important one). Choose from the taxonomy:
   - Sports: "padel", "tennis", "football", "basketball", "golf", "running", "cycling", "swimming", "triathlon", "motorsport", "fitness", "crossfit"
   - Fashion & Beauty: "fashion", "beauty", "skincare", "luxury"
   - Lifestyle: "lifestyle", "travel", "food"
   - Wellness: "yoga", "wellness", "nutrition"
   - Entertainment: "music", "comedy", "nightlife"
   - Gaming & Tech: "gaming", "tech"
   - Pets & Animals: "pets"
   - Family: "parenting"
   - Business: "business", "finance", "ecommerce"
   - Home & Living: "home_decor", "diy"
   - Food & Beverages: "alcoholic_beverages", "soft_drinks"
   - Retail: "retail", "ecommerce"
   - Automotive: "automotive"
   IMPORTANT NICHE SELECTION RULES:
   - Use "skincare" (not "beauty") when the brief is specifically about skincare products, serums, facial routines, dermatology, SPF, etc. Use "beauty" only for general beauty/makeup/cosmetics.
   - Use "gaming" (not "tech") when the brief is about gaming peripherals, headsets, consoles, video games, esports, Twitch, streaming gear. Use "tech" only for smartphones, general gadgets, software, SaaS, or B2B tech.
   - Use "home_decor" (not "lifestyle") when the brief is about furniture, mattresses, bedding, home appliances, interior design, or any product used in the home. Use "lifestyle" only when nothing more specific fits.
   - Always prefer the MOST SPECIFIC niche over a broader one. "gaming" > "tech", "padel" > "sports", "skincare" > "beauty", "running" > "fitness", "home_decor" > "lifestyle".
   This will be matched against influencers' primary_niche column.
2. campaign_topics: Additional specific topics relevant to the campaign (array)
3. exclude_niches: Niches to AVOID - important for precision (e.g., for a padel campaign, exclude "soccer", "football" to avoid famous soccer players)
   CRITICAL: NEVER exclude a niche that is closely RELATED to campaign_niche. Related niches are valuable fallbacks when exact matches are scarce.
   - skincare campaign → do NOT exclude "beauty" (beauty influencers often do skincare content)
   - running campaign → do NOT exclude "fitness" (fitness includes runners)
   - gaming campaign → do NOT exclude "tech" (tech and gaming overlap)
   - Only exclude genuinely CONFLICTING niches (e.g., football for padel, fitness for beer/spirits)

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

### Influencer Tier Counts
When the brief specifies influencers by tier/size (e.g., "3 macro 4 mid", "we need 2 micro-influencers and 1 macro"):
- target_micro_count: Number of micro influencers (1K-50K followers)
- target_mid_count: Number of mid-tier influencers (50K-500K followers)
- target_macro_count: Number of macro influencers (500K-2.5M followers)

Common terms that map to tiers:
- "micro", "micro-influencer", "nano", "small" → micro (1K-50K)
- "mid", "mid-tier", "medium" → mid (50K-500K)
- "macro", "large", "big" → macro (500K+)

Only set these if EXPLICIT tier counts are mentioned. Do NOT set if just "10 influencers" without tier specification.
If the brief just says "micro-influencers" without a count, set target_count to the total and set target_micro_count to that same number.

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

### Creative Influencer Discovery (IMPORTANT)
Think creatively about WHO would authentically represent this brand. Our database has influencers with PrimeTag interest categories, NOT exact niches. You must reason about which interest categories would be good fits.

**Available PrimeTag Interest Categories:**
- Sports, Soccer, Tennis, Fitness, Golf
- Fashion, Beauty, Luxury Goods, Jewellery & Watches
- Entertainment and Music, Celebrity, Actors, Modeling
- Family, Lifestyle, Parenting, Toys Children & Baby
- Cars & Motorbikes, Journalists
- Clothes Shoes Handbags & Accessories
- Television & Film, Health

**Creative Reasoning Process:**
1. Understand the brand's positioning (athletic, luxury, healthy, family-friendly, etc.)
2. Think: "What types of creators would genuinely use/love this product?"
3. Map that reasoning to PrimeTag interest categories (above)
4. Think: "What types would feel INAUTHENTIC?" → exclude those

**Examples:**
- Padel brand → discovery_interests: ["Sports", "Tennis", "Fitness"], exclude_interests: ["Soccer"]
  Reasoning: "Padel is a racket sport. Tennis players and fitness enthusiasts align authentically. Soccer players don't."
  
- Healthy restaurant (Honest Greens) → discovery_interests: ["Fitness", "Health", "Lifestyle", "Family"]
  Reasoning: "Health-conscious, active people would authentically promote healthy food."
  
- Luxury watch brand → discovery_interests: ["Luxury Goods", "Fashion", "Jewellery & Watches", "Celebrity"]
  Reasoning: "Luxury positioning requires aspirational creators."

- Home furniture brand (IKEA) → discovery_interests: ["Lifestyle", "Family", "Parenting"]
  Reasoning: "Home-focused, family-oriented creators would authentically show furniture in real life."

- Spirits/gin brand with "time with your people" social concept (e.g. Puerto de Indias) → discovery_interests: ["Lifestyle", "Entertainment and Music", "Family"], campaign_niche: "alcoholic_beverages"
  Reasoning: "Spirits brands need lifestyle creators who authentically show social moments and gatherings. Note: some creators decline spirits/alcohol brand partnerships — this is expected and normal in this category."

- B2B fintech / payment tech brand targeting restaurant and bar owners (e.g. Square) → discovery_interests: ["Lifestyle", "Family"], campaign_niche: "food", search_keywords: ["restaurante", "gastronomia", "chef", "emprendedor"]
  Reasoning: "B2B event campaigns need credible entrepreneur voices with real business audiences. Gastro entrepreneurs spread across Spanish cities (Madrid, Barcelona, Sevilla, Valencia) are ideal. Geographic spread matters as much as follower size."

- Pet store brand (Tiendanimal, Kiwoko) → discovery_interests: ["Lifestyle", "Family"], campaign_niche: "pets", search_keywords: ["mascota", "perro", "gato", "pet", "dog", "cat"]
  Reasoning: "Pet store campaigns need authentic pet owners who post daily about their animals. Lifestyle and family creators who are also pet lovers connect best."

- Home/retail brand amplifying a youth social cause or competition (e.g. IKEA + Museo Picasso housing competition) → discovery_interests: ["Lifestyle", "Parenting", "Family"], campaign_niche: "lifestyle"
  Reasoning: "Social cause campaigns targeting young people (18-35) need accessible, authentic voices. Lifestyle creators who care about youth issues and housing connect best — not interior design specialists."

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
                # Tier-specific counts
                "target_micro_count": {
                    "type": ["integer", "null"],
                    "description": "Number of micro influencers (1K-50K followers) requested. Only set if explicitly mentioned."
                },
                "target_mid_count": {
                    "type": ["integer", "null"],
                    "description": "Number of mid-tier influencers (50K-500K followers) requested. Only set if explicitly mentioned."
                },
                "target_macro_count": {
                    "type": ["integer", "null"],
                    "description": "Number of macro influencers (500K-2.5M followers) requested. Only set if explicitly mentioned."
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
                "creative_format": {
                    "type": ["string", "null"],
                    "enum": ["documentary", "day_in_the_life", "tutorial", "challenge", "testimonial", "storytelling", "lifestyle", None],
                    "description": "The content format requested: documentary, day_in_the_life, tutorial, challenge, testimonial, storytelling, lifestyle"
                },
                "creative_tone": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tone keywords: authentic, humorous, luxury, edgy, casual, inspirational, etc."
                },
                "creative_themes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key themes: dedication, family, adventure, innovation, etc."
                },
                # Niche targeting
                "campaign_niche": {
                    "type": ["string", "null"],
                    "description": "PRIMARY niche for the campaign (single value): padel, tennis, football, fitness, fashion, beauty, etc."
                },
                "campaign_topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional specific topics for the campaign"
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
                # Creative discovery (PrimeTag interest mapping)
                "discovery_interests": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "PrimeTag interest categories for discovery: Sports, Soccer, Tennis, Fitness, Fashion, Beauty, Luxury Goods, Entertainment and Music, Family, Lifestyle, etc."
                },
                "exclude_interests": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "PrimeTag interest categories to AVOID (e.g., 'Soccer' for padel campaign)"
                },
                "influencer_reasoning": {
                    "type": "string",
                    "description": "Brief reasoning about what types of influencers would authentically represent this brand"
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
                "target_micro_count",
                "target_mid_count",
                "target_macro_count",
                "brand_name",
                "brand_handle",
                "brand_category",
                "creative_concept",
                "creative_format",
                "creative_tone",
                "creative_themes",
                "campaign_niche",
                "campaign_topics",
                "exclude_niches",
                "content_themes",
                "discovery_interests",
                "exclude_interests",
                "influencer_reasoning",
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

            # Tier-specific counts
            target_micro_count=parsed_data.get("target_micro_count"),
            target_mid_count=parsed_data.get("target_mid_count"),
            target_macro_count=parsed_data.get("target_macro_count"),

            # Brand context
            brand_name=parsed_data.get("brand_name"),
            brand_handle=parsed_data.get("brand_handle"),
            brand_category=parsed_data.get("brand_category"),

            # Creative concept
            creative_concept=parsed_data.get("creative_concept"),
            creative_format=parsed_data.get("creative_format"),
            creative_tone=parsed_data.get("creative_tone", []),
            creative_themes=parsed_data.get("creative_themes", []),

            # Niche targeting
            campaign_niche=parsed_data.get("campaign_niche"),
            campaign_topics=parsed_data.get("campaign_topics", []),
            exclude_niches=parsed_data.get("exclude_niches", []),
            content_themes=parsed_data.get("content_themes", []),

            # Creative discovery (PrimeTag interest mapping)
            discovery_interests=parsed_data.get("discovery_interests", []),
            exclude_interests=parsed_data.get("exclude_interests", []),
            influencer_reasoning=parsed_data.get("influencer_reasoning", ""),

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
