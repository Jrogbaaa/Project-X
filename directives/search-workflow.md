# Search Workflow Directive

## Goal
Process brand briefs and natural language queries to find and intelligently rank influencers based on brand affinity, creative fit, and niche match—not just generic popularity metrics.

## Input
- **Brand brief** pasted by user (can be multi-line, detailed campaign description)
- Example: "Find 5 Spanish influencers for Adidas padel campaign. Creative concept: 'Rising Stars' series featuring up-and-coming athletes in authentic training moments, documentary style. Prefer mid-tier influencers (100K-2M followers)."
- Optional filter overrides (credibility, engagement, geography thresholds)
- Optional ranking weight overrides

## Process Flow

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

### Step 2: Cache Check (Execution Layer)
**Script:** `backend/app/services/cache_service.py`

Check PostgreSQL cache for influencers matching:
- Minimum credibility score
- Minimum Spain audience percentage
- Non-expired cache entries (24-hour TTL)

### Step 3: PrimeTag API Search (Execution Layer)
**Script:** `backend/app/services/primetag_client.py`

If cache insufficient:
1. Search `/media-kits` with extracted keywords
2. Limit to 5 keyword searches
3. Fetch `/media-kits/{platform}/{username}` for detailed metrics
4. Limit to 30 detail fetches per search

**API Rate Limits:**
- Max 50 results per search call
- 30-second timeout per request
- Implement exponential backoff on failures

### Step 4: Primetag Verification Gate (NEW)
**Script:** `backend/app/services/search_service.py` → `_verify_candidates_batch()`

**Every candidate must be verified via Primetag API** before filtering:
1. For each discovered candidate, call `get_media_kit_detail()` to fetch full metrics
2. Parallel verification with bounded concurrency (max 5 concurrent)
3. Candidates without full metrics are discarded
4. Verified data is cached for future searches

**Required Metrics (from Primetag):**
- `audience_geography["ES"]` - Spain audience %
- `credibility_score` - Credibility % (Instagram only)
- `engagement_rate` - ER %
- `audience_genders` - Gender distribution
- `audience_age_distribution` - Age breakdown

**Verification Result:**
- Verified candidates proceed to filtering
- Failed candidates (not found, API error, missing metrics) are discarded
- `VerificationStats` tracks: total_candidates, verified, failed_verification, passed_filters

### Step 5: Strict Filtering (Execution Layer)
**Script:** `backend/app/services/filter_service.py`

Apply filters in **strict mode** (`lenient_mode=False`):
1. Credibility score >= threshold (default 70%) - **must have data**
2. Spain audience >= threshold (default 60%) - **must have data**
3. Engagement rate >= threshold (if specified) - **must have data**
4. Audience gender match (if specified)

**Note:** No lenient mode - candidates without real Primetag data are rejected.

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
) × size_multiplier             # Anti-celebrity bias if size preference specified
```

**New Scoring Factors:**

| Factor | Source | Calculation |
|--------|--------|-------------|
| Brand Affinity | Audience overlap or `brand_mentions` | 0.5 (neutral) if no brand, 0.75 if mentioned brand before |
| Creative Fit | `interests`, `bio`, `brand_mentions` | Theme match (40%) + Tone match (30%) + Experience (30%) |
| Niche Match | `interests`, `bio` | Boost for `campaign_topics`, penalty for `exclude_niches` |

**Size Multiplier (Anti-Celebrity Bias):**
- If `preferred_follower_max` specified and influencer exceeds it, apply penalty
- Example: 50M followers with 2M max → multiplier = 0.04

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
  - Full influencer data (including `interests`, `brand_mentions`)

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
