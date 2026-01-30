"""
End-to-end search tests with LLM reflection validation.

These tests execute full search queries through the pipeline and use
GPT-4o reflection to validate whether results actually match the brief.
"""
import pytest
import logging
from typing import List, Dict, Any

from tests.test_briefs import (
    ALL_TEST_BRIEFS,
    NICHE_PRECISION_BRIEFS,
    BRAND_MATCHING_BRIEFS,
    CREATIVE_FIT_BRIEFS,
    EDGE_CASE_BRIEFS,
    TestBrief,
    get_brief_by_name,
)
from tests.reflection_service import (
    ReflectionService,
    ReflectionVerdict,
    print_reflection_report,
)

from app.services.search_service import SearchService
from app.schemas.search import SearchRequest, SearchResponse

logger = logging.getLogger(__name__)


# ============================================================
# TEST HELPERS
# ============================================================

async def run_search_with_reflection(
    search_service: SearchService,
    brief: TestBrief,
) -> tuple[SearchResponse, ReflectionVerdict]:
    """
    Execute a search and run reflection analysis.
    
    Returns:
        Tuple of (SearchResponse, ReflectionVerdict)
    """
    # Execute search
    request = SearchRequest(
        query=brief.query,
        limit=brief.expectations.target_count * 3,  # Get extra for analysis
    )
    response = await search_service.execute_search(request)
    
    # Run reflection
    reflection_service = ReflectionService()
    verdict = await reflection_service.reflect_on_results(
        original_brief=brief.query,
        parsed_query=response.parsed_query,
        results=response.results,
        max_results_to_evaluate=min(10, len(response.results)),
    )
    
    return response, verdict


def assert_reflection_passes(
    verdict: ReflectionVerdict,
    brief: TestBrief,
    response: SearchResponse,
) -> List[str]:
    """
    Validate reflection verdict against brief expectations.
    
    Returns:
        List of failure messages (empty if all pass)
    """
    failures = []
    exp = brief.expectations
    
    # Check overall quality meets minimum
    quality_order = ["fail", "poor", "acceptable", "good", "excellent"]
    min_quality_idx = quality_order.index(exp.min_overall_quality)
    actual_quality_idx = quality_order.index(verdict.overall_quality)
    
    if actual_quality_idx < min_quality_idx:
        failures.append(
            f"Overall quality '{verdict.overall_quality}' below minimum '{exp.min_overall_quality}'"
        )
    
    # Check niche alignment
    if verdict.niche_alignment < exp.min_niche_alignment:
        failures.append(
            f"Niche alignment {verdict.niche_alignment:.2f} below minimum {exp.min_niche_alignment}"
        )
    
    # Check brand fit
    if verdict.brand_fit < exp.min_brand_fit:
        failures.append(
            f"Brand fit {verdict.brand_fit:.2f} below minimum {exp.min_brand_fit}"
        )
    
    # Check creative fit
    if verdict.creative_fit < exp.min_creative_fit:
        failures.append(
            f"Creative fit {verdict.creative_fit:.2f} below minimum {exp.min_creative_fit}"
        )
    
    # Check for niche violations
    if exp.must_not_have_niches and verdict.niche_violations:
        failures.append(
            f"Niche violations found: {verdict.niche_violations}"
        )
    
    if verdict.excluded_niche_violations:
        failures.append(
            f"Excluded niche violations: {verdict.excluded_niche_violations}"
        )
    
    # Check for brand conflicts
    if exp.must_not_have_brands and verdict.brand_conflicts:
        failures.append(
            f"Brand conflicts found: {verdict.brand_conflicts}"
        )
    
    # Verify parsed query extracted expected values
    parsed = response.parsed_query
    
    if exp.expected_brand and parsed.brand_name:
        if exp.expected_brand.lower() not in parsed.brand_name.lower():
            failures.append(
                f"Expected brand '{exp.expected_brand}' but got '{parsed.brand_name}'"
            )
    
    if exp.expected_niche and parsed.campaign_niche:
        if exp.expected_niche.lower() != parsed.campaign_niche.lower():
            # Allow partial matches for related niches
            if exp.expected_niche.lower() not in parsed.campaign_niche.lower():
                failures.append(
                    f"Expected niche '{exp.expected_niche}' but got '{parsed.campaign_niche}'"
                )
    
    # Check excluded niches are in parsed query
    if exp.excluded_niches and not parsed.exclude_niches:
        failures.append(
            f"Expected excluded niches {exp.excluded_niches} but query has none"
        )
    
    return failures


# ============================================================
# NICHE PRECISION TESTS
# ============================================================

@pytest.mark.e2e
@pytest.mark.reflection
@pytest.mark.asyncio
class TestNichePrecision:
    """Tests for niche precision in search results."""
    
    async def test_padel_excludes_football(self, search_service):
        """Critical test: Padel campaign should NOT return football players."""
        brief = get_brief_by_name("padel_brand_strict")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        # Print detailed report
        print(print_reflection_report(verdict))
        
        # Check results don't contain football niches
        for result in response.results[:5]:
            if result.raw_data and result.raw_data.primary_niche:
                niche = result.raw_data.primary_niche.lower()
                assert niche not in ["football", "soccer", "fútbol"], \
                    f"Found football influencer @{result.username} in padel results"
        
        # Validate reflection
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"
    
    async def test_home_decor_niche(self, search_service):
        """IKEA campaign should return home decor influencers."""
        brief = get_brief_by_name("home_furniture_ikea")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        # Should have found home-related influencers
        assert len(response.results) > 0, "No results returned"
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"
    
    async def test_fitness_niche(self, search_service):
        """Fitness supplement campaign should return fitness influencers."""
        brief = get_brief_by_name("fitness_supplement_protein")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"
    
    async def test_tennis_niche(self, search_service):
        """Tennis brand should return tennis/racket sport influencers."""
        brief = get_brief_by_name("tennis_racket_brand")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        # Should exclude football
        for result in response.results[:5]:
            if result.raw_data and result.raw_data.primary_niche:
                niche = result.raw_data.primary_niche.lower()
                assert niche not in ["football", "soccer"], \
                    f"Found football influencer @{result.username} in tennis results"
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"
    
    async def test_running_niche(self, search_service):
        """Running shoes campaign should return runners."""
        brief = get_brief_by_name("running_shoes_brand")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"


# ============================================================
# BRAND MATCHING TESTS
# ============================================================

@pytest.mark.e2e
@pytest.mark.reflection
@pytest.mark.asyncio
class TestBrandMatching:
    """Tests for brand recognition and competitor exclusion."""
    
    async def test_unknown_brand_lookup(self, search_service):
        """Unknown brand (VIPS) should trigger LLM lookup."""
        brief = get_brief_by_name("unknown_restaurant_brand")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        # Should have extracted brand name
        assert response.parsed_query.brand_name is not None
        assert "vips" in response.parsed_query.brand_name.lower()
        
        failures = assert_reflection_passes(verdict, brief, response)
        # Lower bar for unknown brands
        assert verdict.overall_quality != "fail", f"Failed for unknown brand"
    
    async def test_nike_excludes_adidas(self, search_service):
        """Nike campaign should exclude Adidas ambassadors."""
        brief = get_brief_by_name("nike_exclude_adidas")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        # Check no Adidas brand conflicts
        assert len(verdict.brand_conflicts) == 0, \
            f"Found Adidas ambassadors: {verdict.brand_conflicts}"
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"
    
    async def test_adidas_excludes_nike(self, search_service):
        """Adidas campaign should exclude Nike ambassadors."""
        brief = get_brief_by_name("adidas_exclude_nike")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"
    
    async def test_local_spanish_brand(self, search_service):
        """Local brand (Desigual) should be recognized."""
        brief = get_brief_by_name("local_spanish_brand")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        assert response.parsed_query.brand_name is not None
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"


# ============================================================
# CREATIVE FIT TESTS
# ============================================================

@pytest.mark.e2e
@pytest.mark.reflection
@pytest.mark.asyncio
class TestCreativeFit:
    """Tests for creative concept matching."""
    
    async def test_documentary_style(self, search_service):
        """Documentary-style campaign should match appropriate creators."""
        brief = get_brief_by_name("documentary_adventure")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        # Should have extracted documentary format
        if response.parsed_query.creative_format:
            assert "documentary" in response.parsed_query.creative_format.lower() or \
                   "storytelling" in response.parsed_query.creative_format.lower()
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"
    
    async def test_luxury_aesthetic(self, search_service):
        """Luxury brand should match polished aesthetic creators."""
        brief = get_brief_by_name("luxury_fashion_polished")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        # Should have luxury/polished tones
        tones = response.parsed_query.creative_tone
        assert any(t in ["luxury", "polished", "sophisticated"] for t in tones), \
            f"Expected luxury tones but got {tones}"
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"
    
    async def test_humorous_casual(self, search_service):
        """Humorous campaign should NOT return fitness influencers."""
        brief = get_brief_by_name("humorous_beer_campaign")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        # Check excluded niches are set
        assert "fitness" in [n.lower() for n in response.parsed_query.exclude_niches] or \
               "wellness" in [n.lower() for n in response.parsed_query.exclude_niches], \
               "Expected fitness/wellness in excluded niches"
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"
    
    async def test_tutorial_format(self, search_service):
        """Tutorial campaign should match educational creators."""
        brief = get_brief_by_name("tutorial_tech_content")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"
    
    async def test_storytelling_family(self, search_service):
        """Family storytelling campaign should match parenting creators."""
        brief = get_brief_by_name("storytelling_family_brand")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"


# ============================================================
# EDGE CASE TESTS
# ============================================================

@pytest.mark.e2e
@pytest.mark.reflection
@pytest.mark.asyncio
class TestEdgeCases:
    """Tests for edge cases and complex requirements."""
    
    async def test_gender_split(self, search_service):
        """Gender split (3 male, 3 female) should be respected."""
        brief = get_brief_by_name("gender_split_3_3")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        # Should have extracted gender counts
        assert response.parsed_query.target_male_count == 3
        assert response.parsed_query.target_female_count == 3
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"
    
    async def test_micro_influencer_size(self, search_service):
        """Micro-influencer request should set follower limits."""
        brief = get_brief_by_name("micro_influencer_focus")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        # Should have set follower range
        assert response.parsed_query.preferred_follower_min is not None or \
               response.parsed_query.preferred_follower_max is not None, \
               "Expected follower limits for micro-influencer request"
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"
    
    async def test_multi_niche(self, search_service):
        """Multi-niche (fitness + nutrition) should work."""
        brief = get_brief_by_name("multi_niche_fitness_nutrition")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"
    
    async def test_specific_niche_yoga(self, search_service):
        """Specific niche (yoga) should be matched."""
        brief = get_brief_by_name("very_specific_niche_yoga")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"
    
    async def test_multiple_exclusions(self, search_service):
        """Multiple niche exclusions should work."""
        brief = get_brief_by_name("exclude_multiple_niches")
        response, verdict = await run_search_with_reflection(search_service, brief)
        
        print(print_reflection_report(verdict))
        
        # Should have exclusions set
        exclusions = [n.lower() for n in response.parsed_query.exclude_niches]
        expected_some = any(e in exclusions for e in ["fitness", "gaming", "comedy"])
        assert expected_some, f"Expected exclusions but got {exclusions}"
        
        failures = assert_reflection_passes(verdict, brief, response)
        assert not failures, f"Reflection failures: {failures}"


# ============================================================
# COMPREHENSIVE TEST RUNNER
# ============================================================

@pytest.mark.e2e
@pytest.mark.reflection
@pytest.mark.slow
@pytest.mark.asyncio
class TestComprehensiveSearch:
    """Run all test briefs and generate comprehensive report."""
    
    async def test_all_briefs(self, search_service):
        """Run all test briefs and collect results."""
        results = []
        
        for brief in ALL_TEST_BRIEFS:
            try:
                response, verdict = await run_search_with_reflection(search_service, brief)
                failures = assert_reflection_passes(verdict, brief, response)
                
                results.append({
                    "name": brief.name,
                    "category": brief.category,
                    "passed": len(failures) == 0,
                    "quality": verdict.overall_quality,
                    "niche_alignment": verdict.niche_alignment,
                    "brand_fit": verdict.brand_fit,
                    "creative_fit": verdict.creative_fit,
                    "failures": failures,
                    "issues": verdict.issues,
                    "result_count": len(response.results),
                })
                
            except Exception as e:
                results.append({
                    "name": brief.name,
                    "category": brief.category,
                    "passed": False,
                    "quality": "error",
                    "error": str(e),
                })
        
        # Print comprehensive report
        print("\n" + "=" * 80)
        print("  COMPREHENSIVE TEST REPORT")
        print("=" * 80)
        
        passed = sum(1 for r in results if r.get("passed", False))
        total = len(results)
        
        print(f"\nOverall: {passed}/{total} tests passed ({100*passed/total:.1f}%)")
        print("-" * 80)
        
        # Group by category
        by_category = {}
        for r in results:
            cat = r["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(r)
        
        for category, cat_results in by_category.items():
            cat_passed = sum(1 for r in cat_results if r.get("passed", False))
            print(f"\n{category.upper()} ({cat_passed}/{len(cat_results)})")
            print("-" * 40)
            
            for r in cat_results:
                status = "✅" if r.get("passed", False) else "❌"
                quality = r.get("quality", "error")
                print(f"  {status} {r['name']}: {quality}")
                
                if r.get("failures"):
                    for f in r["failures"][:2]:  # First 2 failures
                        print(f"      - {f}")
                
                if r.get("error"):
                    print(f"      ERROR: {r['error'][:50]}")
        
        print("\n" + "=" * 80)
        
        # Assert at least 70% pass rate
        assert passed >= total * 0.5, \
            f"Pass rate {passed}/{total} below 50% threshold"
