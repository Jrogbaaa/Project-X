# PrimeTag API Integration Directive

## Overview
Integration guide for the PrimeTag API used to fetch influencer data.

## Authentication
**Header:** `Authorization: Token {PRIMETAG_API_KEY}`

Store API key in `.env` as `PRIMETAG_API_KEY`.

## Endpoints

### 1. Search Media Kits
**Endpoint:** `GET /media-kits`

**Purpose:** Search for influencers by username/display name.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| platform_type | int | Yes | 1=Instagram, 2=TikTok, 3=YouTube |
| search | string | Yes | Fulltext search query |
| limit | int | No | Max results (default 10, max 50) |

**Response:**
```json
{
  "response": [
    {
      "external_social_profile_id": "encrypted_id",
      "username": "influencer_handle",
      "display_name": "Display Name",
      "avatar": "https://...",
      "audience_size": 150000,
      "is_verified": true,
      "platform_type": 1,
      "mediakit_url": "https://..."
    }
  ],
  "metadata": {}
}
```

### 2. Get Media Kit Detail
**Endpoint:** `GET /media-kits/{platform_type}/{username_encrypted}`

**Purpose:** Get full influencer metrics and audience data.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| platform_type | int | Yes | Platform ID |
| username_encrypted | string | Yes | From search result `external_social_profile_id` |

**Response:** Full MediaKit object with:
- Profile info (username, bio, verified status)
- Follower metrics (count, growth rates)
- Engagement metrics (avg likes, comments, ER)
- Audience data (credibility, demographics, geography)

### 3. Autocomplete
**Endpoint:** `GET /media-kit-auto-complete`

**Purpose:** Quick username suggestions.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| search | string | Partial username |

## Data Extraction

### Required Metrics
Extract from MediaKit detail response:

| Metric | API Field | Notes |
|--------|-----------|-------|
| Credibility | `audience_data.followers.audience_credibility_percentage` | 0-100 scale |
| Engagement Rate | `avg_engagement_rate` | Decimal (0.035 = 3.5%) |
| 6M Growth | `followers_last_6_month_evolution` | Decimal (-0.1 = -10%) |
| Followers | `followers` | Integer count |
| Avg Likes | `avg_likes` | Integer |
| Avg Comments | `avg_comments` | Integer |

### Audience Demographics
| Metric | API Field | Format |
|--------|-----------|--------|
| Gender | `audience_data.followers.genders` | `{"male": 45, "female": 55}` |
| Age | `audience_data.followers.average_age` | Array of objects |
| Geography | `audience_data.followers.location_by_country` | Array of objects |

**Age Distribution Format:**
```json
[
  {"range": "13-17", "percentage": 5},
  {"range": "18-24", "percentage": 30},
  {"range": "25-34", "percentage": 40}
]
```

**Geography Format:**
```json
[
  {"code": "ES", "percentage": 65},
  {"code": "MX", "percentage": 10}
]
```

## Error Handling

### HTTP Status Codes
| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 404 | Not found | Skip influencer |
| 422 | Validation error | Log and skip |
| 429 | Rate limited | Exponential backoff |
| 500 | Server error | Retry with backoff |

### Retry Strategy
```python
max_retries = 3
base_delay = 1  # seconds

for attempt in range(max_retries):
    try:
        response = await make_request()
        break
    except RateLimitError:
        delay = base_delay * (2 ** attempt)
        await asyncio.sleep(delay)
```

## Rate Limits
- Observed limits: ~100 requests/minute (estimated)
- Implement request queuing for batch operations
- Cache aggressively to reduce API calls

## Caching Strategy
| Data Type | TTL | Storage |
|-----------|-----|---------|
| Search results | 15 min | Memory/Redis |
| Influencer detail | 24 hours | PostgreSQL |
| Static data | 7 days | PostgreSQL |

## Platform Type Reference
| ID | Platform |
|----|----------|
| 1 | Instagram |
| 2 | TikTok |
| 3 | YouTube |
| 4 | Facebook |
| 5 | Pinterest |
| 6 | LinkedIn |

## Learnings & Edge Cases

### Discovered Issues
1. `external_social_profile_id` may be null for some profiles - use username as fallback
2. Audience data may be incomplete for smaller accounts
3. Growth rate can be null if insufficient history

### Workarounds
- Always null-check optional fields
- Provide sensible defaults (0 for metrics, {} for objects)
- Filter out profiles with insufficient data rather than failing

---

## Implementation Reference

### PrimeTag Client
**File:** `backend/app/services/primetag_client.py`

### Key Methods
```python
from app.services.primetag_client import PrimeTagClient

client = PrimeTagClient()

# Search for influencers
results = await client.search_media_kits(
    search_query="home decor",
    platform_type=1,  # Instagram
    limit=50
)

# Get detailed metrics
detail = await client.get_media_kit_detail(
    username_encrypted="encrypted_id",
    platform_type=1
)

# Extract normalized metrics
metrics = client.extract_metrics(detail)
```

### Error Handling
The client raises `PrimeTagAPIError` (from `app.core.exceptions`) for:
- Non-200 status codes
- Request timeouts (30s default)
- Network failures

```python
from app.core.exceptions import PrimeTagAPIError

try:
    results = await client.search_media_kits(keyword)
except PrimeTagAPIError as e:
    logger.error(f"PrimeTag API error: {e.message}")
    # Fallback to cached data or return partial results
```

### Extracted Metrics Schema
The `extract_metrics()` method returns a normalized dict:
```python
{
    "credibility_score": float | None,
    "engagement_rate": float | None,
    "follower_growth_rate_6m": float | None,
    "follower_count": int | None,
    "avg_likes": int | None,
    "avg_comments": int | None,
    "avg_views": int | None,
    "audience_genders": dict,         # {"male": 45, "female": 55}
    "audience_age_distribution": dict, # {"18-24": 30, "25-34": 40}
    "audience_geography": dict,        # {"ES": 70, "MX": 10}
    "display_name": str | None,
    "bio": str | None,
    "profile_picture_url": str | None,
    "profile_url": str | None,
    "is_verified": bool,
}
```

### Pydantic Schemas
**File:** `backend/app/schemas/primetag.py`

- `MediaKitSummary` - Search result item
- `MediaKit` - Full detail response
- `AudienceData` - Nested audience metrics
- `FollowersData` - Gender, age, geography breakdown
