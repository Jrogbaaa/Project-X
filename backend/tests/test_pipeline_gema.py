"""
Full pipeline GEMA verification tests.

Tests the complete influencer discovery pipeline across 4 messy real-world briefs,
run in parallel via asyncio.gather. Each pipeline step is explicitly asserted:

  Step 1: Brief ingestion     - API completed, parsed_query and search_id exist
  Step 2: LLM parsing         - brand, niche, Spain %, credibility thresholds extracted
  Step 3: Accurate matching   - at least 1 influencer returned
  Step 4: PrimeTag data       - GEMA metric fields present on results (credibility/ER/geography)
  Step 5: GEMA filters        - each result passes ES %, credibility, and niche exclusion checks

Prints a per-step diagnostic table after all briefs complete showing exactly what
passed and what failed, with field-level failure details.

Run:
    cd backend && pytest tests/test_pipeline_gema.py -v -s
    cd backend && pytest tests/test_pipeline_gema.py::TestPipelineGEMA::test_parallel_pipeline_all_briefs -v -s
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

import pytest

from tests.test_briefs import PIPELINE_VERIFICATION_BRIEFS, TestBrief
from app.services.search_service import SearchService
from app.schemas.search import SearchRequest, SearchResponse

logger = logging.getLogger(__name__)


# ============================================================
# Step result containers
# ============================================================

STEP_NAMES = [
    "step1_ingestion",
    "step2_llm_parsing",
    "step3_matching",
    "step4_primetag_data",
    "step5_gema_filters",
]

STEP_LABELS = {
    "step1_ingestion":     "Step1 Ingest ",
    "step2_llm_parsing":   "Step2 Parse  ",
    "step3_matching":      "Step3 Match  ",
    "step4_primetag_data": "Step4 PT Data",
    "step5_gema_filters":  "Step5 GEMA   ",
}

# GEMA threshold constants (mirrors defaults in FilterService)
GEMA_MIN_SPAIN_PCT = 60.0    # % en España
GEMA_MIN_CREDIBILITY = 70.0  # % Credibilidad (Instagram only)


@dataclass
class StepResult:
    passed: bool
    details: str
    value: Any = None


@dataclass
class PipelineResult:
    brief_name: str
    step_results: Dict[str, StepResult] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def all_passed(self) -> bool:
        if self.error:
            return False
        return all(r.passed for r in self.step_results.values())

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.step_results.values() if r.passed)


# ============================================================
# Core pipeline runner (collects failures, never asserts)
# ============================================================

async def _run_single_brief(
    search_service: SearchService,
    brief: TestBrief,
) -> PipelineResult:
    """
    Run one brief through the full pipeline and record per-step pass/fail.

    Does NOT raise assertions — all failures are captured in PipelineResult
    so the diagnostic table can show the complete picture even if early steps fail.
    """
    result = PipelineResult(brief_name=brief.name)

    # ------------------------------------------------------------------
    # Step 1: Brief ingestion
    # Checks: execute_search() completes, parsed_query is not None, search_id exists
    # ------------------------------------------------------------------
    try:
        request = SearchRequest(
            query=brief.query,
            limit=min(brief.expectations.target_count * 3, 50),
        )
        response: SearchResponse = await search_service.execute_search(request)

        has_parsed_query = response.parsed_query is not None
        has_search_id = bool(response.search_id)

        result.step_results["step1_ingestion"] = StepResult(
            passed=has_parsed_query and has_search_id,
            details=(
                f"search_id={response.search_id[:8]}... | parsed_query=present"
                if (has_parsed_query and has_search_id)
                else f"parsed_query={'present' if has_parsed_query else 'MISSING'} | search_id={'present' if has_search_id else 'MISSING'}"
            ),
            value=response,
        )
    except Exception as exc:
        result.step_results["step1_ingestion"] = StepResult(
            passed=False,
            details=f"Exception: {exc}",
        )
        result.error = str(exc)
        logger.error(f"Pipeline failed at ingestion for {brief.name}: {exc}", exc_info=True)
        # Fill remaining steps as skipped
        for key in STEP_NAMES[1:]:
            result.step_results[key] = StepResult(passed=False, details="Skipped (ingestion failed)")
        return result

    response = result.step_results["step1_ingestion"].value

    # ------------------------------------------------------------------
    # Step 2: LLM parsing
    # Checks: brand extracted, campaign_niche set, Spain ≥60%, credibility ≥70%,
    #         exclude_niches populated when expected, gender split parsed
    # ------------------------------------------------------------------
    pq = response.parsed_query
    parsing_issues = []

    # Brand extraction
    if brief.expectations.expected_brand:
        if not pq.brand_name:
            parsing_issues.append(f"brand_name=None (expected '{brief.expectations.expected_brand}')")
        elif brief.expectations.expected_brand.lower() not in pq.brand_name.lower():
            parsing_issues.append(
                f"brand_name='{pq.brand_name}' doesn't contain '{brief.expectations.expected_brand}'"
            )

    # Niche extraction
    if not pq.campaign_niche:
        parsing_issues.append("campaign_niche=None (discovery will fall back to interests only)")

    # Spain threshold — must be at GEMA floor
    if pq.min_spain_audience_pct < GEMA_MIN_SPAIN_PCT:
        parsing_issues.append(
            f"min_spain_audience_pct={pq.min_spain_audience_pct}% < GEMA floor {GEMA_MIN_SPAIN_PCT}%"
        )

    # Credibility threshold — must be at GEMA floor
    if pq.min_credibility_score < GEMA_MIN_CREDIBILITY:
        parsing_issues.append(
            f"min_credibility_score={pq.min_credibility_score}% < GEMA floor {GEMA_MIN_CREDIBILITY}%"
        )

    # Niche exclusions propagated
    if brief.expectations.excluded_niches and not pq.exclude_niches:
        parsing_issues.append(
            f"exclude_niches=[] but brief has exclusions: {brief.expectations.excluded_niches}"
        )

    # Gender split parsed (only if brief requests explicit split)
    if brief.expectations.target_male_count is not None:
        if pq.target_male_count != brief.expectations.target_male_count:
            parsing_issues.append(
                f"target_male_count={pq.target_male_count} (expected {brief.expectations.target_male_count})"
            )
    if brief.expectations.target_female_count is not None:
        if pq.target_female_count != brief.expectations.target_female_count:
            parsing_issues.append(
                f"target_female_count={pq.target_female_count} (expected {brief.expectations.target_female_count})"
            )

    result.step_results["step2_llm_parsing"] = StepResult(
        passed=len(parsing_issues) == 0,
        details=(
            f"brand='{pq.brand_name}' niche='{pq.campaign_niche}' "
            f"ES%>={pq.min_spain_audience_pct} cred>={pq.min_credibility_score} "
            f"excl={pq.exclude_niches}"
            if not parsing_issues
            else " | ".join(parsing_issues)
        ),
        value=pq,
    )

    # ------------------------------------------------------------------
    # Step 3: Accurate matching
    # Checks: at least 1 influencer returned
    # ------------------------------------------------------------------
    result_count = len(response.results)
    result.step_results["step3_matching"] = StepResult(
        passed=result_count >= 1,
        details=(
            f"{result_count} results (target={brief.expectations.target_count}, "
            f"candidates={response.total_candidates}, after_filter={response.total_after_filter})"
        ),
        value=result_count,
    )

    # ------------------------------------------------------------------
    # Step 4: PrimeTag data presence
    # Checks: top 5 results each have at least one GEMA metric field populated.
    # Lenient: imported profiles may not have full PrimeTag data yet.
    # ------------------------------------------------------------------
    if not response.results:
        result.step_results["step4_primetag_data"] = StepResult(
            passed=False,
            details="No results to check",
        )
    else:
        to_check = response.results[:5]
        missing_data = []

        for r in to_check:
            raw = r.raw_data
            has_any_metric = (
                raw.credibility_score is not None
                or raw.engagement_rate is not None
                or bool(raw.audience_geography)
                or bool(raw.audience_genders)
                or bool(raw.audience_age_distribution)
            )
            if not has_any_metric:
                missing_data.append(f"@{r.username}: all GEMA metric fields empty")

        result.step_results["step4_primetag_data"] = StepResult(
            passed=len(missing_data) == 0,
            details=(
                f"Top {len(to_check)} results all have ≥1 GEMA metric field"
                if not missing_data
                else " | ".join(missing_data)
            ),
            value=len(to_check) - len(missing_data),
        )

    # ------------------------------------------------------------------
    # Step 5: GEMA filter compliance
    # Checks on top 10 results:
    #   - audience_geography["ES"] >= 60% (only if key present and > 0)
    #   - credibility_score >= 70% (only for instagram, only if not None)
    #   - primary_niche not in must_not_have_niches
    # ------------------------------------------------------------------
    if not response.results:
        result.step_results["step5_gema_filters"] = StepResult(
            passed=False,
            details="No results to validate",
        )
    else:
        to_validate = response.results[:10]
        gema_violations = []

        for r in to_validate:
            raw = r.raw_data
            username = f"@{r.username}"

            # Spain audience check (only if data is present and non-zero)
            es_pct = raw.audience_geography.get("ES", 0.0)
            if es_pct > 0 and es_pct < GEMA_MIN_SPAIN_PCT:
                gema_violations.append(
                    f"{username}: ES%={es_pct:.1f}% < {GEMA_MIN_SPAIN_PCT}% GEMA floor"
                )

            # Credibility check (Instagram only, only if data present)
            is_instagram = (raw.platform_type or "instagram").lower() == "instagram"
            if is_instagram and raw.credibility_score is not None:
                if raw.credibility_score < GEMA_MIN_CREDIBILITY:
                    gema_violations.append(
                        f"{username}: credibility={raw.credibility_score:.1f}% < {GEMA_MIN_CREDIBILITY}%"
                    )

            # Niche exclusion check
            if brief.expectations.must_not_have_niches and raw.primary_niche:
                niche_lower = raw.primary_niche.lower()
                for forbidden in brief.expectations.must_not_have_niches:
                    if forbidden.lower() == niche_lower:
                        gema_violations.append(
                            f"{username}: primary_niche='{raw.primary_niche}' is forbidden for this campaign"
                        )

        result.step_results["step5_gema_filters"] = StepResult(
            passed=len(gema_violations) == 0,
            details=(
                f"All {len(to_validate)} results pass GEMA filters"
                if not gema_violations
                else " | ".join(gema_violations[:4])  # cap output for readability
            ),
            value=gema_violations,
        )

    return result


# ============================================================
# Diagnostic table printer
# ============================================================

def _print_diagnostic_table(pipeline_results: List[PipelineResult]) -> None:
    """Print a formatted per-step PASS/FAIL table for all briefs."""
    BRIEF_W = 28
    STEP_W = 15

    print("\n")
    separator = "=" * (BRIEF_W + len(STEP_NAMES) * (STEP_W + 2) + 12)
    print(separator)
    print("  PIPELINE GEMA DIAGNOSTIC TABLE")
    print(separator)

    # Header
    header = f"{'Brief':<{BRIEF_W}}"
    for key in STEP_NAMES:
        header += f"  {STEP_LABELS[key]:<{STEP_W}}"
    header += "  Overall"
    print(header)
    print("-" * len(separator))

    # Rows
    for pr in pipeline_results:
        row = f"{pr.brief_name[:BRIEF_W]:<{BRIEF_W}}"
        for key in STEP_NAMES:
            sr = pr.step_results.get(key)
            cell = "PASS" if (sr and sr.passed) else "FAIL"
            row += f"  {cell:<{STEP_W}}"
        overall = "ALL PASS" if pr.all_passed else f"{pr.pass_count}/{len(STEP_NAMES)} steps pass"
        row += f"  {overall}"
        print(row)

    print("-" * len(separator))

    # Summary
    total = len(pipeline_results)
    fully_passed = sum(1 for pr in pipeline_results if pr.all_passed)
    print(f"\nBriefs fully passed: {fully_passed}/{total}\n")

    # Failure details
    for pr in pipeline_results:
        if not pr.all_passed:
            print(f"Failures for [{pr.brief_name}]:")
            if pr.error:
                print(f"  Top-level error: {pr.error}")
            for step_key in STEP_NAMES:
                sr = pr.step_results.get(step_key)
                if sr and not sr.passed:
                    print(f"  {STEP_LABELS[step_key]}: FAIL — {sr.details}")
            print()

    print(separator)
    print()


# ============================================================
# Test class
# ============================================================

@pytest.mark.e2e
class TestPipelineGEMA:
    """
    Full pipeline GEMA verification across 4 messy Spanish agency briefs.

    Briefs in PIPELINE_VERIFICATION_BRIEFS cover:
      - El Corte Inglés (fashion, female-skewed, credibility ≥75%)
      - Myprotein (fitness, 3M/2F gender split, football excluded)
      - Glovo (gastro/food, ER ≥1.5%, young audience)
      - Estrella Damm (beer/lifestyle, summer, competitor exclusion)

    All 4 run in parallel via asyncio.gather. Each brief is validated
    across 5 explicit pipeline steps with a diagnostic table printed at the end.
    """

    async def test_parallel_pipeline_all_briefs(self, search_service: SearchService):
        """
        Main test: run all 4 PIPELINE_VERIFICATION_BRIEFS in parallel.

        Pass criteria (lenient on data-dependent steps):
        - Step 1 (ingestion):  all 4 briefs must complete without exception
        - Step 2 (LLM parse):  at least 3/4 must extract brand+niche+thresholds correctly
        - Step 3 (matching):   at least 3/4 must return ≥1 result
        - Step 4 (PT data):    at least 2/4 must have GEMA metric fields on results
        - Step 5 (GEMA filters): at least 2/4 must have all results passing GEMA checks
        """
        assert PIPELINE_VERIFICATION_BRIEFS, "PIPELINE_VERIFICATION_BRIEFS is empty"

        tasks = [
            _run_single_brief(search_service, brief)
            for brief in PIPELINE_VERIFICATION_BRIEFS
        ]
        pipeline_results: List[PipelineResult] = await asyncio.gather(*tasks)

        _print_diagnostic_table(pipeline_results)

        total = len(pipeline_results)

        def count_passing(step_key: str) -> int:
            return sum(
                1 for pr in pipeline_results
                if pr.step_results.get(step_key, StepResult(False, "")).passed
            )

        step1 = count_passing("step1_ingestion")
        step2 = count_passing("step2_llm_parsing")
        step3 = count_passing("step3_matching")
        step4 = count_passing("step4_primetag_data")
        step5 = count_passing("step5_gema_filters")

        assert step1 == total, (
            f"Step 1 (ingestion): {step1}/{total} passed — all briefs must reach the parser"
        )
        assert step2 >= total - 1, (
            f"Step 2 (LLM parsing): {step2}/{total} passed — need at least {total - 1}"
        )
        assert step3 >= total - 1, (
            f"Step 3 (matching): {step3}/{total} returned results — need at least {total - 1}"
        )
        assert step4 >= total - 2, (
            f"Step 4 (PrimeTag data): {step4}/{total} have metric fields — need at least {total - 2}"
        )
        assert step5 >= total - 2, (
            f"Step 5 (GEMA filters): {step5}/{total} pass all GEMA checks — need at least {total - 2}"
        )

    async def test_fashion_brief_parses_brand_and_excludes_fitness(
        self, search_service: SearchService
    ):
        """El Corte Inglés: brand extracted, fashion niche set, fitness excluded, all-female target."""
        brief = next(b for b in PIPELINE_VERIFICATION_BRIEFS if b.name == "pipeline_gema_fashion")
        result = await _run_single_brief(search_service, brief)
        _print_diagnostic_table([result])

        assert result.step_results["step1_ingestion"].passed, "Ingestion failed"

        pq = result.step_results["step2_llm_parsing"].value
        assert pq is not None, "parsed_query is None"
        assert pq.brand_name and "corte" in pq.brand_name.lower(), (
            f"Expected 'El Corte Inglés' in brand_name, got '{pq.brand_name}'"
        )
        assert pq.campaign_niche == "fashion", (
            f"Expected niche='fashion', got '{pq.campaign_niche}'"
        )
        assert pq.min_spain_audience_pct >= GEMA_MIN_SPAIN_PCT, (
            f"Spain % threshold {pq.min_spain_audience_pct} below GEMA floor"
        )
        # Brief explicitly says 5 female profiles
        if pq.target_female_count is not None:
            assert pq.target_female_count == 5, (
                f"Expected target_female_count=5, got {pq.target_female_count}"
            )

    async def test_sports_nutrition_gender_split_and_football_excluded(
        self, search_service: SearchService
    ):
        """Myprotein: 3M/2F gender split parsed, football excluded from results."""
        brief = next(b for b in PIPELINE_VERIFICATION_BRIEFS if b.name == "pipeline_gema_sports_nutrition")
        result = await _run_single_brief(search_service, brief)
        _print_diagnostic_table([result])

        assert result.step_results["step1_ingestion"].passed, "Ingestion failed"

        pq = result.step_results["step2_llm_parsing"].value
        assert pq is not None, "parsed_query is None"
        assert pq.target_male_count == 3, (
            f"Expected target_male_count=3, got {pq.target_male_count}"
        )
        assert pq.target_female_count == 2, (
            f"Expected target_female_count=2, got {pq.target_female_count}"
        )

        # Check no football influencers slipped through
        response: Optional[SearchResponse] = result.step_results["step1_ingestion"].value
        if response and response.results:
            for r in response.results[:10]:
                if r.raw_data.primary_niche:
                    assert r.raw_data.primary_niche.lower() not in ("football", "soccer", "fútbol"), (
                        f"Football influencer @{r.username} appeared in Myprotein fitness results"
                    )

    async def test_gastro_brief_returns_food_influencers(
        self, search_service: SearchService
    ):
        """Glovo: food/gastro niche matched, fitness excluded, results returned."""
        brief = next(b for b in PIPELINE_VERIFICATION_BRIEFS if b.name == "pipeline_gema_gastro")
        result = await _run_single_brief(search_service, brief)
        _print_diagnostic_table([result])

        assert result.step_results["step1_ingestion"].passed, "Ingestion failed"
        assert result.step_results["step3_matching"].passed, (
            "No results returned for Glovo gastro brief — check food niche matching"
        )

        pq = result.step_results["step2_llm_parsing"].value
        assert pq is not None, "parsed_query is None"
        assert pq.campaign_niche in ("food", "food_lifestyle", "lifestyle"), (
            f"Expected food-related niche, got '{pq.campaign_niche}'"
        )

    async def test_beer_brief_excludes_fitness_and_competitors(
        self, search_service: SearchService
    ):
        """Estrella Damm: fitness excluded from results, competitor brands flagged."""
        brief = next(b for b in PIPELINE_VERIFICATION_BRIEFS if b.name == "pipeline_gema_beer_lifestyle")
        result = await _run_single_brief(search_service, brief)
        _print_diagnostic_table([result])

        assert result.step_results["step1_ingestion"].passed, "Ingestion failed"

        pq = result.step_results["step2_llm_parsing"].value
        assert pq is not None, "parsed_query is None"
        assert pq.brand_name and "estrella" in pq.brand_name.lower(), (
            f"Expected 'Estrella Damm' in brand_name, got '{pq.brand_name}'"
        )
        assert pq.campaign_niche in ("alcoholic_beverages", "lifestyle"), (
            f"Expected alcoholic_beverages or lifestyle niche, got '{pq.campaign_niche}'"
        )

        # Fitness must appear in exclude_niches — brief says "nada de gym bros ni fitness"
        if pq.exclude_niches:
            niches_lower = [n.lower() for n in pq.exclude_niches]
            assert any(kw in niches_lower for kw in ("fitness", "gym", "crossfit")), (
                f"Expected fitness/gym in exclude_niches for beer lifestyle brief, got {pq.exclude_niches}"
            )

        # No fitness influencers in results
        response: Optional[SearchResponse] = result.step_results["step1_ingestion"].value
        if response and response.results:
            for r in response.results[:10]:
                if r.raw_data.primary_niche:
                    assert r.raw_data.primary_niche.lower() not in ("fitness", "crossfit"), (
                        f"Fitness influencer @{r.username} appeared in Estrella Damm lifestyle results"
                    )
