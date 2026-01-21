# Search Workflow Directive

## Goal
Process natural language queries to find and rank influencers for brand partnerships.

## Input
- Natural language query from user (e.g., "5 female influencers for IKEA")
- Optional filter overrides (credibility, engagement, geography thresholds)
- Optional ranking weight overrides

## Process Flow

### Step 1: Query Parsing (Orchestration Layer)
**Script:** `backend/app/orchestration/query_parser.py`

Parse the natural language query using GPT-4o to extract:
- Target count (default: 5)
- Influencer gender preference
- Target audience gender
- Brand name and category
- Content themes
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

### Step 4: Filtering (Execution Layer)
**Script:** `backend/app/services/filter_service.py`

Apply filters in order:
1. Credibility score >= threshold (default 70%)
2. Spain audience >= threshold (default 60%)
3. Engagement rate >= threshold (if specified)
4. Audience gender match (if specified)

### Step 5: Ranking (Execution Layer)
**Script:** `backend/app/services/ranking_service.py`

Calculate weighted relevance score:
```
score = 0.25 × credibility + 0.30 × engagement + 0.25 × audience_match + 0.10 × growth + 0.10 × geography
```

LLM may adjust weights based on brand context.

### Step 6: Persistence (Execution Layer)
**Script:** `backend/app/services/search_service.py`

Save to database:
- Search record with parsed query and filters
- Search results with ranking data
- Update influencer cache

## Output
- Search ID (UUID)
- Parsed query details
- Ranked list of influencers with:
  - Relevance score
  - Individual score components
  - Full influencer data

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

Uses GPT-4o with structured JSON response format:
```python
from app.orchestration.query_parser import parse_search_query

parsed = await parse_search_query("5 female influencers for IKEA")
# Returns ParsedSearchQuery:
# - target_count: 5
# - influencer_gender: "female"
# - brand_name: "IKEA"
# - brand_category: "home_furniture"
# - keywords: ["home", "decor", "interior"]
# - parsing_confidence: 0.95
```

### Pydantic Schemas
**File:** `backend/app/schemas/search.py`

- `SearchRequest` - Query, filters, ranking weights
- `SearchResponse` - Full response with parsed query, results
- `FilterConfig` - Configurable thresholds
- `RankingWeights` - Weight distribution

**File:** `backend/app/schemas/llm.py`

- `ParsedSearchQuery` - LLM output structure

### Database Models
- `backend/app/models/influencer.py` - Influencer cache
- `backend/app/models/search.py` - Search + SearchResult tables

### Frontend Components
- `frontend/src/lib/api.ts` - `searchInfluencers()` function
- `frontend/src/components/search/SearchBar.tsx` - Natural language input
- `frontend/src/components/search/FilterPanel.tsx` - Threshold sliders
- `frontend/src/components/results/ResultsGrid.tsx` - Results display
