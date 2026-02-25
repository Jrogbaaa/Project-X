# Influencer Discovery API Documentation

Base URL: `http://localhost:8000` (local) | `https://project-x-three-sage.vercel.app/api` (production)

> **Last Updated:** February 24, 2026

## Overview

This API powers an intelligent influencer discovery platform. Users can paste brand briefs in natural language, and the system extracts brand context, creative concepts, and campaign requirements to find and score matching influencers.

### Key Features
- **Natural Language Input**: Paste entire brand briefs or campaign descriptions
- **Niche Matching**: Match influencers based on their content niche (what they post about) - this is one of the most important factors for brand alignment
- **8-Factor Scoring**: Credibility, engagement, audience match, growth, geography, brand affinity, creative fit, niche match
- **Anti-Celebrity Bias**: Optionally prefer mid-tier influencers over mega-celebrities
- **Creative Concept Matching**: Score influencers based on alignment with campaign tone and themes
- **Gender-Split Results**: Request specific counts per gender (e.g., "3 male, 3 female")
- **Local-First Search**: Searches cached database first, uses PrimeTag API only for metric verification
- **Verified Profiles**: All returned influencers are analyzed and validated for authentic metrics and audiences

### Frontend UI

The frontend interface is fully localized in **Spanish** for the Spanish market. Key UI elements include:

- **Look After You**: Logo in main header
- **Perfiles verificados**: Trust badge showing all influencers are vetted
- **Filtros**: Filter panel with credibility, Spain audience %, engagement, growth filters
- **Resultados**: Results display with match scores and detailed breakdowns

The UI displays a verification badge on results: *"Perfiles verificados: Cada influencer ha sido analizado y validado para garantizar métricas reales y audiencias auténticas."*

### Niche Matching - Key Concept

An influencer's **niche** is what they post about - their content category. This is one of the most important factors for matching influencers to brands:

| Brand Type | Should Match Niche |
|------------|-------------------|
| IKEA (home furniture) | Home Decor, Lifestyle, Interior Design |
| Health food brand | Fitness, Nutrition, Healthy Lifestyle |
| Padel equipment | Padel, Racket Sports (NOT soccer players) |
| Fashion brand | Fashion, Style, Beauty |
| Spirits/gin brand (Puerto de Indias) | Lifestyle, Entertainment, Social moments |
| Fintech/payment tech (Square) | Food entrepreneurs, Business, Gastronomy |
| Perfume/fragrance (Halloween) | Beauty, Lifestyle |
| Banking app (imagin) | Fintech, Lifestyle, Entertainment |
| Pet store (Tiendanimal, Kiwoko) | Pets, Lifestyle, Family |
| Skincare brand (CeraVe, The Ordinary) | Skincare, Beauty, Wellness |

Each influencer in the database has an `interests` field containing their content niches. The ranking algorithm scores how well these niches align with the brand's category and campaign topics.

## Authentication

Currently no authentication required for local development.

---

## Endpoints

### Search

#### Execute Search
`POST /search/`

Execute an influencer search by pasting a brand brief or natural language query.

**Request Body:**
```json
{
  "query": "Find 5 Spanish influencers for Adidas padel campaign. Creative concept: 'Rising Stars' series featuring up-and-coming athletes in authentic training moments, documentary style. Prefer mid-tier influencers (100K-2M followers).",
  "filters": {
    "min_credibility_score": 70.0,
    "min_engagement_rate": null,
    "min_spain_audience_pct": 60.0,
    "min_follower_growth_rate": null,
    "target_audience_gender": null,
    "min_target_gender_pct": 50,
    "target_age_ranges": ["18-24", "25-34"],
    "min_target_age_pct": 30,
    "exclude_competitor_ambassadors": true
  },
  "ranking_weights": {
    "credibility": 0.00,
    "engagement": 0.10,
    "audience_match": 0.00,
    "growth": 0.00,
    "geography": 0.00,
    "brand_affinity": 0.10,
    "creative_fit": 0.30,
    "niche_match": 0.50
  }
}
```

**Response:**
```json
{
  "search_id": "uuid-string",
  "query": "Find 5 Spanish influencers for Adidas padel campaign...",
  "parsed_query": {
    "target_count": 5,
    "influencer_gender": "any",
    "target_audience_gender": null,
    "target_male_count": null,
    "target_female_count": null,
    "brand_name": "Adidas",
    "brand_handle": "@adidas",
    "brand_category": "sports_apparel",
    "creative_concept": "Rising Stars series featuring up-and-coming athletes in authentic training moments",
    "creative_tone": ["authentic", "documentary"],
    "creative_themes": ["rising stars", "training", "dedication"],
    "campaign_topics": ["padel", "racket sports"],
    "exclude_niches": ["soccer", "football"],
    "preferred_follower_min": 100000,
    "preferred_follower_max": 2000000,
    "content_themes": ["sports", "fitness", "training"],
    "search_keywords": ["padel", "tenis", "raqueta"],
    "min_credibility_score": 70.0,
    "min_spain_audience_pct": 60.0,
    "parsing_confidence": 0.95,
    "reasoning": "Extracted Adidas brand with padel niche focus, documentary tone, and size preference for mid-tier influencers"
  },
  "filters_applied": {
    "min_credibility_score": 70.0,
    "min_engagement_rate": null,
    "min_spain_audience_pct": 60.0
  },
  "results": [
    {
      "influencer_id": "uuid-string",
      "username": "influencer_handle",
      "rank_position": 1,
      "relevance_score": 0.85,
      "scores": {
        "credibility": 0.92,
        "engagement": 0.78,
        "audience_match": 0.85,
        "growth": 0.65,
        "geography": 0.80,
        "brand_affinity": 0.70,
        "creative_fit": 0.88,
        "niche_match": 0.95
      },
      "raw_data": {
        "id": "uuid-string",
        "username": "influencer_handle",
        "display_name": "Display Name",
        "profile_picture_url": "https://...",
        "bio": "Bio text",
        "is_verified": true,
        "follower_count": 150000,
        "credibility_score": 92.0,
        "engagement_rate": 0.035,
        "follower_growth_rate_6m": 0.15,
        "avg_likes": 5000,
        "avg_comments": 150,
        "audience_genders": {"male": 35, "female": 65},
        "audience_age_distribution": {"18-24": 25, "25-34": 45},
        "audience_geography": {"ES": 70, "MX": 10},
        "interests": ["padel", "fitness", "sports"],
        "brand_mentions": ["nike", "head"],
        "brand_warning_type": null,
        "brand_warning_message": null,
        "niche_warning": null,
        "mediakit_url": "https://mediakit.primetag.com/instagram/Z0FBQ..."
      }
    }
  ],
  "total_candidates": 50,
  "total_after_filter": 15,
  "verification_stats": {
    "total_candidates": 50,
    "verified": 45,
    "failed_verification": 5,
    "passed_filters": 15,
    "rejected_spain_pct": 10,
    "rejected_credibility": 15,
    "rejected_engagement": 5
  },
  "executed_at": "2025-01-20T12:00:00Z"
}
```

---

#### Get Search
`GET /search/{search_id}`

Retrieve a previous search by ID with full results.

**Path Parameters:**
- `search_id` (UUID, required): The search ID

**Response:** Same as Execute Search response

---

#### Save Search
`POST /search/{search_id}/save`

Save a search for later reference.

**Path Parameters:**
- `search_id` (UUID, required): The search ID

**Request Body:**
```json
{
  "name": "IKEA Campaign Q1",
  "description": "Influencers for IKEA home campaign"
}
```

**Response:**
```json
{
  "id": "uuid-string",
  "name": "IKEA Campaign Q1",
  "description": "Influencers for IKEA home campaign",
  "raw_query": "5 female influencers for IKEA",
  "parsed_query": {...},
  "result_count": 5,
  "created_at": "2025-01-20T12:00:00Z",
  "updated_at": "2025-01-20T12:00:00Z"
}
```

---

#### List Saved Searches
`GET /search/saved/list`

Get all saved searches.

**Query Parameters:**
- `limit` (int, optional, default=50, max=100): Maximum results

**Response:**
```json
[
  {
    "id": "uuid-string",
    "name": "IKEA Campaign Q1",
    "description": "...",
    "raw_query": "...",
    "parsed_query": {...},
    "result_count": 5,
    "created_at": "2025-01-20T12:00:00Z",
    "updated_at": "2025-01-20T12:00:00Z"
  }
]
```

---

#### List Search History
`GET /search/history/list`

Get recent search history.

**Query Parameters:**
- `limit` (int, optional, default=50, max=100): Maximum results

**Response:**
```json
[
  {
    "id": "uuid-string",
    "raw_query": "5 female influencers for IKEA",
    "result_count": 5,
    "is_saved": false,
    "saved_name": null,
    "executed_at": "2025-01-20T12:00:00Z"
  }
]
```

---

### Influencers

#### Get Influencer
`GET /influencers/{influencer_id}`

Get detailed information about a cached influencer.

**Path Parameters:**
- `influencer_id` (UUID, required): The influencer ID

**Response:**
```json
{
  "id": "uuid-string",
  "platform_type": "instagram",
  "username": "influencer_handle",
  "display_name": "Display Name",
  "profile_picture_url": "https://...",
  "bio": "Bio text",
  "is_verified": true,
  "follower_count": 150000,
  "credibility_score": 92.0,
  "engagement_rate": 0.035,
  "follower_growth_rate_6m": 0.15,
  "avg_likes": 5000,
  "avg_comments": 150,
  "avg_views": null,
  "audience_genders": {"male": 35, "female": 65},
  "audience_age_distribution": {"18-24": 25, "25-34": 45, "35-44": 20},
  "audience_geography": {"ES": 70, "MX": 10, "AR": 5},
  "interests": ["fitness", "lifestyle"],
  "brand_mentions": ["nike", "head"],
  "country": "Spain",
  "primary_niche": "fitness",
  "niche_confidence": 0.92,
  "influencer_gender": "female",
  "profile_active": true,
  "cached_at": "2025-01-20T12:00:00Z",
  "cache_expires_at": "2025-01-21T12:00:00Z"
}
```

---

### Exports

#### Export to CSV
`GET /exports/{search_id}/csv`

Download search results as CSV file.

**Path Parameters:**
- `search_id` (UUID, required): The search ID

**Response:** CSV file download

**Headers:**
- `Content-Type: text/csv`
- `Content-Disposition: attachment; filename=influencers_{search_id}.csv`

---

#### Export to Excel
`GET /exports/{search_id}/excel`

Download search results as Excel file.

**Path Parameters:**
- `search_id` (UUID, required): The search ID

**Response:** Excel file download

**Headers:**
- `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- `Content-Disposition: attachment; filename=influencers_{search_id}.xlsx`

---

### Brands

The brand knowledge base provides context for search matching. Contains 210+ Spanish brands across 39 categories.

#### List Brands
`GET /brands/`

List all brands in the knowledge base.

**Query Parameters:**
- `category` (string, optional): Filter by category (e.g., "fashion", "food_beverage")
- `limit` (int, optional, default=100, max=1000): Maximum results

**Response:**
```json
[
  {
    "id": "uuid-string",
    "name": "Zara",
    "description": null,
    "category": "fashion",
    "subcategory": "fast_fashion",
    "industry": null,
    "headquarters": "A Coruña",
    "website": null,
    "instagram_handle": null,
    "source": "kantar_brandz_manual",
    "source_rank": 1,
    "brand_value_eur": 33900000000
  }
]
```

---

#### List Categories
`GET /brands/categories`

Get all brand categories with counts.

**Response:**
```json
[
  {"category": "food_beverage", "count": 56},
  {"category": "fashion", "count": 34},
  {"category": "retail", "count": 12}
]
```

---

#### Search Brands
`GET /brands/search`

Search brands by name.

**Query Parameters:**
- `q` (string, required): Search query
- `category` (string, optional): Filter by category
- `limit` (int, optional, default=20, max=100): Maximum results

**Response:** Same as List Brands

---

#### Get Brand Count
`GET /brands/count`

Get total count of brands in database.

**Response:**
```json
{"count": 210}
```

---

#### Import Brands
`POST /brands/import`

Trigger brand import from all configured sources.

**Response:**
```json
{
  "created": 0,
  "updated": 210,
  "errors": 0,
  "total_brands": 210
}
```

---

#### Get Brand
`GET /brands/{brand_id}`

Get a specific brand by ID.

**Path Parameters:**
- `brand_id` (UUID, required): The brand ID

**Response:** Single brand object (same as List Brands item)

---

### Cache Management

#### Get Cache Statistics
`GET /influencers/cache/stats`

Get cache statistics for monitoring.

**Response:**
```json
{
  "total_cached": 1500,
  "active_count": 1200,
  "expired_count": 300,
  "expiring_within_24h": 50,
  "with_full_metrics": 800,
  "partial_data_only": 400,
  "cache_ttl_hours": 24
}
```

---

#### Warm Cache
`POST /influencers/cache/warm`

Pre-emptively refresh cache entries close to expiration. Useful for maintaining fresh data and reducing API calls during searches.

**Request Body:**
```json
{
  "limit": 100,
  "days_until_expiry": 1
}
```

**Response:**
```json
{
  "message": "Cache warming completed for 45 influencers",
  "influencers_queued": 50,
  "refreshed_count": 45,
  "failed_count": 5
}
```

---

#### Cleanup Expired Cache
`DELETE /influencers/cache/expired`

Remove expired cache entries. Maintenance endpoint to clean up stale data.

**Query Parameters:**
- `limit` (int, optional, default=1000): Maximum entries to delete

**Response:**
```json
{
  "message": "Deleted 150 expired cache entries",
  "deleted_count": 150
}
```

---

### Health

#### Health Check
`GET /health`

Basic health check.

**Response:**
```json
{
  "status": "healthy"
}
```

---

#### Readiness Check
`GET /health/ready`

Readiness check including database connectivity.

**Response:**
```json
{
  "status": "ready",
  "database": "connected",
  "debug": true
}
```

---

## Error Responses

All endpoints return errors in the following format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `404` - Resource not found
- `422` - Validation error (invalid request body)
- `500` - Internal server error

---

## Data Models

### FilterConfig
```typescript
{
  min_credibility_score?: number;  // 0-100, default 70
  min_engagement_rate?: number;    // 0-1, e.g., 0.03 = 3%
  min_spain_audience_pct?: number; // 0-100, default 60
  min_follower_growth_rate?: number; // -1 to 1, e.g., 0.1 = 10%
}
```

### RankingWeights
```typescript
{
  // PrimeTag factors (zeroed until API restored — low/no data coverage)
  credibility: number;    // default 0.00 — zeroed, PrimeTag 0.4% coverage
  audience_match: number; // default 0.00 — zeroed, PrimeTag 0.4% coverage
  growth: number;         // default 0.00 — zeroed, PrimeTag 0.4% coverage
  geography: number;      // default 0.00 — zeroed, PrimeTag 0.0% coverage

  // Active factors (where data exists)
  engagement: number;     // default 0.10 — Starngage 98.6% coverage
  brand_affinity: number; // default 0.10 — Apify 3.4% coverage, helps when present
  creative_fit: number;   // default 0.30 — Apify+LLM 50.3% coverage, key differentiator
  niche_match: number;    // default 0.50 — LLM+keyword 98.6% coverage, dominant signal
}
// Note: All weights must sum to 1.0
// LLM-suggested weights are clamped: factors with default 0.0 stay zeroed.
// When PrimeTag is restored, rebalance credibility/geography/audience_match.
```

### ScoreComponents
```typescript
{
  credibility: number;    // 0-1, normalized from credibility_score
  engagement: number;     // 0-1, normalized from engagement_rate
  audience_match: number; // 0-1, gender/age demographic match
  growth: number;         // 0-1, 6-month follower growth
  geography: number;      // 0-1, Spain audience percentage
  brand_affinity: number; // 0-1, audience overlap with target brand (0.5 = neutral)
  creative_fit: number;   // 0-1, alignment with creative concept (0.5 = neutral)
  niche_match: number;    // 0-1, content niche match (0.5 = neutral)
}
```

### VerificationStats
```typescript
{
  total_candidates: number;      // Found in discovery phase
  verified: number;              // Successfully verified via Primetag API
  failed_verification: number;   // Not found or API error
  passed_filters: number;        // Passed hard filters (Spain %, credibility, ER)
  rejected_spain_pct?: number;   // Rejected for Spain audience < threshold
  rejected_credibility?: number; // Rejected for low credibility
  rejected_engagement?: number;  // Rejected for low engagement
}
```

### ParsedSearchQuery
```typescript
{
  // Basic
  target_count: number;           // Number of influencers requested
  influencer_gender?: string;     // "male", "female", "any"
  target_audience_gender?: string;
  
  // Gender-specific counts (for split results)
  target_male_count?: number;     // Specific number of male influencers requested
  target_female_count?: number;   // Specific number of female influencers requested
  // When set, returns 3x the requested count per gender (e.g., 3 male + 3 female = 18 results)
  
  // Tier-specific counts
  target_micro_count?: number;    // Micro influencers (1K-50K) requested
  target_mid_count?: number;      // Mid-tier influencers (50K-500K) requested
  target_macro_count?: number;    // Macro influencers (500K-2.5M) requested
  
  // Brand context
  brand_name?: string;            // e.g., "Adidas"
  brand_handle?: string;          // e.g., "@adidas" for audience overlap
  brand_category?: string;        // e.g., "sports_apparel"
  
  // Creative concept
  creative_concept?: string;      // The campaign creative brief
  creative_format?: string;       // "documentary", "day_in_the_life", "tutorial", "challenge", "testimonial", "storytelling", "lifestyle"
  creative_tone: string[];        // e.g., ["authentic", "documentary"]
  creative_themes: string[];      // e.g., ["dedication", "rising stars"]
  
  // Niche targeting
  campaign_niche?: string;        // PRIMARY niche (single): "padel", "fitness", "beauty", "pets", etc.
  campaign_topics: string[];      // e.g., ["padel", "tennis"]
  exclude_niches: string[];       // e.g., ["soccer"] - avoid these niches (never exclude related niches)
  content_themes: string[];       // Related content themes
  
  // Creative discovery (PrimeTag interest mapping)
  discovery_interests: string[];  // PrimeTag interest categories for discovery, e.g., ["Sports", "Tennis", "Fitness"]
  exclude_interests: string[];    // PrimeTag interest categories to AVOID, e.g., ["Soccer"]
  influencer_reasoning: string;   // LLM reasoning about what types of influencers fit
  
  // Size preferences (anti-celebrity bias)
  preferred_follower_min?: number; // e.g., 100000
  preferred_follower_max?: number; // e.g., 2000000
  
  // Audience
  target_age_ranges: string[];    // e.g., ["18-24", "25-34"]
  min_spain_audience_pct: number; // 0-100, default 60
  
  // Quality
  min_credibility_score: number;  // 0-100, default 70
  min_engagement_rate?: number;   // 0-100
  
  // Search
  search_keywords: string[];      // Keywords for PrimeTag search
  
  // Ranking
  suggested_ranking_weights?: object;
  
  // Meta
  parsing_confidence: number;     // 0-1
  reasoning: string;              // LLM's parsing explanation
}
```

---

## Examples

### Paste a Full Brand Brief
```bash
curl -X POST http://localhost:8000/search/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Find 5 Spanish influencers for Adidas padel campaign. Creative concept: Rising Stars series featuring up-and-coming athletes in authentic training moments, documentary style, focus on dedication and the grind rather than glamour. Prefer mid-tier influencers (100K-2M followers) over mega-celebrities."
  }'
```

The LLM will extract:
- Brand: Adidas (@adidas)
- Category: sports_apparel
- Creative concept, tone (documentary, authentic), themes (rising stars, dedication)
- Niche: padel (excludes soccer/football stars)
- Size preference: 100K-2M followers

### Simple Search Query
```bash
curl -X POST http://localhost:8000/search/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "5 female influencers for IKEA home campaign",
    "filters": {
      "min_credibility_score": 75.0
    }
  }'
```

### Prioritize Creative Fit
```bash
curl -X POST http://localhost:8000/search/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Nike running campaign, gritty black-and-white documentary style, everyday athletes pushing limits",
    "ranking_weights": {
      "credibility": 0.00,
      "engagement": 0.10,
      "audience_match": 0.00,
      "growth": 0.00,
      "geography": 0.00,
      "brand_affinity": 0.10,
      "creative_fit": 0.40,
      "niche_match": 0.40
    }
  }'
```
> **Note:** PrimeTag-dependent factors (credibility, audience_match, growth, geography) are currently zeroed due to API unavailability. LLM-suggested weights for these factors are clamped to 0 automatically.

### Gender-Split Search
Request specific counts of male and female influencers:
```bash
curl -X POST http://localhost:8000/search/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "3 male and 3 female influencers for Nike campaign, athletic lifestyle content"
  }'
```

The LLM will extract `target_male_count: 3` and `target_female_count: 3`, returning up to 9 males + 9 females (3x headroom for each gender).

### Export Results
```bash
# CSV
curl -O http://localhost:8000/exports/{search_id}/csv

# Excel
curl -O http://localhost:8000/exports/{search_id}/excel
```

---

## Search Behavior

### Local-First Discovery
The search service prioritizes the local database for candidate discovery:
1. **Step 1**: Parse query with LLM — extract brand, niche, creative concept, filters
2. **Step 2**: Search local DB by taxonomy-aware niche matching (exact → related → interests)
3. **Step 3**: Expand via creative discovery interests if niche matches are sparse
4. **Step 4**: Pre-filter and verify top candidates via PrimeTag API for fresh metrics
5. **Step 5**: Apply hard filters (Spain %, credibility, ER, follower range, gender)
6. **Step 6**: Rank survivors using 8-factor weighted scoring

PrimeTag API is used **only for verification** — not for discovering new influencers. When PrimeTag is unavailable, the system falls back gracefully to cached data with lenient filtering.

### Niche Selection Rules
The LLM follows specificity rules when selecting campaign_niche:
- **"skincare"** (not "beauty") for skincare products, serums, facial routines
- **"gaming"** (not "tech") for gaming peripherals, headsets, esports, streaming
- **"home_decor"** (not "lifestyle") for furniture, mattresses, home appliances
- **"pets"** for pet stores and animal brands
- Most specific niche always preferred: "padel" > "sports", "running" > "fitness"
- `exclude_niches` never contains niches related to `campaign_niche` (e.g., never exclude "beauty" for a skincare campaign)

### Graceful Fallbacks
The system avoids returning empty results through cascading fallbacks:
- **Follower range**: If the requested range (e.g., 10K-80K) would remove ALL candidates, the filter relaxes and ranking's size penalty handles deprioritization
- **Tier distribution**: If requested tiers (e.g., micro only) have 0 candidates, falls back to best-ranked from any tier
- **PrimeTag unavailable**: Falls back to cached data with lenient mode filters

### Default Result Limit
- Default: **20 results** returned
- Maximum: 50 results
- When gender-specific counts are requested: returns 3x the requested count per gender
