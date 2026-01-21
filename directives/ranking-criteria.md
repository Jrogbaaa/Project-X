# Ranking Criteria Directive

## Goal
Rank influencer candidates using a transparent, multi-factor scoring system.

## Ranking Formula

```
relevance_score = Σ(weight_i × score_i)
```

Where scores are normalized to 0-1 scale.

## Score Components

### 1. Credibility Score (Default Weight: 0.25)
**Source:** `audience_credibility_percentage` from PrimeTag

**Normalization:**
```
credibility_normalized = credibility_score / 100
```

**Interpretation:**
- 90-100%: Excellent, highly authentic audience
- 80-89%: Good, mostly real followers
- 70-79%: Acceptable, some fake/inactive followers
- Below 70%: Filtered out by default

### 2. Engagement Score (Default Weight: 0.30)
**Source:** `avg_engagement_rate` from PrimeTag

**Normalization:**
```
engagement_normalized = min(engagement_rate / 0.15, 1.0)
```

Typical ranges:
- Micro (10K-100K): 3-6% ER is good
- Mid (100K-500K): 2-4% ER is good
- Macro (500K+): 1-2% ER is good

Cap at 15% to prevent outliers from dominating.

### 3. Audience Match Score (Default Weight: 0.25)
**Source:** `audience_genders`, `audience_age_distribution`

**Calculation:**
```python
if target_audience_gender == "female":
    gender_score = female_pct / 100
elif target_audience_gender == "male":
    gender_score = male_pct / 100
else:
    gender_score = 0.5

if target_age_ranges:
    age_overlap = sum(age_distribution[range] for range in target_age_ranges) / 100
    audience_match = (gender_score + age_overlap) / 2
else:
    audience_match = gender_score
```

### 4. Growth Score (Default Weight: 0.10)
**Source:** `followers_last_6_month_evolution`

**Normalization:**
```
# Typical range: -20% to +50%
growth_normalized = clamp((growth_rate + 20) / 70, 0, 1)
```

**Interpretation:**
- Positive growth indicates rising influence
- Negative growth may indicate declining relevance
- Neutral score (0.5) for 0% growth

### 5. Geography Score (Default Weight: 0.10)
**Source:** `audience_geography.ES`

**Normalization:**
```
geography_normalized = spain_audience_pct / 100
```

**Note:** Spain focus is default for this platform. Adjust for other markets.

## Weight Presets

### Balanced (Default)
```json
{
  "credibility": 0.25,
  "engagement": 0.30,
  "audience_match": 0.25,
  "growth": 0.10,
  "geography": 0.10
}
```

### Engagement Focus
For viral campaigns, brand awareness:
```json
{
  "credibility": 0.15,
  "engagement": 0.50,
  "audience_match": 0.20,
  "growth": 0.10,
  "geography": 0.05
}
```

### Quality First
For premium brands, long-term partnerships:
```json
{
  "credibility": 0.40,
  "engagement": 0.20,
  "audience_match": 0.30,
  "growth": 0.05,
  "geography": 0.05
}
```

### Growth Oriented
For emerging brands, trend-setting:
```json
{
  "credibility": 0.15,
  "engagement": 0.25,
  "audience_match": 0.20,
  "growth": 0.35,
  "geography": 0.05
}
```

### Local Reach
For local businesses, regional campaigns:
```json
{
  "credibility": 0.20,
  "engagement": 0.20,
  "audience_match": 0.20,
  "growth": 0.10,
  "geography": 0.30
}
```

## LLM Weight Adjustment

The LLM query parser may suggest weight adjustments based on brand context:

| Brand Category | Suggested Adjustment |
|----------------|---------------------|
| Fashion/Beauty | +0.10 engagement |
| B2B/Professional | +0.10 credibility |
| Local Business | +0.15 geography |
| Startup/Emerging | +0.15 growth |
| Home/Furniture | +0.10 audience_match |

## Transparency

For each ranked result, provide:
- Overall relevance score
- Individual score components
- Weights used
- Reasoning (from LLM if applicable)

This allows agents to understand WHY an influencer ranked where they did.
