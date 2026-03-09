"""
Result differentiation tests.

Validates that the search pipeline returns meaningfully different influencer
sets for different brand briefs, proving brand intelligence drives result
selection — not a fixed ordering.

Tests are split into:
  - Unit tests: fast, no external calls (RankingService only)
  - Integration tests (marked @pytest.mark.e2e): require real DB + OpenAI

Run:
  # Unit test only (fast)
  cd backend && pytest tests/test_result_differentiation.py::TestRankingDifferentiation -v

  # Full integration (requires DB + OpenAI, ~60-90s)
  cd backend && pytest tests/test_result_differentiation.py -v -s -m e2e
"""
import pytest
import logging
from typing import Set

from app.services.ranking_service import RankingService
from app.services.search_service import SearchService
from app.schemas.search import SearchRequest, SearchResponse
from app.schemas.llm import ParsedSearchQuery

logger = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================

def _usernames(response: SearchResponse) -> Set[str]:
    return {r.username for r in response.results}


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union)


def _print_overlap_table(
    labels: list[str],
    sets: list[Set[str]],
) -> None:
    """Print a pairwise Jaccard similarity table."""
    print("\n  Pairwise Jaccard Similarity:")
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            sim = _jaccard(sets[i], sets[j])
            overlap = sets[i] & sets[j]
            print(
                f"    {labels[i]} vs {labels[j]}: "
                f"{sim:.1%} ({len(overlap)} shared of {len(sets[i] | sets[j])} unique)"
            )
            if overlap:
                print(f"      Shared: {', '.join(sorted(overlap))}")


# ============================================================
# UNIT TEST — RankingService differentiation (no external calls)
# ============================================================

class TestRankingDifferentiation:
    """Verify RankingService scores influencers differently based on niche."""

    def test_ranking_differentiates_by_niche(self, influencer_factory, parsed_query_factory):
        """A fitness influencer should score higher than a fashion one for a fitness campaign."""
        ranking = RankingService()

        fitness_inf = influencer_factory.create(
            username="fit_guru",
            primary_niche="fitness",
            interests=["Fitness", "Health"],
            engagement_rate=4.0,
            follower_count=200_000,
        )
        fashion_inf = influencer_factory.create(
            username="style_queen",
            primary_niche="fashion",
            interests=["Fashion", "Beauty"],
            engagement_rate=4.0,
            follower_count=200_000,
        )
        food_inf = influencer_factory.create(
            username="chef_master",
            primary_niche="food",
            interests=["Lifestyle", "Family"],
            engagement_rate=4.0,
            follower_count=200_000,
        )

        query = parsed_query_factory.create(
            campaign_niche="fitness",
            campaign_topics=["gym", "workout", "nutrition"],
            brand_name="MyProtein",
        )

        ranked = ranking.rank_influencers(
            [fitness_inf, fashion_inf, food_inf],
            query,
        )

        fitness_result = next(r for r in ranked if r.username == "fit_guru")
        fashion_result = next(r for r in ranked if r.username == "style_queen")
        food_result = next(r for r in ranked if r.username == "chef_master")

        print(f"\n  Fitness campaign ranking:")
        print(f"    fit_guru:    niche={fitness_result.scores.niche_match:.3f}  total={fitness_result.relevance_score:.3f}")
        print(f"    style_queen: niche={fashion_result.scores.niche_match:.3f}  total={fashion_result.relevance_score:.3f}")
        print(f"    chef_master: niche={food_result.scores.niche_match:.3f}  total={food_result.relevance_score:.3f}")

        assert fitness_result.scores.niche_match > fashion_result.scores.niche_match, \
            "Fitness influencer should have higher niche_match than fashion for fitness campaign"
        assert fitness_result.scores.niche_match > food_result.scores.niche_match, \
            "Fitness influencer should have higher niche_match than food for fitness campaign"
        assert fitness_result.relevance_score > fashion_result.relevance_score, \
            "Fitness influencer should rank higher overall for fitness campaign"

    def test_ranking_differentiates_home_vs_sports(self, influencer_factory, parsed_query_factory):
        """A home_decor influencer should score higher for an IKEA campaign than a sports one."""
        ranking = RankingService()

        home_inf = influencer_factory.create(
            username="decor_lover",
            primary_niche="home_decor",
            interests=["Lifestyle", "Family"],
            engagement_rate=3.5,
            follower_count=150_000,
        )
        sports_inf = influencer_factory.create(
            username="goal_scorer",
            primary_niche="football",
            interests=["Sports", "Soccer"],
            engagement_rate=5.0,
            follower_count=500_000,
        )

        query = parsed_query_factory.create(
            campaign_niche="home_decor",
            campaign_topics=["interior design", "furniture", "home"],
            brand_name="IKEA",
        )

        ranked = ranking.rank_influencers([home_inf, sports_inf], query)

        home_result = next(r for r in ranked if r.username == "decor_lover")
        sports_result = next(r for r in ranked if r.username == "goal_scorer")

        print(f"\n  IKEA campaign ranking:")
        print(f"    decor_lover: niche={home_result.scores.niche_match:.3f}  total={home_result.relevance_score:.3f}")
        print(f"    goal_scorer: niche={sports_result.scores.niche_match:.3f}  total={sports_result.relevance_score:.3f}")

        assert home_result.scores.niche_match > sports_result.scores.niche_match, \
            "Home decor influencer should have higher niche_match for IKEA campaign"
        assert home_result.relevance_score > sports_result.relevance_score, \
            "Home decor influencer should rank higher despite lower followers/engagement"

    def test_excluded_niche_gets_penalized(self, influencer_factory, parsed_query_factory):
        """An influencer in an excluded niche should score much lower."""
        ranking = RankingService()

        padel_inf = influencer_factory.create(
            username="padel_pro",
            primary_niche="padel",
            interests=["Sports", "Tennis"],
            engagement_rate=3.0,
            follower_count=120_000,
        )
        football_inf = influencer_factory.create(
            username="football_star",
            primary_niche="football",
            interests=["Sports", "Soccer"],
            engagement_rate=6.0,
            follower_count=800_000,
        )

        query = parsed_query_factory.create(
            campaign_niche="padel",
            exclude_niches=["football", "soccer"],
            brand_name="Bullpadel",
        )

        ranked = ranking.rank_influencers([padel_inf, football_inf], query)

        padel_result = next(r for r in ranked if r.username == "padel_pro")
        football_result = next(r for r in ranked if r.username == "football_star")

        print(f"\n  Padel campaign with football exclusion:")
        print(f"    padel_pro:     niche={padel_result.scores.niche_match:.3f}  total={padel_result.relevance_score:.3f}")
        print(f"    football_star: niche={football_result.scores.niche_match:.3f}  total={football_result.relevance_score:.3f}")

        assert padel_result.scores.niche_match > football_result.scores.niche_match, \
            "Padel influencer must score higher than football (excluded niche)"
        assert padel_result.relevance_score > football_result.relevance_score, \
            "Padel influencer must rank higher despite fewer followers"


# ============================================================
# INTEGRATION TESTS — Full pipeline (requires DB + OpenAI)
# ============================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestPipelineDifferentiation:
    """
    Verify the full search pipeline produces different results for
    different brand briefs.

    Run:
      cd backend && pytest tests/test_result_differentiation.py::TestPipelineDifferentiation -v -s
    """

    BRIEFS = {
        "home": "Campaign for IKEA Spain — 5 home and lifestyle influencers for interior design and home decor content.",
        "padel": "Find 5 influencers for Adidas Padel. Premium padel equipment campaign. No football or soccer influencers.",
        "fashion": "Loewe luxury fashion campaign — 5 fashion influencers with premium, high-end aesthetic in Spain.",
    }

    async def test_different_briefs_produce_different_results(self, search_service: SearchService):
        """Three distinct brand briefs must return significantly different influencer sets."""
        responses: dict[str, SearchResponse] = {}

        for label, brief in self.BRIEFS.items():
            request = SearchRequest(query=brief, limit=10)
            responses[label] = await search_service.execute_search(request)
            count = len(responses[label].results)
            niche = responses[label].parsed_query.campaign_niche
            print(f"\n  {label}: {count} results, campaign_niche={niche}")

        labels = list(responses.keys())
        sets = [_usernames(responses[l]) for l in labels]

        _print_overlap_table(labels, sets)

        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                sim = _jaccard(sets[i], sets[j])
                assert sim < 0.5, (
                    f"{labels[i]} vs {labels[j]}: Jaccard similarity {sim:.1%} >= 50%. "
                    f"Results are too similar — brand intelligence is not differentiating."
                )

    async def test_brand_intelligence_sets_campaign_niche(self, search_service: SearchService):
        """The LLM + brand lookup pipeline must extract the correct campaign_niche for known brands."""
        cases = [
            ("5 influencers for IKEA Spain home furniture campaign", ["home_decor", "lifestyle", "home"]),
            ("Find influencers for Bullpadel padel equipment brand in Spain", ["padel", "tennis", "sports"]),
            ("Loewe luxury fashion campaign in Spain, 5 fashion influencers", ["fashion", "luxury"]),
        ]

        for brief, expected_niches in cases:
            request = SearchRequest(query=brief, limit=5)
            response = await search_service.execute_search(request)
            niche = response.parsed_query.campaign_niche

            print(f"\n  Brief: \"{brief[:60]}...\"")
            print(f"    Extracted niche: {niche}")
            print(f"    Expected one of: {expected_niches}")

            assert niche is not None, f"campaign_niche is None for: {brief}"
            assert niche.lower() in expected_niches, (
                f"Extracted niche '{niche}' not in expected {expected_niches} for: {brief}"
            )

    async def test_niche_discovery_returns_relevant_influencers(self, search_service: SearchService):
        """Padel search should return padel/tennis/fitness influencers, never football."""
        request = SearchRequest(
            query="Find 10 influencers for a padel brand. No football or soccer.",
            limit=10,
        )
        response = await search_service.execute_search(request)

        allowed_niches = {"padel", "tennis", "fitness", "racket_sports", "sports", "lifestyle"}
        forbidden_niches = {"football", "soccer", "fútbol"}

        results = response.results
        assert len(results) > 0, "Padel search returned no results"

        relevant_count = 0
        for r in results:
            niche = (getattr(r.raw_data, "primary_niche", None) or "").lower()
            print(f"  @{r.username}: primary_niche={niche or '(none)'}")

            if niche in forbidden_niches:
                pytest.fail(f"@{r.username} has forbidden niche '{niche}' in padel search")

            if niche in allowed_niches:
                relevant_count += 1

        relevance_pct = relevant_count / len(results) if results else 0
        print(f"\n  Relevant niche coverage: {relevant_count}/{len(results)} ({relevance_pct:.0%})")

        assert relevance_pct >= 0.4, (
            f"Only {relevance_pct:.0%} of results have a relevant niche. "
            f"Expected >= 40% in {allowed_niches}"
        )
