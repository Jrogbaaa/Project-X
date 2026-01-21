---
description: "Update project documentation after code changes"
---

# Update Documentation

You are being asked to update the project documentation to reflect recent code changes.

## Documentation Files to Update

Review and update the following documentation files:

### 1. AGENTS.md (Project Root)
- Update service descriptions if new services were added
- Update API endpoints table if routes changed
- Update frontend components table if components changed
- Update database schema if models changed
- Keep the architecture diagram current

### 2. directives/*.md (Directive Layer)
- **search-workflow.md** - Update if search flow changed
- **ranking-criteria.md** - Update if ranking algorithm changed
- **api-integration.md** - Update if PrimeTag integration changed
- Add "Implementation Reference" sections pointing to actual files

### 3. docs/API.md
- Update endpoint documentation if API routes changed
- Update request/response schemas if Pydantic schemas changed
- Add new examples for new endpoints

## Process

1. **Scan for Recent Changes**
   - Check git status for modified files
   - Read the modified files to understand what changed
   - Focus on: `backend/app/`, `frontend/src/`, `directives/`

2. **Identify Documentation Impact**
   - New files? Add to appropriate tables/lists
   - Changed schemas? Update API docs
   - New endpoints? Document them
   - Bug fixes? Update "Learnings & Edge Cases" in directives

3. **Update Documentation**
   - Keep changes minimal and focused
   - Maintain existing formatting and structure
   - Add implementation references with file paths
   - Update version/status information

4. **Verify Accuracy**
   - Cross-reference code with documentation
   - Ensure file paths are correct
   - Test any example commands/curl requests

## Output

After updating documentation, provide a summary of:
- Files updated
- What was changed in each
- Any areas that need manual review

## Important Notes

- Do NOT create new documentation files unless necessary
- Do NOT add unnecessary details or verbose explanations
- Keep documentation concise and actionable
- Focus on WHAT and WHERE, not excessive WHY
- Update timestamps/status markers where applicable
