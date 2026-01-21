# Influencer Discovery API Documentation

Base URL: `http://localhost:8000`

## Authentication

Currently no authentication required for local development.

---

## Endpoints

### Search

#### Execute Search
`POST /search/`

Execute an influencer search using natural language query.

**Request Body:**
```json
{
  "query": "5 female influencers for IKEA",
  "filters": {
    "min_credibility_score": 70.0,
    "min_engagement_rate": null,
    "min_spain_audience_pct": 60.0,
    "min_follower_growth_rate": null
  },
  "ranking_weights": {
    "credibility": 0.25,
    "engagement": 0.30,
    "audience_match": 0.25,
    "growth": 0.10,
    "geography": 0.10
  }
}
```

**Response:**
```json
{
  "search_id": "uuid-string",
  "query": "5 female influencers for IKEA",
  "parsed_query": {
    "target_count": 5,
    "influencer_gender": "female",
    "target_audience_gender": null,
    "brand_name": "IKEA",
    "brand_category": "home_furniture",
    "content_themes": ["home", "decor", "interior"],
    "keywords": ["home", "decor", "lifestyle"],
    "min_credibility": 70.0,
    "min_spain_audience": 60.0,
    "parsing_confidence": 0.95
  },
  "filters_applied": {
    "min_credibility_score": 70.0,
    "min_engagement_rate": null,
    "min_spain_audience_pct": 60.0
  },
  "results": [
    {
      "influencer_id": "uuid-string",
      "username": "influencer_handle",
      "rank_position": 1,
      "relevance_score": 0.85,
      "scores": {
        "credibility": 0.92,
        "engagement": 0.78,
        "audience_match": 0.85,
        "growth": 0.65,
        "geography": 0.80
      },
      "raw_data": {
        "id": "uuid-string",
        "username": "influencer_handle",
        "display_name": "Display Name",
        "profile_picture_url": "https://...",
        "bio": "Bio text",
        "is_verified": true,
        "follower_count": 150000,
        "credibility_score": 92.0,
        "engagement_rate": 0.035,
        "follower_growth_rate_6m": 0.15,
        "avg_likes": 5000,
        "avg_comments": 150,
        "audience_genders": {"male": 35, "female": 65},
        "audience_age_distribution": {"18-24": 25, "25-34": 45},
        "audience_geography": {"ES": 70, "MX": 10}
      }
    }
  ],
  "total_candidates": 50,
  "total_after_filter": 15,
  "executed_at": "2025-01-20T12:00:00Z"
}
```

---

#### Get Search
`GET /search/{search_id}`

Retrieve a previous search by ID with full results.

**Path Parameters:**
- `search_id` (UUID, required): The search ID

**Response:** Same as Execute Search response

---

#### Save Search
`POST /search/{search_id}/save`

Save a search for later reference.

**Path Parameters:**
- `search_id` (UUID, required): The search ID

**Request Body:**
```json
{
  "name": "IKEA Campaign Q1",
  "description": "Influencers for IKEA home campaign"
}
```

**Response:**
```json
{
  "id": "uuid-string",
  "name": "IKEA Campaign Q1",
  "description": "Influencers for IKEA home campaign",
  "raw_query": "5 female influencers for IKEA",
  "parsed_query": {...},
  "result_count": 5,
  "created_at": "2025-01-20T12:00:00Z",
  "updated_at": "2025-01-20T12:00:00Z"
}
```

---

#### List Saved Searches
`GET /search/saved/list`

Get all saved searches.

**Query Parameters:**
- `limit` (int, optional, default=50, max=100): Maximum results

**Response:**
```json
[
  {
    "id": "uuid-string",
    "name": "IKEA Campaign Q1",
    "description": "...",
    "raw_query": "...",
    "parsed_query": {...},
    "result_count": 5,
    "created_at": "2025-01-20T12:00:00Z",
    "updated_at": "2025-01-20T12:00:00Z"
  }
]
```

---

#### List Search History
`GET /search/history/list`

Get recent search history.

**Query Parameters:**
- `limit` (int, optional, default=50, max=100): Maximum results

**Response:**
```json
[
  {
    "id": "uuid-string",
    "raw_query": "5 female influencers for IKEA",
    "result_count": 5,
    "is_saved": false,
    "saved_name": null,
    "executed_at": "2025-01-20T12:00:00Z"
  }
]
```

---

### Influencers

#### Get Influencer
`GET /influencers/{influencer_id}`

Get detailed information about a cached influencer.

**Path Parameters:**
- `influencer_id` (UUID, required): The influencer ID

**Response:**
```json
{
  "id": "uuid-string",
  "platform_type": "instagram",
  "username": "influencer_handle",
  "display_name": "Display Name",
  "profile_picture_url": "https://...",
  "bio": "Bio text",
  "profile_url": "https://instagram.com/...",
  "is_verified": true,
  "follower_count": 150000,
  "following_count": 500,
  "post_count": 1200,
  "credibility_score": 92.0,
  "engagement_rate": 0.035,
  "follower_growth_rate_6m": 0.15,
  "avg_likes": 5000,
  "avg_comments": 150,
  "avg_views": null,
  "audience_genders": {"male": 35, "female": 65},
  "audience_age_distribution": {"18-24": 25, "25-34": 45, "35-44": 20},
  "audience_geography": {"ES": 70, "MX": 10, "AR": 5},
  "cached_at": "2025-01-20T12:00:00Z",
  "cache_expires_at": "2025-01-21T12:00:00Z"
}
```

---

### Exports

#### Export to CSV
`GET /exports/{search_id}/csv`

Download search results as CSV file.

**Path Parameters:**
- `search_id` (UUID, required): The search ID

**Response:** CSV file download

**Headers:**
- `Content-Type: text/csv`
- `Content-Disposition: attachment; filename=influencers_{search_id}.csv`

---

#### Export to Excel
`GET /exports/{search_id}/excel`

Download search results as Excel file.

**Path Parameters:**
- `search_id` (UUID, required): The search ID

**Response:** Excel file download

**Headers:**
- `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- `Content-Disposition: attachment; filename=influencers_{search_id}.xlsx`

---

### Health

#### Health Check
`GET /health`

Basic health check.

**Response:**
```json
{
  "status": "healthy"
}
```

---

#### Readiness Check
`GET /health/ready`

Readiness check including database connectivity.

**Response:**
```json
{
  "status": "ready",
  "database": "connected",
  "debug": true
}
```

---

## Error Responses

All endpoints return errors in the following format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `404` - Resource not found
- `422` - Validation error (invalid request body)
- `500` - Internal server error

---

## Data Models

### FilterConfig
```typescript
{
  min_credibility_score?: number;  // 0-100, default 70
  min_engagement_rate?: number;    // 0-1, e.g., 0.03 = 3%
  min_spain_audience_pct?: number; // 0-100, default 60
  min_follower_growth_rate?: number; // -1 to 1, e.g., 0.1 = 10%
}
```

### RankingWeights
```typescript
{
  credibility: number;    // default 0.25
  engagement: number;     // default 0.30
  audience_match: number; // default 0.25
  growth: number;         // default 0.10
  geography: number;      // default 0.10
}
// Note: All weights must sum to 1.0
```

### ParsedSearchQuery
```typescript
{
  target_count: number;           // Number of influencers requested
  influencer_gender?: string;     // "male", "female", or null
  target_audience_gender?: string;
  brand_name?: string;
  brand_category?: string;
  content_themes: string[];
  keywords: string[];
  min_credibility?: number;
  min_spain_audience?: number;
  suggested_weight_adjustments?: object;
  parsing_confidence: number;     // 0-1
}
```

---

## Examples

### Search for Home & Lifestyle Influencers
```bash
curl -X POST http://localhost:8000/search/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "5 female influencers for IKEA",
    "filters": {
      "min_credibility_score": 75.0
    }
  }'
```

### Search with Custom Ranking Weights
```bash
curl -X POST http://localhost:8000/search/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "10 high engagement influencers for beauty brand",
    "ranking_weights": {
      "credibility": 0.15,
      "engagement": 0.50,
      "audience_match": 0.20,
      "growth": 0.10,
      "geography": 0.05
    }
  }'
```

### Export Results
```bash
# CSV
curl -O http://localhost:8000/exports/{search_id}/csv

# Excel
curl -O http://localhost:8000/exports/{search_id}/excel
```
