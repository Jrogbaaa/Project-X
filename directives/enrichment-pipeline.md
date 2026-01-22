# Instagram Enrichment Pipeline Directive

## Overview

Pipeline for enriching influencer CSV data with profile information from Instagram's public API. Extracts category (genre) and biography (details) for each profile. Supports batch processing with automatic pausing and resume capability.

## Effectiveness Assessment (January 2026)

### Key Finding: Limited Value for GENRE, Useful for Details

After testing on 425 profiles from the Spanish influencer database:

| Metric | Original CSV (StarNgage) | Instagram API | Net Gain |
|--------|--------------------------|---------------|----------|
| **GENRE coverage** | 93% already filled | 24% have category_name | **+2 profiles** |
| **Details coverage** | 0.2% had details | 43% have biography | **+182 profiles** |

### Why Instagram GENRE Data is Limited

Instagram's `category_name` field only exists for **business/creator accounts** (~24% of profiles). Most celebrities and influencers either:
- Use personal accounts (no category)
- Haven't set a business category
- Have generic categories like "Public figure" or "Artist"

**StarNgage provides better genre data** with specific categories like "SportsSoccer", "BooksLifestyleModeling", etc.

### Instagram Category Examples

| Category | Count | Notes |
|----------|-------|-------|
| Athlete | 26 | Most common, but generic |
| Artist | 20 | Very broad |
| Public figure | 14 | Non-descriptive |
| Actor | 9 | Useful |
| Digital creator | 8 | Generic |

### Recommendation

| Use Case | Recommended? | Reason |
|----------|--------------|--------|
| Fill empty GENRE fields | ❌ No | StarNgage data is better; only 2 profiles gained |
| Fill empty Details/Bio | ✅ Yes | 182 profiles enriched (43% have bios) |
| Get "what they post" content | ❌ No | Would need post scraping, not profile data |

### What This Pipeline CANNOT Do

- **Content theme analysis**: Instagram API returns profile bio, not post content themes
- **Rich genre classification**: Only basic business categories available
- **Private account data**: Limited data for private profiles

## Tool Location

**Script:** `backend/app/services/instagram_enrichment.py`

## Usage

### Basic Usage (with batching)

```bash
cd backend && source ../venv/bin/activate
python -m app.services.instagram_enrichment \
    --input "/Users/JackEllis/Project X/top 4000 influencers in spain  - Influencers.csv" \
    --output "/Users/JackEllis/Project X/influencers_enriched.csv" \
    --rate-limit 10 \
    --batch-size 100 \
    --batch-pause 1800
```

### Recommended Settings (to avoid rate limiting)

```bash
python -m app.services.instagram_enrichment \
    --input "../influencers.csv" \
    --output "../enriched.csv" \
    --rate-limit 10 \
    --batch-size 100 \
    --batch-pause 1800
```

This processes 100 profiles, pauses 30 minutes, then continues. Safe for overnight runs.

### Testing (Limited Run)

```bash
python -m app.services.instagram_enrichment \
    --input "../influencers.csv" \
    --output "../test_enriched.csv" \
    --limit 50
```

## Command Line Arguments

| Argument | Short | Default | Description |
|----------|-------|---------|-------------|
| `--input` | `-i` | Required | Path to input CSV file |
| `--output` | `-o` | Required | Path for output CSV file |
| `--rate-limit` | `-r` | 20 | Max requests per minute (recommend 10) |
| `--cache-dir` | | `.tmp` | Directory for cache files |
| `--force` | `-f` | False | Re-fetch all profiles (ignore cache & progress) |
| `--limit` | | None | Limit profiles to process (for testing) |
| `--verbose` | `-v` | False | Enable debug logging |
| `--batch-size` | `-b` | 100 | Profiles to process per batch |
| `--batch-pause` | | 1800 | Seconds to pause between batches (30 min) |

## Data Mapping

| Instagram API Field | CSV Column | Notes |
|---------------------|------------|-------|
| `category_name` | GENRE | e.g., "Athlete", "Public figure" |
| `biography` | Details | Truncated to 500 chars, newlines cleaned |

## Instagram API Details

**Endpoint:**
```
GET https://www.instagram.com/api/v1/users/web_profile_info/?username={USERNAME}
```

**Required Header:**
```
x-ig-app-id: 936619743392459
```

**Response Fields Used:**
- `data.user.category_name` - Business category (may be null)
- `data.user.biography` - Profile bio text
- `data.user.full_name` - Display name
- `data.user.edge_followed_by.count` - Follower count
- `data.user.is_business_account` - Business account flag
- `data.user.is_verified` - Verification badge

## Rate Limiting Strategy

| Setting | Value | Rationale |
|---------|-------|-----------|
| Recommended rate | 10 req/min | Safe to avoid blocks |
| Request jitter | 2-4 seconds | Randomized delay between requests |
| Batch size | 100 profiles | Process then pause |
| Batch pause | 30 minutes | Cool-down between batches |
| Rate limit detection | 5 consecutive 401s | Triggers automatic pause |
| Max retries | 3 | Per-request retry limit |

**Estimated Runtime:**
- 4,000 profiles at 100/batch with 30 min pauses = ~20 hours
- Can run overnight or over multiple sessions
- With caching, re-runs only process new profiles

## Batch Processing

The pipeline processes profiles in batches to avoid Instagram rate limiting:

1. **Batch size** (default 100): Number of profiles before pausing
2. **Batch pause** (default 30 min): Cool-down between batches
3. **Progress saved**: After each profile, position saved to `.tmp/ig_progress.json`
4. **CSV checkpoints**: Saved after each batch

**You can safely stop the script anytime** (Ctrl+C) - it will resume from the last saved position.

## Error Handling

| Error Type | Detection | Action |
|------------|-----------|--------|
| Profile not found | HTML response (not JSON) | Mark as `NOT_FOUND`, skip |
| Rate limited | HTTP 429 | Pause 60s, retry |
| Timeout | Request timeout | Retry 3x with backoff |
| Network error | Connection failed | Retry 3x with backoff |
| No category | `category_name: null` | Keep existing GENRE |

## Cache & Progress System

**Files:**
| File | Purpose |
|------|---------|
| `.tmp/ig_cache.json` | Cached profile data (persists across runs) |
| `.tmp/ig_progress.json` | Current position for resume (cleared on completion) |

**Features:**
- **Cache**: Saves fetched profile data, never re-fetches same profile
- **Progress**: Tracks row position, allows resume from exact spot
- **Checkpoints**: CSV saved after each batch
- Use `--force` to clear both cache and progress (full restart)

**Cache Entry Format:**
```json
{
  "dulceida": {
    "username": "dulceida",
    "full_name": "Aida Domenech",
    "biography": "Bio text...",
    "category_name": "Personal blog",
    "follower_count": 3476678,
    "is_business": true,
    "is_verified": true,
    "fetched_at": "2026-01-22T10:30:00+00:00",
    "error": null
  }
}
```

**Progress File Format:**
```json
{
  "last_processed_index": 425
}
```

## Output Format

The output CSV preserves the original structure with enriched columns:
- **GENRE**: Populated from Instagram `category_name` (only if previously empty)
- **Details**: Populated from Instagram `biography` (only if previously empty)

Existing values are NOT overwritten.

## Learnings & Edge Cases

### Discovered Issues

1. **~76% of profiles have no `category_name`** - Personal accounts and most celebrities don't set business categories
2. **StarNgage GENRE > Instagram category** - Original CSV has 93% genre coverage vs Instagram's 24%
3. **Rate limits are VERY strict** - Instagram blocks after ~200-300 requests in quick succession
4. **401 "Please wait" = rate limited** - Not just 429, also 401 with specific message
5. **HTML response = profile not found** - Different from JSON error responses
6. **Multi-line bios** - Cleaned to single line for CSV compatibility
7. **Multi-line GENRE in CSV** - Original CSV has newlines in GENRE cells (6604 lines but only 4015 rows)

### Best Practices

1. **Use batch mode** - Process 100 profiles, pause 30 min, repeat
2. **Rate limit 10/min** - Safer than 20/min
3. **Run overnight** - Full enrichment takes ~20 hours with safe settings
4. **Use cache** - Never re-fetches cached profiles
5. **Monitor logs** - Watch for consecutive 401 errors
6. **Test first** - Use `--limit 50` before full runs
7. **Can stop anytime** - Progress saved after each profile

## Re-running the Pipeline

### Resume Interrupted Run
Just run the same command again - it automatically resumes from last position:
```bash
python -m app.services.instagram_enrichment \
    --input "../influencers.csv" \
    --output "../enriched.csv" \
    --batch-size 100 \
    --batch-pause 1800
```

### Incremental Updates (New Profiles Only)
```bash
python -m app.services.instagram_enrichment \
    --input "../new_influencers.csv" \
    --output "../enriched.csv"
```
Cache will skip already-fetched usernames.

### Full Refresh
```bash
python -m app.services.instagram_enrichment \
    --input "../influencers.csv" \
    --output "../enriched.csv" \
    --force
```
Clears cache and progress, re-fetches all profiles.

### Background/Overnight Run

```bash
cd backend && source ../venv/bin/activate
nohup python -m app.services.instagram_enrichment \
    --input "/full/path/to/influencers.csv" \
    --output "/full/path/to/enriched.csv" \
    --rate-limit 10 \
    --batch-size 100 \
    --batch-pause 1800 \
    > "../.tmp/enrichment.log" 2>&1 &

# Monitor progress
tail -f "../.tmp/enrichment.log"
```

## Troubleshooting

### Rate Limited (401 "Please wait")
- **Stop immediately** - More requests make it worse
- **Wait 30-60 minutes** before retrying
- **Reduce settings**: `--rate-limit 5 --batch-size 50 --batch-pause 3600`
- Progress is saved, just restart later

### High Error Rate
- If seeing many consecutive 401s, you're rate limited
- Reduce `--rate-limit` to 5-10
- Increase `--batch-pause` to 3600 (1 hour)
- Consider running from different network/IP

### Slow Progress
- Expected: ~3-6 seconds per profile with jitter
- Batches of 100 take ~10-15 minutes
- Full run (4000 profiles) = ~20 hours with pauses

### Missing Data
- Some profiles genuinely have no category (~30%)
- Private profiles return limited data
- Deleted/suspended accounts return NOT_FOUND
- Cached profiles with errors won't be retried unless `--force`

### Check Current State
```bash
# See cache size
wc -l ".tmp/ig_cache.json"

# See progress position  
cat ".tmp/ig_progress.json"

# Test if rate limit cleared
curl -s "https://www.instagram.com/api/v1/users/web_profile_info/?username=cristiano" \
  -H "x-ig-app-id: 936619743392459" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status'))"
```
