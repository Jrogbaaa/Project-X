"""
Brand Scraper Service

Collects brand data from various Spanish market sources.
Can be used in two modes:
1. Direct HTTP scraping (for accessible sources)
2. Processing pre-scraped data (from Firecrawl MCP)

Sources:
- IBEX 35 companies (public companies)
- Kantar BrandZ Top Spanish Brands
- Interbrand Best Spanish Brands
- Industry directories (fashion, food, etc.)
"""

import httpx
import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ScrapedBrand:
    """Intermediate representation of scraped brand data."""
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    industry: Optional[str] = None
    headquarters: Optional[str] = None
    website: Optional[str] = None
    instagram_handle: Optional[str] = None
    source: str = "manual"
    source_rank: Optional[int] = None
    brand_value_eur: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, filtering None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class BrandScraperService:
    """
    Service for collecting Spanish brand data from multiple sources.
    """

    # Category mappings for standardization
    CATEGORY_MAPPING = {
        # IBEX 35 sectors
        "apparel retail": "fashion",
        "textiles, apparel & luxury goods": "fashion",
        "utilities": "utilities",
        "banks": "banking",
        "diversified banks": "banking",
        "airports & air services": "travel",
        "construction & engineering": "construction",
        "it services": "technology",
        "electric utilities": "utilities",
        "integrated oil & gas": "energy",
        "oil & gas exploration & production": "energy",
        "insurance": "insurance",
        "telecommunications": "telecom",
        "telecom": "telecom",
        "specialty chemicals": "chemicals",
        "steel": "manufacturing",
        "real estate": "real_estate",
        "food retail": "retail",
        "retail": "retail",
        "food & beverage": "food_beverage",
        "beverages": "food_beverage",
        "automotive": "automotive",
        "beauty": "beauty",
        "cosmetics": "beauty",
        "sports": "sports",
        "sports apparel": "sports",
        "technology": "technology",
        "media": "media",
        "healthcare": "healthcare",
        "pharmaceuticals": "healthcare",
    }

    def __init__(self):
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )

    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()

    def normalize_category(self, raw_category: str) -> str:
        """Normalize category to standard taxonomy."""
        if not raw_category:
            return "other"
        
        normalized = raw_category.lower().strip()
        return self.CATEGORY_MAPPING.get(normalized, normalized.replace(" ", "_"))

    # ==================== IBEX 35 ====================

    async def scrape_ibex35(self) -> List[ScrapedBrand]:
        """
        Scrape IBEX 35 companies from disfold.com.
        Returns list of ScrapedBrand objects.
        """
        url = "https://disfold.com/stock-index/ibex35/companies/"
        brands = []

        try:
            logger.info(f"Scraping IBEX 35 from {url}")
            response = await self.http_client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the table with company data
            table = soup.find('table')
            if not table:
                logger.warning("IBEX 35 table not found on page")
                return brands

            rows = table.find_all('tr')[1:]  # Skip header row
            
            for rank, row in enumerate(rows, 1):
                cells = row.find_all('td')
                if len(cells) >= 3:
                    # Extract company name and sector
                    name_cell = cells[1] if len(cells) > 1 else cells[0]
                    name = name_cell.get_text(strip=True)
                    
                    # Try to get sector from last column
                    sector = cells[-1].get_text(strip=True) if cells else None
                    
                    # Try to get market cap
                    market_cap = None
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        if '$' in text and 'B' in text:
                            # Parse market cap like "$159.95B"
                            try:
                                cap_str = text.replace('$', '').replace('B', '').strip()
                                market_cap = int(float(cap_str) * 1_000_000_000)
                            except ValueError:
                                pass

                    brand = ScrapedBrand(
                        name=name,
                        category=self.normalize_category(sector) if sector else "other",
                        industry=sector,
                        source="ibex35",
                        source_rank=rank,
                        brand_value_eur=market_cap,
                        headquarters="Spain",
                        metadata={"stock_index": "IBEX 35"}
                    )
                    brands.append(brand)
                    logger.debug(f"IBEX 35: Found {name} (rank {rank})")

            logger.info(f"IBEX 35: Scraped {len(brands)} companies")

        except httpx.HTTPError as e:
            logger.error(f"IBEX 35 scrape failed: {e}")
        except Exception as e:
            logger.error(f"IBEX 35 parse error: {e}")

        return brands

    # ==================== MANUAL DATA SOURCES ====================

    def get_top_spanish_brands_manual(self) -> List[ScrapedBrand]:
        """
        Returns manually curated list of top Spanish brands.
        Used as a reliable baseline when web scraping fails.
        Based on Kantar BrandZ 2025 and other public sources.
        """
        brands_data = [
            # Fashion (Inditex family)
            {"name": "Zara", "category": "fashion", "subcategory": "fast_fashion", "headquarters": "A Coruña", "brand_value_eur": 33_900_000_000, "source_rank": 1},
            {"name": "Pull & Bear", "category": "fashion", "subcategory": "fast_fashion", "headquarters": "A Coruña", "source_rank": 15},
            {"name": "Bershka", "category": "fashion", "subcategory": "fast_fashion", "headquarters": "A Coruña", "source_rank": 16},
            {"name": "Massimo Dutti", "category": "fashion", "subcategory": "premium_fashion", "headquarters": "A Coruña", "source_rank": 17},
            {"name": "Stradivarius", "category": "fashion", "subcategory": "fast_fashion", "headquarters": "A Coruña", "source_rank": 18},
            {"name": "Oysho", "category": "fashion", "subcategory": "lingerie", "headquarters": "A Coruña"},
            {"name": "Mango", "category": "fashion", "subcategory": "fast_fashion", "headquarters": "Barcelona"},
            {"name": "Desigual", "category": "fashion", "subcategory": "fashion", "headquarters": "Barcelona"},
            {"name": "Camper", "category": "fashion", "subcategory": "footwear", "headquarters": "Mallorca"},
            {"name": "Loewe", "category": "fashion", "subcategory": "luxury", "headquarters": "Madrid"},
            {"name": "Balenciaga", "category": "fashion", "subcategory": "luxury", "headquarters": "Paris", "metadata": {"origin": "Spanish founder"}},
            {"name": "Tous", "category": "fashion", "subcategory": "jewelry", "headquarters": "Barcelona"},
            
            # Banking
            {"name": "Banco Santander", "category": "banking", "headquarters": "Madrid", "brand_value_eur": 11_000_000_000, "source_rank": 2},
            {"name": "BBVA", "category": "banking", "headquarters": "Bilbao", "brand_value_eur": 11_400_000_000, "source_rank": 3},
            {"name": "CaixaBank", "category": "banking", "headquarters": "Valencia", "source_rank": 5},
            {"name": "Banco Sabadell", "category": "banking", "headquarters": "Barcelona"},
            {"name": "Bankinter", "category": "banking", "headquarters": "Madrid"},
            
            # Telecom
            {"name": "Movistar", "category": "telecom", "headquarters": "Madrid", "brand_value_eur": 12_600_000_000, "source_rank": 4},
            {"name": "Orange España", "category": "telecom", "headquarters": "Madrid"},
            {"name": "Vodafone España", "category": "telecom", "headquarters": "Madrid"},
            {"name": "MásMóvil", "category": "telecom", "headquarters": "Madrid"},
            {"name": "Yoigo", "category": "telecom", "headquarters": "Madrid"},
            
            # Energy & Utilities
            {"name": "Iberdrola", "category": "utilities", "headquarters": "Bilbao", "source_rank": 6},
            {"name": "Endesa", "category": "utilities", "headquarters": "Madrid"},
            {"name": "Naturgy", "category": "utilities", "headquarters": "Barcelona"},
            {"name": "Repsol", "category": "energy", "headquarters": "Madrid", "source_rank": 7},
            {"name": "Cepsa", "category": "energy", "headquarters": "Madrid"},
            
            # Retail & Grocery
            {"name": "Mercadona", "category": "retail", "subcategory": "grocery", "headquarters": "Valencia", "source_rank": 8},
            {"name": "El Corte Inglés", "category": "retail", "subcategory": "department_store", "headquarters": "Madrid", "source_rank": 9},
            {"name": "Carrefour España", "category": "retail", "subcategory": "grocery", "headquarters": "Madrid"},
            {"name": "Lidl España", "category": "retail", "subcategory": "discount_grocery", "headquarters": "Barcelona"},
            {"name": "Dia", "category": "retail", "subcategory": "grocery", "headquarters": "Madrid"},
            {"name": "Eroski", "category": "retail", "subcategory": "grocery", "headquarters": "País Vasco"},
            {"name": "Alcampo", "category": "retail", "subcategory": "hypermarket", "headquarters": "Madrid"},
            {"name": "MediaMarkt España", "category": "retail", "subcategory": "electronics", "headquarters": "Barcelona"},
            {"name": "Fnac España", "category": "retail", "subcategory": "electronics", "headquarters": "Madrid"},
            {"name": "Leroy Merlin España", "category": "retail", "subcategory": "home_improvement", "headquarters": "Madrid"},
            {"name": "IKEA España", "category": "retail", "subcategory": "furniture", "headquarters": "Madrid"},
            {"name": "Decathlon España", "category": "retail", "subcategory": "sports", "headquarters": "Madrid"},
            
            # Food & Beverage
            {"name": "Mahou San Miguel", "category": "food_beverage", "subcategory": "beer", "headquarters": "Madrid"},
            {"name": "Estrella Galicia", "category": "food_beverage", "subcategory": "beer", "headquarters": "A Coruña"},
            {"name": "Cruzcampo", "category": "food_beverage", "subcategory": "beer", "headquarters": "Sevilla"},
            {"name": "Damm", "category": "food_beverage", "subcategory": "beer", "headquarters": "Barcelona"},
            {"name": "San Miguel", "category": "food_beverage", "subcategory": "beer", "headquarters": "Madrid"},
            {"name": "Freixenet", "category": "food_beverage", "subcategory": "wine", "headquarters": "Barcelona"},
            {"name": "Codorníu", "category": "food_beverage", "subcategory": "wine", "headquarters": "Barcelona"},
            {"name": "Torres", "category": "food_beverage", "subcategory": "wine", "headquarters": "Barcelona"},
            {"name": "Osborne", "category": "food_beverage", "subcategory": "wine_spirits", "headquarters": "Cádiz"},
            {"name": "Gallo", "category": "food_beverage", "subcategory": "olive_oil", "headquarters": "Córdoba"},
            {"name": "Carbonell", "category": "food_beverage", "subcategory": "olive_oil", "headquarters": "Córdoba"},
            {"name": "La Española", "category": "food_beverage", "subcategory": "olive_oil", "headquarters": "Alcalá de Guadaíra"},
            {"name": "Casa Tarradellas", "category": "food_beverage", "subcategory": "charcuterie", "headquarters": "Barcelona"},
            {"name": "El Pozo", "category": "food_beverage", "subcategory": "charcuterie", "headquarters": "Murcia"},
            {"name": "Campofrío", "category": "food_beverage", "subcategory": "charcuterie", "headquarters": "Madrid"},
            {"name": "Pescanova", "category": "food_beverage", "subcategory": "seafood", "headquarters": "Vigo"},
            {"name": "Danone España", "category": "food_beverage", "subcategory": "dairy", "headquarters": "Barcelona"},
            {"name": "Central Lechera Asturiana", "category": "food_beverage", "subcategory": "dairy", "headquarters": "Asturias"},
            {"name": "Puleva", "category": "food_beverage", "subcategory": "dairy", "headquarters": "Granada"},
            {"name": "Pascual", "category": "food_beverage", "subcategory": "dairy", "headquarters": "Burgos"},
            {"name": "Cola Cao", "category": "food_beverage", "subcategory": "beverages", "headquarters": "Barcelona"},
            {"name": "Nocilla", "category": "food_beverage", "subcategory": "spreads", "headquarters": "Valencia"},
            {"name": "Valor", "category": "food_beverage", "subcategory": "chocolate", "headquarters": "Alicante"},
            {"name": "Lacasa", "category": "food_beverage", "subcategory": "chocolate", "headquarters": "Zaragoza"},
            
            # Automotive
            {"name": "SEAT", "category": "automotive", "headquarters": "Barcelona"},
            {"name": "Cupra", "category": "automotive", "headquarters": "Barcelona"},
            
            # Insurance
            {"name": "Mapfre", "category": "insurance", "headquarters": "Madrid", "source_rank": 10},
            {"name": "Mutua Madrileña", "category": "insurance", "headquarters": "Madrid"},
            {"name": "Línea Directa", "category": "insurance", "headquarters": "Madrid"},
            {"name": "Sanitas", "category": "insurance", "subcategory": "health", "headquarters": "Madrid"},
            {"name": "Adeslas", "category": "insurance", "subcategory": "health", "headquarters": "Madrid"},
            
            # Travel & Hospitality
            {"name": "Iberia", "category": "travel", "subcategory": "airline", "headquarters": "Madrid"},
            {"name": "Vueling", "category": "travel", "subcategory": "airline", "headquarters": "Barcelona"},
            {"name": "Air Europa", "category": "travel", "subcategory": "airline", "headquarters": "Mallorca"},
            {"name": "Meliá Hotels", "category": "travel", "subcategory": "hotels", "headquarters": "Mallorca"},
            {"name": "NH Hotels", "category": "travel", "subcategory": "hotels", "headquarters": "Madrid"},
            {"name": "Barceló Hotels", "category": "travel", "subcategory": "hotels", "headquarters": "Mallorca"},
            {"name": "Riu Hotels", "category": "travel", "subcategory": "hotels", "headquarters": "Mallorca"},
            {"name": "Paradores", "category": "travel", "subcategory": "hotels", "headquarters": "Madrid"},
            {"name": "Renfe", "category": "travel", "subcategory": "rail", "headquarters": "Madrid"},
            {"name": "Aena", "category": "travel", "subcategory": "airports", "headquarters": "Madrid"},
            
            # Technology
            {"name": "Telefónica", "category": "technology", "subcategory": "telecom", "headquarters": "Madrid"},
            {"name": "Indra", "category": "technology", "subcategory": "it_services", "headquarters": "Madrid"},
            {"name": "Amadeus IT", "category": "technology", "subcategory": "travel_tech", "headquarters": "Madrid"},
            {"name": "Cabify", "category": "technology", "subcategory": "mobility", "headquarters": "Madrid"},
            {"name": "Glovo", "category": "technology", "subcategory": "delivery", "headquarters": "Barcelona"},
            {"name": "Wallapop", "category": "technology", "subcategory": "marketplace", "headquarters": "Barcelona"},
            {"name": "Idealista", "category": "technology", "subcategory": "real_estate", "headquarters": "Madrid"},
            {"name": "Fotocasa", "category": "technology", "subcategory": "real_estate", "headquarters": "Barcelona"},
            
            # Beauty & Personal Care
            {"name": "Natura Bissé", "category": "beauty", "subcategory": "skincare", "headquarters": "Barcelona"},
            {"name": "Puig", "category": "beauty", "subcategory": "fragrances", "headquarters": "Barcelona"},
            {"name": "Druni", "category": "beauty", "subcategory": "retail", "headquarters": "Valencia"},
            {"name": "Primor", "category": "beauty", "subcategory": "retail", "headquarters": "Sevilla"},
            {"name": "Equivalenza", "category": "beauty", "subcategory": "fragrances", "headquarters": "Madrid"},
            
            # Construction & Infrastructure
            {"name": "ACS", "category": "construction", "headquarters": "Madrid"},
            {"name": "Ferrovial", "category": "construction", "headquarters": "Madrid"},
            {"name": "Acciona", "category": "construction", "headquarters": "Madrid"},
            {"name": "FCC", "category": "construction", "headquarters": "Madrid"},
            {"name": "OHL", "category": "construction", "headquarters": "Madrid"},
            {"name": "Sacyr", "category": "construction", "headquarters": "Madrid"},
            
            # Media & Entertainment
            {"name": "Mediaset España", "category": "media", "subcategory": "tv", "headquarters": "Madrid"},
            {"name": "Atresmedia", "category": "media", "subcategory": "tv", "headquarters": "Madrid"},
            {"name": "RTVE", "category": "media", "subcategory": "tv", "headquarters": "Madrid"},
            {"name": "Prisa", "category": "media", "subcategory": "publishing", "headquarters": "Madrid"},
            {"name": "Vocento", "category": "media", "subcategory": "publishing", "headquarters": "Bilbao"},
            
            # Sports Equipment (relevant for influencer matching)
            {"name": "Joma", "category": "sports", "subcategory": "sports_apparel", "headquarters": "Toledo"},
            {"name": "Kelme", "category": "sports", "subcategory": "sports_apparel", "headquarters": "Elche"},
            {"name": "Munich", "category": "sports", "subcategory": "sports_footwear", "headquarters": "Barcelona"},
            {"name": "Bullpadel", "category": "sports", "subcategory": "padel", "headquarters": "Barcelona"},
            {"name": "Head Padel", "category": "sports", "subcategory": "padel", "headquarters": "Spain"},
            {"name": "Nox Padel", "category": "sports", "subcategory": "padel", "headquarters": "Spain"},
            {"name": "Siux", "category": "sports", "subcategory": "padel", "headquarters": "Spain"},
            {"name": "Babolat España", "category": "sports", "subcategory": "tennis_padel", "headquarters": "Spain"},
            
            # Healthcare & Pharma
            {"name": "Grifols", "category": "healthcare", "subcategory": "pharma", "headquarters": "Barcelona"},
            {"name": "Almirall", "category": "healthcare", "subcategory": "pharma", "headquarters": "Barcelona"},
            {"name": "PharmaMar", "category": "healthcare", "subcategory": "pharma", "headquarters": "Madrid"},
            {"name": "Esteve", "category": "healthcare", "subcategory": "pharma", "headquarters": "Barcelona"},
            {"name": "Cinfa", "category": "healthcare", "subcategory": "pharma", "headquarters": "Navarra"},
            {"name": "Quirónsalud", "category": "healthcare", "subcategory": "hospitals", "headquarters": "Madrid"},
            {"name": "HM Hospitales", "category": "healthcare", "subcategory": "hospitals", "headquarters": "Madrid"},
            
            # Real Estate
            {"name": "Merlin Properties", "category": "real_estate", "headquarters": "Madrid"},
            {"name": "Colonial", "category": "real_estate", "headquarters": "Barcelona"},
            
            # Other notable brands
            {"name": "Prosegur", "category": "services", "subcategory": "security", "headquarters": "Madrid"},
            {"name": "Eulen", "category": "services", "subcategory": "facility_services", "headquarters": "Madrid"},
            {"name": "Correos", "category": "services", "subcategory": "postal", "headquarters": "Madrid"},
            {"name": "Seur", "category": "services", "subcategory": "logistics", "headquarters": "Madrid"},
            {"name": "MRW", "category": "services", "subcategory": "logistics", "headquarters": "Barcelona"},
        ]

        brands = []
        for data in brands_data:
            brand = ScrapedBrand(
                name=data["name"],
                category=data.get("category"),
                subcategory=data.get("subcategory"),
                headquarters=data.get("headquarters"),
                brand_value_eur=data.get("brand_value_eur"),
                source="kantar_brandz_manual",
                source_rank=data.get("source_rank"),
                metadata=data.get("metadata", {})
            )
            brands.append(brand)

        logger.info(f"Loaded {len(brands)} manually curated Spanish brands")
        return brands

    # ==================== INDUSTRY SPECIFIC ====================

    def get_spanish_fashion_brands(self) -> List[ScrapedBrand]:
        """Returns curated list of Spanish fashion brands."""
        fashion_data = [
            # Inditex Group
            {"name": "Zara", "subcategory": "fast_fashion", "headquarters": "A Coruña"},
            {"name": "Pull & Bear", "subcategory": "fast_fashion", "headquarters": "A Coruña"},
            {"name": "Bershka", "subcategory": "fast_fashion", "headquarters": "A Coruña"},
            {"name": "Massimo Dutti", "subcategory": "premium_fashion", "headquarters": "A Coruña"},
            {"name": "Stradivarius", "subcategory": "fast_fashion", "headquarters": "A Coruña"},
            {"name": "Oysho", "subcategory": "lingerie_athleisure", "headquarters": "A Coruña"},
            {"name": "Zara Home", "subcategory": "home", "headquarters": "A Coruña"},
            {"name": "Lefties", "subcategory": "value_fashion", "headquarters": "A Coruña"},
            
            # Other Spanish fashion
            {"name": "Mango", "subcategory": "fast_fashion", "headquarters": "Barcelona"},
            {"name": "Desigual", "subcategory": "fashion", "headquarters": "Barcelona"},
            {"name": "Adolfo Domínguez", "subcategory": "designer", "headquarters": "Ourense"},
            {"name": "Pedro del Hierro", "subcategory": "designer", "headquarters": "Madrid"},
            {"name": "Purificación García", "subcategory": "designer", "headquarters": "Madrid"},
            {"name": "Sfera", "subcategory": "fast_fashion", "headquarters": "Madrid"},
            {"name": "Springfield", "subcategory": "casual", "headquarters": "Madrid"},
            {"name": "Women'secret", "subcategory": "lingerie", "headquarters": "Madrid"},
            {"name": "Cortefiel", "subcategory": "fashion", "headquarters": "Madrid"},
            {"name": "Pronovias", "subcategory": "bridal", "headquarters": "Barcelona"},
            {"name": "Rosa Clará", "subcategory": "bridal", "headquarters": "Barcelona"},
            
            # Footwear
            {"name": "Camper", "subcategory": "footwear", "headquarters": "Mallorca"},
            {"name": "Pikolinos", "subcategory": "footwear", "headquarters": "Elche"},
            {"name": "Lottusse", "subcategory": "footwear", "headquarters": "Mallorca"},
            {"name": "Panama Jack", "subcategory": "footwear", "headquarters": "Alicante"},
            {"name": "Martinelli", "subcategory": "footwear", "headquarters": "Almansa"},
            {"name": "Unisa", "subcategory": "footwear", "headquarters": "Elche"},
            {"name": "Wonders", "subcategory": "footwear", "headquarters": "Elche"},
            {"name": "Marypaz", "subcategory": "footwear", "headquarters": "Sevilla"},
            
            # Luxury
            {"name": "Loewe", "subcategory": "luxury", "headquarters": "Madrid"},
            {"name": "Balenciaga", "subcategory": "luxury", "headquarters": "Paris", "metadata": {"origin": "Spanish"}},
            {"name": "Manolo Blahnik", "subcategory": "luxury_footwear", "headquarters": "London", "metadata": {"origin": "Spanish"}},
            
            # Accessories & Jewelry
            {"name": "Tous", "subcategory": "jewelry", "headquarters": "Barcelona"},
            {"name": "UNOde50", "subcategory": "jewelry", "headquarters": "Madrid"},
            {"name": "Majorica", "subcategory": "jewelry", "headquarters": "Mallorca"},
            {"name": "Aristocrazy", "subcategory": "jewelry", "headquarters": "Madrid"},
        ]

        return [
            ScrapedBrand(
                name=d["name"],
                category="fashion",
                subcategory=d.get("subcategory"),
                headquarters=d.get("headquarters"),
                source="fashion_directory",
                metadata=d.get("metadata", {})
            )
            for d in fashion_data
        ]

    def get_spanish_food_brands(self) -> List[ScrapedBrand]:
        """Returns curated list of Spanish food & beverage brands."""
        food_data = [
            # Beer
            {"name": "Mahou", "subcategory": "beer", "headquarters": "Madrid"},
            {"name": "San Miguel", "subcategory": "beer", "headquarters": "Madrid"},
            {"name": "Estrella Galicia", "subcategory": "beer", "headquarters": "A Coruña"},
            {"name": "Estrella Damm", "subcategory": "beer", "headquarters": "Barcelona"},
            {"name": "Cruzcampo", "subcategory": "beer", "headquarters": "Sevilla"},
            {"name": "Alhambra", "subcategory": "beer", "headquarters": "Granada"},
            {"name": "Ambar", "subcategory": "beer", "headquarters": "Zaragoza"},
            {"name": "Moritz", "subcategory": "beer", "headquarters": "Barcelona"},
            
            # Wine & Spirits
            {"name": "Freixenet", "subcategory": "cava", "headquarters": "Barcelona"},
            {"name": "Codorníu", "subcategory": "cava", "headquarters": "Barcelona"},
            {"name": "Torres", "subcategory": "wine", "headquarters": "Barcelona"},
            {"name": "Protos", "subcategory": "wine", "headquarters": "Valladolid"},
            {"name": "Marqués de Riscal", "subcategory": "wine", "headquarters": "La Rioja"},
            {"name": "Vega Sicilia", "subcategory": "wine", "headquarters": "Valladolid"},
            {"name": "Osborne", "subcategory": "spirits", "headquarters": "Cádiz"},
            {"name": "González Byass", "subcategory": "sherry", "headquarters": "Jerez"},
            {"name": "DYC", "subcategory": "whiskey", "headquarters": "Segovia"},
            
            # Olive Oil
            {"name": "Carbonell", "subcategory": "olive_oil", "headquarters": "Córdoba"},
            {"name": "Hojiblanca", "subcategory": "olive_oil", "headquarters": "Málaga"},
            {"name": "La Española", "subcategory": "olive_oil", "headquarters": "Sevilla"},
            {"name": "Borges", "subcategory": "olive_oil", "headquarters": "Tarragona"},
            {"name": "Ybarra", "subcategory": "olive_oil", "headquarters": "Sevilla"},
            
            # Meat & Charcuterie
            {"name": "El Pozo", "subcategory": "charcuterie", "headquarters": "Murcia"},
            {"name": "Campofrío", "subcategory": "charcuterie", "headquarters": "Madrid"},
            {"name": "Casa Tarradellas", "subcategory": "charcuterie", "headquarters": "Barcelona"},
            {"name": "Navidul", "subcategory": "ham", "headquarters": "Jabugo"},
            {"name": "5 Jotas", "subcategory": "ham", "headquarters": "Huelva"},
            {"name": "Joselito", "subcategory": "ham", "headquarters": "Salamanca"},
            
            # Dairy
            {"name": "Danone España", "subcategory": "dairy", "headquarters": "Barcelona"},
            {"name": "Puleva", "subcategory": "dairy", "headquarters": "Granada"},
            {"name": "Pascual", "subcategory": "dairy", "headquarters": "Burgos"},
            {"name": "Central Lechera Asturiana", "subcategory": "dairy", "headquarters": "Asturias"},
            {"name": "Kaiku", "subcategory": "dairy", "headquarters": "País Vasco"},
            {"name": "Larsa", "subcategory": "dairy", "headquarters": "Galicia"},
            {"name": "García Baquero", "subcategory": "cheese", "headquarters": "Ciudad Real"},
            {"name": "Queso Manchego", "subcategory": "cheese", "headquarters": "La Mancha"},
            
            # Seafood
            {"name": "Pescanova", "subcategory": "seafood", "headquarters": "Vigo"},
            {"name": "Conservas Ortiz", "subcategory": "canned_fish", "headquarters": "País Vasco"},
            {"name": "Calvo", "subcategory": "canned_fish", "headquarters": "Galicia"},
            {"name": "Isabel", "subcategory": "canned_fish", "headquarters": "Galicia"},
            
            # Snacks & Sweets
            {"name": "Valor", "subcategory": "chocolate", "headquarters": "Alicante"},
            {"name": "Lacasa", "subcategory": "chocolate", "headquarters": "Zaragoza"},
            {"name": "Cola Cao", "subcategory": "cocoa", "headquarters": "Barcelona"},
            {"name": "Nocilla", "subcategory": "spread", "headquarters": "Valencia"},
            {"name": "Gullón", "subcategory": "cookies", "headquarters": "Palencia"},
            {"name": "Cuétara", "subcategory": "cookies", "headquarters": "Madrid"},
            {"name": "Chupa Chups", "subcategory": "candy", "headquarters": "Barcelona"},
            {"name": "Conguitos", "subcategory": "candy", "headquarters": "Valencia"},
            
            # Other Food
            {"name": "Gallo", "subcategory": "pasta", "headquarters": "Córdoba"},
            {"name": "SOS", "subcategory": "rice", "headquarters": "Madrid"},
            {"name": "La Fallera", "subcategory": "rice", "headquarters": "Valencia"},
            {"name": "Arroz Dacsa", "subcategory": "rice", "headquarters": "Valencia"},
            {"name": "Helios", "subcategory": "preserves", "headquarters": "Valladolid"},
            {"name": "Hero España", "subcategory": "preserves", "headquarters": "Murcia"},
        ]

        return [
            ScrapedBrand(
                name=d["name"],
                category="food_beverage",
                subcategory=d.get("subcategory"),
                headquarters=d.get("headquarters"),
                source="food_directory",
                metadata=d.get("metadata", {})
            )
            for d in food_data
        ]

    # ==================== PARSING FIRECRAWL OUTPUT ====================

    def parse_firecrawl_brand_list(
        self,
        markdown_content: str,
        source: str,
        category: Optional[str] = None
    ) -> List[ScrapedBrand]:
        """
        Parse brand names from Firecrawl markdown output.
        
        Args:
            markdown_content: Raw markdown from Firecrawl scrape
            source: Source identifier (e.g., "kantar_brandz")
            category: Optional default category for all brands
        
        Returns:
            List of ScrapedBrand objects
        """
        brands = []
        
        # Look for common patterns: numbered lists, bullet points, tables
        lines = markdown_content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and headers
            if not line or line.startswith('#'):
                continue
            
            # Try to extract brand name from various formats
            brand_name = None
            
            # Numbered list: "1. Brand Name" or "1. **Brand Name**"
            match = re.match(r'^\d+[\.\)]\s*\*{0,2}([^*|\-\(\[]+)', line)
            if match:
                brand_name = match.group(1).strip()
            
            # Bullet point: "- Brand Name" or "* Brand Name"
            if not brand_name:
                match = re.match(r'^[\-\*]\s*\*{0,2}([^*|\-\(\[]+)', line)
                if match:
                    brand_name = match.group(1).strip()
            
            # Table row: "| Brand Name | Category |"
            if not brand_name and '|' in line:
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if parts and not parts[0].startswith('-'):
                    brand_name = parts[0]
            
            # Clean up extracted name
            if brand_name:
                # Remove markdown formatting
                brand_name = re.sub(r'\*+', '', brand_name)
                brand_name = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', brand_name)  # Links
                brand_name = brand_name.strip()
                
                # Skip if too short or looks like a header
                if len(brand_name) >= 2 and brand_name.lower() not in ['brand', 'name', 'company']:
                    brand = ScrapedBrand(
                        name=brand_name,
                        category=category,
                        source=source
                    )
                    brands.append(brand)
        
        logger.info(f"Parsed {len(brands)} brands from Firecrawl content (source: {source})")
        return brands

    # ==================== AGGREGATE COLLECTION ====================

    async def collect_all_brands(self) -> List[ScrapedBrand]:
        """
        Collect brands from all available sources.
        Returns deduplicated list of ScrapedBrand objects.
        """
        all_brands: List[ScrapedBrand] = []
        
        # 1. Manual curated list (most reliable)
        logger.info("Collecting manually curated brands...")
        all_brands.extend(self.get_top_spanish_brands_manual())
        
        # 2. Fashion brands
        logger.info("Collecting fashion brands...")
        all_brands.extend(self.get_spanish_fashion_brands())
        
        # 3. Food brands
        logger.info("Collecting food & beverage brands...")
        all_brands.extend(self.get_spanish_food_brands())
        
        # 4. Try IBEX 35 scrape (may fail due to website changes)
        try:
            logger.info("Attempting IBEX 35 scrape...")
            ibex_brands = await self.scrape_ibex35()
            all_brands.extend(ibex_brands)
        except Exception as e:
            logger.warning(f"IBEX 35 scrape failed: {e}")
        
        # Deduplicate by normalized name
        seen_names = set()
        unique_brands = []
        
        for brand in all_brands:
            # Simple normalization for dedup
            normalized = brand.name.lower().strip()
            normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
            normalized = re.sub(r'\s+', ' ', normalized)
            
            if normalized not in seen_names:
                seen_names.add(normalized)
                unique_brands.append(brand)
        
        logger.info(f"Collected {len(unique_brands)} unique brands from all sources")
        return unique_brands


# Singleton instance
_scraper_instance: Optional[BrandScraperService] = None


def get_brand_scraper_service() -> BrandScraperService:
    """Get or create brand scraper service singleton."""
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = BrandScraperService()
    return _scraper_instance
