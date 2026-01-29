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
- **Related niches**: Similar content areas that are good matches (e.g., padel ↔ tennis ↔ fitness)
- **Conflicting niches**: Content areas that should be excluded (e.g., padel ✗ football/soccer)

**Discovery Pipeline:**
1. LLM extracts `campaign_niche` and `exclude_niches` from the brief
2. `find_by_niche()` queries by `primary_niche` column (exact + related matches)
3. Conflicting niches are **hard-excluded** at database level (not just penalized)
4. Falls back to `interests` field matching when `primary_niche` is not set

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

1. **Paste brief** → LLM extracts brand/creative/niche context → PrimeTag API → Filter → 8-factor ranking → Display
2. **Export search results** to CSV/Excel
3. **Save searches** for later reference
4. **Search history** tracking

### Backend Services (`backend/app/services/`)

| Service | File | Purpose |
|---------|------|---------|
| PrimeTag Client | `primetag_client.py` | API integration for influencer data with **exponential backoff retry** (3 retries, handles 429/5xx) |
| Search Service | `search_service.py` | Main search orchestration with **Primetag verification gate** |
| Filter Service | `filter_service.py` | Configurable filtering (credibility, geography, gender, growth) + **competitor ambassador exclusion** |
| Ranking Service | `ranking_service.py` | **8-factor scoring**: credibility, engagement, audience, growth, geography, brand_affinity, creative_fit, niche_match |
| **Brand Intelligence** | `brand_intelligence_service.py` | Competitor detection, ambassador tracking, niche relevance scoring |
| Cache Service | `cache_service.py` | PostgreSQL-based influencer caching (24h TTL) + **bulk upsert & cache warming** |
| Export Service | `export_service.py` | CSV/Excel export generation |
| Instagram Enrichment | `instagram_enrichment.py` | Batch scrape Instagram bios (⚠️ limited for niche data—see directive) |
| Import Service | `import_influencers.py` | Import enriched CSV into database with **niche/interests parsing** |

### Orchestration Layer (`backend/app/orchestration/`)

| Module | File | Purpose |
|--------|------|---------|
| Query Parser | `query_parser.py` | GPT-4o extracts brand, creative concept, tone, themes, niches, size preferences from briefs |

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

### Database Schema

| Table | Purpose |
|-------|---------|
| `influencers` | Cached influencer data with JSONB audience fields |
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

### Search Filtering

The search pipeline applies these filters in order:

| Filter | Default | Description |
|--------|---------|-------------|
| Max Followers | 2,500,000 | Excludes mega-celebrities (>2.5M followers) |
| Credibility | ≥70% | Audience authenticity score |
| Spain Audience | ≥60% | Minimum Spanish audience percentage |
| Engagement Rate | Optional | Minimum interaction rate |
| Growth Rate | Optional | 6-month follower growth |

The terminal shows detailed logging during searches with step-by-step progress and filter breakdowns.

### Testing a Search

```bash
# Execute a search
curl -X POST http://localhost:8000/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "5 female influencers for IKEA"}'
```

## Summary

You sit between human intent (directives) and deterministic execution (Python scripts). Read instructions, make decisions, call tools, handle errors, continuously improve the system.

Be pragmatic. Be reliable. Self-anneal.
