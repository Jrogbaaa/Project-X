"""
Brand Lookup Service

Uses LLM to understand brands that aren't in our database.
When a search query mentions a brand we don't know, this service
asks GPT-4o to provide context about the brand.
"""

import json
import logging
from typing import Optional, List
from dataclasses import dataclass, field
from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class BrandLookupResult:
    """Result from LLM brand lookup."""
    brand_name: str
    category: str  # e.g., "restaurant", "fashion", "sports"
    niche: str  # Maps to niche_taxonomy.yaml (e.g., "food", "fashion", "fitness")
    description: str  # Brief description
    country_focus: str = "Spain"  # Primary market
    competitors: List[str] = field(default_factory=list)
    suggested_keywords: List[str] = field(default_factory=list)
    instagram_handle: Optional[str] = None
    confidence: float = 0.0  # 0-1 confidence score


# Map LLM categories to our niche taxonomy
CATEGORY_TO_NICHE = {
    # Food & Beverage
    "restaurant": "food",
    "casual_dining": "food",
    "fast_food": "food",
    "cafe": "food",
    "bakery": "food",
    "food_delivery": "food",
    "food_beverage": "food",
    "food": "food",
    "grocery": "food",
    "supermarket": "food",
    
    # Alcoholic beverages
    "bar": "alcoholic_beverages",
    "brewery": "alcoholic_beverages",
    "winery": "alcoholic_beverages",
    "spirits": "alcoholic_beverages",
    "beer": "alcoholic_beverages",
    "wine": "alcoholic_beverages",
    
    # Fashion & Beauty
    "fashion": "fashion",
    "clothing": "fashion",
    "apparel": "fashion",
    "luxury_fashion": "luxury",
    "luxury": "luxury",
    "beauty": "beauty",
    "cosmetics": "beauty",
    "skincare": "beauty",
    "jewelry": "fashion",
    "accessories": "fashion",
    
    # Sports & Fitness
    "sports": "fitness",
    "sports_apparel": "fitness",
    "fitness": "fitness",
    "gym": "fitness",
    "sportswear": "fitness",
    "athletic": "fitness",
    
    # Travel & Lifestyle
    "travel": "travel",
    "hospitality": "travel",
    "hotel": "travel",
    "airline": "travel",
    "lifestyle": "lifestyle",
    
    # Technology
    "technology": "tech",
    "tech": "tech",
    "electronics": "tech",
    "software": "tech",
    "app": "tech",
    
    # Home & Living
    "home": "home_decor",
    "furniture": "home_decor",
    "home_decor": "home_decor",
    "interior_design": "home_decor",
    
    # Entertainment
    "entertainment": "lifestyle",
    "media": "lifestyle",
    "gaming": "gaming",
    
    # Automotive
    "automotive": "automotive",
    "car": "automotive",
    "motorcycle": "automotive",
    
    # Finance & Business
    "banking": "business",
    "finance": "finance",
    "insurance": "business",
    "business": "business",
    
    # Other
    "retail": "retail",
    "ecommerce": "ecommerce",
    "telecom": "tech",
    "energy": "business",
    "healthcare": "wellness",
    "pharmacy": "wellness",
    "parenting": "parenting",
    "kids": "parenting",
    "pets": "lifestyle",
}


SYSTEM_PROMPT = """You are a brand analyst specializing in Spanish and international brands.
Given a brand name, provide structured information about it.

Your response must be valid JSON with these fields:
- brand_name: The official brand name
- category: Business category (e.g., "restaurant", "fashion", "sports_apparel", "beauty", "tech", "food_beverage")
- niche: Content niche for influencer matching. Choose from: food, fashion, beauty, fitness, travel, lifestyle, tech, home_decor, automotive, gaming, music, parenting, wellness, business, alcoholic_beverages
- description: Brief 1-sentence description of the brand
- country_focus: Primary market (default "Spain" for Spanish brands, or "International")
- competitors: List of 3-5 direct competitors (preferably ones active in Spain)
- suggested_keywords: 5-10 keywords for finding relevant influencers (include Spanish terms if relevant)
- instagram_handle: The brand's Instagram handle if known (without @), or null
- confidence: How confident you are this information is accurate (0.0-1.0)

Examples:
- VIPS: Spanish casual dining restaurant chain
- 100 Montaditos: Spanish tapas restaurant franchise
- Mercadona: Spanish supermarket chain
- El Corte Inglés: Spanish department store

If you don't recognize the brand at all, set confidence to 0.0 and provide your best guess based on the name."""


class BrandLookupService:
    """
    Service for looking up brand information using LLM.
    
    Used as a fallback when a brand isn't found in our database.
    """

    def __init__(self):
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    async def lookup_brand(self, brand_name: str) -> Optional[BrandLookupResult]:
        """
        Look up brand information using LLM.
        
        Args:
            brand_name: The brand name to look up
            
        Returns:
            BrandLookupResult with brand information, or None if lookup fails
        """
        if not brand_name or len(brand_name.strip()) < 2:
            return None

        try:
            logger.info(f"Looking up unknown brand via LLM: '{brand_name}'")
            
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Provide information about the brand: {brand_name}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,  # Lower temperature for more consistent results
                max_tokens=500,
            )

            content = response.choices[0].message.content
            if not content:
                logger.warning(f"Empty response from LLM for brand: {brand_name}")
                return None

            data = json.loads(content)
            
            # Map the category to our niche taxonomy
            raw_category = data.get("category", "").lower().replace(" ", "_")
            raw_niche = data.get("niche", "").lower().replace(" ", "_")
            
            # Try to map category to niche, fall back to the LLM's niche suggestion
            mapped_niche = CATEGORY_TO_NICHE.get(raw_category)
            if not mapped_niche:
                mapped_niche = CATEGORY_TO_NICHE.get(raw_niche, raw_niche or "lifestyle")

            result = BrandLookupResult(
                brand_name=data.get("brand_name", brand_name),
                category=raw_category or "unknown",
                niche=mapped_niche,
                description=data.get("description", ""),
                country_focus=data.get("country_focus", "Spain"),
                competitors=data.get("competitors", [])[:5],
                suggested_keywords=data.get("suggested_keywords", [])[:10],
                instagram_handle=data.get("instagram_handle"),
                confidence=float(data.get("confidence", 0.5)),
            )

            logger.info(
                f"Brand lookup result: {result.brand_name} -> "
                f"category={result.category}, niche={result.niche}, "
                f"confidence={result.confidence:.2f}"
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response for brand '{brand_name}': {e}")
            return None
        except Exception as e:
            logger.error(f"Brand lookup failed for '{brand_name}': {e}")
            return None

    def get_niche_for_category(self, category: str) -> str:
        """
        Map a category string to our niche taxonomy.
        
        Args:
            category: Category string from LLM or database
            
        Returns:
            Niche string from our taxonomy
        """
        normalized = category.lower().replace(" ", "_").replace("-", "_")
        return CATEGORY_TO_NICHE.get(normalized, "lifestyle")


# Singleton instance
_brand_lookup_service: Optional[BrandLookupService] = None


def get_brand_lookup_service() -> BrandLookupService:
    """Get singleton brand lookup service instance."""
    global _brand_lookup_service
    if _brand_lookup_service is None:
        _brand_lookup_service = BrandLookupService()
    return _brand_lookup_service
