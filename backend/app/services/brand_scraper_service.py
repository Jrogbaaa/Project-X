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
        Based on comprehensive Spanish market research (Jan 2025).
        """
        brands_data = [
            # ==================== MODA Y COMPLEMENTOS (Fashion & Accessories) ====================
            # Inditex Group
            {"name": "Zara", "category": "fashion", "subcategory": "fast_fashion", "headquarters": "A Coruña", "brand_value_eur": 33_900_000_000, "source_rank": 1,
             "description": "Cadena de moda española perteneciente a Inditex, reconocida internacionalmente por sus tiendas de ropa y accesorios de tendencia."},
            {"name": "Mango", "category": "fashion", "subcategory": "fast_fashion", "headquarters": "Barcelona",
             "description": "Empresa de moda española con presencia global, dedicada al diseño y la venta de prendas de vestir y complementos contemporáneos."},
            {"name": "Desigual", "category": "fashion", "subcategory": "fashion", "headquarters": "Barcelona",
             "description": "Marca de ropa española conocida por sus coloridos diseños estampados y estilo juvenil, con tiendas en numerosos países."},
            {"name": "Bershka", "category": "fashion", "subcategory": "fast_fashion", "headquarters": "A Coruña", "source_rank": 16,
             "description": "Cadena española de tiendas de moda juvenil del grupo Inditex, enfocada en tendencias actuales para el público joven."},
            {"name": "Stradivarius", "category": "fashion", "subcategory": "fast_fashion", "headquarters": "A Coruña", "source_rank": 18,
             "description": "Marca española de ropa del grupo Inditex, orientada a moda joven y urbana con diseños modernos para mujer."},
            {"name": "Pull & Bear", "category": "fashion", "subcategory": "fast_fashion", "headquarters": "A Coruña", "source_rank": 15,
             "description": "Cadena de moda casual española de Inditex, que ofrece ropa y accesorios desenfadados para público juvenil a precios asequibles."},
            {"name": "Massimo Dutti", "category": "fashion", "subcategory": "premium_fashion", "headquarters": "A Coruña", "source_rank": 17,
             "description": "Firma de moda española perteneciente a Inditex, especializada en prendas de estilo elegante y urbano para hombre y mujer."},
            {"name": "Oysho", "category": "fashion", "subcategory": "lingerie", "headquarters": "A Coruña",
             "description": "Marca española de moda íntima, ropa de hogar y deporte del grupo Inditex, reconocida por su estilo cómodo y actual."},
            {"name": "Uterqüe", "category": "fashion", "subcategory": "accessories", "headquarters": "A Coruña",
             "description": "Marca española de moda femenina y complementos de Inditex (ya integrada en Massimo Dutti), destacada por productos de calidad y diseño sofisticado."},
            {"name": "Lefties", "category": "fashion", "subcategory": "value_fashion", "headquarters": "A Coruña",
             "description": "Cadena española de tiendas de moda asequible perteneciente al grupo Inditex, que comercializa ropa y accesorios a precios económicos."},
            
            # Tendam Group
            {"name": "Cortefiel", "category": "fashion", "subcategory": "fashion", "headquarters": "Madrid",
             "description": "Marca española de ropa clásica fundada en 1945 (parte del grupo Tendam), con colecciones de moda para hombre y mujer de estilo atemporal."},
            {"name": "Springfield", "category": "fashion", "subcategory": "casual", "headquarters": "Madrid",
             "description": "Cadena española de moda casual perteneciente al grupo Tendam, orientada a ropa juvenil y urbana para hombre y mujer."},
            {"name": "Women'secret", "category": "fashion", "subcategory": "lingerie", "headquarters": "Madrid",
             "description": "Marca española de lencería y ropa de dormir del grupo Tendam, enfocada en moda íntima femenina y accesorios."},
            {"name": "Pedro del Hierro", "category": "fashion", "subcategory": "designer", "headquarters": "Madrid",
             "description": "Firma de moda española de lujo (grupo Tendam) que diseña prendas de vestir elegantes y de alta calidad para hombre y mujer."},
            {"name": "Tendam", "category": "fashion", "subcategory": "holding", "headquarters": "Madrid",
             "description": "Grupo español de moda que engloba marcas como Cortefiel, Springfield, Women'secret y Pedro del Hierro, destacado en el sector textil a nivel internacional."},
            
            # Spanish Designers & Premium Fashion
            {"name": "Adolfo Domínguez", "category": "fashion", "subcategory": "designer", "headquarters": "Ourense",
             "description": "Casa de moda española de autor, pionera en el prêt-à-porter nacional, conocida por sus diseños de estilo minimalista y calidad en confección."},
            {"name": "Bimba y Lola", "category": "fashion", "subcategory": "accessories", "headquarters": "Vigo",
             "description": "Marca española de moda y complementos con sede en Vigo, destacada por sus bolsos, accesorios originales y prendas de diseño vanguardista."},
            {"name": "Scalpers", "category": "fashion", "subcategory": "casual_chic", "headquarters": "Sevilla",
             "description": "Firma española de moda fundada en Sevilla, inicialmente centrada en ropa masculina y ahora con colecciones para mujer, reconocida por su estilo casual chic."},
            {"name": "El Ganso", "category": "fashion", "subcategory": "preppy", "headquarters": "Madrid",
             "description": "Cadena española de moda masculina y femenina, caracterizada por su estilo preppy y desenfadado, con presencia en múltiples países."},
            {"name": "Roberto Verino", "category": "fashion", "subcategory": "designer", "headquarters": "Ourense",
             "description": "Diseñador de moda español cuya marca homónima ofrece prendas de vestir y accesorios de estilo sofisticado, combinando tradición y modernidad."},
            {"name": "Lola Casademunt", "category": "fashion", "subcategory": "fashion", "headquarters": "Cataluña",
             "description": "Marca de moda española originaria de Cataluña, dedicada a ropa femenina, accesorios y bisutería con un estilo colorido y juvenil."},
            {"name": "Custo Barcelona", "category": "fashion", "subcategory": "designer", "headquarters": "Barcelona",
             "description": "Firma de moda española creada por los hermanos Dalmau, conocida por sus llamativas prendas con estampados gráficos y estilo vanguardista desde los años 80."},
            {"name": "Purificación García", "category": "fashion", "subcategory": "designer", "headquarters": "Madrid",
             "description": "Diseñadora y marca de moda española, enfocada en ropa, bolsos y accesorios de estilo elegante y contemporáneo para mujer y hombre."},
            
            # Luxury
            {"name": "Loewe", "category": "fashion", "subcategory": "luxury", "headquarters": "Madrid",
             "description": "Firma española de lujo fundada en 1846 y especializada en artículos de cuero, marroquinería, moda y perfumes, reconocida internacionalmente por su calidad artesanal."},
            {"name": "Balenciaga", "category": "fashion", "subcategory": "luxury", "headquarters": "Paris", "metadata": {"origin": "Spanish founder"},
             "description": "Casa de moda de lujo fundada por el diseñador español Cristóbal Balenciaga."},
            
            # Bridal
            {"name": "Pronovias", "category": "fashion", "subcategory": "bridal", "headquarters": "Barcelona",
             "description": "Empresa española líder mundial en moda nupcial de lujo, fundada en Barcelona y especializada en el diseño y confección de vestidos de novia elegantes."},
            {"name": "Rosa Clará", "category": "fashion", "subcategory": "bridal", "headquarters": "Barcelona",
             "description": "Marca española de vestidos de novia y fiesta fundada en 1995, reconocida por su innovación, elegancia y presencia internacional en el sector nupcial."},
            
            # Lingerie
            {"name": "Andrés Sardá", "category": "fashion", "subcategory": "lingerie", "headquarters": "Barcelona",
             "description": "Marca española de lencería de lujo, fundada por el diseñador homónimo, famosa por sus diseños innovadores en ropa interior femenina de alta gama."},
            
            # Footwear
            {"name": "Camper", "category": "fashion", "subcategory": "footwear", "headquarters": "Mallorca",
             "description": "Marca española de calzado originaria de Mallorca, conocida internacionalmente por sus zapatos casual e innovadores de alta calidad."},
            {"name": "Pikolinos", "category": "fashion", "subcategory": "footwear", "headquarters": "Elche",
             "description": "Empresa española de calzado con sede en Elche, dedicada al diseño y fabricación de zapatos de piel con estilo informal y artesanal."},
            {"name": "Munich", "category": "fashion", "subcategory": "footwear", "headquarters": "Barcelona",
             "description": "Marca española de calzado deportivo y urbano fundada en Barcelona, famosa por sus zapatillas de estilo retro y colores llamativos."},
            {"name": "Hispanitas", "category": "fashion", "subcategory": "footwear", "headquarters": "Elche",
             "description": "Marca española de calzado y complementos para mujer, que fabrica zapatos de piel de estilo contemporáneo combinando moda y comodidad."},
            {"name": "Gioseppo", "category": "fashion", "subcategory": "footwear", "headquarters": "Elche",
             "description": "Empresa española de calzado con sede en Elche, centrada en diseños juveniles de zapatos, sandalias y accesorios con presencia en varios países."},
            {"name": "Magnanni", "category": "fashion", "subcategory": "luxury_footwear", "headquarters": "Almansa",
             "description": "Marca española de zapatos de lujo hechos a mano, fundada en 1954 en Almansa, reconocida por su calzado de piel artesanal para caballero."},
            {"name": "Pablosky", "category": "fashion", "subcategory": "footwear", "headquarters": "Spain",
             "description": "Empresa familiar española de calzado infantil, con proyección internacional, especializada en zapatos para niños con diseño ergonómico y colorido."},
            
            # Jewelry & Accessories
            {"name": "Majorica", "category": "fashion", "subcategory": "jewelry", "headquarters": "Mallorca",
             "description": "Firma española tradicional de joyería con sede en Mallorca, famosa por sus perlas orgánicas cultivadas y sus diseños de joyas clásicas."},
            {"name": "Carrera y Carrera", "category": "fashion", "subcategory": "jewelry", "headquarters": "Madrid",
             "description": "Casa de joyería de lujo española, reconocida mundialmente por sus diseños sofisticados en oro y piedras preciosas inspirados en la cultura española."},
            {"name": "Tous", "category": "fashion", "subcategory": "jewelry", "headquarters": "Barcelona",
             "description": "Empresa española de joyería y accesorios de moda, célebre por su icónico logotipo del osito, que ofrece joyas, bolsos y perfumes de estilo actual."},
            {"name": "UNOde50", "category": "fashion", "subcategory": "jewelry", "headquarters": "Madrid",
             "description": "Marca española de joyería y bisutería artesanal, conocida por sus piezas originales de edición limitada elaboradas con metales y cuero."},
            
            # Retail
            {"name": "El Corte Inglés", "category": "retail", "subcategory": "department_store", "headquarters": "Madrid", "source_rank": 9,
             "description": "Gran cadena española de grandes almacenes, que abarca moda, hogar, electrónica y alimentación, emblemática en el sector minorista nacional."},
            
            # ==================== ALIMENTACIÓN Y BEBIDAS (Food & Beverages) ====================
            # Supermarkets & Retail
            {"name": "Mercadona", "category": "retail", "subcategory": "grocery", "headquarters": "Valencia", "source_rank": 8,
             "description": "Cadena de supermercados española líder en distribución alimentaria, conocida por su amplia presencia nacional y su marca de productos propios."},
            {"name": "Grupo DIA", "category": "retail", "subcategory": "grocery", "headquarters": "Madrid",
             "description": "Empresa española de distribución con supermercados de descuento, presente en varios países, enfocada en productos de alimentación a precios competitivos."},
            {"name": "Eroski", "category": "retail", "subcategory": "grocery", "headquarters": "País Vasco",
             "description": "Cooperativa de supermercados de origen vasco, una de las mayores distribuidoras de alimentación en España, gestionada bajo un modelo de economía social."},
            {"name": "Consum", "category": "retail", "subcategory": "grocery", "headquarters": "Valencia",
             "description": "Cooperativa valenciana de supermercados con implantación regional, dedicada a la venta de productos de alimentación y gran consumo."},
            {"name": "Covirán", "category": "retail", "subcategory": "grocery", "headquarters": "Granada",
             "description": "Cooperativa española de supermercados de proximidad, formada por detallistas independientes, con amplia presencia en zonas rurales y urbanas."},
            
            # Meat & Charcuterie
            {"name": "El Pozo Alimentación", "category": "food_beverage", "subcategory": "charcuterie", "headquarters": "Murcia",
             "description": "Empresa española líder en el sector cárnico, con sede en Murcia, especializada en producción de embutidos, jamones y otros productos alimentarios."},
            {"name": "Campofrío", "category": "food_beverage", "subcategory": "charcuterie", "headquarters": "Madrid",
             "description": "Compañía alimentaria española especializada en productos cárnicos elaborados (embutidos, jamón, fiambres), con reconocidas marcas y amplia distribución internacional."},
            
            # Olive Oil
            {"name": "Grupo Ybarra", "category": "food_beverage", "subcategory": "olive_oil", "headquarters": "Sevilla",
             "description": "Grupo alimentario español con larga trayectoria, productor de aceites de oliva, mayonesas, salsas y otros alimentos bajo marcas como Ybarra."},
            {"name": "Acesur", "category": "food_beverage", "subcategory": "olive_oil", "headquarters": "Sevilla",
             "description": "Empresa española del sector oleícola, dedicada a la producción y comercialización de aceite de oliva y girasol, propietaria de marcas como La Española y Coosur."},
            {"name": "Deoleo", "category": "food_beverage", "subcategory": "olive_oil", "headquarters": "Córdoba",
             "description": "Grupo alimentario español líder mundial en aceite de oliva embotellado, dueño de marcas históricas como Carbonell, Koipe y Hojiblanca."},
            {"name": "Carbonell", "category": "food_beverage", "subcategory": "olive_oil", "headquarters": "Córdoba",
             "description": "Marca española emblemática de aceite de oliva fundada en 1866, reconocida por su aceite virgen extra y productos derivados de la aceituna."},
            {"name": "Borges", "category": "food_beverage", "subcategory": "olive_oil", "headquarters": "Tarragona",
             "description": "Empresa alimentaria española productora de aceites de oliva, frutos secos, vinagres y otros productos mediterráneos, con fuerte presencia exportadora."},
            
            # Cocoa & Spreads
            {"name": "Idilia Foods", "category": "food_beverage", "subcategory": "cocoa", "headquarters": "Barcelona",
             "description": "Grupo español de alimentación dueño de marcas tradicionales como Cola Cao (cacao en polvo) y Nocilla (crema de cacao), populares en los hogares españoles."},
            {"name": "Cola Cao", "category": "food_beverage", "subcategory": "cocoa", "headquarters": "Barcelona",
             "description": "Marca española de cacao soluble en polvo para preparar bebida de chocolate, icono del desayuno en España desde hace décadas."},
            {"name": "Nocilla", "category": "food_beverage", "subcategory": "spread", "headquarters": "Valencia",
             "description": "Crema de cacao y avellanas española similar a una mermelada de chocolate, muy extendida en la merienda infantil y parte de la cultura popular."},
            
            # Cookies & Biscuits
            {"name": "Galletas Gullón", "category": "food_beverage", "subcategory": "cookies", "headquarters": "Palencia",
             "description": "Empresa galletera española, líder en la fabricación de galletas y productos de pastelería, conocida por su innovación y por exportar a numerosos países."},
            
            # Confectionery
            {"name": "Chupa Chups", "category": "food_beverage", "subcategory": "confectionery", "headquarters": "Barcelona",
             "description": "Marca española de caramelos con palo (piruletas) fundada en 1958, de fama mundial gracias a sus sabores variados y su logotipo diseñado por Salvador Dalí."},
            {"name": "Lacasa", "category": "food_beverage", "subcategory": "chocolate", "headquarters": "Zaragoza",
             "description": "Empresa chocolatera española fundada en 1852, productora de chocolates y dulces populares como Lacasitos y Conguitos, con fuerte presencia en temporadas navideñas."},
            {"name": "Chocolates Valor", "category": "food_beverage", "subcategory": "chocolate", "headquarters": "Alicante",
             "description": "Tradicional empresa española dedicada al chocolate, famosa por sus chocolates a la taza, bombones y tabletas de alta calidad desde 1881."},
            {"name": "Vidal Golosinas", "category": "food_beverage", "subcategory": "confectionery", "headquarters": "Murcia",
             "description": "Compañía española líder en producción de golosinas y caramelos, con amplio catálogo de dulces de goma, regaliz y confitería exportados a numerosos países."},
            {"name": "Fini", "category": "food_beverage", "subcategory": "confectionery", "headquarters": "Valencia",
             "description": "Empresa española de confitería especializada en caramelos de goma, regalices y marshmallows, muy conocida por sus dulces innovadores y de fantasía."},
            
            # Snacks
            {"name": "Matutano", "category": "food_beverage", "subcategory": "snacks", "headquarters": "Madrid",
             "description": "Marca española de snacks salados (patatas fritas, aperitivos de maíz) fundada en los años 60, integrada actualmente en Pepsico, muy reconocida por productos como Cheetos o Doritos en España."},
            
            # Bakery
            {"name": "Vicky Foods", "category": "food_beverage", "subcategory": "bakery", "headquarters": "Valencia",
             "description": "Grupo alimentario español (antes llamado Dulcesol) líder en bollería, panadería y alimentación infantil, con marcas propias de productos de pastelería y pan de molde."},
            
            # Pasta & Rice
            {"name": "Pastas Gallo", "category": "food_beverage", "subcategory": "pasta", "headquarters": "Córdoba",
             "description": "Empresa alimentaria española fundada en 1946, líder nacional en la producción de pasta alimenticia, así como en sémolas, harinas y platos preparados."},
            {"name": "Arroz SOS", "category": "food_beverage", "subcategory": "rice", "headquarters": "Madrid",
             "description": "Marca española de arroz fundada en 1903, referente en el mercado por su arroz de grano redondo, ahora parte del grupo Ebro Foods."},
            
            # Prepared Foods
            {"name": "Casa Tarradellas", "category": "food_beverage", "subcategory": "prepared_foods", "headquarters": "Barcelona",
             "description": "Empresa española de alimentación con sede en Cataluña, conocida por sus pizzas frescas, patés y fuets, ampliamente distribuidos en supermercados."},
            {"name": "Gallina Blanca", "category": "food_beverage", "subcategory": "prepared_foods", "headquarters": "Barcelona",
             "description": "Marca española histórica de productos alimenticios (caldos, sopas, pasta) fundada en 1937, referente en la cocina casera con su famoso caldo Avecrem."},
            
            # Spices
            {"name": "Carmencita", "category": "food_beverage", "subcategory": "spices", "headquarters": "Novelda",
             "description": "Empresa española líder en especias y condimentos, originaria de Novelda, conocida por su gama de pimentón, azafrán, infusiones y preparaciones para paella."},
            
            # Juices & Non-Alcoholic
            {"name": "Don Simón", "category": "food_beverage", "subcategory": "beverages", "headquarters": "Jumilla",
             "description": "Marca española de bebidas y alimentos (perteneciente a J. García-Carrión) célebre por sus zumos y vinos envasados, muy presentes en supermercados nacionales."},
            {"name": "J. García-Carrión", "category": "food_beverage", "subcategory": "beverages", "headquarters": "Jumilla",
             "description": "Grupo vinícola y de bebidas español, mayor productor de vino de Europa y conocido por marcas populares de vino y zumos como Don Simón."},
            
            # Wine & Cava
            {"name": "Freixenet", "category": "food_beverage", "subcategory": "cava", "headquarters": "Barcelona",
             "description": "Bodega española líder en la elaboración de cava (vino espumoso), originaria de Cataluña, reconocida internacionalmente por sus cavas brut y semisecos."},
            {"name": "Codorníu", "category": "food_beverage", "subcategory": "cava", "headquarters": "Barcelona",
             "description": "Bodega centenaria española con sede en Cataluña, pionera en la producción de cava tradicional, famosa por sus vinos espumosos desde el siglo XVI."},
            {"name": "Marqués de Cáceres", "category": "food_beverage", "subcategory": "wine", "headquarters": "La Rioja",
             "description": "Prestigiosa bodega de la Rioja (España) que produce vinos tintos, blancos y rosados de renombre, muy valorados en el mercado internacional."},
            {"name": "Bodegas Matarromera", "category": "food_beverage", "subcategory": "wine", "headquarters": "Valladolid",
             "description": "Grupo vitivinícola español con origen en Ribera del Duero, destacado por sus vinos tintos de alta gama y diversificación en aceite y enoturismo."},
            {"name": "Marqués de Vargas", "category": "food_beverage", "subcategory": "wine", "headquarters": "La Rioja",
             "description": "Bodega boutique española de la Rioja, dedicada a la producción limitada de vinos de alta calidad bajo una de las familias históricas del vino español."},
            {"name": "Abadía Retuerta", "category": "food_beverage", "subcategory": "wine", "headquarters": "Valladolid",
             "description": "Bodega española situada en Valladolid, reconocida por sus vinos de pago elaborados en su finca, así como por su hotel enoturístico en un monasterio del siglo XII."},
            {"name": "Pago de los Capellanes", "category": "food_beverage", "subcategory": "wine", "headquarters": "Burgos",
             "description": "Bodega familiar española de Ribera del Duero, aclamada por sus vinos tintos elegantes y con carácter, elaborados de forma artesanal."},
            {"name": "Vivanco", "category": "food_beverage", "subcategory": "wine", "headquarters": "La Rioja",
             "description": "Bodega española de Rioja que combina la producción de vinos de calidad con la difusión de la cultura del vino a través de su Museo Vivanco de la Cultura del Vino."},
            {"name": "Barbadillo", "category": "food_beverage", "subcategory": "sherry", "headquarters": "Cádiz",
             "description": "Bodega española de Sanlúcar de Barrameda (Cádiz), famosa por sus vinos de Jerez y manzanillas, entre ellos la popular manzanilla Barbadillo y otros vinos blancos andaluces."},
            {"name": "Félix Solís Avantis", "category": "food_beverage", "subcategory": "wine", "headquarters": "Ciudad Real",
             "description": "Importante grupo vinícola español de la Mancha, productor de vinos y sangrías bajo marcas reconocidas (como Los Molinos o Viña Albali), con amplia exportación global."},
            
            # Spirits & Liqueurs
            {"name": "Osborne", "category": "food_beverage", "subcategory": "spirits", "headquarters": "Cádiz",
             "description": "Grupo bodeguero español fundado en 1772, productor de vinos de Jerez, brandis y otros licores (con el emblemático toro de Osborne), dueño de marcas como Cinco Jotas (jamón ibérico)."},
            {"name": "Fundador", "category": "food_beverage", "subcategory": "brandy", "headquarters": "Jerez",
             "description": "Primera marca de brandy de Jerez de España (desde 1874), elaborada en las bodegas Fundador de Jerez, famosa por sus brandis y vinos sherry tradicionales."},
            {"name": "Zamora Company", "category": "food_beverage", "subcategory": "spirits", "headquarters": "Cartagena",
             "description": "Grupo español propietario de destacadas marcas de bebidas espirituosas y licores, como Licor 43, Ramón Bilbao (vinos) o Martin Miller's (ginebra), con amplia presencia internacional."},
            {"name": "Licor 43", "category": "food_beverage", "subcategory": "liqueur", "headquarters": "Cartagena",
             "description": "Licor dulce español elaborado a base de hierbas y cítricos, originario de Cartagena, muy popular internacionalmente por su sabor vainillado único."},
            {"name": "Destilerías DYC", "category": "food_beverage", "subcategory": "whiskey", "headquarters": "Segovia",
             "description": "Productora española de whisky fundada en Segovia en 1958, célebre por crear el primer whisky español de malta, DYC, muy arraigado en el mercado nacional."},
            
            # Beer
            {"name": "Damm", "category": "food_beverage", "subcategory": "beer", "headquarters": "Barcelona",
             "description": "Empresa cervecera española fundada en Barcelona, productora de cervezas populares como Estrella Damm, y otras variedades, con fuerte arraigo en la cultura cervecera mediterránea."},
            {"name": "Estrella Damm", "category": "food_beverage", "subcategory": "beer", "headquarters": "Barcelona",
             "description": "Cerveza lager pálida emblemática de Barcelona, elaborada por Damm desde 1876, conocida como la cerveza mediterránea por excelencia."},
            {"name": "Mahou San Miguel", "category": "food_beverage", "subcategory": "beer", "headquarters": "Madrid",
             "description": "Grupo cervecero español líder (resultado de la fusión de Mahou y San Miguel), responsable de cervezas tan conocidas como Mahou Cinco Estrellas, San Miguel Especial y Alhambra."},
            {"name": "Cruzcampo", "category": "food_beverage", "subcategory": "beer", "headquarters": "Sevilla",
             "description": "Marca de cerveza española fundada en Sevilla en 1904, muy popular a nivel nacional, especialmente conocida por su cerveza tipo lager rubia de sabor suave."},
            {"name": "Estrella Galicia", "category": "food_beverage", "subcategory": "beer", "headquarters": "A Coruña",
             "description": "Cerveza lager gallega producida por Hijos de Rivera desde 1906, apreciada por su sabor equilibrado y convertida en una de las cervezas artesanales industriales más populares de España."},
            {"name": "Hijos de Rivera", "category": "food_beverage", "subcategory": "beer", "headquarters": "A Coruña",
             "description": "Corporación gallega dueña de la cerveza Estrella Galicia y otras bebidas, incluyendo aguas y sidras, destacada por mantener la tradición cervecera familiar."},
            
            # Dairy & Ice Cream
            {"name": "Grupo Kalise", "category": "food_beverage", "subcategory": "dairy", "headquarters": "Canarias",
             "description": "Empresa canaria de alimentación, conocida por sus helados y lácteos con marca Kalise y Celgán, muy presente en el mercado local y nacional."},
            
            # Seafood & Canned Fish
            {"name": "Conservas Antonio Alonso (Albo)", "category": "food_beverage", "subcategory": "canned_fish", "headquarters": "Cantabria",
             "description": "Empresa española conservera, propietaria de la marca Albo, dedicada a la fabricación de conservas de pescado y marisco de alta calidad desde 1869."},
            {"name": "Grupo Nueva Pescanova", "category": "food_beverage", "subcategory": "seafood", "headquarters": "Vigo",
             "description": "Compañía pesquera española líder en productos del mar, dedicada a la pesca, acuicultura y elaboración de congelados, con marca emblemática Pescanova."},
            
            # Fast Food & Restaurants
            {"name": "Restalia", "category": "food_beverage", "subcategory": "restaurant", "headquarters": "Madrid",
             "description": "Grupo español de restauración que opera la popular cadena 100 Montaditos, conocida por sus bocadillos pequeños a precios económicos y ambiente informal."},
            {"name": "100 Montaditos", "category": "food_beverage", "subcategory": "restaurant", "headquarters": "Sevilla",
             "description": "Cadena de cervecerías y restaurantes española especializada en montaditos (pequeños bocadillos) con variedades diversas, reconocida por su modelo de precios económicos."},
            {"name": "Telepizza", "category": "food_beverage", "subcategory": "restaurant", "headquarters": "Madrid",
             "description": "Franquicia española de comida rápida centrada en la elaboración y entrega a domicilio de pizzas, con amplia presencia en España y expansión en Latinoamérica y Europa."},
            {"name": "Pans & Company", "category": "food_beverage", "subcategory": "restaurant", "headquarters": "Barcelona",
             "description": "Cadena española de comida rápida perteneciente al grupo Eat Out, especializada en bocadillos recién hechos, focaccias y otros productos de panadería salada."},
            
            # ==================== AUTOMOCIÓN Y TRANSPORTE (Automotive & Transport) ====================
            # Automotive
            {"name": "SEAT", "category": "automotive", "headquarters": "Barcelona",
             "description": "Histórica marca española de automóviles fundada en 1950, con sede en Martorell, fabricante de vehículos populares como Ibiza o León, actualmente parte del grupo Volkswagen."},
            {"name": "Cupra", "category": "automotive", "headquarters": "Barcelona",
             "description": "Marca automovilística española de alto rendimiento surgida en 2018 como división deportiva de SEAT, enfocada en coches de diseño vanguardista y carácter deportivo."},
            
            # Bus & Coach Manufacturing
            {"name": "Irizar", "category": "automotive", "subcategory": "bus_manufacturing", "headquarters": "País Vasco",
             "description": "Empresa española con sede en el País Vasco dedicada a la fabricación de autobuses y autocares, reconocida internacionalmente por sus autobuses de turismo y eléctricos."},
            
            # Rail
            {"name": "CAF", "category": "manufacturing", "subcategory": "rail", "headquarters": "País Vasco",
             "description": "Compañía española fabricante de material ferroviario (trenes, tranvías y metros), con presencia mundial suministrando vehículos y equipo de transporte público."},
            {"name": "Talgo", "category": "manufacturing", "subcategory": "rail", "headquarters": "Madrid",
             "description": "Empresa española dedicada a la construcción de trenes de pasajeros y tecnología ferroviaria, famosa por sus trenes de rodadura desplazable utilizados en servicios de alta velocidad y larga distancia."},
            
            # Shipbuilding & Aerospace
            {"name": "Navantia", "category": "manufacturing", "subcategory": "shipbuilding", "headquarters": "Cartagena",
             "description": "Astillero público español especializado en la construcción naval militar y civil, responsable de la fabricación de buques de guerra, submarinos y embarcaciones para armadas internacionales."},
            {"name": "Airbus España", "category": "manufacturing", "subcategory": "aerospace", "headquarters": "Madrid",
             "description": "División española del consorcio aeronáutico Airbus, que integra antiguas empresas CASA, participando en el diseño y fabricación de aviones civiles y militares (como el Airbus A400M)."},
            
            # Airlines
            {"name": "Iberia", "category": "travel", "subcategory": "airline", "headquarters": "Madrid",
             "description": "Aerolínea de bandera española fundada en 1927, que opera rutas nacionales e internacionales, miembro de IAG y reconocida como una de las compañías aéreas más antiguas del mundo."},
            {"name": "Air Europa", "category": "travel", "subcategory": "airline", "headquarters": "Mallorca",
             "description": "Aerolínea española privada con base en Mallorca, enfocada en vuelos domésticos e internacionales, especialmente rutas entre Europa y América, parte del grupo Globalia."},
            {"name": "Vueling", "category": "travel", "subcategory": "airline", "headquarters": "Barcelona",
             "description": "Aerolínea española de bajo coste perteneciente al grupo IAG, con sede en Barcelona, que opera numerosos destinos europeos con un modelo de tarifas económicas."},
            {"name": "Volotea", "category": "travel", "subcategory": "airline", "headquarters": "Asturias",
             "description": "Aerolínea española de bajo costo fundada en 2012, especializada en conectar ciudades europeas medianas y pequeñas, con sede operativa en Asturias."},
            {"name": "Plus Ultra Líneas Aéreas", "category": "travel", "subcategory": "airline", "headquarters": "Madrid",
             "description": "Compañía aérea española de larga distancia fundada en 2011, que opera vuelos chárter y regulares principalmente entre España y Latinoamérica."},
            {"name": "Binter Canarias", "category": "travel", "subcategory": "airline", "headquarters": "Canarias",
             "description": "Aerolínea regional española con base en Canarias, dedicada al transporte aéreo interinsular y conexiones con destinos próximos en África y Europa."},
            
            # Rail Transport
            {"name": "Renfe", "category": "travel", "subcategory": "rail", "headquarters": "Madrid",
             "description": "Operadora ferroviaria nacional de España (de propiedad pública), encargada del transporte de pasajeros y mercancías por tren, incluyendo servicios de Alta Velocidad (AVE) en el país."},
            {"name": "Metro de Madrid", "category": "travel", "subcategory": "metro", "headquarters": "Madrid",
             "description": "Sistema de ferrocarril metropolitano de la ciudad de Madrid, uno de los metros más extensos del mundo, operado por la empresa pública homónima desde 1919."},
            
            # Mobility & Transport Services
            {"name": "Cabify", "category": "technology", "subcategory": "mobility", "headquarters": "Madrid",
             "description": "Plataforma española de transporte que conecta pasajeros con vehículos con conductor a través de una app móvil, presente en España y Latinoamérica como alternativa a los taxis tradicionales."},
            {"name": "ALSA", "category": "travel", "subcategory": "bus", "headquarters": "Madrid",
             "description": "Empresa española líder en transporte de autobús de larga distancia, que opera líneas regulares nacionales e internacionales, con una larga trayectoria desde 1923."},
            {"name": "Correos", "category": "services", "subcategory": "postal", "headquarters": "Madrid",
             "description": "Operador público del servicio postal en España, encargado de la distribución de envíos postales y paquetería a nivel nacional e internacional, con amplia red de oficinas."},
            
            # Fuel & Service Stations
            {"name": "CEPSA", "category": "energy", "subcategory": "fuel", "headquarters": "Madrid",
             "description": "Compañía Española de Petróleos que, además de refino y distribución de combustibles, gestiona la red de estaciones de servicio CEPSA, presente en carreteras de toda España."},
            {"name": "Wible", "category": "technology", "subcategory": "carsharing", "headquarters": "Madrid",
             "description": "Servicio de carsharing en Madrid fruto de una joint venture hispano-coreana (Repsol y Kia), que proporciona coches compartidos híbridos para alquiler por minutos."},
            
            # ==================== TECNOLOGÍA Y TELECOMUNICACIONES (Technology & Telecom) ====================
            {"name": "Telefónica", "category": "telecom", "headquarters": "Madrid",
             "description": "Multinacional española de telecomunicaciones, una de las mayores del mundo, que brinda servicios de telefonía fija, móvil, internet y TV (con marcas como Movistar y O2 en distintos mercados)."},
            {"name": "Movistar", "category": "telecom", "headquarters": "Madrid", "brand_value_eur": 12_600_000_000, "source_rank": 4,
             "description": "Marca comercial principal de Telefónica en España para telefonía e internet, que ofrece servicios de móvil, fibra óptica, televisión de pago (Movistar+) y soluciones digitales para el hogar."},
            {"name": "Orange España", "category": "telecom", "headquarters": "Madrid",
             "description": "Operadora de telecomunicaciones en España (filial de la francesa Orange) que presta servicios de móvil, internet y TV, tras la adquisición de Amena y Jazztel en el mercado español."},
            {"name": "Vodafone España", "category": "telecom", "headquarters": "Madrid",
             "description": "Filial española de la multinacional británica Vodafone, proveedora de servicios integrales de telecomunicaciones móviles, fijas y de televisión por cable en el país."},
            {"name": "MásMóvil", "category": "telecom", "headquarters": "Madrid",
             "description": "Operador español de telecomunicaciones surgido en 2006, que ha crecido con marcas como Yoigo, Pepephone y Lowi (joint venture), ofreciendo servicios de móvil e internet convergentes."},
            {"name": "Yoigo", "category": "telecom", "headquarters": "Madrid",
             "description": "Cuarto operador móvil español por tamaño, originalmente lanzado en 2006, conocido por sus tarifas competitivas, actualmente parte del Grupo MásMóvil."},
            {"name": "Jazztel", "category": "telecom", "headquarters": "Madrid",
             "description": "Operador español de telecomunicaciones fundado en los 90, enfocado en internet de banda ancha y telefonía fija/móvil, hoy integrado bajo la marca Orange tras su adquisición."},
            {"name": "Euskaltel", "category": "telecom", "headquarters": "País Vasco",
             "description": "Operador de telecomunicaciones regional del País Vasco (ahora parte del Grupo MásMóvil), que ofrece servicios de fibra óptica, telefonía móvil y televisión principalmente en el norte de España."},
            
            # Technology Companies
            {"name": "Indra", "category": "technology", "subcategory": "it_services", "headquarters": "Madrid",
             "description": "Empresa tecnológica multinacional española, líder en consultoría, transformación digital y sistemas de defensa, que desarrolla soluciones de TI para transporte, energía, administraciones y más."},
            {"name": "Amadeus IT Group", "category": "technology", "subcategory": "travel_tech", "headquarters": "Madrid",
             "description": "Compañía tecnológica española proveedora de soluciones de reserva y gestión para la industria de viajes (aerolíneas, hoteles, agencias), con sistemas implantados a nivel global."},
            {"name": "Panda Security", "category": "technology", "subcategory": "cybersecurity", "headquarters": "Bilbao",
             "description": "Empresa española desarrolladora de software antivirus y ciberseguridad, reconocida por sus soluciones de protección informática y pionera en ofrecer antivirus en la nube."},
            {"name": "Glovo", "category": "technology", "subcategory": "delivery", "headquarters": "Barcelona",
             "description": "Startup tecnológica española fundada en Barcelona, que opera una plataforma de reparto a domicilio multi-categoría, conectando a través de app a repartidores con restaurantes y tiendas locales."},
            {"name": "Softonic", "category": "technology", "subcategory": "software", "headquarters": "Barcelona",
             "description": "Portal web español fundado en 1997 especializado en la descarga segura de software, aplicaciones y juegos, convertido en una referencia internacional para obtener software en múltiples idiomas."},
            {"name": "Wallapop", "category": "technology", "subcategory": "marketplace", "headquarters": "Barcelona",
             "description": "Plataforma española en línea de compra-venta de productos de segunda mano geolocalizada, que permite a usuarios particulares comerciar artículos usados de forma cercana y segura mediante app móvil."},
            {"name": "Bq", "category": "technology", "subcategory": "electronics", "headquarters": "Madrid",
             "description": "Marca española de electrónica de consumo que destacó por diseñar y comercializar smartphones, tabletas y lectores electrónicos, así como impresoras 3D, fomentando tecnología accesible (operó entre 2010–2018)."},
            {"name": "Energy Sistem", "category": "technology", "subcategory": "electronics", "headquarters": "Alicante",
             "description": "Empresa española de tecnología de consumo con sede en Alicante, dedicada al diseño de dispositivos electrónicos asequibles (auriculares, altavoces, tablets, e-readers) orientados al gran público."},
            {"name": "Tuenti", "category": "technology", "subcategory": "telecom", "headquarters": "Madrid",
             "description": "Antigua red social española muy popular entre jóvenes (2006–2012), que posteriormente se reconvirtió en un operador móvil virtual bajo Movistar, recordada como fenómeno de internet en España."},
            {"name": "Scytl", "category": "technology", "subcategory": "govtech", "headquarters": "Barcelona",
             "description": "Compañía tecnológica española especializada en soluciones de voto electrónico y modernización electoral, con reconocimiento internacional por implantar sistemas de voto seguro en múltiples países."},
            {"name": "Sherpa.ai", "category": "technology", "subcategory": "ai", "headquarters": "País Vasco",
             "description": "Startup española centrada en inteligencia artificial y asistentes virtuales de voz, originaria del País Vasco, que desarrolla tecnologías de IA aplicadas a asistentes personales en español."},
            {"name": "EGA Master", "category": "technology", "subcategory": "industrial_tools", "headquarters": "Álava",
             "description": "Empresa española innovadora de herramientas profesionales y equipos industriales, con sede en Álava, reconocida por su catálogo de herramientas de mano y soluciones para entornos industriales exigentes."},
            {"name": "Hisdesat", "category": "technology", "subcategory": "satellites", "headquarters": "Madrid",
             "description": "Operador español de satélites gubernamentales, dedicado a comunicaciones seguras y observación terrestre para defensa, emergencias y usos científicos, participada por entidades públicas y privadas."},
            
            # ==================== FINANZAS Y SERVICIOS (Finance & Services) ====================
            # Banking
            {"name": "Banco Santander", "category": "banking", "headquarters": "Santander", "brand_value_eur": 11_000_000_000, "source_rank": 2,
             "description": "Banco global español con sede en Santander, uno de los mayores grupos financieros del mundo, que ofrece servicios bancarios universales en Europa y América."},
            {"name": "BBVA", "category": "banking", "headquarters": "Bilbao", "brand_value_eur": 11_400_000_000, "source_rank": 3,
             "description": "Gran banco multinacional español, con origen en el País Vasco, dedicado a banca comercial, inversiones y servicios financieros en más de 30 países."},
            {"name": "CaixaBank", "category": "banking", "headquarters": "Valencia", "source_rank": 5,
             "description": "Importante entidad bancaria española, resultado de la fusión de La Caixa y Bankia, con fuerte presencia nacional en banca minorista y una reconocida obra social."},
            {"name": "Banco Sabadell", "category": "banking", "headquarters": "Barcelona",
             "description": "Banco español con sede en Cataluña, centrado en banca comercial y de empresas, con presencia internacional y conocido por sus campañas publicitarias emotivas."},
            {"name": "Bankinter", "category": "banking", "headquarters": "Madrid",
             "description": "Banco español independiente con enfoque en banca minorista y privada, destacado por su innovación tecnológica y sólida posición en el mercado ibérico."},
            {"name": "Ibercaja", "category": "banking", "headquarters": "Zaragoza",
             "description": "Entidad financiera española originaria de Aragón, surgida de una antigua caja de ahorros, que ofrece servicios bancarios principalmente en el noreste y centro de España."},
            {"name": "Unicaja Banco", "category": "banking", "headquarters": "Málaga",
             "description": "Banco español con base en Andalucía, nacido de la fusión de cajas andaluzas, enfocado en banca de particulares y pymes con implantación en el sur y centro del país."},
            {"name": "Kutxabank", "category": "banking", "headquarters": "País Vasco",
             "description": "Grupo bancario español formado por las antiguas cajas vascas (BBK, Kutxa, Vital), centrado en el País Vasco y regiones aledañas, con actividad en banca minorista y seguros."},
            {"name": "Abanca", "category": "banking", "headquarters": "Galicia",
             "description": "Entidad bancaria española con sede en Galicia (heredera de Caixa Galicia/Caixanova), dedicada a banca comercial y de empresas, con expansión en Portugal y América."},
            
            # Insurance
            {"name": "Mapfre", "category": "insurance", "headquarters": "Madrid", "source_rank": 10,
             "description": "Aseguradora multinacional española, líder en seguros de automóvil, hogar y vida, con presencia en Europa y América, originaria como mutualidad de propietarios de fincas rústicas."},
            {"name": "Mutua Madrileña", "category": "insurance", "headquarters": "Madrid",
             "description": "Compañía aseguradora española (mutua) fundada en 1930, especializada en seguros de automóvil y salud, con amplia cuota de mercado y sede en Madrid."},
            {"name": "Catalana Occidente", "category": "insurance", "headquarters": "Barcelona",
             "description": "Grupo asegurador español con origen en Cataluña, destacado en seguros de crédito y seguro multirriesgo, que engloba marcas como Plus Ultra, Seguros Bilbao y NorteHispana."},
            {"name": "Línea Directa", "category": "insurance", "headquarters": "Madrid",
             "description": "Aseguradora española de venta directa fundada en 1995, especializada en seguros de coche, moto y hogar, conocida por operar principalmente vía telefónica e internet sin oficinas físicas."},
            {"name": "Mutua MAZ", "category": "insurance", "subcategory": "occupational", "headquarters": "Zaragoza",
             "description": "Mutua de Accidentes de Zaragoza, entidad colaboradora de la Seguridad Social española especializada en la gestión de riesgos laborales y prestaciones por accidentes de trabajo y enfermedad profesional."},
            {"name": "CESCE", "category": "insurance", "subcategory": "credit", "headquarters": "Madrid",
             "description": "Compañía Española de Seguros de Crédito a la Exportación, entidad mixta público-privada que asegura a las empresas españolas frente al riesgo de impago en sus operaciones comerciales internacionales."},
            {"name": "Crédito y Caución", "category": "insurance", "subcategory": "credit", "headquarters": "Madrid",
             "description": "Aseguradora española especializada en seguros de crédito interior y a la exportación, que protege a las empresas frente al impago de sus clientes y ofrece servicios de información comercial."},
            
            # Legal & Consulting
            {"name": "Garrigues", "category": "services", "subcategory": "legal", "headquarters": "Madrid",
             "description": "Firma de abogados española, una de las más grandes de Europa continental, que ofrece asesoría jurídica y fiscal en todas las ramas de derecho, con destacada proyección internacional."},
            {"name": "Cuatrecasas", "category": "services", "subcategory": "legal", "headquarters": "Barcelona",
             "description": "Prestigioso bufete de abogados español con presencia global, especializado en derecho empresarial, que brinda asesoramiento legal integral a grandes empresas e instituciones."},
            {"name": "ClarkeModet", "category": "services", "subcategory": "intellectual_property", "headquarters": "Madrid",
             "description": "Consultora española líder en propiedad industrial e intelectual en países de habla hispana, dedicada al registro de patentes, marcas y defensa de la propiedad intelectual para empresas."},
            {"name": "LLYC", "category": "services", "subcategory": "communications", "headquarters": "Madrid",
             "description": "Consultora española de comunicación y relaciones públicas de alcance internacional, especializada en comunicación corporativa, gestión de crisis y asuntos públicos para empresas e instituciones."},
            
            # Certification & Standards
            {"name": "AENOR", "category": "services", "subcategory": "certification", "headquarters": "Madrid",
             "description": "Entidad Nacional de Certificación española, líder en otorgar certificados de calidad, gestión ambiental, I+D+i y otras normas, cuyos sellos son reconocidos en el ámbito empresarial y comercial."},
            
            # Education & Business Schools
            {"name": "IESE Business School", "category": "services", "subcategory": "education", "headquarters": "Barcelona",
             "description": "Escuela de negocios de la Universidad de Navarra (España), reconocida entre las mejores del mundo, que ofrece programas MBA y formación para directivos con un enfoque internacional."},
            {"name": "IE University", "category": "services", "subcategory": "education", "headquarters": "Madrid",
             "description": "Universidad privada española con campus en Madrid y Segovia, destacada en áreas de negocios, derecho y arquitectura, que atrae a estudiantes internacionales con programas innovadores."},
            {"name": "ESADE", "category": "services", "subcategory": "education", "headquarters": "Barcelona",
             "description": "Escuela superior de administración y dirección de empresas en Barcelona (España), reputada internacionalmente por sus programas de MBA, derecho y formación ejecutiva."},
            {"name": "ESIC Business & Marketing School", "category": "services", "subcategory": "education", "headquarters": "Madrid",
             "description": "Institución académica privada española especializada en estudios de marketing, empresa y economía digital, con campus en varias ciudades y reconocida por su conexión con el mundo empresarial."},
            {"name": "EOI", "category": "services", "subcategory": "education", "headquarters": "Madrid",
             "description": "Escuela de negocios pública española fundada en 1955, centrada en la formación de directivos en áreas de empresa, tecnología y sostenibilidad, dependiente del Ministerio de Industria."},
            
            # ==================== INDUSTRIA Y ENERGÍA (Industry & Energy) ====================
            # Energy
            {"name": "Repsol", "category": "energy", "headquarters": "Madrid", "source_rank": 7,
             "description": "Multinacional energética española con actividades en exploración, producción de petróleo y gas, refino y estaciones de servicio, siendo una de las principales petroleras integradas de Europa."},
            {"name": "Cepsa", "category": "energy", "headquarters": "Madrid",
             "description": "Compañía energética española (Compañía Española de Petróleos) dedicada a la exploración petrolífera, refino, química y venta de combustibles, con presencia notable en España y el norte de África."},
            {"name": "Iberdrola", "category": "utilities", "headquarters": "Bilbao", "source_rank": 6,
             "description": "Empresa española líder en el sector de energía eléctrica, pionera en energías renovables, que genera, distribuye y comercializa electricidad en España y numerosos países del mundo."},
            {"name": "Endesa", "category": "utilities", "headquarters": "Madrid",
             "description": "Compañía eléctrica española fundada en 1944, dedicada a la generación y distribución de electricidad, con importante presencia en España y Latinoamérica (actualmente parte del grupo Enel)."},
            {"name": "Naturgy", "category": "utilities", "headquarters": "Barcelona",
             "description": "Grupo energético español antes conocido como Gas Natural Fenosa, centrado en la distribución de gas natural, generación eléctrica y soluciones energéticas en mercados internacionales."},
            {"name": "Enagás", "category": "utilities", "subcategory": "gas", "headquarters": "Madrid",
             "description": "Empresa española que actúa como el principal operador del sistema de gas natural en España, encargada del transporte y gestión de infraestructuras de gas (gasoductos, plantas de GNL) a nivel nacional."},
            {"name": "Red Eléctrica de España", "category": "utilities", "subcategory": "electricity", "headquarters": "Madrid",
             "description": "Operador español del sistema eléctrico nacional, encargado del transporte de electricidad de alta tensión y la gestión técnica de la red para garantizar el suministro eléctrico en el país."},
            
            # Construction & Infrastructure
            {"name": "Acciona", "category": "construction", "headquarters": "Madrid",
             "description": "Corporación española diversificada enfocada en infraestructuras sostenibles, construcción civil y energías renovables (eólica, solar), destacada por proyectos globales de ingeniería y obra pública."},
            {"name": "Ferrovial", "category": "construction", "headquarters": "Madrid",
             "description": "Grupo multinacional español dedicado a la construcción, operación de infraestructuras de transporte (autopistas, aeropuertos) y servicios urbanos, con proyectos emblemáticos en varios continentes."},
            {"name": "ACS", "category": "construction", "headquarters": "Madrid",
             "description": "Empresa española de construcción e ingeniería (Actividades de Construcción y Servicios), una de las mayores a nivel mundial, que desarrolla grandes obras civiles, concesiones de infraestructuras y servicios industriales."},
            {"name": "FCC", "category": "construction", "headquarters": "Madrid",
             "description": "Grupo Fomento de Construcciones y Contratas, compañía española centrada en construcción, servicios medioambientales y gestión de infraestructuras, con gran trayectoria en obra civil dentro y fuera de España."},
            {"name": "Sacyr", "category": "construction", "headquarters": "Madrid",
             "description": "Empresa española de construcción, infraestructuras y servicios, reconocida por proyectos de ingeniería civil tanto en España como en América (como la ampliación del Canal de Panamá)."},
            {"name": "OHL", "category": "construction", "headquarters": "Madrid",
             "description": "Grupo español de ingeniería y construcción internacional, implicado en grandes obras civiles, proyectos hospitalarios y de transporte, con presencia significativa en Latinoamérica y Europa."},
            {"name": "Abengoa", "category": "construction", "subcategory": "energy", "headquarters": "Sevilla",
             "description": "Empresa española de ingeniería y energía, especialista en proyectos de energías renovables (solar, bioetanol), agua y medioambiente, aunque reestructurada recientemente tras dificultades financieras."},
            
            # Wind Energy
            {"name": "Siemens Gamesa", "category": "manufacturing", "subcategory": "wind_energy", "headquarters": "Zamudio",
             "description": "Compañía fabricante de aerogeneradores de origen español (antigua Gamesa) fusionada con Siemens, líder global en diseño y producción de turbinas eólicas terrestres y marinas."},
            
            # Industrial Cooperatives
            {"name": "Mondragón Corporación", "category": "manufacturing", "subcategory": "cooperative", "headquarters": "País Vasco",
             "description": "Mayor grupo cooperativo del mundo, originario del País Vasco (España), que agrupa empresas en industria, distribución y finanzas gestionadas bajo principios cooperativos (incluye marcas como Fagor, Eroski, etc.)."},
            {"name": "Fagor", "category": "manufacturing", "subcategory": "appliances", "headquarters": "País Vasco",
             "description": "Marca cooperativa española de electrodomésticos y equipamiento del hogar, nacida en Mondragón, conocida históricamente por sus líneas de cocción, lavado y frigoríficos (actualmente bajo nuevos gestores tras reestructuración)."},
            {"name": "Balay", "category": "manufacturing", "subcategory": "appliances", "headquarters": "Zaragoza",
             "description": "Marca española de electrodomésticos fundada en Zaragoza, conocida por sus lavadoras, frigoríficos y cocinas, actualmente integrada en el grupo BSH manteniendo su identidad en el mercado nacional."},
            
            # Building Materials & Ceramics
            {"name": "Roca", "category": "manufacturing", "subcategory": "sanitary", "headquarters": "Barcelona",
             "description": "Multinacional española líder en fabricación de sanitarios, azulejos y equipamiento de baño (inodoros, lavabos, grifería), con amplia presencia internacional y más de un siglo de historia."},
            {"name": "Porcelanosa", "category": "manufacturing", "subcategory": "ceramics", "headquarters": "Castellón",
             "description": "Empresa española referente en pavimentos y revestimientos cerámicos, baños y cocinas de alta gama, reconocida mundialmente por el diseño y calidad de sus productos para la construcción y decoración."},
            {"name": "Cosentino", "category": "manufacturing", "subcategory": "surfaces", "headquarters": "Almería",
             "description": "Grupo industrial español conocido por la producción de superficies innovadoras para arquitectura y diseño, como la piedra de cuarzo Silestone y la porcelánica Dekton, exportadas a nivel global."},
            {"name": "Keraben Grupo", "category": "manufacturing", "subcategory": "ceramics", "headquarters": "Castellón",
             "description": "Firma española dedicada a la fabricación de baldosas cerámicas y soluciones cerámicas decorativas, con sede en Castellón, reconocida en el sector de materiales de construcción."},
            
            # Electrical & Lighting
            {"name": "Simon", "category": "manufacturing", "subcategory": "electrical", "headquarters": "Barcelona",
             "description": "Empresa española líder en material eléctrico e iluminación, fundada en 1916, fabricante de interruptores, enchufes, sistemas de domótica y alumbrado con presencia en decenas de países."},
            {"name": "Salicru", "category": "manufacturing", "subcategory": "electrical", "headquarters": "Barcelona",
             "description": "Compañía española especializada en electrónica de potencia, que fabrica Sistemas de Alimentación Ininterrumpida (SAI/UPS) y equipos de eficiencia energética para garantizar suministro eléctrico estable."},
            
            # Industrial Components
            {"name": "Válvulas Arco", "category": "manufacturing", "subcategory": "plumbing", "headquarters": "Valencia",
             "description": "Empresa española fabricante de válvulas y accesorios para fontanería, gas y calefacción, con una amplia gama de productos utilizados en instalaciones domésticas e industriales."},
            {"name": "Tubacex", "category": "manufacturing", "subcategory": "steel", "headquarters": "Álava",
             "description": "Multinacional española con sede en Álava, uno de los mayores fabricantes mundiales de tubos y aleaciones de acero inoxidable sin soldadura, suministrando al sector petroquímico, energético y aeroespacial."},
            {"name": "CIE Automotive", "category": "manufacturing", "subcategory": "automotive_components", "headquarters": "Bilbao",
             "description": "Grupo industrial español diversificado, proveedor global de componentes para la automoción (metal, plástico, forja), presente en Europa, América y Asia como parte de la cadena de suministro de vehículos."},
            
            # Furniture & Storage
            {"name": "Gandía Blasco", "category": "manufacturing", "subcategory": "furniture", "headquarters": "Valencia",
             "description": "Empresa española de diseño y mobiliario de exterior contemporáneo, originaria de Valencia, cuyos muebles de jardín y terrazas de estilo mediterráneo son valorados internacionalmente."},
            {"name": "Actiu", "category": "manufacturing", "subcategory": "furniture", "headquarters": "Alicante",
             "description": "Compañía española fabricante de mobiliario de oficina y soluciones de espacios de trabajo, con sede en Alicante, premiada por sus diseños ergonómicos y sostenibles."},
            {"name": "Simonrack", "category": "manufacturing", "subcategory": "storage", "headquarters": "Valencia",
             "description": "Empresa española dedicada a la fabricación de estanterías metálicas modulares y sistemas de almacenaje industrial y doméstico, con más de 50 años de trayectoria en el sector logístico."},
            {"name": "Rolser", "category": "manufacturing", "subcategory": "household", "headquarters": "Alicante",
             "description": "Empresa española fabricante de carros de la compra, escaleras domésticas y otros artículos para el hogar, con sede en Alicante, conocida por sus carritos de compra plegables de diseño."},
            
            # Pumps & Industrial Equipment
            {"name": "Bombas Ideal", "category": "manufacturing", "subcategory": "pumps", "headquarters": "Valencia",
             "description": "Empresa española especializada en la fabricación de bombas hidráulicas y sistemas de bombeo, con aplicaciones en riego, abastecimiento de agua y sectores industriales desde 1902."},
            
            # Paper & Cellulose
            {"name": "Miquel y Costas", "category": "manufacturing", "subcategory": "paper", "headquarters": "Barcelona",
             "description": "Grupo industrial español dedicado a la fabricación de papel, notable por ser uno de los principales productores mundiales de papel de fumar (marcas como Smoking), con casi 300 años de historia."},
            
            # Logistics & Hydrocarbons
            {"name": "CLH (Exolum)", "category": "energy", "subcategory": "logistics", "headquarters": "Madrid",
             "description": "Compañía logística española (antes Compañía Logística de Hidrocarburos) encargada del almacenamiento y transporte de productos petrolíferos a través de oleoductos y terminales por toda España."},
            
            # ==================== TURISMO Y HOSTELERÍA (Tourism & Hospitality) ====================
            {"name": "Paradores de Turismo", "category": "travel", "subcategory": "hotels", "headquarters": "Madrid",
             "description": "Red pública española de hoteles ubicada en monumentos históricos y sitios singulares (castillos, conventos, palacios), que ofrece alojamiento de calidad combinando patrimonio cultural y gastronomía regional."},
            {"name": "Meliá Hotels International", "category": "travel", "subcategory": "hotels", "headquarters": "Mallorca",
             "description": "Cadena hotelera multinacional española fundada en Mallorca, con hoteles urbanos y vacacionales en todo el mundo, referente en el sector turístico de alta categoría."},
            {"name": "Barceló Hotel Group", "category": "travel", "subcategory": "hotels", "headquarters": "Mallorca",
             "description": "Importante grupo hotelero español con sede en Palma de Mallorca, que opera hoteles y resorts vacacionales en Europa, América, África y Asia bajo marcas como Barceló, Occidental y Allegro."},
            {"name": "NH Hotel Group", "category": "travel", "subcategory": "hotels", "headquarters": "Madrid",
             "description": "Cadena hotelera urbana española (ahora parte de Minor International) con presencia global, reconocida por sus hoteles de ciudad orientados a negocios y turismo en principales destinos."},
            {"name": "Iberostar", "category": "travel", "subcategory": "hotels", "headquarters": "Mallorca",
             "description": "Cadena hotelera española con sede en Mallorca, especializada en resorts vacacionales de playa y hoteles de lujo, comprometida con la sostenibilidad y presente en Europa, América y Norte de África."},
            {"name": "RIU Hotels & Resorts", "category": "travel", "subcategory": "hotels", "headquarters": "Mallorca",
             "description": "Grupo hotelero español originario de Mallorca, gestionando hoteles vacacionales y urbanos en 20+ países, conocido por sus resorts todo incluido en destinos turísticos de playa."},
            {"name": "Grupo Palladium", "category": "travel", "subcategory": "hotels", "headquarters": "Ibiza",
             "description": "Conglomerado turístico español (de la familia Matutes) que engloba cadenas hoteleras como Palladium, Ushuaïa y Hard Rock (bajo licencia), con hoteles en el Caribe, México y Europa."},
            {"name": "Globalia", "category": "travel", "subcategory": "tourism", "headquarters": "Mallorca",
             "description": "Grupo turístico español propietario de varias empresas de viajes, destacando la aerolínea Air Europa, la cadena de agencias Halcón Viajes, y touroperadores, con fuerte presencia en conexiones entre Europa y América."},
            {"name": "Viajes El Corte Inglés", "category": "travel", "subcategory": "travel_agency", "headquarters": "Madrid",
             "description": "Agencia de viajes española perteneciente al Grupo El Corte Inglés, con amplia red de oficinas, especializada en vacaciones, negocios y organización de eventos y congresos."},
            {"name": "Hotusa", "category": "travel", "subcategory": "hotels", "headquarters": "Barcelona",
             "description": "Grupo turístico español que opera la cadena hotelera Eurostars Hotels y una amplia red de hoteles independientes asociados, además de actividades de gestión y reservas hoteleras a nivel internacional."},
            {"name": "PortAventura World", "category": "travel", "subcategory": "theme_park", "headquarters": "Tarragona",
             "description": "Complejo de ocio y resorts en Tarragona (Cataluña), que incluye uno de los parques temáticos más grandes de Europa, un parque acuático y hoteles temáticos, siendo un destino turístico familiar destacado en España."},
            {"name": "Fira de Barcelona", "category": "travel", "subcategory": "exhibitions", "headquarters": "Barcelona",
             "description": "Institución ferial española que organiza importantes salones profesionales y congresos internacionales en Barcelona (como el Mobile World Congress), disponiendo de recintos feriales de primer nivel."},
            {"name": "IFEMA Madrid", "category": "travel", "subcategory": "exhibitions", "headquarters": "Madrid",
             "description": "Institución ferial de Madrid que gestiona uno de los principales recintos feriales de Europa, sede de grandes ferias comerciales, exposiciones y congresos internacionales en múltiples sectores."},
            {"name": "Camino de Santiago", "category": "travel", "subcategory": "pilgrimage", "headquarters": "Spain",
             "description": "Ruta de peregrinación milenaria que atraviesa España hasta Santiago de Compostela, convertida en atractivo turístico-cultural de alcance global y motor de turismo rural y religioso."},
            
            # ==================== MEDIOS Y ENTRETENIMIENTO (Media & Entertainment) ====================
            # Newspapers
            {"name": "El País", "category": "media", "subcategory": "newspaper", "headquarters": "Madrid",
             "description": "Diario español de tirada nacional fundado en 1976, de línea editorial centro-izquierda, considerado referente informativo en el mundo hispanohablante por la calidad de sus contenidos."},
            {"name": "El Mundo", "category": "media", "subcategory": "newspaper", "headquarters": "Madrid",
             "description": "Periódico español generalista fundado en 1989, de línea editorial liberal-conservadora, uno de los diarios más vendidos en España, conocido por sus investigaciones y crónica política."},
            {"name": "ABC", "category": "media", "subcategory": "newspaper", "headquarters": "Madrid",
             "description": "Diario español conservador centenario (desde 1903), destacado por su formato tradicional y crónicas políticas y culturales, famoso por su hemeroteca y por mantener la tercera página de opinión."},
            {"name": "La Vanguardia", "category": "media", "subcategory": "newspaper", "headquarters": "Barcelona",
             "description": "Periódico español con sede en Barcelona, fundado en 1881, de amplia difusión en Cataluña y edición en español, valorado por su cobertura política, cultural y su vocación europeísta."},
            {"name": "La Razón", "category": "media", "subcategory": "newspaper", "headquarters": "Madrid",
             "description": "Diario español de orientación conservadora fundado en 1998, con sede en Madrid, conocido por su énfasis en información política nacional y columnas de opinión."},
            {"name": "Marca", "category": "media", "subcategory": "sports_newspaper", "headquarters": "Madrid",
             "description": "Diario deportivo español líder en difusión, especializado en fútbol y otros deportes, muy popular por su cobertura del Real Madrid, LaLiga y competiciones deportivas internacionales."},
            {"name": "AS", "category": "media", "subcategory": "sports_newspaper", "headquarters": "Madrid",
             "description": "Periódico deportivo español de gran tirada, centrado en fútbol (cobertura del Real Madrid y otros clubes) y polideportivo, con amplia audiencia en el mundo hispanohablante."},
            
            # Magazines
            {"name": "¡Hola!", "category": "media", "subcategory": "magazine", "headquarters": "Madrid",
             "description": "Revista española del corazón y entretenimiento social, famosa internacionalmente por sus exclusivas sobre celebridades, familias reales y estilos de vida glamorosos."},
            
            # Television
            {"name": "Antena 3", "category": "media", "subcategory": "tv", "headquarters": "Madrid",
             "description": "Canal de televisión español de ámbito nacional perteneciente al grupo Atresmedia, con programación generalista de series, informativos y entretenimiento, líder de audiencia en varios segmentos."},
            {"name": "Telecinco", "category": "media", "subcategory": "tv", "headquarters": "Madrid",
             "description": "Cadena de televisión generalista española del grupo Mediaset, conocida por sus programas de entretenimiento, realities y magazines, habitualmente entre las más vistas del país."},
            {"name": "La 1 (TVE)", "category": "media", "subcategory": "tv", "headquarters": "Madrid",
             "description": "Canal principal de la televisión pública española (RTVE), con programación generalista que incluye informativos, series, concursos y eventos institucionales, siendo la cadena más histórica de España."},
            {"name": "La Sexta", "category": "media", "subcategory": "tv", "headquarters": "Madrid",
             "description": "Canal de televisión español de cobertura nacional (grupo Atresmedia), caracterizado por sus programas de actualidad, humor y debate político, orientado a un público joven-adulto."},
            {"name": "Cuatro", "category": "media", "subcategory": "tv", "headquarters": "Madrid",
             "description": "Cadena de televisión generalista española (grupo Mediaset) enfocada en un público juvenil, con contenidos de factual, docu-realities, deportes y series internacionales."},
            
            # Radio
            {"name": "Cadena SER", "category": "media", "subcategory": "radio", "headquarters": "Madrid",
             "description": "Principal cadena de radio española en formato generalista, líder en audiencia, perteneciente al Grupo PRISA, reconocida por sus informativos (Hora 14, Hora 25) y programas emblemáticos como 'El Larguero'."},
            {"name": "Los 40 Principales", "category": "media", "subcategory": "radio", "headquarters": "Madrid",
             "description": "Cadena de radio musical española (Grupo PRISA Radio) líder en éxitos de música pop y listas de éxitos, con gran influencia cultural desde su fundación en 1966."},
            
            # Media Groups
            {"name": "RTVE", "category": "media", "subcategory": "broadcasting", "headquarters": "Madrid",
             "description": "Radio Televisión Española, corporación pública que engloba TVE (televisión pública) y RNE (radio pública), encargada de los medios estatales de comunicación, sin publicidad y con vocación de servicio público."},
            {"name": "Atresmedia", "category": "media", "subcategory": "media_group", "headquarters": "Madrid",
             "description": "Grupo de comunicación español propietario de canales de TV (Antena 3, La Sexta, etc.), emisoras de radio (Onda Cero, Europa FM) y productoras, destacado como uno de los dos grandes holdings mediáticos privados en España."},
            {"name": "Mediaset España", "category": "media", "subcategory": "media_group", "headquarters": "Madrid",
             "description": "Grupo de medios español dueño de cadenas como Telecinco y Cuatro, parte de la multinacional italiana Mediaset, centrado en televisión comercial y producción audiovisual en España."},
            {"name": "Telefónica Studios", "category": "media", "subcategory": "production", "headquarters": "Madrid",
             "description": "División de producción audiovisual de Telefónica, involucrada en la creación de contenidos cinematográficos y series para plataformas y TV, impulsando la ficción española a nivel global."},
            
            # Sports Clubs
            {"name": "Real Madrid CF", "category": "sports", "subcategory": "football_club", "headquarters": "Madrid",
             "description": "Club de fútbol español con sede en Madrid, el más laureado de Europa con numerosas Copas de Europa y Ligas, reconocido mundialmente por su historia, afición y estrellas futbolísticas."},
            {"name": "FC Barcelona", "category": "sports", "subcategory": "football_club", "headquarters": "Barcelona",
             "description": "Club de fútbol español de Barcelona, referente deportivo global, ganador de múltiples Champions League y Ligas, famoso por su estilo de juego, su cantera (La Masía) y el lema 'Més que un club'."},
            {"name": "Club Atlético de Madrid", "category": "sports", "subcategory": "football_club", "headquarters": "Madrid",
             "description": "Histórico club de fútbol de la capital española, conocido por su afición rojiblanca, sus éxitos en Liga y competiciones europeas, y por un estilo de juego aguerrido."},
            {"name": "LaLiga", "category": "sports", "subcategory": "football_league", "headquarters": "Madrid",
             "description": "Marca comercial de la máxima categoría del fútbol español (Primera División), organizada por la Liga de Fútbol Profesional, considerada una de las ligas más competitivas y populares del mundo."},
            
            # Sports Equipment
            {"name": "Joma", "category": "sports", "subcategory": "sports_apparel", "headquarters": "Toledo",
             "description": "Marca deportiva española dedicada a la fabricación de ropa, calzado y equipamiento deportivo, presente como patrocinador en numerosos equipos internacionales."},
            {"name": "Kelme", "category": "sports", "subcategory": "sports_apparel", "headquarters": "Elche",
             "description": "Empresa española de indumentaria deportiva, conocida por sus calzados y uniformes de fútbol y otros deportes, con amplia trayectoria desde los años 70."},
            
            # Lottery & Gaming
            {"name": "ONCE", "category": "services", "subcategory": "lottery", "headquarters": "Madrid",
             "description": "Organización Nacional de Ciegos Españoles, entidad social que opera la popular lotería Cupón ONCE y otros juegos, destinando sus ingresos a la integración de personas con discapacidad visual y servicios sociales."},
            {"name": "Loterías y Apuestas del Estado", "category": "services", "subcategory": "lottery", "headquarters": "Madrid",
             "description": "Entidad pública española encargada de loterías nacionales (Lotería de Navidad, La Primitiva, El Gordo, Quinielas), con célebres sorteos navideños y una extensa red de administraciones de lotería en todo el país."},
            
            # Entertainment & Events
            {"name": "Starlite Festival", "category": "media", "subcategory": "festival", "headquarters": "Marbella",
             "description": "Festival boutique de música y entretenimiento celebrado cada verano en Marbella (España), que combina conciertos de artistas internacionales con experiencias gastronómicas y de ocio de lujo en un entorno al aire libre exclusivo."},
            {"name": "eSports Vodafone Giants", "category": "sports", "subcategory": "esports", "headquarters": "Málaga",
             "description": "Club español de deportes electrónicos (videojuegos competitivos) con sede en Málaga, destacado en competiciones internacionales de juegos como League of Legends, patrocinado por grandes marcas."},
            
            # Padel Equipment (relevant for influencer matching)
            {"name": "Bullpadel", "category": "sports", "subcategory": "padel", "headquarters": "Barcelona"},
            {"name": "Head Padel", "category": "sports", "subcategory": "padel", "headquarters": "Spain"},
            {"name": "Nox Padel", "category": "sports", "subcategory": "padel", "headquarters": "Spain"},
            {"name": "Siux", "category": "sports", "subcategory": "padel", "headquarters": "Spain"},
            {"name": "Babolat España", "category": "sports", "subcategory": "tennis_padel", "headquarters": "Spain"},
            
            # Healthcare & Pharma (preserved from original)
            {"name": "Grifols", "category": "healthcare", "subcategory": "pharma", "headquarters": "Barcelona"},
            {"name": "Almirall", "category": "healthcare", "subcategory": "pharma", "headquarters": "Barcelona"},
            {"name": "PharmaMar", "category": "healthcare", "subcategory": "pharma", "headquarters": "Madrid"},
            {"name": "Esteve", "category": "healthcare", "subcategory": "pharma", "headquarters": "Barcelona"},
            {"name": "Cinfa", "category": "healthcare", "subcategory": "pharma", "headquarters": "Navarra"},
            {"name": "Quirónsalud", "category": "healthcare", "subcategory": "hospitals", "headquarters": "Madrid"},
            {"name": "HM Hospitales", "category": "healthcare", "subcategory": "hospitals", "headquarters": "Madrid"},
            
            # Real Estate (preserved from original)
            {"name": "Merlin Properties", "category": "real_estate", "headquarters": "Madrid"},
            {"name": "Colonial", "category": "real_estate", "headquarters": "Barcelona"},
            
            # Beauty & Personal Care (preserved from original)
            {"name": "Natura Bissé", "category": "beauty", "subcategory": "skincare", "headquarters": "Barcelona"},
            {"name": "Puig", "category": "beauty", "subcategory": "fragrances", "headquarters": "Barcelona"},
            {"name": "Druni", "category": "beauty", "subcategory": "retail", "headquarters": "Valencia"},
            {"name": "Primor", "category": "beauty", "subcategory": "retail", "headquarters": "Sevilla"},
            {"name": "Equivalenza", "category": "beauty", "subcategory": "fragrances", "headquarters": "Madrid"},
            
            # Logistics (preserved from original)
            {"name": "Prosegur", "category": "services", "subcategory": "security", "headquarters": "Madrid"},
            {"name": "Eulen", "category": "services", "subcategory": "facility_services", "headquarters": "Madrid"},
            {"name": "Seur", "category": "services", "subcategory": "logistics", "headquarters": "Madrid"},
            {"name": "MRW", "category": "services", "subcategory": "logistics", "headquarters": "Barcelona"},
            
            # International Brands in Spain (preserved from original)
            {"name": "Carrefour España", "category": "retail", "subcategory": "grocery", "headquarters": "Madrid"},
            {"name": "Lidl España", "category": "retail", "subcategory": "discount_grocery", "headquarters": "Barcelona"},
            {"name": "MediaMarkt España", "category": "retail", "subcategory": "electronics", "headquarters": "Barcelona"},
            {"name": "Fnac España", "category": "retail", "subcategory": "electronics", "headquarters": "Madrid"},
            {"name": "Leroy Merlin España", "category": "retail", "subcategory": "home_improvement", "headquarters": "Madrid"},
            {"name": "IKEA España", "category": "retail", "subcategory": "furniture", "headquarters": "Madrid"},
            {"name": "Decathlon España", "category": "retail", "subcategory": "sports", "headquarters": "Madrid"},
            {"name": "Sanitas", "category": "insurance", "subcategory": "health", "headquarters": "Madrid"},
            {"name": "Adeslas", "category": "insurance", "subcategory": "health", "headquarters": "Madrid"},
            {"name": "Idealista", "category": "technology", "subcategory": "real_estate", "headquarters": "Madrid"},
            {"name": "Fotocasa", "category": "technology", "subcategory": "real_estate", "headquarters": "Barcelona"},
            {"name": "Aena", "category": "travel", "subcategory": "airports", "headquarters": "Madrid"},
        ]

        brands = []
        for data in brands_data:
            brand = ScrapedBrand(
                name=data["name"],
                description=data.get("description"),
                category=data.get("category"),
                subcategory=data.get("subcategory"),
                headquarters=data.get("headquarters"),
                brand_value_eur=data.get("brand_value_eur"),
                source="spanish_market_research_2025",
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
