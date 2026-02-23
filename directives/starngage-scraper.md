# Starngage Scraper Directive

## Overview

Scrapes the Starngage Instagram ranking for Spain to get an updated list of influencers with their follower counts, engagement rates, and topic/genre data. This is the primary source of genre data for the influencer database — Starngage provides far better genre/topic classification than Instagram's own API.

## When to Run

- **Periodic refresh**: Run monthly or when you need updated follower counts and rankings.
- **After initial setup**: Run once to populate the base influencer list before PrimeTag enrichment.

## Process (Interactive via Cursor + Playwright MCP)

This is an interactive process run from Cursor. Cloudflare blocks automated HTTP requests, so we use the Playwright MCP browser with manual login.

### Step 1: User logs into Starngage

Navigate to the ranking page in the Playwright browser:

```
browser_navigate → https://starngage.com/plus/en-us/influencer/ranking/instagram/spain?page=1
```

The user solves any Cloudflare challenge and/or logs into their Starngage account in the Chromium window. Once the ranking table is visible, we're ready.

### Step 2: Extract data in batches via fetch()

Use `browser_evaluate` with an async JS function that fetches 10 pages at a time using the browser's `fetch()` API. This reuses the authenticated session cookies without visually navigating the page.

**Batch extraction function** (fetch pages N to N+9):

```javascript
async () => {
  const allData = [];
  let hitThreshold = false;
  for (let page = START; page <= END; page++) {
    const resp = await fetch(`/plus/en-us/influencer/ranking/instagram/spain?page=${page}`);
    const html = await resp.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const rows = doc.querySelectorAll('table tbody tr');
    if (rows.length === 0) { hitThreshold = true; break; }
    rows.forEach(row => {
      const cells = row.querySelectorAll('td');
      const nameCell = cells[1];
      const handleLink = nameCell ? nameCell.querySelector('a') : null;
      const handle = handleLink ? handleLink.textContent.trim() : '';
      const nameContainer = nameCell ? nameCell.querySelector('div > div:last-child') : null;
      let name = '';
      if (nameContainer) {
        const firstDiv = nameContainer.querySelector('div:first-child');
        name = firstDiv ? firstDiv.textContent.trim() : '';
      }
      const topicCell = cells[5];
      const topics = topicCell ? Array.from(topicCell.querySelectorAll('a')).map(e => e.textContent.trim()).filter(t => t) : [];
      allData.push({
        rank: cells[0] ? cells[0].textContent.trim() : '',
        name, handle,
        followers: cells[2] ? cells[2].textContent.trim() : '',
        er: cells[3] ? cells[3].textContent.trim() : '',
        topics: topics.join(', ')
      });
    });
    const lastFollowers = allData[allData.length - 1]?.followers || '';
    if (lastFollowers.includes('K')) {
      const num = parseFloat(lastFollowers.replace('K',''));
      if (num < 100) { hitThreshold = true; break; }
    }
  }
  return JSON.stringify({ total: allData.length, lastPage: hitThreshold ? 'threshold_reached' : 'page_END',
    firstRank: allData[0]?.rank, lastRank: allData[allData.length-1]?.rank,
    lastFollowers: allData[allData.length-1]?.followers, data: allData });
}
```

Run in batches of 10 pages:
- Pages 1-10 (ranks 1-1000)
- Pages 11-20 (ranks 1001-2000)
- Pages 21-30 (ranks 2001-3000)
- Pages 31-40 (ranks 3001-4000)
- Pages 41-47 (ranks 4001-4700, threshold hit)

Each batch returns a JSON string with metadata (`total`, `lastRank`, `lastFollowers`) plus all influencer data. Check `lastFollowers` after each batch — stop when it drops below 100K.

### Step 3: Combine batches and write CSV

Use a Python script (via Shell) to:
1. Read each batch's JSON output from the agent-tools files
2. Combine all batches
3. Filter out anyone below 100K followers
4. Write to `starngage_spain_influencers_{year}.csv`

## Output

CSV file at project root: `starngage_spain_influencers_{year}.csv`

| Column | Example | Description |
|--------|---------|-------------|
| rank | 1 | Starngage ranking position |
| name | Rosalía | Display name |
| handle | @rosalia.vt | Instagram handle with @ prefix |
| followers | 25.4M | Follower count (K/M suffix) |
| er | 2.61% | Engagement rate |
| topics | Entertainment and Music, Celebrity | Starngage genre/topic tags (comma-separated) |

## Data Volume (February 2026)

- **~47 pages** to reach the 100K follower threshold
- **~4,639 influencers** with 100K+ followers in Spain
- Takes ~2-3 minutes across 5 batch calls

## Key Technical Details

- **Why fetch() works**: `fetch()` inside `browser_evaluate` makes HTTP requests using the browser's existing session cookies (including `cf_clearance`). No visible navigation occurs.
- **Why plain HTTP doesn't work**: Cloudflare ties `cf_clearance` to the browser's TLS fingerprint. `httpx`/`requests`/`curl` have different fingerprints and get blocked even with valid cookies.
- **DOM parsing**: Uses `DOMParser` in-browser to parse the fetched HTML, then `querySelectorAll` to extract table rows. No external libraries needed.
- **100 influencers per page**: Each page has exactly 100 rows.

## Integration with Enrichment Pipeline

The Starngage CSV is the starting point for the enrichment pipeline:

```
Starngage scrape (this directive)
  → Import to DB (import_influencers.py)
    → Keyword niche detection (keyword_niche_detector.py)
      → LLM niche enrichment (llm_niche_enrichment.py)
        → PrimeTag enrichment (cache_service.py)
```

The `topics` column from Starngage maps to the `interests` field in the database and is used for niche matching when `primary_niche` is not set.

## Edge Cases & Learnings

- **Cloudflare detection**: Bot detection triggers on direct page navigation more than on fetch() from an already-authenticated page. Once logged in, the in-browser fetch approach is reliable.
- **Follower counts use K/M suffixes**: 209.6K = 209,600. Parse accordingly.
- **Some names contain emojis/unicode**: CSV must use UTF-8 encoding.
- **Topic tags are `<a>` links**: Extracted from anchor tags inside the topics cell (column index 5), not plain text.
- **Empty topics**: Some influencers have no topic tags — these appear as empty strings.
- **Page 47 boundary**: At 100K threshold, the cutoff typically falls mid-page. Include all above threshold, stop at first below.
- **Session expiry**: If the browser session expires mid-scrape, navigate to any Starngage page again to refresh, then continue with `--start-page`.
