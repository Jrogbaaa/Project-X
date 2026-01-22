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
8. **Niche Match** (content category alignment)

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
| PrimeTag Client | `primetag_client.py` | API integration for influencer data (metrics, interests, brand mentions) |
| Search Service | `search_service.py` | Main search orchestration |
| Filter Service | `filter_service.py` | Configurable filtering (credibility, geography, etc.) |
| Ranking Service | `ranking_service.py` | **8-factor scoring**: credibility, engagement, audience, growth, geography, brand_affinity, creative_fit, niche_match |
| Cache Service | `cache_service.py` | PostgreSQL-based influencer caching (24h TTL) |
| Export Service | `export_service.py` | CSV/Excel export generation |
| Instagram Enrichment | `instagram_enrichment.py` | Batch scrape Instagram bios (⚠️ limited for GENRE—see directive) |
| Import Service | `import_influencers.py` | Import enriched CSV into database with interests/country parsing |

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
| GET | `/exports/{search_id}/csv` | Export results as CSV |
| GET | `/exports/{search_id}/excel` | Export results as Excel |
| GET | `/health` | Health check |
| GET | `/health/ready` | Readiness check (includes DB) |

### Frontend Components (`frontend/src/components/`)

| Component | Path | Purpose |
|-----------|------|---------|
| SearchBar | `search/SearchBar.tsx` | **Paste brand briefs** or natural language queries (expandable textarea) |
| FilterPanel | `search/FilterPanel.tsx` | Sliders for configurable thresholds |
| ResultsGrid | `results/ResultsGrid.tsx` | Grid layout for influencer cards |
| InfluencerCard | `results/InfluencerCard.tsx` | Individual influencer display with metrics |
| AudienceChart | `results/AudienceChart.tsx` | Pie/bar charts for demographics |
| ScoreBreakdown | `results/ScoreBreakdown.tsx` | Visual breakdown of all 8 ranking factors |

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
# Backend (from project root)
cd backend && source ../venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Frontend (from project root)
cd frontend && npm run dev

# Database migrations
cd backend && alembic upgrade head
```

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
