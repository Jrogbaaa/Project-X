# Search Workflow Directive

## Goal
Process brand briefs and natural language queries to find and intelligently rank influencers based on brand affinity, creative fit, and niche match—not just generic popularity metrics.

## Input
- **Brand brief** pasted by user (can be multi-line, detailed campaign description)
- Example: "Find 5 Spanish influencers for Adidas padel campaign. Creative concept: 'Rising Stars' series featuring up-and-coming athletes in authentic training moments, documentary style. Prefer mid-tier influencers (100K-2M followers)."
- Optional filter overrides (credibility, engagement, geography thresholds)
- Optional ranking weight overrides

## Process Flow

### Architecture: Batch Verification Approach

The search flow uses a **batch verification architecture** to ensure predictable latency and controlled API costs:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Get large candidate pool from DB (200 candidates)           │
│     Fast, local operation - no API calls                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  2. Soft pre-filter using cached metrics (select top 15)        │
│     Scores candidates by likelihood of passing verification     │
│     Fast, local operation - no API calls                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  3. Cache-first verification split                              │
│     - Already verified (full metrics + fresh cache) → skip API  │
│     - Needs verification → batch verify via PrimeTag API        │
│     - MAX 15 API calls per search (predictable cost)            │
│     - 5 concurrent requests with exponential backoff            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  4. Strict filter verified candidates                           │
│     5. Rank and return top N results                            │
└─────────────────────────────────────────────────────────────────┘
```

**Why this approach?** Previous loop-based verification (verify → filter → if not enough → repeat) was slow and expensive. This batch approach ensures:
- **Cache-first**: Already-verified candidates skip API calls entirely (0 calls for repeat searches)
- Predictable latency (~15-30 API calls max for new candidates)
- Predictable cost per search
- No runaway loops when filter rejection rate is high

### Step 1: Brief Parsing (Orchestration Layer)
**Script:** `backend/app/orchestration/query_parser.py`

Parse the brand brief using GPT-4o to extract:

**Basic:**
- Target count (default: 5)
- Influencer gender preference
- Target audience gender

**Brand Context:**
- Brand name (e.g., "Adidas")
- Brand handle (e.g., "@adidas") for audience overlap
- Brand category (e.g., "sports_apparel")

**Creative Concept:**
- Creative concept description
- Creative tone (e.g., ["authentic", "documentary"])
- Creative themes (e.g., ["dedication", "rising stars", "training"])

**Niche Targeting:**
- Campaign topics (e.g., ["padel", "racket sports"])
- Exclude niches (e.g., ["soccer", "football"]) - important for precision

**Size Preferences:**
- Preferred follower min (e.g., 100000)
- Preferred follower max (e.g., 2000000) - anti-celebrity bias

**Standard:**
- Minimum thresholds (credibility, Spain audience %)
- Search keywords for PrimeTag API

**Error Handling:**
- If LLM fails, fallback to basic keyword extraction
- Log parsing confidence for debugging

### Step 2: Candidate Discovery (Execution Layer)
**Script:** `backend/app/services/cache_service.py`

Get large candidate pool from local database (200 candidates):
1. Search by interests matching campaign topics
2. Search by keywords in bio
3. Fall back to generic cache search

**Configuration:** `CANDIDATE_POOL_SIZE = 200` in search_service.py

### Step 3: Soft Pre-Filter (Execution Layer)
**Script:** `backend/app/services/search_service.py` → `_soft_prefilter_candidates()`

Score candidates using cached/imported data **before** expensive API verification:
- Candidates with cached metrics meeting thresholds score highest
- Candidates with partial metrics (need verification) score medium
- Candidates clearly failing filters are deprioritized
- Interest/niche match bonuses applied
- Excluded niche penalties applied

**Configuration:** `MAX_CANDIDATES_TO_VERIFY = 15` (controls API cost, caps at 15-30 calls max)

### Step 4: Primetag Verification Gate (Execution Layer)
**Script:** `backend/app/services/search_service.py` → `_verify_candidates_batch()`

**Cache-First Optimization:** Before batch verification, candidates are split:
- **Already verified** (full metrics + fresh cache) → skip API entirely
- **Needs verification** → proceed to batch API calls

Verify **only candidates needing verification** (up to 15 max):
1. Check if candidate already has full cached metrics (skip API call)
2. If cached `primetag_encrypted_username` exists, call detail endpoint directly (1 API call)
3. Otherwise, search + detail (2 API calls)
4. Parallel verification with bounded concurrency (max 5 concurrent)

**Optimization:** New fields `external_social_profile_id` and `primetag_encrypted_username` are stored in the database to skip the search step on subsequent verifications.

**Required Metrics (from Primetag):**
- `audience_geography["ES"]` - Spain audience % (from `location_by_country`)
- `credibility_score` - Credibility % (Instagram only)
- `engagement_rate` - ER %
- `audience_genders` - Gender distribution
- `audience_age_distribution` - Age breakdown

**API Configuration:**
- Authentication: `Authorization: Bearer {PRIMETAG_API_KEY}` header
- Platform types: Instagram = 2, TikTok = 6 (verified 2026-01-28)
- Max 50 results per search call
- 30-second timeout per request
- Exponential backoff on 429/5xx errors (3 retries, 1-30s delay)

**Known Issue:** Some profiles return empty `location_by_country` from PrimeTag, causing Spain % to show as 0%. When this happens, the filter service falls back to checking the `country` field for Spanish influencers.

**Verification Result:**
- Verified candidates (real Gema data fetched) proceed to filtering
- Failed candidates (not found in PrimeTag) are discarded from the verified pool
- `VerificationStats` tracks: total_candidates, verified, failed_verification, passed_filters

**Graceful Degradation:** If **all** verifications fail (e.g. `401 Expired authentication header`, API outage), the system automatically falls back to prefiltered candidates with lenient mode. This keeps the app functional when PrimeTag credentials expire. A warning is logged:
```
⚠ All 15 PrimeTag verifications failed (API may be unavailable or credentials expired).
Falling back to prefiltered candidates with lenient mode.
```
**Action when this happens:** Refresh `PRIMETAG_API_KEY` in `.env`.

### Step 5: Filtering (Execution Layer)
**Script:** `backend/app/services/filter_service.py`

Apply filters with `lenient_mode=True` (lenient for PrimeTag misses, strict for verified data):
1. Credibility score >= threshold (default 70%) — skip if data is None
2. Spain audience >= threshold (default 60%) — skip if data is None, fallback to `country` field
3. Engagement rate >= threshold (if specified) — skip if data is None
4. Audience gender match (if specified)

**Lenient mode rationale:** Influencers not found in PrimeTag (niche markets, TikTok-only) are allowed through rather than silently discarded, preserving coverage. Once PrimeTag data is populated via verification, their Gema metrics are enforced strictly on subsequent searches (cache hit path).

### Step 6: Ranking (Execution Layer)
**Script:** `backend/app/services/ranking_service.py`

Calculate weighted relevance score using **8 factors**:

```
score = (
    0.15 × credibility +
    0.20 × engagement +
    0.15 × audience_match +
    0.05 × growth +
    0.10 × geography +
    0.15 × brand_affinity +     # NEW: audience overlap with brand
    0.15 × creative_fit +       # NEW: tone/theme alignment
    0.05 × niche_match          # NEW: content niche match
) × size_multiplier             # Anti-celebrity bias + unknown-follower penalty
```

**New Scoring Factors:**

| Factor | Source | Calculation |
|--------|--------|-------------|
| Brand Affinity | Audience overlap or `brand_mentions` | 0.5 (neutral) if no brand, 0.75 if mentioned brand before |
| Creative Fit | `interests`, `bio`, `brand_mentions` | Theme match (40%) + Tone match (30%) + Experience (30%) |
| Niche Match | `interests`, `bio` | Boost for `campaign_topics`, penalty for `exclude_niches` |

**Size Multiplier (Anti-Celebrity Bias):**
- Profiles with 0/null follower counts always get 0.3x-0.4x penalty (unknown reach)
- If `preferred_follower_max` specified and influencer exceeds it, apply penalty
- Example: 50M followers with 2M max → multiplier = 0.04
- Even without size preferences, 0-follower profiles get 0.4x penalty to rank below verified profiles

LLM adjusts weights based on brief context (more brand info → higher brand_affinity weight).

### Step 7: Persistence (Execution Layer)
**Script:** `backend/app/services/search_service.py`

Save to database:
- Search record with parsed query and filters
- Search results with ranking data
- Update influencer cache

## Output
- Search ID (UUID)
- Parsed query details (including extracted brand/creative/niche context)
- **Verification stats** (total_candidates, verified, failed_verification, passed_filters)
- Ranked list of influencers with:
  - Relevance score (0-1)
  - All 8 score components for transparency
  - Full influencer data (including `interests`, `brand_mentions`, `mediakit_url`)

## Edge Cases

### No Results Found
- Return empty results with total_candidates count
- Log for debugging

### API Errors
- Gracefully degrade to cached data only
- Return partial results if some API calls succeed

### LLM Parsing Failures
- Use fallback parser
- Set parsing_confidence to 0.3
- Continue with basic keyword search

## Metrics to Track
- Search execution time
- API call count per search
- Cache hit rate
- LLM parsing confidence distribution

---

## Implementation Reference

### API Endpoint
**File:** `backend/app/api/routes/search.py`
**Route:** `POST /search/`

### Search Service (Main Orchestration)
**File:** `backend/app/services/search_service.py`

```python
from app.services.search_service import SearchService

service = SearchService(db_session)
result = await service.execute_search(SearchRequest(
    query="5 female influencers for IKEA",
    filters=FilterConfig(min_credibility_score=75.0)
))
```

### Query Parser (LLM Integration)
**File:** `backend/app/orchestration/query_parser.py`

Uses GPT-4o with structured JSON response format to extract brand/creative/niche context:
```python
from app.orchestration.query_parser import parse_search_query

brief = """
Find 5 Spanish influencers for Adidas padel campaign. 
Creative concept: 'Rising Stars' series - authentic documentary style,
focus on dedication. Prefer 100K-2M followers.
"""
parsed = await parse_search_query(brief)

# Returns ParsedSearchQuery:
# - target_count: 5
# - brand_name: "Adidas"
# - brand_handle: "@adidas"
# - brand_category: "sports_apparel"
# - creative_concept: "Rising Stars series..."
# - creative_tone: ["authentic", "documentary"]
# - creative_themes: ["dedication", "rising stars"]
# - campaign_topics: ["padel", "racket sports"]
# - exclude_niches: ["soccer", "football"]
# - preferred_follower_min: 100000
# - preferred_follower_max: 2000000
# - search_keywords: ["padel", "tenis", "raqueta"]
# - parsing_confidence: 0.95
```

### Pydantic Schemas
**File:** `backend/app/schemas/search.py`

- `SearchRequest` - Query, filters, ranking weights
- `SearchResponse` - Full response with parsed query, results, verification_stats
- `FilterConfig` - Configurable thresholds
- `RankingWeights` - 8 weight factors (including brand_affinity, creative_fit, niche_match)
- `VerificationStats` - Tracks verification funnel (total, verified, failed, passed filters)

**File:** `backend/app/schemas/llm.py`

- `ParsedSearchQuery` - LLM output with brand/creative/niche context

**File:** `backend/app/schemas/influencer.py`

- `ScoreComponents` - All 8 scoring factors
- `InfluencerData` - Including `interests` and `brand_mentions` for matching

### Database Models
- `backend/app/models/influencer.py` - Influencer cache
- `backend/app/models/search.py` - Search + SearchResult tables

### Frontend Components
- `frontend/src/lib/api.ts` - `searchInfluencers()` function
- `frontend/src/components/search/SearchBar.tsx` - **Brief-pasting textarea** (expandable)
- `frontend/src/components/search/FilterPanel.tsx` - Threshold sliders
- `frontend/src/components/results/ResultsGrid.tsx` - Results with 8-factor score display
