# PrimeTag Media Kit API - OpenAPI Documentation

**Version:** 0.45.0
**OAS:** 3.1
**GitLab:** https://gitlab.com/primetag/backend/microservices/media-kit-microservice

## Endpoints

### GET /media-kits
Search Media Kits, returning a small summary filtered by platform type and username.

**Parameters:**
| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| platform_type | integer | query | Yes | Social Platform (1-6) |
| search | string | query | Yes | Fulltext search in username and display_name |
| limit | integer | query | No | Max results (default: 10, max: 50) |
| X-User-ID | string | header | No | User ID |
| X-Auth-User-ID | string | header | No | Auth User ID |

**Response 200:**
```json
{
  "response": [
    {
      "external_social_profile_id": "string",
      "username": "string",
      "display_name": "string",
      "avatar": "https://example.com/",
      "audience_size": 0,
      "is_verified": true,
      "platform_type": 1,
      "mediakit_url": "https://example.com/"
    }
  ],
  "metadata": {}
}
```

### GET /media-kits/settings/platforms
List current platform settings.

**Response 200:**
```json
{
  "response": [
    {
      "enabled": true,
      "name": "string",
      "platform_type": "string"
    }
  ],
  "metadata": {}
}
```

### GET /media-kits/{platform_type}/{username_encrypted}
Get all Media Kit data to fill Media Kit client page.

**Parameters:**
| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| platform_type | integer | path | Yes | Social Platform (1-6) |
| username_encrypted | string | path | Yes | Username to filter |
| empty_months_engagement_spread | boolean | query | No | Add empty months (default: false) |
| limit_posts_engagement_spread | integer | query | No | Limit posts count |
| limit_months_engagement_spread | integer | query | No | Limit months count |
| redirect_when_not_found | boolean | query | No | Redirect to social platform (default: false) |

**Response 200:** Full MediaKit object with:
- Profile info (platform_type, profile_pic, cover_photo, profile_url, fullname, is_verified, username, description, interests, location, contacts)
- Follower metrics (followers, followers_evolution, followers_last_month_evolution, followers_last_6_month_evolution)
- Engagement metrics (avg_likes, avg_comments, avg_views, avg_reels_plays, avg_shares, avg_saves, avg_reach, avg_engagements, avg_engagement_rate)
- Content (top_posts, brand_mentions, paid_posts)
- Paid metrics (paid_avg_likes, paid_avg_comments, paid_avg_engagements, paid_avg_reels_plays, paid_avg_engagement_rate, paid_followers, paid_evolution_last_month)
- Audience data (audience_data with followers/likes breakdown)
- Engagement info (engagements_info)

### GET /media-kit-auto-complete
Autocomplete search for usernames.

**Parameters:**
| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| platform_type | integer | query | No | Social Platform (1-6) |
| username_startswith | string | query | Yes | Username prefix to filter |
| limit | integer | query | No | Max results (default: 10) |

## Platform Types (Verified 2026-01-28)
| ID | Platform | Status |
|----|----------|--------|
| 1 | Facebook | Not supported |
| 2 | Instagram | **Supported** |
| 3 | Twitter | Not supported |
| 4 | Pinterest | Not supported |
| 5 | LinkedIn | Not supported |
| 6 | TikTok | **Supported** |

**Note:** Only Instagram (2) and TikTok (6) are currently supported. Other platform types return 400 error.

## Authentication (Verified 2026-01-28)
- `Authorization: Bearer {PRIMETAG_API_KEY}` header (NOT "Token")
- Optional: `X-User-ID` and `X-Auth-User-ID` headers

## Rate Limits (Observed)
- Returns 429 "Too many requests" after ~100-200 requests
- `metadata.num_requests` in error response shows request count
- Implement exponential backoff (1s, 2s, 4s... up to 30s)
- Consider request queuing to stay under limits

## Key Schemas

### MediaKitSummary (Search Result)
```json
{
  "external_social_profile_id": "string | null",
  "username": "string",
  "display_name": "string | null",
  "avatar": "string | null",
  "audience_size": "integer >= 0",
  "is_verified": "boolean | null",
  "platform_type": "integer",
  "mediakit_url": "string (uri)"
}
```

### AudienceDataSection
```json
{
  "audience_credibility_percentage": "number | null",
  "audience_credibility_label": "string | null (e.g., 'Low')",
  "audience_credibility_emoji": "string | null",
  "audience_reachability": "array | null",
  "follow_for_follow": { "percentage": "number", "label": "string" },
  "genders": { "female": "number", "male": "number" },
  "average_age": [{ "female": "number", "label": "string", "male": "number" }],
  "location_by_country": [{ "female": "number", "male": "number", "name": "string", "percentage": "number" }],
  "location_by_city": [{ "female": "number", "male": "number", "name": "string", "percentage": "number" }]
}
```

## Error Responses

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["string", 0],
      "msg": "string",
      "type": "string"
    }
  ]
}
```
