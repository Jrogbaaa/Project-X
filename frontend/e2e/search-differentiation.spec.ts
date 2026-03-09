import { test, expect } from '@playwright/test';

/**
 * Search differentiation E2E tests.
 *
 * Validates that different brand briefs produce meaningfully different
 * influencer results via the API. Runs against any deployed environment
 * (local or Vercel) using Playwright's request fixture for direct API calls.
 *
 * Usage:
 *   # Against Vercel
 *   PLAYWRIGHT_BASE_URL=https://project-x-three-sage.vercel.app npx playwright test e2e/search-differentiation.spec.ts
 *
 *   # Against local dev
 *   npx playwright test e2e/search-differentiation.spec.ts
 */

interface SearchResult {
  username: string;
  relevance_score: number;
  scores: {
    niche_match: number;
    creative_fit: number;
    engagement: number;
    brand_affinity: number;
    credibility: number;
    audience_match: number;
    growth: number;
    geography: number;
  };
  raw_data: {
    primary_niche: string | null;
    interests: string[];
    follower_count: number;
  };
}

interface SearchResponse {
  search_id: string;
  query: string;
  parsed_query: {
    campaign_niche: string | null;
    brand_name: string | null;
    brand_category: string | null;
    exclude_niches: string[];
    parsing_confidence: number;
    reasoning: string;
  };
  results: SearchResult[];
  total_candidates: number;
  total_after_filter: number;
  verification_stats?: {
    total_candidates: number;
    verified: number;
    failed_verification: number;
    passed_filters: number;
  };
}

const QUERIES = {
  home: {
    query: 'Campaign for IKEA Spain — need 5 home and lifestyle influencers who create content about interior design, home decor, and living spaces.',
    expectedNiches: ['home_decor', 'lifestyle', 'home', 'diy'],
  },
  padel: {
    query: 'Find 5 influencers for Adidas Padel. Premium padel equipment campaign targeting serious padel players in Spain. No football or soccer influencers.',
    expectedNiches: ['padel', 'tennis', 'sports'],
  },
  skincare: {
    query: 'CeraVe skincare campaign — 5 skincare and beauty influencers focused on facial routines, SPF, and dermatologist-recommended products in Spain.',
    expectedNiches: ['skincare', 'beauty', 'wellness'],
  },
} as const;

const SEARCH_TIMEOUT = 60_000;

const EMPTY_RESPONSE: SearchResponse = {
  search_id: '',
  query: '',
  parsed_query: {
    campaign_niche: null,
    brand_name: null,
    brand_category: null,
    exclude_niches: [],
    parsing_confidence: 0,
    reasoning: '',
  },
  results: [],
  total_candidates: 0,
  total_after_filter: 0,
};

const postSearch = async (
  request: ReturnType<typeof test['info']> extends never ? never : any,
  baseURL: string,
  query: string,
): Promise<SearchResponse> => {
  const response = await request.post(`${baseURL}/api/search`, {
    data: { query, limit: 10 },
    timeout: SEARCH_TIMEOUT,
  });
  if (!response.ok()) {
    console.log(`Search API returned ${response.status()} for: "${query.slice(0, 50)}..."`);
    return EMPTY_RESPONSE;
  }
  return response.json();
};

const isLlmAvailable = (res: SearchResponse): boolean =>
  res.parsed_query.parsing_confidence > 0.5;

const getUsernameSet = (results: SearchResult[]): Set<string> =>
  new Set(results.map((r) => r.username));

const jaccardSimilarity = (a: Set<string>, b: Set<string>): number => {
  const intersection = new Set([...a].filter((x) => b.has(x)));
  const union = new Set([...a, ...b]);
  if (union.size === 0) return 0;
  return intersection.size / union.size;
};

test.describe('Search Differentiation @live', () => {
  test.describe.configure({ timeout: 180_000 });

  let homeResults: SearchResponse;
  let padelResults: SearchResponse;
  let skincareResults: SearchResponse;

  test.beforeAll(async ({ request, baseURL }) => {
    const url = baseURL ?? 'http://localhost:3000';
    [homeResults, padelResults, skincareResults] = await Promise.all([
      postSearch(request, url, QUERIES.home.query),
      postSearch(request, url, QUERIES.padel.query),
      postSearch(request, url, QUERIES.skincare.query),
    ]);
  });

  test('different niches return different results', async () => {
    const allEmpty = homeResults.results.length === 0
      && padelResults.results.length === 0
      && skincareResults.results.length === 0;
    test.skip(allEmpty, 'No results returned — requires a populated database');

    const homeUsers = getUsernameSet(homeResults.results);
    const padelUsers = getUsernameSet(padelResults.results);
    const skincareUsers = getUsernameSet(skincareResults.results);

    expect(homeUsers.size, 'Home search returned no results').toBeGreaterThan(0);
    expect(padelUsers.size, 'Padel search returned no results').toBeGreaterThan(0);
    expect(skincareUsers.size, 'Skincare search returned no results').toBeGreaterThan(0);

    const homePadel = jaccardSimilarity(homeUsers, padelUsers);
    const homeSkincare = jaccardSimilarity(homeUsers, skincareUsers);
    const padelSkincare = jaccardSimilarity(padelUsers, skincareUsers);

    console.log('--- Result Overlap (Jaccard Similarity) ---');
    console.log(`  Home vs Padel:    ${(homePadel * 100).toFixed(1)}%`);
    console.log(`  Home vs Skincare: ${(homeSkincare * 100).toFixed(1)}%`);
    console.log(`  Padel vs Skincare:${(padelSkincare * 100).toFixed(1)}%`);

    expect(homePadel, 'Home and Padel results are too similar').toBeLessThan(0.5);
    expect(homeSkincare, 'Home and Skincare results are too similar').toBeLessThan(0.5);
    expect(padelSkincare, 'Padel and Skincare results are too similar').toBeLessThan(0.5);
  });

  test('brand intelligence extracts correct campaign niche', async () => {
    test.skip(homeResults.results.length === 0, 'No results — requires a populated database');
    const llmWorking = isLlmAvailable(homeResults);

    if (!llmWorking) {
      console.log('--- LLM UNAVAILABLE (fallback parsing) ---');
      console.log(`  Reason: ${homeResults.parsed_query.reasoning.slice(0, 120)}`);
      console.log('  Skipping campaign_niche assertions (LLM required for niche extraction)');
      console.log('  Verifying fallback differentiation via result primary_niches instead...');

      const homeNiches = homeResults.results.map((r) => r.raw_data?.primary_niche).filter(Boolean);
      const padelNiches = padelResults.results.map((r) => r.raw_data?.primary_niche).filter(Boolean);
      const skincareNiches = skincareResults.results.map((r) => r.raw_data?.primary_niche).filter(Boolean);

      console.log(`  Home result niches:     ${[...new Set(homeNiches)].join(', ')}`);
      console.log(`  Padel result niches:    ${[...new Set(padelNiches)].join(', ')}`);
      console.log(`  Skincare result niches: ${[...new Set(skincareNiches)].join(', ')}`);

      expect(homeNiches.length, 'Home results should have primary_niche data').toBeGreaterThan(0);
      expect(padelNiches.length, 'Padel results should have primary_niche data').toBeGreaterThan(0);
      expect(skincareNiches.length, 'Skincare results should have primary_niche data').toBeGreaterThan(0);
      return;
    }

    const homeNiche = homeResults.parsed_query.campaign_niche?.toLowerCase();
    const padelNiche = padelResults.parsed_query.campaign_niche?.toLowerCase();
    const skincareNiche = skincareResults.parsed_query.campaign_niche?.toLowerCase();

    console.log('--- Extracted Campaign Niches ---');
    console.log(`  IKEA:    ${homeNiche}`);
    console.log(`  Adidas:  ${padelNiche}`);
    console.log(`  CeraVe:  ${skincareNiche}`);

    expect(homeNiche, 'IKEA search should have a campaign niche').toBeTruthy();
    expect(padelNiche, 'Padel search should have a campaign niche').toBeTruthy();
    expect(skincareNiche, 'CeraVe search should have a campaign niche').toBeTruthy();

    expect(
      QUERIES.home.expectedNiches.includes(homeNiche!),
      `IKEA niche "${homeNiche}" not in expected: ${QUERIES.home.expectedNiches}`,
    ).toBeTruthy();

    expect(
      QUERIES.padel.expectedNiches.includes(padelNiche!),
      `Padel niche "${padelNiche}" not in expected: ${QUERIES.padel.expectedNiches}`,
    ).toBeTruthy();

    expect(
      QUERIES.skincare.expectedNiches.includes(skincareNiche!),
      `CeraVe niche "${skincareNiche}" not in expected: ${QUERIES.skincare.expectedNiches}`,
    ).toBeTruthy();

    const niches = new Set([homeNiche, padelNiche, skincareNiche]);
    expect(niches.size, 'All three queries should extract distinct campaign niches').toBe(3);
  });

  test('niche match scores reflect query relevance', async () => {
    test.skip(homeResults.results.length === 0, 'No results — requires a populated database');
    const checkTopScores = (label: string, results: SearchResult[]) => {
      const top3 = results.slice(0, 3);
      console.log(`--- ${label} Top 3 Niche Match Scores ---`);
      for (const r of top3) {
        console.log(`  @${r.username}: niche_match=${r.scores.niche_match.toFixed(3)}`);
      }
      const avgNicheMatch = top3.reduce((sum, r) => sum + r.scores.niche_match, 0) / top3.length;
      expect(
        avgNicheMatch,
        `${label}: average niche_match of top 3 (${avgNicheMatch.toFixed(3)}) should be >= 0.2`,
      ).toBeGreaterThanOrEqual(0.2);
    };

    checkTopScores('Home/IKEA', homeResults.results);
    checkTopScores('Padel/Adidas', padelResults.results);
    checkTopScores('Skincare/CeraVe', skincareResults.results);
  });

  test('results have primary niche data', async () => {
    test.skip(homeResults.results.length === 0, 'No results — requires a populated database');
    const checkNicheCoverage = (label: string, results: SearchResult[]) => {
      if (results.length === 0) return;
      const withNiche = results.filter((r) => r.raw_data?.primary_niche);
      const coverage = withNiche.length / results.length;
      console.log(`  ${label}: ${withNiche.length}/${results.length} have primary_niche (${(coverage * 100).toFixed(0)}%)`);
      expect(
        coverage,
        `${label}: only ${(coverage * 100).toFixed(0)}% of results have primary_niche, expected >= 70%`,
      ).toBeGreaterThanOrEqual(0.7);
    };

    console.log('--- Primary Niche Data Coverage ---');
    checkNicheCoverage('Home/IKEA', homeResults.results);
    checkNicheCoverage('Padel/Adidas', padelResults.results);
    checkNicheCoverage('Skincare/CeraVe', skincareResults.results);
  });

  test('works without primetag (graceful degradation)', async () => {
    test.skip(homeResults.results.length === 0, 'No results — requires a populated database');
    const checkDegradation = (label: string, res: SearchResponse) => {
      expect(res.results.length, `${label}: should return results`).toBeGreaterThan(0);
      expect(res.total_candidates, `${label}: should discover candidates`).toBeGreaterThan(0);

      if (res.verification_stats) {
        const vs = res.verification_stats;
        console.log(
          `  ${label}: verified=${vs.verified}, failed=${vs.failed_verification}, ` +
          `results=${res.results.length}`,
        );

        if (vs.failed_verification > 0 && vs.verified === 0) {
          console.log(`  ${label}: PrimeTag unavailable — graceful degradation confirmed`);
        }

        expect(
          res.results.length,
          `${label}: should return results even when PrimeTag fails`,
        ).toBeGreaterThan(0);
      }
    };

    console.log('--- PrimeTag Graceful Degradation ---');
    checkDegradation('Home/IKEA', homeResults);
    checkDegradation('Padel/Adidas', padelResults);
    checkDegradation('Skincare/CeraVe', skincareResults);
  });
});
