"""
Pipeline Diagnostic Tests
=========================
End-to-end pipeline verification using realistic "messy email" briefs.

Tests each pipeline step:
  1. API Call         - POST /search/ returns 200
  2. LLM Parse        - LLM extracts brand, niche, count, filter thresholds
  3. Results Count    - Enough results returned
  4. GEMA Filters     - Results pass stored filter values (Spain %, Cred, ER, Gender)
  5. PrimeTag XCheck  - Cross-verify stored GEMA values against live PrimeTag API

Prerequisites:
  - Backend server running at http://localhost:8000
  - PRIMETAG_API_KEY set in .env (for XCheck step)
  - OPENAI_API_KEY set in .env (used by the server)

Run all (parallel):
  cd backend && pytest tests/test_pipeline_diagnostic.py::TestPipelineDiagnostic::test_all_diagnostics_parallel -v -s

Run individually (for parallel agent testing):
  cd backend && pytest tests/test_pipeline_diagnostic.py::TestPipelineDiagnostic::test_pipeline_gema_fashion -v -s
  cd backend && pytest tests/test_pipeline_diagnostic.py::TestPipelineDiagnostic::test_pipeline_gema_sports_nutrition -v -s
  cd backend && pytest tests/test_pipeline_diagnostic.py::TestPipelineDiagnostic::test_pipeline_gema_gastro -v -s
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

import httpx
import pytest

from app.services.primetag_client import PrimeTagClient, PrimeTagAPIError
from tests.test_briefs import PIPELINE_VERIFICATION_BRIEFS, TestBrief


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL = "http://localhost:8000/api"
TOP_N_TO_CROSS_CHECK = 5
API_TIMEOUT = 90.0  # Seconds — LLM parsing can be slow

# GEMA value tolerance for cached vs live comparison
SPAIN_PCT_TOLERANCE = 5.0       # ±5 percentage points
CREDIBILITY_TOLERANCE = 5.0     # ±5 points
ER_TOLERANCE = 2.0              # ±2 percentage points (stored ER may be decimal or %)
GENDER_TOLERANCE = 5.0          # ±5 percentage points


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PipelineStepResult:
    step_name: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class GEMAFilterCheck:
    filter_name: str        # "spain_pct" | "credibility" | "er" | "gender_female" | "gender_male"
    stored_value: Optional[float]
    live_value: Optional[float]
    threshold: Optional[float]
    verdict: str            # "MATCH" | "DRIFT" | "MISMATCH" | "SKIP"
    delta: Optional[float] = None


@dataclass
class InfluencerDiagnosticResult:
    username: str
    rank: int
    gema_checks: List[GEMAFilterCheck] = field(default_factory=list)
    primetag_fetch_succeeded: bool = False
    primetag_error: Optional[str] = None


@dataclass
class BriefDiagnosticResult:
    brief_name: str
    step_api_call: Optional[PipelineStepResult] = None
    step_llm_parse: Optional[PipelineStepResult] = None
    step_results_count: Optional[PipelineStepResult] = None
    step_gema_filters: Optional[PipelineStepResult] = None
    step_primetag_xcheck: Optional[PipelineStepResult] = None
    influencer_results: List[InfluencerDiagnosticResult] = field(default_factory=list)
    overall_passed: bool = False
    execution_time_s: float = 0.0
    raw_response: Optional[Dict[str, Any]] = None
    fatal_error: Optional[str] = None


# ---------------------------------------------------------------------------
# ER normalisation helper
# ---------------------------------------------------------------------------

def _normalise_er_to_pct(value: Optional[float]) -> Optional[float]:
    """
    Return ER as a percentage (0–100 scale).
    PrimeTag stores ER as 0–100; some DB rows may store as 0–1 decimal.
    Heuristic: if value <= 1.5 treat as decimal and multiply by 100.
    """
    if value is None:
        return None
    return value * 100.0 if value <= 1.5 else value


# ---------------------------------------------------------------------------
# GEMA check builder
# ---------------------------------------------------------------------------

def _build_gema_check(
    filter_name: str,
    stored: Optional[float],
    live: Optional[float],
    threshold: Optional[float],
    tolerance: float,
) -> GEMAFilterCheck:
    """Compare a single GEMA filter dimension (stored vs live)."""
    if stored is None or live is None:
        return GEMAFilterCheck(filter_name, stored, live, threshold, "SKIP")

    delta = abs(stored - live)
    stored_passes = threshold is None or stored >= threshold
    live_passes = threshold is None or live >= threshold

    if delta <= tolerance:
        verdict = "MATCH"
    elif stored_passes and not live_passes:
        verdict = "MISMATCH"   # Critical: stored OK but live would fail
    else:
        verdict = "DRIFT"      # Stale but not a false-positive

    return GEMAFilterCheck(filter_name, stored, live, threshold, verdict, delta)


# ---------------------------------------------------------------------------
# Step 1: API call
# ---------------------------------------------------------------------------

async def _step_api_call(
    client: httpx.AsyncClient,
    brief: TestBrief,
) -> Tuple[PipelineStepResult, Optional[Dict[str, Any]], float]:
    """POST /search/ and return (step_result, response_json, elapsed_s)."""
    payload = {
        "query": brief.query,
        "limit": max(15, brief.expectations.target_count * 2),
    }
    start = time.time()
    try:
        resp = await client.post(f"{API_BASE_URL}/search", json=payload, timeout=API_TIMEOUT)
        elapsed = time.time() - start
        if resp.status_code != 200:
            return (
                PipelineStepResult(
                    "API Call",
                    False,
                    failures=[f"HTTP {resp.status_code}: {resp.text[:300]}"],
                    details={"status_code": resp.status_code, "elapsed_s": elapsed},
                ),
                None,
                elapsed,
            )
        data = resp.json()
        return (
            PipelineStepResult(
                "API Call",
                True,
                details={
                    "status_code": 200,
                    "elapsed_s": round(elapsed, 2),
                    "search_id": data.get("search_id", "?"),
                    "total_candidates": data.get("total_candidates", "?"),
                    "total_after_filter": data.get("total_after_filter", "?"),
                    "results_returned": len(data.get("results", [])),
                },
            ),
            data,
            elapsed,
        )
    except httpx.ConnectError:
        return (
            PipelineStepResult(
                "API Call",
                False,
                failures=["Cannot connect to http://localhost:8000 — is the server running? (npm run dev)"],
            ),
            None,
            time.time() - start,
        )
    except httpx.TimeoutException:
        return (
            PipelineStepResult(
                "API Call",
                False,
                failures=[f"Request timed out after {API_TIMEOUT}s"],
            ),
            None,
            time.time() - start,
        )


# ---------------------------------------------------------------------------
# Step 2: LLM parse validation
# ---------------------------------------------------------------------------

def _step_llm_parse(
    parsed_query: Dict[str, Any],
    brief: TestBrief,
) -> PipelineStepResult:
    """Verify the LLM extracted the expected fields from the brief."""
    exp = brief.expectations
    failures = []
    warnings = []
    details = {}

    # Brand
    brand_name = parsed_query.get("brand_name")
    details["brand_name"] = brand_name
    if exp.expected_brand and brand_name:
        if exp.expected_brand.lower() not in brand_name.lower():
            warnings.append(f"brand_name '{brand_name}' doesn't clearly match expected '{exp.expected_brand}'")
    elif exp.expected_brand and not brand_name:
        failures.append(f"brand_name not extracted (expected '{exp.expected_brand}')")

    # Niche
    niche = parsed_query.get("campaign_niche")
    details["campaign_niche"] = niche
    if exp.expected_niche and not niche:
        failures.append(f"campaign_niche not extracted (expected '{exp.expected_niche}')")

    # Target count
    count = parsed_query.get("target_count", 5)
    details["target_count"] = count
    if abs(count - exp.target_count) > 1:
        warnings.append(f"target_count={count} differs from expected {exp.target_count}")

    # Gender split
    male_count = parsed_query.get("target_male_count")
    female_count = parsed_query.get("target_female_count")
    details["target_male_count"] = male_count
    details["target_female_count"] = female_count
    if exp.target_male_count and male_count != exp.target_male_count:
        failures.append(f"target_male_count={male_count} (expected {exp.target_male_count})")
    if exp.target_female_count and female_count != exp.target_female_count:
        failures.append(f"target_female_count={female_count} (expected {exp.target_female_count})")

    # Spain audience threshold
    spain_pct = parsed_query.get("min_spain_audience_pct", 60.0)
    details["min_spain_audience_pct"] = spain_pct

    # Credibility threshold
    cred = parsed_query.get("min_credibility_score", 70.0)
    details["min_credibility_score"] = cred

    # ER threshold
    er = parsed_query.get("min_engagement_rate")
    details["min_engagement_rate"] = er

    # Follower range
    fol_min = parsed_query.get("preferred_follower_min")
    fol_max = parsed_query.get("preferred_follower_max")
    details["preferred_follower_min"] = fol_min
    details["preferred_follower_max"] = fol_max
    if exp.preferred_follower_min and not fol_min:
        warnings.append(f"preferred_follower_min not extracted (expected ~{exp.preferred_follower_min:,})")
    if exp.preferred_follower_max and not fol_max:
        warnings.append(f"preferred_follower_max not extracted (expected ~{exp.preferred_follower_max:,})")

    # Exclude niches
    exclude_niches = parsed_query.get("exclude_niches", [])
    details["exclude_niches"] = exclude_niches
    if exp.excluded_niches and not exclude_niches:
        failures.append(f"No exclude_niches extracted (expected to include: {exp.excluded_niches})")

    # Reasoning
    details["influencer_reasoning"] = parsed_query.get("influencer_reasoning", "")[:100]

    return PipelineStepResult(
        "LLM Parse",
        passed=len(failures) == 0,
        details=details,
        failures=failures,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Step 3: Results count
# ---------------------------------------------------------------------------

def _step_results_count(results: List[Dict], brief: TestBrief) -> PipelineStepResult:
    n = len(results)
    expected = brief.expectations.target_count
    failures = []
    warnings = []
    if n == 0:
        failures.append("Zero results returned — pipeline produced no output")
    elif n < expected:
        warnings.append(f"Only {n} results returned (requested {expected})")
    return PipelineStepResult(
        "Results Count",
        passed=n > 0,
        details={"returned": n, "requested": expected},
        failures=failures,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Step 4: GEMA filters — stored values
# ---------------------------------------------------------------------------

def _step_gema_filters(
    results: List[Dict],
    filters_applied: Dict[str, Any],
    brief: TestBrief,
) -> PipelineStepResult:
    """
    Check each result's stored GEMA values against the applied thresholds.
    None values are SKIP (lenient_mode=True in filter service allows Nones).
    """
    min_spain = filters_applied.get("min_spain_audience_pct", 60.0)
    min_cred = filters_applied.get("min_credibility_score", 70.0)
    min_er = filters_applied.get("min_engagement_rate")  # Optional

    failures = []
    warnings = []
    rows = []

    for r in results[:TOP_N_TO_CROSS_CHECK]:
        raw = r.get("raw_data", {})
        username = r.get("username", "?")

        spain_val = None
        geo = raw.get("audience_geography", {})
        if geo:
            spain_val = geo.get("ES") or geo.get("es")

        cred_val = raw.get("credibility_score")
        er_val_raw = raw.get("engagement_rate")
        er_val = _normalise_er_to_pct(er_val_raw)

        gender_m = None
        gender_f = None
        genders = raw.get("audience_genders", {})
        if genders:
            gender_m = genders.get("male")
            gender_f = genders.get("female")

        age_dist = raw.get("audience_age_distribution", {})

        # Spain check
        spain_status = "SKIP" if spain_val is None else ("PASS" if spain_val >= min_spain else "FAIL")
        if spain_status == "FAIL":
            failures.append(f"@{username}: Spain={spain_val:.1f}% < {min_spain}%")

        # Credibility check
        cred_status = "SKIP" if cred_val is None else ("PASS" if cred_val >= min_cred else "FAIL")
        if cred_status == "FAIL":
            failures.append(f"@{username}: Credibility={cred_val:.1f} < {min_cred}")

        # ER check (only if threshold set)
        er_status = "N/A"
        if min_er is not None and er_val is not None:
            er_status = "PASS" if er_val >= min_er else "FAIL"
            if er_status == "FAIL":
                failures.append(f"@{username}: ER={er_val:.2f}% < {min_er}%")
        elif min_er is not None and er_val is None:
            er_status = "SKIP"

        rows.append({
            "username": username,
            "spain_pct": spain_val,
            "spain": spain_status,
            "credibility": cred_val,
            "cred": cred_status,
            "er_pct": er_val,
            "er": er_status,
            "gender_m": gender_m,
            "gender_f": gender_f,
            "age_dist": age_dist,
            "followers": raw.get("follower_count"),
            "niche": raw.get("primary_niche"),
        })

    return PipelineStepResult(
        "GEMA Filters (stored)",
        passed=len(failures) == 0,
        details={
            "thresholds": {
                "spain_pct": min_spain,
                "credibility": min_cred,
                "er": min_er,
            },
            "rows": rows,
        },
        failures=failures,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Step 5: PrimeTag cross-check
# ---------------------------------------------------------------------------

async def _fetch_primetag_for_influencer(
    username: str,
    mediakit_url: Optional[str],
    primetag_client: PrimeTagClient,
    semaphore: asyncio.Semaphore,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Fetch live PrimeTag metrics for one influencer.
    Returns (success, metrics_dict, error_message).
    """
    async with semaphore:
        try:
            # Prefer extracting from mediakit_url (faster, no search needed)
            encrypted = None
            if mediakit_url:
                encrypted = PrimeTagClient.extract_encrypted_username(mediakit_url)

            # Fall back to searching by username
            if not encrypted:
                summaries = await primetag_client.search_media_kits(
                    search_query=username,
                    platform_type=PrimeTagClient.PLATFORM_INSTAGRAM,
                    limit=5,
                )
                for s in summaries:
                    if s.username and s.username.lower() == username.lower():
                        encrypted = PrimeTagClient.extract_encrypted_username(s.mediakit_url or "")
                        break
                if not encrypted and summaries:
                    encrypted = PrimeTagClient.extract_encrypted_username(summaries[0].mediakit_url or "")

            if not encrypted:
                return False, None, "Could not resolve encrypted username from PrimeTag"

            detail = await primetag_client.get_media_kit_detail(
                encrypted,
                platform_type=PrimeTagClient.PLATFORM_INSTAGRAM,
            )
            metrics = primetag_client.extract_metrics(detail)
            return True, metrics, None

        except PrimeTagAPIError as e:
            return False, None, f"PrimeTag API error: {e}"
        except Exception as e:
            return False, None, f"Unexpected error: {type(e).__name__}: {e}"


async def _step_primetag_xcheck(
    results: List[Dict],
    filters_applied: Dict[str, Any],
    primetag_client: PrimeTagClient,
) -> Tuple[PipelineStepResult, List[InfluencerDiagnosticResult]]:
    """
    Cross-check stored GEMA filter values against live PrimeTag data for top N results.
    Verdict logic:
      MATCH    - |stored - live| within tolerance
      DRIFT    - delta > tolerance but both pass (or both fail) the threshold
      MISMATCH - stored passes threshold but live would fail (false positive — critical)
      SKIP     - one or both values are None
    """
    min_spain = filters_applied.get("min_spain_audience_pct", 60.0)
    min_cred = filters_applied.get("min_credibility_score", 70.0)
    min_er = filters_applied.get("min_engagement_rate")

    semaphore = asyncio.Semaphore(3)  # Max 3 concurrent PrimeTag calls

    top_results = results[:TOP_N_TO_CROSS_CHECK]
    tasks = [
        _fetch_primetag_for_influencer(
            r.get("username", "?"),
            r.get("raw_data", {}).get("mediakit_url"),
            primetag_client,
            semaphore,
        )
        for r in top_results
    ]
    fetched = await asyncio.gather(*tasks, return_exceptions=True)

    influencer_results = []
    mismatches = []
    drifts = []

    for i, (result, fetch_result) in enumerate(zip(top_results, fetched)):
        username = result.get("username", f"unknown_{i}")
        raw = result.get("raw_data", {})
        rank = result.get("rank_position", i + 1)

        if isinstance(fetch_result, Exception):
            influencer_results.append(
                InfluencerDiagnosticResult(
                    username=username,
                    rank=rank,
                    primetag_fetch_succeeded=False,
                    primetag_error=str(fetch_result),
                )
            )
            continue

        success, live_metrics, error = fetch_result
        if not success or live_metrics is None:
            influencer_results.append(
                InfluencerDiagnosticResult(
                    username=username,
                    rank=rank,
                    primetag_fetch_succeeded=False,
                    primetag_error=error,
                )
            )
            continue

        # Extract stored values
        geo = raw.get("audience_geography", {})
        stored_spain = geo.get("ES") or geo.get("es")
        stored_cred = raw.get("credibility_score")
        stored_er = _normalise_er_to_pct(raw.get("engagement_rate"))
        genders = raw.get("audience_genders", {})
        stored_gf = genders.get("female")
        stored_gm = genders.get("male")

        # Extract live values
        live_geo = live_metrics.get("audience_geography", {})
        live_spain = live_geo.get("ES") or live_geo.get("es")
        live_cred = live_metrics.get("credibility_score")
        live_er = _normalise_er_to_pct(live_metrics.get("engagement_rate"))
        live_genders = live_metrics.get("audience_genders", {})
        live_gf = live_genders.get("female")
        live_gm = live_genders.get("male")

        checks = [
            _build_gema_check("spain_pct",   stored_spain, live_spain, min_spain, SPAIN_PCT_TOLERANCE),
            _build_gema_check("credibility",  stored_cred,  live_cred,  min_cred,  CREDIBILITY_TOLERANCE),
            _build_gema_check("er",           stored_er,    live_er,    min_er,    ER_TOLERANCE),
            _build_gema_check("gender_female", stored_gf,   live_gf,    None,      GENDER_TOLERANCE),
            _build_gema_check("gender_male",   stored_gm,   live_gm,    None,      GENDER_TOLERANCE),
        ]

        for c in checks:
            if c.verdict == "MISMATCH":
                mismatches.append(f"@{username}/{c.filter_name}: stored={c.stored_value} passes threshold={c.threshold} but live={c.live_value} would fail")
            elif c.verdict == "DRIFT":
                drifts.append(f"@{username}/{c.filter_name}: delta={c.delta:.1f} (stored={c.stored_value}, live={c.live_value})")

        influencer_results.append(
            InfluencerDiagnosticResult(
                username=username,
                rank=rank,
                gema_checks=checks,
                primetag_fetch_succeeded=True,
            )
        )

    step = PipelineStepResult(
        "PrimeTag Cross-Check",
        passed=len(mismatches) == 0,
        details={
            "checked": len([r for r in influencer_results if r.primetag_fetch_succeeded]),
            "failed_to_fetch": len([r for r in influencer_results if not r.primetag_fetch_succeeded]),
            "mismatches": len(mismatches),
            "drifts": len(drifts),
        },
        failures=mismatches,
        warnings=drifts,
    )
    return step, influencer_results


# ---------------------------------------------------------------------------
# Main diagnostic runner
# ---------------------------------------------------------------------------

async def run_brief_diagnostic(
    brief: TestBrief,
    client: httpx.AsyncClient,
    primetag_client: PrimeTagClient,
) -> BriefDiagnosticResult:
    result = BriefDiagnosticResult(brief_name=brief.name)
    start_total = time.time()

    # Step 1: API call
    step1, response_data, api_time = await _step_api_call(client, brief)
    result.step_api_call = step1
    result.raw_response = response_data

    if not step1.passed or response_data is None:
        result.execution_time_s = time.time() - start_total
        return result

    parsed_query = response_data.get("parsed_query", {})
    filters_applied = response_data.get("filters_applied", {})
    results = response_data.get("results", [])

    # Step 2: LLM parse
    result.step_llm_parse = _step_llm_parse(parsed_query, brief)

    # Step 3: Results count
    result.step_results_count = _step_results_count(results, brief)

    if not result.step_results_count.passed:
        result.execution_time_s = time.time() - start_total
        return result

    # Step 4: GEMA filters (stored values)
    result.step_gema_filters = _step_gema_filters(results, filters_applied, brief)

    # Step 5: PrimeTag cross-check
    result.step_primetag_xcheck, result.influencer_results = await _step_primetag_xcheck(
        results, filters_applied, primetag_client
    )

    result.execution_time_s = round(time.time() - start_total, 2)
    result.overall_passed = all([
        result.step_api_call.passed,
        result.step_llm_parse.passed,
        result.step_results_count.passed,
        result.step_gema_filters.passed,
        result.step_primetag_xcheck.passed,
    ])
    return result


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------

def format_diagnostic_report(results: List[BriefDiagnosticResult]) -> str:
    lines = []
    sep = "=" * 70

    lines.append("\n" + sep)
    lines.append("PIPELINE DIAGNOSTIC REPORT")
    lines.append(sep)

    # Summary table
    lines.append("\nSUMMARY")
    lines.append("-" * 70)
    header = f"{'Brief':<40} {'API':>4} {'Parse':>6} {'Count':>6} {'GEMA':>5} {'XChk':>5} {'Result':>7}"
    lines.append(header)
    lines.append("-" * 70)

    for r in results:
        def _s(step): return "OK" if (step and step.passed) else ("--" if not step else "FAIL")
        overall = "PASS" if r.overall_passed else ("ERR" if r.fatal_error else "FAIL")
        lines.append(
            f"{r.brief_name:<40} {_s(r.step_api_call):>4} {_s(r.step_llm_parse):>6} "
            f"{_s(r.step_results_count):>6} {_s(r.step_gema_filters):>5} {_s(r.step_primetag_xcheck):>5} {overall:>7}"
        )

    # Detail per brief
    for r in results:
        lines.append(f"\n{'=' * 70}")
        lines.append(f"DETAIL: {r.brief_name}  ({r.execution_time_s}s)")
        lines.append("=" * 70)

        if r.fatal_error:
            lines.append(f"  FATAL: {r.fatal_error}")
            continue

        # Step 1
        s1 = r.step_api_call
        if s1:
            status = "PASS" if s1.passed else "FAIL"
            d = s1.details
            lines.append(f"\nStep 1/5 - API Call: {status}")
            if s1.passed:
                lines.append(f"  search_id:           {d.get('search_id')}")
                lines.append(f"  total_candidates:    {d.get('total_candidates')}")
                lines.append(f"  total_after_filter:  {d.get('total_after_filter')}")
                lines.append(f"  results_returned:    {d.get('results_returned')}")
                lines.append(f"  elapsed:             {d.get('elapsed_s')}s")
            for f in s1.failures:
                lines.append(f"  FAIL: {f}")

        # Step 2
        s2 = r.step_llm_parse
        if s2:
            status = "PASS" if s2.passed else "FAIL"
            lines.append(f"\nStep 2/5 - LLM Parse: {status}")
            d = s2.details
            lines.append(f"  brand_name:            {d.get('brand_name')}")
            lines.append(f"  campaign_niche:        {d.get('campaign_niche')}")
            lines.append(f"  target_count:          {d.get('target_count')}")
            lines.append(f"  target_male_count:     {d.get('target_male_count')}")
            lines.append(f"  target_female_count:   {d.get('target_female_count')}")
            lines.append(f"  min_spain_pct:         {d.get('min_spain_audience_pct')}%")
            lines.append(f"  min_credibility:       {d.get('min_credibility_score')}")
            lines.append(f"  min_er:                {d.get('min_engagement_rate')}")
            lines.append(f"  preferred_followers:   {d.get('preferred_follower_min'):,}–{d.get('preferred_follower_max'):,}"
                         if d.get('preferred_follower_min') and d.get('preferred_follower_max')
                         else f"  preferred_followers:   {d.get('preferred_follower_min')} – {d.get('preferred_follower_max')}")
            lines.append(f"  exclude_niches:        {d.get('exclude_niches')}")
            lines.append(f"  reasoning:             {d.get('influencer_reasoning')!r:.80}")
            for f in s2.failures:
                lines.append(f"  FAIL: {f}")
            for w in s2.warnings:
                lines.append(f"  WARN: {w}")

        # Step 3
        s3 = r.step_results_count
        if s3:
            status = "PASS" if s3.passed else "FAIL"
            d = s3.details
            lines.append(f"\nStep 3/5 - Results Count: {status}")
            lines.append(f"  returned={d.get('returned')}  requested={d.get('requested')}")
            for f in s3.failures:
                lines.append(f"  FAIL: {f}")

        # Step 4
        s4 = r.step_gema_filters
        if s4:
            status = "PASS" if s4.passed else "FAIL"
            d = s4.details
            thresh = d.get("thresholds", {})
            lines.append(f"\nStep 4/5 - GEMA Filters (stored values): {status}")
            lines.append(
                f"  Thresholds — Spain≥{thresh.get('spain_pct')}%  "
                f"Cred≥{thresh.get('credibility')}  "
                f"ER≥{thresh.get('er') or 'n/a'}%"
            )
            col_hdr = f"  {'Username':<22} {'Spain%':>7} {'Spaok':>5} {'Cred':>6} {'Crdk':>5} {'ER%':>6} {'ERok':>5} {'Fol':>8} {'Niche'}"
            lines.append(col_hdr)
            for row in d.get("rows", []):
                spain_v = f"{row['spain_pct']:.1f}" if row['spain_pct'] is not None else "None"
                cred_v = f"{row['credibility']:.1f}" if row['credibility'] is not None else "None"
                er_v = f"{row['er_pct']:.2f}" if row['er_pct'] is not None else "None"
                fol = row['followers'] or 0
                fol_k = f"{fol // 1000}K" if fol else "?"
                lines.append(
                    f"  {row['username']:<22} {spain_v:>7} {row['spain']:>5} "
                    f"{cred_v:>6} {row['cred']:>5} {er_v:>6} {row['er']:>5} "
                    f"{fol_k:>8} {row['niche'] or '?'}"
                )
            for f in s4.failures:
                lines.append(f"  FAIL: {f}")

        # Step 5
        s5 = r.step_primetag_xcheck
        if s5:
            status = "PASS" if s5.passed else "FAIL"
            d = s5.details
            lines.append(f"\nStep 5/5 - PrimeTag Cross-Check: {status}")
            lines.append(
                f"  Checked: {d.get('checked')}  "
                f"Failed to fetch: {d.get('failed_to_fetch')}  "
                f"MISMATCHes: {d.get('mismatches')}  "
                f"DRIFTs: {d.get('drifts')}"
            )
            for inf in r.influencer_results:
                lines.append(f"\n  @{inf.username} (rank {inf.rank})")
                if not inf.primetag_fetch_succeeded:
                    lines.append(f"    PrimeTag fetch failed: {inf.primetag_error}")
                    continue
                for c in inf.gema_checks:
                    stored_s = f"{c.stored_value:.2f}" if c.stored_value is not None else "None"
                    live_s = f"{c.live_value:.2f}" if c.live_value is not None else "None"
                    delta_s = f"Δ{c.delta:.2f}" if c.delta is not None else ""
                    thresh_s = f"(thresh={c.threshold})" if c.threshold is not None else ""
                    lines.append(
                        f"    {c.filter_name:<14} stored={stored_s:<8} live={live_s:<8} "
                        f"{delta_s:<8} [{c.verdict}] {thresh_s}"
                    )
            for f in s5.failures:
                lines.append(f"  FAIL: {f}")
            for w in s5.warnings:
                lines.append(f"  WARN: {w}")

        overall = "PASS" if r.overall_passed else "FAIL"
        lines.append(f"\n{'─' * 70}")
        lines.append(f"RESULT: {overall}  (total {r.execution_time_s}s)")

    lines.append(f"\n{'=' * 70}")
    passed = sum(1 for r in results if r.overall_passed)
    lines.append(f"OVERALL: {passed}/{len(results)} briefs passed")
    lines.append("=" * 70 + "\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@pytest.mark.diagnostic
@pytest.mark.asyncio
class TestPipelineDiagnostic:
    """
    Live end-to-end pipeline diagnostic tests.

    Each test method maps to one of the PIPELINE_VERIFICATION_BRIEFS.
    Run individually for parallel agent testing, or all at once via
    test_all_diagnostics_parallel.
    """

    async def _run_one(self, brief_name: str) -> BriefDiagnosticResult:
        brief = next((b for b in PIPELINE_VERIFICATION_BRIEFS if b.name == brief_name), None)
        assert brief is not None, f"Brief '{brief_name}' not found in PIPELINE_VERIFICATION_BRIEFS"

        async with httpx.AsyncClient() as client:
            pt_client = PrimeTagClient()
            result = await run_brief_diagnostic(brief, client, pt_client)

        report = format_diagnostic_report([result])
        print(report)
        return result

    async def test_pipeline_gema_fashion(self):
        """El Corte Inglés fashion — female-skewed, Spain ≥65%, cred ≥75%, ER ≥2%."""
        result = await self._run_one("pipeline_gema_fashion")
        assert result.step_api_call and result.step_api_call.passed, \
            "API call failed — is the server running? Run: npm run dev"
        assert result.step_results_count and result.step_results_count.passed, \
            "No results returned from search"
        if result.step_gema_filters and not result.step_gema_filters.passed:
            pytest.fail("GEMA filter violations in stored data:\n" +
                        "\n".join(result.step_gema_filters.failures))
        if result.step_primetag_xcheck and not result.step_primetag_xcheck.passed:
            pytest.fail("PrimeTag cross-check found MISMATCHes:\n" +
                        "\n".join(result.step_primetag_xcheck.failures))

    async def test_pipeline_gema_sports_nutrition(self):
        """Myprotein España — 3M/2F split, fitness, excludes football, Spain ≥60%."""
        result = await self._run_one("pipeline_gema_sports_nutrition")
        assert result.step_api_call and result.step_api_call.passed, \
            "API call failed — is the server running? Run: npm run dev"
        assert result.step_results_count and result.step_results_count.passed, \
            "No results returned from search"
        if result.step_gema_filters and not result.step_gema_filters.passed:
            pytest.fail("GEMA filter violations in stored data:\n" +
                        "\n".join(result.step_gema_filters.failures))
        if result.step_primetag_xcheck and not result.step_primetag_xcheck.passed:
            pytest.fail("PrimeTag cross-check found MISMATCHes:\n" +
                        "\n".join(result.step_primetag_xcheck.failures))

    async def test_pipeline_gema_gastro(self):
        """Glovo España — gastro/urban, young 18-30 audience, ER ≥1.5%, Spain ≥65%."""
        result = await self._run_one("pipeline_gema_gastro")
        assert result.step_api_call and result.step_api_call.passed, \
            "API call failed — is the server running? Run: npm run dev"
        assert result.step_results_count and result.step_results_count.passed, \
            "No results returned from search"
        if result.step_gema_filters and not result.step_gema_filters.passed:
            pytest.fail("GEMA filter violations in stored data:\n" +
                        "\n".join(result.step_gema_filters.failures))
        if result.step_primetag_xcheck and not result.step_primetag_xcheck.passed:
            pytest.fail("PrimeTag cross-check found MISMATCHes:\n" +
                        "\n".join(result.step_primetag_xcheck.failures))

    async def test_all_diagnostics_parallel(self):
        """
        Run all 3 PIPELINE_VERIFICATION_BRIEFS in parallel using asyncio.gather.
        Use this as the single entry point for full pipeline validation.

        Command:
          cd backend && pytest tests/test_pipeline_diagnostic.py::TestPipelineDiagnostic::test_all_diagnostics_parallel -v -s
        """
        async with httpx.AsyncClient() as client:
            pt_client = PrimeTagClient()
            tasks = [
                run_brief_diagnostic(brief, client, pt_client)
                for brief in PIPELINE_VERIFICATION_BRIEFS
            ]
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        for i, r in enumerate(raw_results):
            if isinstance(r, Exception):
                err_result = BriefDiagnosticResult(
                    brief_name=PIPELINE_VERIFICATION_BRIEFS[i].name,
                    fatal_error=str(r),
                )
                results.append(err_result)
            else:
                results.append(r)

        report = format_diagnostic_report(results)
        print(report)

        # Hard fail: server must be reachable
        unreachable = [
            r.brief_name for r in results
            if r.step_api_call is None or not r.step_api_call.passed
        ]
        assert not unreachable, (
            f"Server unreachable for {unreachable} — is the server running? Run: npm run dev"
        )

        # Hard fail: MISMATCH means cached data passes filters but live PrimeTag would fail
        all_mismatches = []
        for r in results:
            if r.step_primetag_xcheck:
                all_mismatches.extend(r.step_primetag_xcheck.failures)

        if all_mismatches:
            pytest.fail(
                "CRITICAL: Stored GEMA values pass thresholds but live PrimeTag values would fail.\n"
                "These influencers are shown to clients but wouldn't pass real-time verification:\n"
                + "\n".join(f"  {m}" for m in all_mismatches)
            )

        # Soft warn: report GEMA filter violations in stored data
        stored_violations = []
        for r in results:
            if r.step_gema_filters and r.step_gema_filters.failures:
                stored_violations.extend(
                    [f"[{r.brief_name}] {f}" for f in r.step_gema_filters.failures]
                )
        if stored_violations:
            # Not a hard fail — lenient_mode=True intentionally allows some Nones
            print("\nWARNING: Stored GEMA value violations (lenient_mode=True allows these):")
            for v in stored_violations:
                print(f"  {v}")
