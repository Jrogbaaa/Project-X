# Brand Database Directive

## Purpose

Maintain a comprehensive database of Spanish brands to enhance influencer search matching. This knowledge base provides context for:

1. **Brand Recognition** - Identify brands mentioned in search queries
2. **Category Matching** - Match influencers to appropriate brand categories
3. **Competitive Context** - Understand brand relationships and competitors
4. **Search Enhancement** - Improve LLM query parsing with brand context

## Database Schema

The `brands` table in PostgreSQL stores brand knowledge:

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `name` | VARCHAR(255) | Brand display name |
| `name_normalized` | VARCHAR(255) | Lowercase, no accents (for deduplication) |
| `description` | TEXT | What the brand does |
| `category` | VARCHAR(100) | Primary category (fashion, food_beverage, etc.) |
| `subcategory` | VARCHAR(100) | More specific classification |
| `industry` | VARCHAR(100) | Broader industry sector |
| `headquarters` | VARCHAR(100) | City/region in Spain |
| `website` | VARCHAR(255) | Brand website URL |
| `instagram_handle` | VARCHAR(100) | Instagram username |
| `source` | VARCHAR(100) | Data source (kantar_brandz_manual, ibex35, etc.) |
| `source_rank` | INTEGER | Ranking in source list |
| `brand_value_eur` | BIGINT | Brand value in euros (if available) |
| `is_active` | BOOLEAN | Whether brand is active |
| `extra_data` | JSONB | Flexible additional metadata |

## Data Sources

### 1. Manual Curated List (Primary)
**Source:** `backend/app/services/brand_scraper_service.py` → `get_top_spanish_brands_manual()`

Most reliable source with ~120 hand-picked brands:
- Kantar BrandZ Top 30 Spanish Brands
- Major retail, banking, telecom brands
- Food & beverage leaders
- Fashion houses (Inditex family, Mango, etc.)

### 2. IBEX 35 Web Scrape
**Source:** `scrape_ibex35()` method

Scrapes from disfold.com:
- 35 largest Spanish public companies
- Market capitalization data
- Industry classification

### 3. Industry Directories
**Source:** `get_spanish_fashion_brands()`, `get_spanish_food_brands()`

Curated lists by industry:
- Fashion: 40+ brands (Inditex, Mango, footwear, luxury, jewelry)
- Food & Beverage: 60+ brands (beer, wine, olive oil, dairy, charcuterie)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/brands/` | List all brands (optional category filter) |
| GET | `/api/brands/categories` | List categories with counts |
| GET | `/api/brands/search?q=` | Search brands by name |
| GET | `/api/brands/count` | Get total brand count |
| POST | `/api/brands/import` | Trigger brand import from all sources |
| GET | `/api/brands/{id}` | Get specific brand |

## Import Procedures

### Running the Import

```bash
# Option 1: Via script
cd backend && source ../venv/bin/activate
python scripts/import_brands.py

# Option 2: Via API
curl -X POST http://localhost:8000/api/brands/import
```

### Import Behavior

1. **Deduplication** - Uses `name_normalized` for uniqueness
2. **Upsert Logic** - Updates existing brands, creates new ones
3. **Source Tracking** - Records where each brand came from
4. **Idempotent** - Safe to run multiple times

## Category Taxonomy

### Primary Categories

| Category | Description | Example Brands |
|----------|-------------|----------------|
| `fashion` | Apparel, footwear, accessories | Zara, Mango, Camper |
| `food_beverage` | Food, drinks, restaurants | Mahou, Mercadona, Valor |
| `banking` | Banks, financial services | Santander, BBVA, CaixaBank |
| `telecom` | Telecommunications | Movistar, Vodafone, Orange |
| `retail` | Retail stores | El Corte Inglés, IKEA España |
| `travel` | Airlines, hotels, tourism | Iberia, Meliá, Renfe |
| `automotive` | Car manufacturers | SEAT, Cupra |
| `beauty` | Cosmetics, personal care | Natura Bissé, Puig |
| `technology` | Tech companies | Indra, Glovo, Cabify |
| `sports` | Sports equipment, apparel | Joma, Bullpadel |
| `healthcare` | Pharma, hospitals | Grifols, Quirónsalud |
| `insurance` | Insurance companies | Mapfre, Mutua Madrileña |
| `construction` | Construction firms | ACS, Ferrovial |
| `utilities` | Energy, utilities | Iberdrola, Endesa |
| `media` | Media, entertainment | Atresmedia, Mediaset |
| `services` | Business services | Prosegur, Correos |

### Subcategories (Examples)

- `fashion` → fast_fashion, luxury, footwear, jewelry
- `food_beverage` → beer, wine, olive_oil, dairy, charcuterie
- `retail` → grocery, department_store, electronics
- `travel` → airline, hotels, rail

## Maintenance Procedures

### Adding New Brands Manually

1. Edit `backend/app/services/brand_scraper_service.py`
2. Add to appropriate method (`get_top_spanish_brands_manual()` or industry-specific)
3. Run import: `python scripts/import_brands.py`

### Adding New Industry Directory

1. Create new method in `BrandScraperService`: `get_spanish_{industry}_brands()`
2. Add to `collect_all_brands()` method
3. Run import

### Updating Brand Data

1. Use API: `PUT /api/brands/{id}` (if implemented)
2. Or modify source data and re-run import (upsert will update)

### Quarterly Review

1. Check for new major brands to add
2. Verify brand information is current
3. Add notable brand deals or ambassadors to `brand_intelligence.yaml`
4. Update category taxonomy if needed

## Integration with Search

### Query Parser Enhancement

The brand database can be used by the query parser (`backend/app/orchestration/query_parser.py`) to:

1. **Recognize Brand Names** - Match query text against brand database
2. **Infer Categories** - Use brand category to set search context
3. **Suggest Competitors** - Cross-reference with `brand_intelligence.yaml`

### Brand Context in Ranking

The `brand_intelligence_service.py` uses brand data for:

1. **Competitor Detection** - Flag conflicting brand relationships
2. **Category Matching** - Score influencers by category alignment
3. **Saturation Warnings** - Identify existing brand ambassadors

## Files Reference

| File | Purpose |
|------|---------|
| `backend/alembic/versions/003_add_brands_table.py` | Database migration |
| `backend/app/models/brand.py` | SQLAlchemy model |
| `backend/app/services/brand_scraper_service.py` | Data collection |
| `backend/app/services/brand_import_service.py` | Database import |
| `backend/app/api/routes/brands.py` | API endpoints |
| `backend/scripts/import_brands.py` | CLI import script |

## Current Stats

As of initial import:
- **Total Brands**: 210+
- **Categories**: 40+
- **Sources**: 4 (manual, fashion_directory, food_directory, ibex35)

## Future Enhancements

1. **Web Scraping Expansion** - Add more sources (Interbrand, Brands of Spain)
2. **Brand Descriptions** - Add LLM-generated descriptions
3. **Logo/Image Storage** - Store brand logos for UI display
4. **Ambassador Tracking** - Link to known influencer relationships
5. **Campaign History** - Track past brand campaigns
