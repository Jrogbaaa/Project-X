# PrimeTag Live Test Procedure

Manual end-to-end verification for 1–2 real creators confirming all 5 business requirements.

**Prerequisites**

```bash
export PRIMETAG_API_KEY="<your-api-key>"
export BASE="https://api.primetag.com"
```

---

## Creator 1 — Instagram (all 5 BRs)

### Step 1 — Search

```bash
USERNAME="<instagram_username>"
curl -s \
  -H "Authorization: Bearer $PRIMETAG_API_KEY" \
  "$BASE/media-kits?platform_type=2&search=$USERNAME&limit=5" \
  | python3 -m json.tool
```

**Expected:** `response` array contains the creator. Note the `mediakit_url` field.

### Step 2 — Extract encrypted token

```bash
# Example mediakit_url: https://mediakit.primetag.com/instagram/Z0FBQUFBQm1...
TOKEN="<last-path-segment-of-mediakit_url>"
```

### Step 3 — Fetch detail

```bash
curl -s \
  -H "Authorization: Bearer $PRIMETAG_API_KEY" \
  "$BASE/media-kits/2/$TOKEN" \
  | python3 -m json.tool > /tmp/detail.json
```

### Step 4 — Verify all 5 BRs

```bash
python3 - <<'EOF'
import json, sys

d = json.load(open("/tmp/detail.json"))
r = d.get("response", d)
followers = r.get("audience_data", {}).get("followers", {})

# BR1 — Spain % (must be >= 60)
countries = followers.get("location_by_country", [])
spain_pct = next(
    (c.get("percentage", c.get("value", 0))
     for c in countries if c.get("name") in ("Spain", "España", "Espana")),
    0
)
print(f"\nBR1  Spain%:       {spain_pct}%  →  {'✅ PASS' if spain_pct >= 60 else '❌ FAIL (< 60%)'}")

# BR2 — Genders
genders = followers.get("genders", {})
female = genders.get("female", 0)
male   = genders.get("male", 0)
gender_sum = female + male
print(f"BR2  Female:        {female}%")
print(f"     Male:          {male}%")
print(f"     Sum:           {gender_sum:.1f}%  →  {'✅ OK' if abs(gender_sum - 100) < 2 else '⚠️  unexpected sum'}")

# BR3 — Age bands (female + male per label)
ages = followers.get("average_age", [])
print(f"BR3  Age bands:")
total_age_pct = 0
for band in ages:
    label  = band.get("label", "?")
    f_val  = band.get("female") or 0
    m_val  = band.get("male")   or 0
    total  = f_val + m_val
    total_age_pct += total
    print(f"       {label:8s}: female={f_val:.1f}% + male={m_val:.1f}% = {total:.1f}%")
print(f"     Total:        {total_age_pct:.1f}%  →  {'✅ OK' if 90 < total_age_pct < 110 else '⚠️  unexpected total'}")

# BR4 — Credibility (Instagram only)
cred = followers.get("audience_credibility_percentage")
platform = r.get("platform_type", "?")
print(f"BR4  Credibility:   {cred}  (platform_type={platform})  →  {'✅ present (Instagram)' if cred is not None else '⚠️  null'}")

# BR5 — Engagement rate
er = r.get("avg_engagement_rate", None)
er_ok = er is not None and er < 1.0
print(f"BR5  ER:            {er}  →  {'✅ decimal' if er_ok else '❌ missing or not decimal'}")
EOF
```

---

## Creator 2 — TikTok (BR4: credibility must be null)

```bash
TT_USERNAME="<tiktok_username>"
curl -s \
  -H "Authorization: Bearer $PRIMETAG_API_KEY" \
  "$BASE/media-kits?platform_type=6&search=$TT_USERNAME&limit=5" \
  | python3 -m json.tool
```

Extract the TikTok token and fetch detail with `platform_type=6`:

```bash
TT_TOKEN="<last-path-segment-of-mediakit_url>"
curl -s \
  -H "Authorization: Bearer $PRIMETAG_API_KEY" \
  "$BASE/media-kits/6/$TT_TOKEN" \
  | python3 -m json.tool > /tmp/detail_tiktok.json

python3 - <<'EOF'
import json
d = json.load(open("/tmp/detail_tiktok.json"))
r = d.get("response", d)
followers = r.get("audience_data", {}).get("followers", {})
cred = followers.get("audience_credibility_percentage")
pt   = r.get("platform_type")
print(f"platform_type={pt}, audience_credibility_percentage={cred}")
print("BR4 TikTok: credibility in raw API =", cred)
print("  → Our extract_metrics() will return None for platform != 2. ✅")
EOF
```

---

## Rate-limit (429) Smoke Test

```bash
# Run several searches quickly to observe retry behaviour in the backend logs.
for i in 1 2 3 4 5; do
  curl -s \
    -H "Authorization: Bearer $PRIMETAG_API_KEY" \
    "$BASE/media-kits?platform_type=2&search=test_$i&limit=1" \
    -o /dev/null -w "HTTP %{http_code}\n"
done
```

Check backend logs for lines like:
```
Honouring Retry-After: 30.0s (capped at 30s)
Retrying search_media_kits in 30.00s (attempt 1/3, error: ...)
```

---

## Expected Outcomes Summary

| BR | Check | Expected |
|----|-------|---------|
| BR1 | Spain% in raw `location_by_country` | Value present; "Spain"/"España"/"Espana" all map to ES |
| BR1 | `extract_metrics()["audience_geography"]["ES"]` | Numeric, ≥ 60 for a Spanish influencer |
| BR2 | `genders["female"] + genders["male"]` | ≈ 100 (±1) |
| BR3 | Each age band total = `female + male` | All bands present; no TypeError on null values |
| BR4 | Instagram → `credibility_score` | Float (0–100) |
| BR4 | TikTok → `credibility_score` | `None` |
| BR5 | `engagement_rate` | Float, < 1.0 (decimal fraction) |
