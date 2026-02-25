# Agent Instructions

> This file is mirrored across CLAUDE.md, AGENTS.md, and GEMINI.md so the same instructions load in any AI environment.

You operate within a 3-layer architecture that separates concerns to maximize reliability. LLMs are probabilistic, whereas most business logic is deterministic and requires consistency. This system fixes that mismatch.

## The 3-Layer Architecture

**Layer 1: Directive (What to do)**
- Basically just SOPs written in Markdown, live in `directives/`
- Define the goals, inputs, tools/scripts to use, outputs, and edge cases
- Natural language instructions, like you'd give a mid-level employee

**Layer 2: Orchestration (Decision making)**
- This is you. Your job: intelligent routing.
- Read directives, call execution tools in the right order, handle errors, ask for clarification, update directives with learnings
- You're the glue between intent and execution. E.g you don't try scraping websites yourself—you read `directives/search-workflow.md` and come up with inputs/outputs and then run `backend/app/services/primetag_client.py`

**Layer 3: Execution (Doing the work)**
- Deterministic Python scripts in `backend/app/services/` and `backend/app/orchestration/`
- Environment variables, api tokens, etc are stored in `.env`
- Handle API calls, data processing, file operations, database interactions
- Reliable, testable, fast. Use scripts instead of manual work.

**Why this works:** if you do everything yourself, errors compound. 90% accuracy per step = 59% success over 5 steps. The solution is push complexity into deterministic code. That way you just focus on decision-making.

## Operating Principles

**1. Check for tools first**
Before writing a script, check `backend/app/services/` per your directive. Only create new scripts if none exist.

**2. Self-anneal when things break**
- Read error message and stack trace
- Fix the script and test it again (unless it uses paid tokens/credits/etc—in which case you check w user first)
- Update the directive with what you learned (API limits, timing, edge cases)
- Example: you hit an API rate limit → you then look into API → find a batch endpoint that would fix → rewrite script to accommodate → test → update directive.

**3. Update directives as you learn**
Directives are living documents. When you discover API constraints, better approaches, common errors, or timing expectations—update the directive. But don't create or overwrite directives without asking unless explicitly told to. Directives are your instruction set and must be preserved (and improved upon over time, not extemporaneously used and then discarded).

## Self-annealing loop

Errors are learning opportunities. When something breaks:
1. Fix it
2. Update the tool
3. Test tool, make sure it works
4. Update directive to include new flow
5. System is now stronger

## File Organization

**Deliverables vs Intermediates:**
- **Deliverables**: Exported CSVs, Excel files, or saved searches that agents can share with clients
- **Intermediates**: Temporary files needed during processing

**Directory structure:**
- `.tmp/` - All intermediate files (cached API responses, temp exports). Never commit, always regenerated.
- `backend/app/services/` - Python scripts (the deterministic tools)
- `backend/app/orchestration/` - LLM decision-making layer
- `directives/` - SOPs in Markdown (the instruction set)
- `.env` - Environment variables and API keys

**Key principle:** Local files are only for processing. Deliverables are exported on-demand (CSV/Excel). Everything in `.tmp/` can be deleted and regenerated.

## Project-Specific Context

This is an **Influencer Discovery Tool** for talent agents to find influencers for brand partnerships.

### How It Works

**Input:** Users paste their brand brief into the search bar. This can include:
- Brand name and campaign details
- Creative concept and tone (e.g., "documentary style", "authentic")
- Target themes (e.g., "dedication", "rising stars")
- Niche requirements (e.g., "padel" with exclusion of "soccer")
- Size preferences (e.g., "prefer 100K-2M followers")

**Output:** Ranked list of influencers scored on 8 factors:
1. Credibility (audience authenticity)
2. Engagement (interaction rate)
3. Audience Match (demographics)
4. Growth (follower trajectory)
5. Geography (Spain focus)
6. **Brand Affinity** (audience overlap with brand)
7. **Creative Fit** (tone/theme alignment)
8. **Niche Match** (content niche alignment) ⭐ **Key Factor**

### Niche Matching - Key Concept

**An influencer's niche is what they post about** - their content category (e.g., fitness, home decor, fashion, sports). This is one of the most important factors for matching influencers to brands:

- A **home furniture brand** (IKEA) should match with **home/lifestyle influencers**
- A **health food brand** should match with **fitness/nutrition influencers**
- A **padel equipment brand** should match with **padel/racket sports influencers** (not soccer players)

**Taxonomy-Aware Matching:** The system uses `niche_taxonomy.yaml` which defines relationships between niches:
- **Related niches**: Similar content areas that are good matches (e.g., padel ↔ tennis ↔ fitness, skincare ↔ beauty ↔ wellness)
- **Conflicting niches**: Content areas that should be excluded (e.g., padel ✗ football/soccer)
- **Distinct niches**: "skincare" is separate from "beauty" — skincare matches wellness/health creators, while beauty catches general makeup/cosmetics. Use "skincare" for serum, SPF, facial routine briefs.
- **Pets niche**: "pets" matches pet owners, animal care creators. Related to lifestyle/parenting. Use for pet stores (Tiendanimal, Kiwoko) and animal brands (Royal Canin, Purina).
- **Niche selection rules**: Always prefer the MOST SPECIFIC niche over a broader one: "gaming" > "tech", "padel" > "sports", "skincare" > "beauty", "running" > "fitness", "home_decor" > "lifestyle". Use "gaming" for gaming peripherals/esports, "tech" for smartphones/software. Use "home_decor" for furniture/interior design, "lifestyle" only when nothing specific fits.
- **Exclude-niche safety**: The LLM is instructed to NEVER exclude a niche that is closely related to campaign_niche (e.g., don't exclude "beauty" for a skincare campaign, don't exclude "fitness" for a running campaign). Only genuinely conflicting niches should be excluded.

**Discovery Pipeline:**
1. LLM extracts `campaign_niche` and `exclude_niches` from the brief
2. **Creative Matching**: LLM also outputs `discovery_interests` - PrimeTag interest categories that would be good fits (e.g., padel brand → ["Sports", "Tennis", "Fitness"])
3. `find_by_niche()` queries by `primary_niche` column (exact + related matches)
4. **Creative Discovery**: If niche matches are sparse (<20 results), expands using `discovery_interests`
5. Conflicting niches are **hard-excluded** at database level (not just penalized)
6. Falls back to `interests` field matching when `primary_niche` is not set

**Creative Matching Example:**
- Brief: "Find influencers for Bullpadel, a padel equipment brand"
- LLM extracts: `campaign_niche: "padel"`, `discovery_interests: ["Sports", "Tennis", "Fitness"]`, `exclude_interests: ["Soccer"]`
- Reasoning: "Padel is a racket sport. Tennis and fitness influencers align authentically. Avoid soccer players."
- Result: Even without literal "padel" influencers in the database, finds relevant fitness/tennis creators

Each influencer has:
- `primary_niche`: Detected niche from post content analysis (e.g., "padel", "football")
- `interests`: Coarse categories from PrimeTag API (e.g., "Sports", "Soccer")

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Frontend (Next.js 16 + TypeScript + Tailwind)                              │
│   • SearchBar - Paste brand briefs or natural language queries             │
│   • FilterPanel - Configurable thresholds (credibility, engagement, etc.)  │
│   • ResultsGrid - Influencer cards with 8-factor score breakdowns          │
│   • Export buttons (CSV/Excel)                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Backend API (FastAPI + SQLAlchemy Async)                                   │
│   /search       - Execute brief parsing + intelligent matching             │
│   /search/{id}  - Retrieve previous search                                 │
│   /influencers  - Get influencer details                                   │
│   /exports      - Download CSV/Excel                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌───────────┐   ┌───────────┐   ┌───────────┐
            │ OpenAI    │   │ PrimeTag  │   │ PostgreSQL│
            │ GPT-4o    │   │ API       │   │ (Neon)    │
            └───────────┘   └───────────┘   └───────────┘
```

### Key Flows

1. **Paste brief** → LLM extracts brand/creative/niche context → Brand lookup (DB or LLM fallback) → Niche-based discovery → Filter → 8-factor ranking → Display
2. **Export search results** to CSV/Excel
3. **Save searches** for later reference
4. **Search history** tracking

### Brand Recognition Flow

When a brand is mentioned in a search query:

1. **Database lookup first**: Check `brands` table for known brands
2. **LLM fallback**: If not found, `brand_lookup_service.py` asks GPT-4o to identify the brand
3. **Extract context**: Category, niche, competitors, suggested keywords
4. **Enrich search**: Set `campaign_niche` for taxonomy-aware discovery

This allows the system to handle **any brand** - even ones not in our database (e.g., "VIPS" restaurant → niche: "food").

### Backend Services (`backend/app/services/`)

| Service | File | Purpose |
|---------|------|---------|
| PrimeTag Client | `primetag_client.py` | API integration for influencer data with **exponential backoff retry** (3 retries, handles 429/5xx) |
| Search Service | `search_service.py` | Main search orchestration with **taxonomy-aware niche discovery** |
| Filter Service | `filter_service.py` | Configurable filtering (credibility, geography, gender, growth) + **hard follower range filter** + **influencer gender filter** (3-signal inference: audience inverse heuristic, bio keywords, name matching) + **competitor ambassador exclusion**. Treats 0/null follower counts as unknown (allows through; ranking deprioritizes). |
| Ranking Service | `ranking_service.py` | **8-factor scoring**: credibility, engagement, audience, growth, geography, brand_affinity, creative_fit, niche_match. **Unknown follower penalty**: 0/null followers get 0.3x-0.4x score multiplier so verified profiles always rank above unverified ones. **Gender confidence boost**: when `influencer_gender` filter is active, influencers with a DB-confirmed `influencer_gender` matching the requested gender receive a 1.08x post-score multiplier over runtime-inferred passes — prefers confirmed profiles without excluding inferred ones. Zero effect on non-gender-filtered searches. |
| **Brand Intelligence** | `brand_intelligence_service.py` | Competitor detection, ambassador tracking, **niche taxonomy helpers** (`get_niche_relationships`, `get_all_excluded_niches`) |
| **Brand Lookup** | `brand_lookup_service.py` | **LLM-based brand recognition** for unknown brands - extracts category, niche, competitors, keywords via GPT-4o |
| Brand Context | `brand_context_service.py` | Database-backed brand context lookup with category keywords |
| Cache Service | `cache_service.py` | PostgreSQL-based caching + **`find_by_niche()` for taxonomy-aware discovery with hard exclusion** |
| Export Service | `export_service.py` | CSV/Excel export generation |
| Instagram Enrichment | `instagram_enrichment.py` | Batch scrape Instagram bios (⚠️ limited for niche data—see directive) |
| **LLM Niche Enrichment** | `llm_niche_enrichment.py` | **Batch LLM classification** — sends bio + interests + post hashtags to GPT-4o and writes `primary_niche`, `niche_confidence`, `content_themes` back to DB. Processes influencers where `primary_niche IS NULL` in batches of 50 (10 per LLM call). `--dry-run` to preview, `--force` to re-classify all. ~$0.01/influencer. |
| Import Service | `import_influencers.py` | Import enriched CSV into database with **niche/interests parsing** |
| **Keyword Niche Detector** | `keyword_niche_detector.py` | **Free, instant niche detection** — pattern-matches bio + interests + post hashtags against `niche_taxonomy.yaml` keywords. Assigns `primary_niche` + `niche_confidence` where currently NULL. No LLM cost. Run before LLM enrichment to cover clear-cut cases cheaply. `cd backend && python -m app.services.keyword_niche_detector --confidence-threshold 0.5` |
| **Tier Computation** | `compute_tiers.py` | Bulk-populate `influencer_tier` (micro/mid/macro/mega) from `follower_count`. Idempotent — safe to re-run. `cd backend && python -m app.services.compute_tiers` |
| **Gender Computation** | `compute_gender.py` | Pre-compute `influencer_gender` ('male'/'female'/NULL) from display name, bio, and audience signals using expanded Spanish/Catalan/Latin name lists (300+ names). Populates NULL rows by default. `cd backend && python -m app.services.compute_gender` / `--dry-run` to preview / `--force` to re-classify all. Run after importing new influencers. |
| **DB Audit** | `db_audit.py` | Read-only diagnostic — prints field coverage %, niche distribution, interests breakdown, follower tier split, and a matching-quality health summary. `cd backend && python -m app.services.db_audit` |
| **Match Quality Review** | `match_quality_review.py` | Repeatable human review of matching quality — picks N random briefs (default 4) from a diverse pool of 23, runs each through the full search pipeline in parallel, and prints LLM parsing + discovery funnel + matched influencers table for manual evaluation. No assertions. `cd backend && python -m app.services.match_quality_review` / `--seed 42` / `--brief "custom text"` / `--all` |
| **Starngage Scraper** | `starngage_scraper.py` | Interactive Starngage scrape + DB import (see `directives/starngage-scraper.md`). Three subcommands: `combine` merges batch JSON extracts into CSV; `import` upserts CSV into DB (updates follower_count/display_name/interests/engagement_rate for existing, creates new, preserves all enrichment data); `audit` read-only cross-reference of DB vs CSV to verify import freshness, detect stale/orphan records, and spot-check follower counts. Scraping done via Playwright MCP browser — user logs in, agent uses `browser_evaluate` with `fetch()`. `cd backend && python -m app.services.starngage_scraper import --csv ../starngage_spain_influencers_2026.csv` / `audit --csv ../starngage_spain_influencers_2026.csv` |
| **Profile Validator** | `validate_profiles.py` | Batch HEAD-checks `instagram.com/{username}` and sets `profile_active=False` for 404 (deleted/renamed) accounts. Excluded from all search results automatically. Rate-limited (1 req/s default). `cd backend && python -m app.services.validate_profiles --dry-run` to preview, then run without flag to apply. Options: `--delay 0.3` (faster), `--since-days 30` (only check profiles not updated in N days). ~77 min for full DB at 1 req/s. |

### Orchestration Layer (`backend/app/orchestration/`)

| Module | File | Purpose |
|--------|------|---------|
| Query Parser | `query_parser.py` | GPT-4o extracts brand, creative concept, tone, themes, niches, size preferences + **creative matching fields** (`discovery_interests`, `exclude_interests`, `influencer_reasoning`) |

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/search/` | Execute natural language search |
| GET | `/search/{id}` | Retrieve previous search with results |
| POST | `/search/{id}/save` | Save search for later |
| GET | `/search/saved/list` | List all saved searches |
| GET | `/search/history/list` | Get recent search history |
| GET | `/influencers/{id}` | Get influencer details |
| GET | `/influencers/cache/stats` | Cache statistics (total, active, expiring) |
| POST | `/influencers/cache/warm` | Pre-warm expiring cache entries |
| DELETE | `/influencers/cache/expired` | Clean up expired cache entries |
| GET | `/exports/{search_id}/csv` | Export results as CSV |
| GET | `/exports/{search_id}/excel` | Export results as Excel |
| GET | `/health` | Health check |
| GET | `/health/ready` | Readiness check (includes DB) |

### Frontend Components (`frontend/src/components/`)

| Component | Path | Purpose |
|-----------|------|---------|
| SearchBar | `search/SearchBar.tsx` | **Paste brand briefs** or natural language queries (expandable textarea) |
| FilterPanel | `search/FilterPanel.tsx` | Sliders for configurable thresholds (credibility, Spain %, engagement, growth, gender, age brackets) |
| ResultsGrid | `results/ResultsGrid.tsx` | Grid layout with **card/list view toggle**, sticky header, export/save actions |
| InfluencerCard | `results/InfluencerCard.tsx` | Individual influencer display with metrics, **quick copy buttons** |
| InfluencerRow | `results/InfluencerRow.tsx` | **Compact list view** showing username, MediaKit URL, metrics at a glance |
| AudienceChart | `results/AudienceChart.tsx` | Pie/bar charts for demographics |
| ScoreBreakdown | `results/ScoreBreakdown.tsx` | Visual breakdown of all 8 ranking factors |
| Toast | `ui/Toast.tsx` | Toast notifications for copy/save/export feedback |

### Frontend Hooks (`frontend/src/hooks/`)

| Hook | File | Purpose |
|------|------|---------|
| useToast | `useToast.ts` | Toast notification state management |

### Frontend UX Features

**Auto-scroll**: Results section automatically scrolls into view when search completes.

**View Modes**: Toggle between card view (detailed) and list view (compact, scannable).

**Keyboard Shortcuts** (when results are displayed):
- `j` / `k` - Navigate to next/previous result
- `c` - Copy selected influencer's username
- `o` - Open profile in new tab
- `m` - Open MediaKit in new tab (if available)
- `Escape` - Clear selection

**Quick Copy**: Hover over influencer cards/rows to reveal one-click copy buttons for username and MediaKit URL.

**Toast Notifications**: Visual feedback for copy, save, and export actions.

### Frontend Testing

```bash
# Run tests
cd frontend && npm test

# Run tests once (CI mode)
cd frontend && npm run test:run
```

Test coverage includes:
- InfluencerCard: username display, MediaKit links, copy functionality, metrics
- InfluencerRow: compact view, all essential data visible without expansion

### Backend Testing

The backend has a comprehensive pytest-based test suite with **LLM reflection** for validating search result quality.

**Test Files:**
- `backend/tests/test_filter_service.py` - 32 unit tests for filter logic (including follower range + influencer gender)
- `backend/tests/test_ranking_service.py` - 23 unit tests for 8-factor scoring
- `backend/tests/test_search_e2e.py` - End-to-end tests with GPT-4o reflection
- `backend/tests/test_pipeline_verification.py` - **Full pipeline + Gema filter audit** — 4 independent test classes (Fashion/ElCorteInglés, Sports Nutrition/Myprotein, Gastro/Glovo, Beer/Estrella Damm), each using a messy Spanish agency email brief. Validates all 5 pipeline steps and prints a per-influencer Gema audit table (Spain%, Gender%, Age%, Credibility, ER). Detects PrimeTag API key expiry automatically.
- `backend/tests/test_pipeline_diagnostic.py` - **Live pipeline diagnostic** — requires a running server at `localhost:8000`. Marked `@pytest.mark.e2e` so it is excluded from CI (`-m "not e2e"`). Run locally only.
- `backend/tests/test_briefs.py` - 28 test briefs (24 original + 4 Gema pipeline briefs: `pipeline_gema_fashion`, `pipeline_gema_sports_nutrition`, `pipeline_gema_gastro`, `pipeline_gema_beer_lifestyle`)
- `backend/tests/reflection_service.py` - LLM-powered result validation
- `backend/tests/test_result_differentiation.py` - **Result differentiation tests** — 3 unit tests verifying RankingService differentiates by niche + 3 integration tests (marked `@pytest.mark.e2e`) verifying full pipeline produces distinct results for different brand briefs (home_decor vs padel vs fashion: 0% overlap). Validates brand intelligence → campaign_niche extraction and niche discovery relevance.

```bash
# Run unit tests (fast, ~0.1s)
cd backend && pytest tests/test_filter_service.py tests/test_ranking_service.py -v

# Run ranking differentiation unit tests (fast, ~0.1s)
cd backend && pytest tests/test_result_differentiation.py::TestRankingDifferentiation -v -s

# Run full pipeline differentiation tests (requires DB + OpenAI, ~80s)
cd backend && pytest tests/test_result_differentiation.py::TestPipelineDifferentiation -v -s -m e2e

# Run pipeline + Gema audit — run each class in parallel (each ~20-80s)
cd backend && pytest tests/test_pipeline_verification.py::TestPipelineFashion -v -s
cd backend && pytest tests/test_pipeline_verification.py::TestPipelineSportsNutrition -v -s
cd backend && pytest tests/test_pipeline_verification.py::TestPipelineGastro -v -s
cd backend && pytest tests/test_pipeline_verification.py::TestPipelineBeerLifestyle -v -s

# Run a single E2E test with reflection (~40s due to LLM calls)
cd backend && pytest tests/test_search_e2e.py::TestNichePrecision::test_padel_excludes_football -v -s

# Run all tests
cd backend && pytest tests/ -v
```

**LLM Reflection Service:**
The reflection service uses GPT-4o to analyze if search results actually match the original brief:
- Evaluates niche alignment, brand fit, and creative fit
- Identifies excluded niche violations (e.g., football influencers for padel campaign)
- Detects brand conflicts (e.g., Adidas ambassador for Nike campaign)
- Returns structured verdict: excellent/good/acceptable/poor/fail

**Test Brief Categories:**
1. **Niche Precision** - Padel brand (excludes football), IKEA (home decor), fitness supplement
2. **Brand Matching** - Unknown brands (LLM lookup), competitor exclusion (Nike vs Adidas)
3. **Creative Fit** - Documentary style, luxury aesthetic, humorous/casual
4. **Edge Cases** - Gender splits, micro-influencers, multiple niche exclusions
5. **Real World** - Real Spanish agency email briefs: Puerto de Indias (spirits/"Tarde con los tuyos"), IKEA Novedades ("primeras veces"), Square (B2B gastro fintech), IKEA GREJSIMOJS (3-phase playful collection)
6. **Pipeline Verification** - Messy forwarded emails for GEMA filter testing: El Corte Inglés (fashion, female-skewed), Myprotein (fitness, 3M/2F split, football excluded), Glovo (gastro, ER ≥1.5%), Estrella Damm (beer/lifestyle, competitor exclusion)

### Database Schema

| Table | Purpose |
|-------|---------|
| `influencers` | Cached influencer data with JSONB audience fields. Key columns: `primary_niche`, `influencer_tier` (micro/mid/macro/mega, indexed), `credibility_score`, `engagement_rate`, `profile_active` (bool, default true — false = Instagram handle confirmed dead, excluded from all searches). As of Feb 2026: 4,645 influencers, 98.6% have primary_niche, 99.9% have follower_count. |
| `searches` | Search history with parsed queries and filters |
| `search_results` | Links searches to influencers with ranking scores |
| `ranking_presets` | Configurable weight presets (Balanced, Engagement Focus, etc.) |
| `api_audit_log` | Tracks all external API calls |

### Environment Variables

```env
# Required
DATABASE_URL=postgresql+asyncpg://...
PRIMETAG_API_KEY=your_key
OPENAI_API_KEY=your_key

# Optional with defaults
CORS_ORIGINS=http://localhost:3000
DEBUG=false
DEFAULT_MIN_CREDIBILITY=70.0
DEFAULT_MIN_SPAIN_AUDIENCE=60.0
```

### Running the Application

```bash
# Run entire app with single command (from repo root)
npm run dev

# Or run separately:
npm run dev:backend   # Backend only
npm run dev:frontend  # Frontend only

# Database migrations
cd backend && alembic upgrade head
```

The unified `npm run dev` command uses `concurrently` to run both services in parallel with color-coded output:
- `[backend]` - FastAPI/uvicorn on http://localhost:8000
- `[frontend]` - Next.js on http://localhost:3000

### CI/CD & GitHub Actions

The project uses GitHub Actions for continuous integration with E2E tests as the final quality gate.

**Workflow:** `.github/workflows/ci.yml`

```
push/PR → Lint ─┬─→ Build → E2E Tests (Quality Gate)
                │
        Test Frontend (Vitest)
                │
        Test Backend (pytest)
```

**Jobs:**
| Job | Description |
|-----|-------------|
| `lint` | ESLint on frontend code |
| `test-frontend` | Vitest unit tests |
| `test-backend` | pytest unit tests (excludes heavy e2e/reflection tests) |
| `build` | Verifies Next.js build succeeds |
| `e2e` | Playwright browser tests against running app |

**Required GitHub Secrets** (Settings → Secrets → Actions):
- `OPENAI_API_KEY` - For backend tests
- `PRIMETAG_API_KEY` - For backend tests

**Running E2E Tests Locally:**

```bash
# Run Playwright E2E tests (auto-starts servers)
cd frontend && npm run test:e2e

# Run with browser visible
npm run test:e2e:headed

# Run with Playwright UI
npm run test:e2e:ui
```

**E2E Test Files** (`frontend/e2e/`):
- `health.spec.ts` - App loads, API responds
- `search.spec.ts` - Search flow works end-to-end
- `accessibility.spec.ts` - Basic a11y checks
- `search-differentiation.spec.ts` - **Result differentiation tests** — 5 tests that hit the search API directly (not UI) to verify: (1) different niches return different influencer sets (<50% overlap), (2) brand intelligence extracts correct campaign_niche (or graceful fallback when LLM unavailable), (3) niche_match scores are meaningful, (4) primary_niche data coverage >= 70%, (5) PrimeTag graceful degradation

```bash
# Run differentiation tests against Vercel
cd frontend && PLAYWRIGHT_BASE_URL=https://project-x-three-sage.vercel.app npx playwright test e2e/search-differentiation.spec.ts

# Run against local dev
cd frontend && npx playwright test e2e/search-differentiation.spec.ts
```

### Search Filtering

The search pipeline applies these filters in order:

| Filter | Default | Description |
|--------|---------|-------------|
| **Follower Range** | From brief | **HARD FILTER with graceful fallback** — when the brief specifies a preferred range (e.g., "15K-150K"), influencers outside that range are removed. If range would remove ALL candidates (e.g., requesting micro-influencers when DB only has 100K+), filter is relaxed and ranking's size penalty handles deprioritization instead. 0/null treated as unknown (passes). |
| **Influencer Gender** | From brief | **HARD FILTER** — when the brief specifies influencer gender (e.g., "female"), uses 3-signal inference: (1) audience_genders inverse heuristic, (2) bio keyword scan for pronouns/gendered words, (3) display_name first-name matching against common Spanish names. Unknown gender passes through. |
| Min Followers | 100,000 | Minimum follower count (DB sourced from 100K+ profiles). |
| Max Followers | 2,500,000 | Excludes mega-celebrities (>2.5M followers). 0/null treated as unknown (passes). |
| Credibility | ≥70% | Audience authenticity score |
| Spain Audience | ≥60% | Minimum Spanish audience percentage |
| Engagement Rate | Optional | Minimum interaction rate |
| Growth Rate | Optional | 6-month follower growth |

**Ranking Weight Tuning (Feb 2026):** Default ranking weights are tuned for current data reality (PrimeTag API unavailable). Niche match (0.50), creative fit (0.30), engagement (0.10), and brand affinity (0.10) carry the weight; credibility/geography/audience_match/growth are zeroed out until PrimeTag is restored. LLM-suggested weights are clamped with two guards: (1) factors with default weight 0.0 stay zeroed regardless of LLM suggestion; (2) `niche_match` can only be boosted, never reduced below its default (0.50) — prevents engagement from overriding niche relevance in sparse-niche scenarios. Additionally, if the LLM suggests near-equal weights for all factors (variance < 0.15, e.g. all 1.0), the system falls back to default weights — this indicates the LLM has no meaningful preference. When PrimeTag comes back, rebalance the `DEFAULT_WEIGHTS` in `ranking_service.py`.

**Query Parsing Safeguards (Feb 2026):** `query_parser.py` applies three post-LLM guards before building the search parameters: (1) **Niche mapping** — food/restaurant brands (`campaign_niche: "food"`), beer/spirits brands (`"alcoholic_beverages"`), energy drinks (`"soft_drinks"` or `"fitness"`). (2) **`exclude_niches` safety** — related niches are stripped from exclusion lists (e.g. `beauty` is never excluded for a skincare campaign; `lifestyle` is never excluded for a food campaign). A brand's own niche is also never self-excluded. (3) **`discovery_interests` fallback** — if the LLM returns an empty array, a `_NICHE_DISCOVERY_FALLBACK` dict maps `campaign_niche` to default PrimeTag interest categories to ensure creative discovery always has interests to work with.

The terminal shows detailed logging during searches with step-by-step progress and filter breakdowns.

### Testing a Search

```bash
# Execute a search
curl -X POST http://localhost:8000/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "5 female influencers for IKEA"}'
```

## After Any Code Change

Whenever you make changes to the codebase, always:
1. **Update relevant documentation** - Update AGENTS.md (this file), `docs/API.md`, and any `directives/` files that reference the changed behaviour.
2. **Commit all changes** - Stage all modified files and commit with a clear message.
3. **Push to GitHub** - Push to `origin/main` so changes are reflected in production.

This is a standing instruction. Do not wait to be asked.

## Summary

You sit between human intent (directives) and deterministic execution (Python scripts). Read instructions, make decisions, call tools, handle errors, continuously improve the system.

Be pragmatic. Be reliable. Self-anneal.
