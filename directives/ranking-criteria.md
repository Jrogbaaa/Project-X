# Ranking Criteria Directive

## Goal
Rank influencer candidates using a transparent, multi-factor scoring system that considers brand affinity, creative fit, and content niche alignment in addition to standard metrics.

## Ranking Formula

```
relevance_score = Σ(weight_i × score_i) × size_multiplier
```

Where scores are normalized to 0-1 scale, and size_multiplier adjusts for follower count preferences.

## Score Components (8 Factors)

### Original 5 Factors

### 1. Credibility Score (Default Weight: 0.15)
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

### 2. Engagement Score (Default Weight: 0.20)
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

### 3. Audience Match Score (Default Weight: 0.15)
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

### 4. Growth Score (Default Weight: 0.05)
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

---

### New Brand/Creative Factors

### 6. Brand Affinity Score (Default Weight: 0.15)
**Source:** Audience overlap data (if available) or `brand_mentions` as fallback

**Purpose:** Measures how well an influencer's audience aligns with the target brand's followers.

**Calculation:**
```python
if audience_overlap_available:
    # Audience overlap percentage with brand followers
    # 50%+ overlap is exceptional, maps to 1.0
    brand_affinity = min(overlap_pct / 0.50, 1.0)
elif brand in influencer.brand_mentions:
    # Prior relationship with brand
    brand_affinity = 0.75
else:
    # No data available
    brand_affinity = 0.5  # Neutral
```

**Note:** Returns 0.5 (neutral) if no brand context provided in query.

#### Brand Conflict Detection (NEW)

Brand affinity scoring now includes **conflict detection** to penalize influencers with competitor associations.

**Conflict Types:**

| Type | Detection | Penalty | Score Range |
|------|-----------|---------|-------------|
| **Competitor Ambassador** | Username in `brand_intelligence.yaml` ambassador list for competitor | 95% penalty | 0.05 |
| **High Severity Mention** | `brand_mentions` contains competitor handle (sports/fashion) | 75% penalty | 0.25 |
| **Medium Severity Mention** | `brand_mentions` contains competitor (retail/food) | 65% penalty | 0.35 |
| **Low Severity Mention** | `brand_mentions` contains competitor (other) | 55% penalty | 0.45 |

**Example: Nike Campaign**

| Influencer | brand_mentions | Ambassador Status | Affinity Score |
|------------|---------------|-------------------|----------------|
| @cristiano | ["nike"] | Nike Ambassador | **0.75** (boost) |
| @leomessi | ["adidas"] | Adidas Ambassador | **0.05** (conflict!) |
| @padel_star | [] | None | 0.50 (neutral) |
| @fitness_guru | ["puma", "reebok"] | None | **0.25** (competitor) |

**Saturation Detection:**

When an influencer is already an ambassador for the target brand (not a competitor), they receive a "saturation warning" instead of a conflict penalty:

| Relationship | Score | Warning |
|--------------|-------|---------|
| Lifetime deal | 0.35 | "Already Adidas ambassador (too obvious)" |
| Ambassador | 0.40 | "Already Adidas ambassador since 2023" |
| Sponsored | 0.45 | "Previously sponsored by Adidas" |

This helps find **fresh talent** rather than the brand's existing, obvious partners.

**Data Source:** `/backend/app/data/brand_intelligence.yaml`

### 7. Creative Fit Score (Default Weight: 0.15)
**Source:** `interests`, `bio`, `brand_mentions`

**Purpose:** Measures alignment between influencer's content style and the campaign creative concept.

**Calculation combines three signals:**

1. **Theme Alignment (40%)** - Do influencer's interests/bio match creative themes?
2. **Tone Alignment (30%)** - Does content style match creative tone (authentic, luxury, humorous, etc.)?
3. **Experience Score (30%)** - Has influencer done brand campaigns before?

```python
# Theme matching
theme_score = matches_found / total_themes

# Tone matching using keyword analysis
tone_keywords = {
    'authentic': ['real', 'genuine', 'honest', 'raw'],
    'luxury': ['premium', 'exclusive', 'elegant'],
    'humorous': ['funny', 'comedy', 'laugh'],
    'documentary': ['story', 'journey', 'behind'],
    # ... etc
}
tone_score = tones_matched / total_tones

# Experience
experience_score = 0.7 if has_brand_mentions else 0.5

creative_fit = (theme_score * 0.4) + (tone_score * 0.3) + (experience_score * 0.3)
```

**Note:** Returns 0.5 (neutral) if no creative concept provided in query.

### 8. Niche Match Score (Default Weight: 0.05)
**Source:** `interests`, `bio`, niche taxonomy

**Purpose:** Ensures influencer's content niche aligns with campaign topics, and penalizes irrelevant niches.

#### Enhanced Niche Taxonomy (NEW - The Messi/Padel Solution)

When a `campaign_niche` is specified (e.g., "padel"), the system uses a niche taxonomy to detect:
1. **Exact matches** - Influencer IS in the campaign niche
2. **Related niches** - Adjacent/similar niches (tennis for padel)
3. **Conflicting niches** - Wrong niche entirely (football for padel)

**Score Ranges:**

| Match Type | Score | Example |
|------------|-------|---------|
| Exact match | 0.95 | Padel player for padel campaign |
| Related niche | 0.70 | Tennis player for padel campaign |
| No clear niche | 0.50 | Generic lifestyle influencer |
| Conflicting niche | 0.20 | Football player for padel campaign |
| Celebrity mismatch | 0.15 | Mega-celebrity (>5M followers) in wrong niche |

**Example: Adidas Padel Campaign**

| Influencer | Niche | Followers | Niche Score | Why |
|------------|-------|-----------|-------------|-----|
| @alegalan96 | padel | 743K | **0.95** | Exact match - actual padel player |
| @tenisplayer | tennis | 500K | **0.70** | Related niche - racket sport |
| @lifestyle_spain | lifestyle | 200K | 0.50 | Neutral - no specific niche |
| @leomessi | football | 500M | **0.15** | Conflicting niche + celebrity penalty |

**This solves the Messi/Padel problem:** Even though Messi is an Adidas ambassador, he scores poorly for a **padel** campaign because:
1. His niche (football) conflicts with the campaign niche (padel)
2. He's a mega-celebrity (>5M followers) with no niche match

**Data Source:** `/backend/app/data/niche_taxonomy.yaml`

**Fallback Calculation (when no campaign_niche specified):**
```python
# Positive matching for campaign_topics
topic_matches = count matches in interests/bio
topic_score = 0.5 + (topic_matches / total_topics * 0.5)  # 0.5 to 1.0

# Penalty for excluded niches
if any exclude_niche in interests/bio:
    penalty = exclusions / total_excludes * 0.4
    score = max(0.1, topic_score - penalty)
```

---

## Size Penalty (Anti-Celebrity Bias)

When `preferred_follower_min` and/or `preferred_follower_max` are specified, a multiplier adjusts the final score:

```python
if min_followers <= follower_count <= max_followers:
    multiplier = 1.0  # Perfect range
elif follower_count < min_followers:
    multiplier = max(0.5, follower_count / min_followers)
else:  # Too large (anti-celebrity)
    multiplier = max(0.3, max_followers / follower_count)

final_score = relevance_score * multiplier
```

**Purpose:** Prevents mega-celebrities from dominating results when mid-tier influencers are preferred.

## Weight Presets

### Balanced (Default)
Standard weights for general searches:
```json
{
  "credibility": 0.15,
  "engagement": 0.20,
  "audience_match": 0.15,
  "growth": 0.05,
  "geography": 0.10,
  "brand_affinity": 0.15,
  "creative_fit": 0.15,
  "niche_match": 0.05
}
```

### Brand Campaign Focus
When brand affinity data is available and important:
```json
{
  "credibility": 0.10,
  "engagement": 0.15,
  "audience_match": 0.10,
  "growth": 0.05,
  "geography": 0.10,
  "brand_affinity": 0.25,
  "creative_fit": 0.15,
  "niche_match": 0.10
}
```

### Creative-Driven
For campaigns where creative fit is paramount:
```json
{
  "credibility": 0.10,
  "engagement": 0.15,
  "audience_match": 0.10,
  "growth": 0.05,
  "geography": 0.10,
  "brand_affinity": 0.15,
  "creative_fit": 0.25,
  "niche_match": 0.10
}
```

### Niche Specialist
For highly targeted niche campaigns:
```json
{
  "credibility": 0.15,
  "engagement": 0.20,
  "audience_match": 0.10,
  "growth": 0.05,
  "geography": 0.10,
  "brand_affinity": 0.10,
  "creative_fit": 0.10,
  "niche_match": 0.20
}
```

### Engagement Focus
For viral campaigns, brand awareness:
```json
{
  "credibility": 0.10,
  "engagement": 0.35,
  "audience_match": 0.15,
  "growth": 0.10,
  "geography": 0.05,
  "brand_affinity": 0.10,
  "creative_fit": 0.10,
  "niche_match": 0.05
}
```

### Quality First
For premium brands, long-term partnerships:
```json
{
  "credibility": 0.25,
  "engagement": 0.15,
  "audience_match": 0.20,
  "growth": 0.05,
  "geography": 0.05,
  "brand_affinity": 0.15,
  "creative_fit": 0.10,
  "niche_match": 0.05
}
```

### Local Reach
For local businesses, regional campaigns:
```json
{
  "credibility": 0.15,
  "engagement": 0.15,
  "audience_match": 0.15,
  "growth": 0.05,
  "geography": 0.25,
  "brand_affinity": 0.10,
  "creative_fit": 0.10,
  "niche_match": 0.05
}
```

## LLM Weight Adjustment

The LLM query parser suggests weight adjustments based on context:

| Context | Suggested Adjustment |
|---------|---------------------|
| Brand handle provided | +0.10 brand_affinity |
| Creative concept provided | +0.10 creative_fit |
| Specific niche/topics | +0.10 niche_match |
| Fashion/Beauty brands | +0.10 engagement |
| B2B/Professional brands | +0.10 credibility |
| Local Business | +0.15 geography |
| Size preference specified | Apply size_multiplier |

## Transparency

For each ranked result, provide:
- Overall relevance score
- Individual score components (all 8 factors)
- Weights used
- Size multiplier (if applied)
- Reasoning (from LLM if applicable)

This allows agents to understand WHY an influencer ranked where they did.

## Example Scoring

Query: "Find 5 Spanish influencers for Adidas padel campaign. Documentary style, focus on dedication."

| Factor | Weight | Score | Weighted |
|--------|--------|-------|----------|
| Credibility | 0.15 | 0.85 | 0.128 |
| Engagement | 0.20 | 0.70 | 0.140 |
| Audience Match | 0.15 | 0.60 | 0.090 |
| Growth | 0.05 | 0.55 | 0.028 |
| Geography | 0.10 | 0.80 | 0.080 |
| **Brand Affinity** | 0.15 | 0.45 | 0.068 |
| **Creative Fit** | 0.15 | 0.75 | 0.113 |
| **Niche Match** | 0.05 | 0.90 | 0.045 |
| **Total** | 1.00 | - | **0.692** |

With size multiplier (if influencer has 50M followers but preferred max is 5M):
- Size multiplier: 0.10 (5M/50M)
- Final score: 0.692 × 0.10 = **0.069**

This correctly deprioritizes mega-celebrities for niche campaigns.
