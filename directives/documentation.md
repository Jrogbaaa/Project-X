# Documentation Directive

## Goal
Maintain accurate, up-to-date documentation that reflects the current state of the codebase.

## Documentation Structure

### Layer 1: Project Overview
**File:** `AGENTS.md` (project root)

Contains:
- 3-layer architecture explanation
- Service overview tables
- API endpoint summary
- Database schema summary
- Quick start commands

**Update when:** Architecture changes, new services added, endpoints modified

### Layer 2: Directives (SOPs)
**Directory:** `directives/`

| File | Purpose | Update When |
|------|---------|-------------|
| `search-workflow.md` | Search flow documentation | Search logic changes |
| `ranking-criteria.md` | Ranking algorithm docs | Weights/scoring changes |
| `api-integration.md` | PrimeTag API guide | API client changes |
| `enrichment-pipeline.md` | Instagram profile scraping | Enrichment approach changes |
| `documentation.md` | This file | Documentation standards change |

**Format:** Each directive should have:
1. Goal section
2. Process/Flow section
3. Edge cases
4. Implementation Reference section (with file paths)

### Layer 3: Technical Reference
**Directory:** `docs/`

| File | Purpose | Update When |
|------|---------|-------------|
| `API.md` | Full API documentation | Any API route changes |

**Format:** OpenAPI-style with:
- Endpoint path and method
- Request/response examples
- Data model schemas
- Error responses

## Update Triggers

### Automatic (via /update-docs command)
- After implementing new features
- After fixing bugs
- After refactoring

### Manual Review Needed
- Architecture changes
- Breaking API changes
- New service layers

## Documentation Standards

### File References
Always use relative paths from project root:
```
backend/app/services/search_service.py
frontend/src/components/search/SearchBar.tsx
```

### Code Examples
Include minimal, working examples:
```python
# Good
from app.services.search_service import SearchService
result = await service.execute_search(request)

# Bad - too verbose
# First, import all the necessary modules...
# Then create an instance...
# Finally, call the method...
```

### Tables
Use tables for:
- Service/component listings
- API endpoints
- Configuration options

### Avoid
- Verbose explanations of obvious code
- Duplicate information across files
- Outdated examples
- Screenshots (prefer text/code)

## Implementation Reference

### Update Documentation Command
**File:** `.claude/commands/update-docs.md`

Invoke with: `/update-docs`

This command:
1. Scans recent code changes
2. Identifies documentation impact
3. Updates relevant documentation files
4. Reports what was changed

### Documentation Files by Area

| Area | Files to Update |
|------|-----------------|
| Backend services | `AGENTS.md`, `directives/search-workflow.md` |
| API routes | `AGENTS.md`, `docs/API.md` |
| LLM integration | `directives/search-workflow.md` |
| PrimeTag client | `directives/api-integration.md` |
| Instagram enrichment | `directives/enrichment-pipeline.md` |
| Frontend components | `AGENTS.md` |
| Database models | `AGENTS.md` |
| Ranking algorithm | `directives/ranking-criteria.md` |
