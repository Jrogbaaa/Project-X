# Brand Intelligence Directive

## Purpose

Maintain competitive intelligence for accurate influencer-brand matching. This system enables:

1. **Competitor Conflict Detection** - Prevent recommending competitor ambassadors (e.g., Messi for Nike)
2. **Brand Saturation Tracking** - Flag existing ambassadors as "too obvious" for fresh campaigns
3. **Niche Relevance Scoring** - Ensure niche alignment (padel players for padel campaigns)

## Data Sources

### Primary: Brand Intelligence Database
**Location:** `/backend/app/data/brand_intelligence.yaml`

Contains:
- Brand names and Instagram handles
- Competitor brand mappings
- Known ambassador relationships
- Conflict severity settings

### Secondary: Niche Taxonomy
**Location:** `/backend/app/data/niche_taxonomy.yaml`

Contains:
- Niche definitions with keywords
- Related niche mappings
- Conflicting niche definitions
- Celebrity penalty rules

## Brand Intelligence Schema

```yaml
brands:
  adidas:
    name: "Adidas"
    category: "sports_apparel"
    instagram_handles: ["adidas", "adidasoriginals", "adidas_es"]
    competitors: [nike, puma, reebok, new_balance, under_armour]
    ambassadors:
      - username: "leomessi"
        status: "active"           # active, past, rumored
        relationship: "lifetime_deal"  # lifetime_deal, ambassador, sponsored
        niche: "football"
        since: "2006"
        notes: "Lifetime contract since 2017"
    conflict_severity: "high"      # high, medium, low
```

## Niche Taxonomy Schema

```yaml
niches:
  padel:
    keywords: ["padel", "pádel", "padel player", "raqueta"]
    related_niches: [tennis, racket_sports, fitness]
    conflicting_niches: [football, soccer, basketball]
    parent_category: "sports"

rules:
  celebrity_threshold: 5000000     # Follower count for "celebrity"
  celebrity_mismatch_penalty: 0.15  # Score for wrong-niche celebrities
  conflicting_niche_penalty: 0.20
  related_niche_score: 0.70
  exact_match_score: 0.95
```

## Update Procedures

### Adding a New Brand

1. **Identify brand category** from existing categories or create new one
2. **List all Instagram handles** (main + regional accounts)
3. **Identify direct competitors** (same category, same market position)
4. **Research known ambassadors** via public announcements only
5. **Set conflict_severity** based on exclusivity expectations:
   - `high`: Exclusive contracts common (sports, luxury, automotive)
   - `medium`: Less exclusivity (fast fashion, beauty, retail)
   - `low`: Category overlap acceptable (grocery, general consumer)

### Adding an Ambassador

Only add ambassadors with **publicly confirmed** relationships:

```yaml
ambassadors:
  - username: "influencer_handle"  # Without @
    status: "active"               # active, past, rumored
    relationship: "ambassador"     # lifetime_deal, ambassador, sponsored
    niche: "their_primary_niche"
    since: "2024-01"               # When relationship started
    notes: "Optional context"
```

**Relationship types:**
- `lifetime_deal`: Permanent, exclusive (e.g., Messi-Adidas, Ronaldo-Nike)
- `ambassador`: Long-term partnership, potentially exclusive
- `sponsored`: Campaign-based, not necessarily exclusive

### Removing/Updating Ambassadors

- Update `status` to `past` when contracts end publicly
- Remove entirely if relationship was never official
- Add `notes` with context for changes

### Adding a New Niche

1. Define **keywords** that indicate this niche in bio/interests
2. Identify **related_niches** that are similar/adjacent
3. Identify **conflicting_niches** that are explicitly NOT this niche
4. Assign **parent_category** for fallback matching

## Conflict Detection Logic

### Competitor Ambassador (Most Severe)

```
IF influencer is known ambassador for competitor of target brand
THEN score = 0.05 (95% penalty)
     exclude = True (if exclude_competitor_ambassadors enabled)
```

**Example:** Messi (Adidas ambassador) for Nike campaign → Score: 0.05

### Competitor Brand Mention (Moderate)

```
IF influencer.brand_mentions contains competitor handles
THEN score = 0.25-0.45 based on conflict_severity
```

**Severity mapping:**
- `high` (sports, luxury): 0.25
- `medium` (fashion, beauty): 0.35
- `low` (retail, food): 0.45

### Brand Saturation (Info Only)

```
IF influencer is already ambassador for target brand
THEN flag with saturation_warning
     score = 0.35-0.45 (penalize but don't exclude)
```

**Purpose:** Help find fresh talent, not the obvious choice.

## Niche Relevance Logic

### With Campaign Niche Specified

```python
if influencer_niche == campaign_niche:
    score = 0.95  # Exact match
elif influencer_niche in campaign_niche.related_niches:
    score = 0.70  # Related niche
elif influencer_niche in campaign_niche.conflicting_niches:
    score = 0.20  # Conflicting niche
    if follower_count > 5_000_000:
        score = 0.15  # Celebrity penalty
else:
    score = 0.50  # Neutral
```

### Without Campaign Niche (Fallback)

Falls back to keyword matching against `campaign_topics`.

## LLM Integration

The query parser extracts:

1. **brand_handle** - For conflict detection
2. **brand_name** - For display/logging
3. **brand_category** - For category-level fallback
4. **campaign_niche** - For niche relevance scoring
5. **campaign_topics** - For keyword fallback
6. **exclude_niches** - For explicit exclusion

**System prompt guidance:**
- Extract brand handles when brand names are mentioned
- Infer campaign_niche from context (e.g., "padel campaign" → niche: "padel")
- Suggest `exclude_niches` for niche campaigns (padel → exclude football)

## Maintenance Schedule

### Quarterly Review

1. Check ambassador relationships for ended contracts
2. Add new confirmed ambassadors from major brands
3. Update competitor relationships if market changes
4. Review niche taxonomy for new niches

### As-Needed Updates

- New brand launches
- Major ambassador announcements
- Brand acquisitions/mergers

## Testing Recommendations

### Test Case 1: Competitor Conflict
```
Query: "Find influencers for Nike running campaign"
Expected:
- Messi (Adidas ambassador) excluded or score ~0.05
- Ronaldo (Nike ambassador) scores high with saturation warning
- Neutral running influencer scores 0.50+
```

### Test Case 2: Niche Relevance
```
Query: "Find influencers for Adidas padel campaign"
Expected:
- Padel players score 0.95
- Tennis players score 0.70
- Messi (football niche) scores 0.15-0.20 despite being Adidas ambassador
```

### Test Case 3: Brand Saturation
```
Query: "Find fresh faces for Adidas campaign"
Expected:
- Messi flagged with saturation_warning
- New talent without existing Adidas relationship scores higher
```

## Files Reference

| File | Purpose |
|------|---------|
| `backend/app/data/brand_intelligence.yaml` | Brand and ambassador data |
| `backend/app/data/niche_taxonomy.yaml` | Niche relationships |
| `backend/app/services/brand_intelligence_service.py` | Service class |
| `backend/app/services/ranking_service.py` | Scoring integration |
| `backend/app/services/filter_service.py` | Hard exclusion filter |
| `directives/ranking-criteria.md` | Scoring documentation |
