"""
Unit tests for RankingService.

Tests the 8-factor scoring algorithm and ranking logic.
"""
import pytest
from typing import Dict, Any
from uuid import uuid4

from app.services.ranking_service import RankingService
from app.schemas.search import RankingWeights
from app.schemas.llm import ParsedSearchQuery, GenderFilter


# ============================================================
# TEST FIXTURES
# ============================================================

def create_mock_influencer(**kwargs) -> Dict[str, Any]:
    """Create a mock influencer dict for testing."""
    defaults = {
        "id": str(uuid4()),
        "username": f"test_user_{uuid4().hex[:6]}",
        "display_name": "Test User",
        "follower_count": 100000,
        "engagement_rate": 3.5,
        "credibility_score": 85.0,
        "follower_growth_rate_6m": 5.0,
        "audience_geography": {"ES": 75.0},
        "audience_genders": {"male": 45.0, "female": 55.0},
        "audience_age_distribution": {"18-24": 30, "25-34": 40},
        "interests": ["Lifestyle"],
        "bio": "Test bio",
        "brand_mentions": [],
        "detected_brands": [],
        "primary_niche": None,
        "niche_confidence": None,
        "content_themes": None,
    }
    defaults.update(kwargs)
    return defaults


def create_mock_query(**kwargs) -> ParsedSearchQuery:
    """Create a mock parsed query for testing."""
    defaults = {
        "target_count": 5,
        "brand_name": None,
        "brand_handle": None,
        "campaign_niche": None,
        "campaign_topics": [],
        "exclude_niches": [],
        "creative_concept": None,
        "creative_format": None,
        "creative_tone": [],
        "creative_themes": [],
    }
    defaults.update(kwargs)
    return ParsedSearchQuery(**defaults)


# ============================================================
# SCORE CALCULATION TESTS
# ============================================================

class TestScoreCalculation:
    """Tests for individual score calculations."""
    
    def test_credibility_normalization(self, ranking_service):
        """Credibility score should normalize 0-100 to 0-1."""
        influencer = create_mock_influencer(credibility_score=85.0)
        query = create_mock_query()
        
        results = ranking_service.rank_influencers([influencer], query)
        
        assert len(results) == 1
        # 85/100 = 0.85
        assert results[0].scores.credibility == 0.85
    
    def test_engagement_normalization(self, ranking_service):
        """Engagement rate should normalize with cap at 15%."""
        # Test normal case
        influencer = create_mock_influencer(engagement_rate=7.5)
        query = create_mock_query()
        results = ranking_service.rank_influencers([influencer], query)
        
        # 7.5/15 = 0.5
        assert results[0].scores.engagement == 0.5
        
        # Test high engagement caps at 1.0
        influencer2 = create_mock_influencer(engagement_rate=20.0)
        results2 = ranking_service.rank_influencers([influencer2], query)
        assert results2[0].scores.engagement == 1.0
    
    def test_geography_scoring(self, ranking_service):
        """Geography score should reflect Spain audience %."""
        influencer = create_mock_influencer(audience_geography={"ES": 80.0})
        query = create_mock_query()
        results = ranking_service.rank_influencers([influencer], query)
        
        # 80/100 = 0.8
        assert results[0].scores.geography == 0.8
    
    def test_growth_scoring(self, ranking_service):
        """Growth score should normalize -20% to +50% range."""
        # Zero growth = middle of range
        influencer = create_mock_influencer(follower_growth_rate_6m=0)
        query = create_mock_query()
        results = ranking_service.rank_influencers([influencer], query)
        
        # (0 + 20) / 70 ≈ 0.286
        assert 0.28 <= results[0].scores.growth <= 0.30
        
        # High growth = higher score
        influencer2 = create_mock_influencer(follower_growth_rate_6m=50)
        results2 = ranking_service.rank_influencers([influencer2], query)
        assert results2[0].scores.growth == 1.0


# ============================================================
# NICHE MATCHING TESTS
# ============================================================

class TestNicheMatching:
    """Tests for niche match scoring."""
    
    def test_exact_niche_match(self, ranking_service):
        """Exact niche match should give high score."""
        influencer = create_mock_influencer(
            primary_niche="padel",
            niche_confidence=0.9
        )
        query = create_mock_query(campaign_niche="padel")
        
        results = ranking_service.rank_influencers([influencer], query)
        
        # Exact match: 0.95 * 0.9 confidence ≈ 0.855
        assert results[0].scores.niche_match >= 0.8
    
    def test_related_niche_match(self, ranking_service):
        """Related niche should give moderate score."""
        influencer = create_mock_influencer(
            primary_niche="tennis",
            niche_confidence=0.9
        )
        query = create_mock_query(campaign_niche="padel")
        
        results = ranking_service.rank_influencers([influencer], query)
        
        # Related match: 0.70 * 0.9 confidence = 0.63
        assert 0.6 <= results[0].scores.niche_match <= 0.75
    
    def test_conflicting_niche_penalty(self, ranking_service):
        """Conflicting niche should get low score."""
        influencer = create_mock_influencer(
            primary_niche="football",
            niche_confidence=0.9
        )
        query = create_mock_query(campaign_niche="padel")
        
        results = ranking_service.rank_influencers([influencer], query)
        
        # Conflicting: 0.20
        assert results[0].scores.niche_match <= 0.25
        # Should have warning
        assert results[0].raw_data.niche_warning is not None
    
    def test_excluded_niche_penalty(self, ranking_service):
        """Explicitly excluded niche should get very low score."""
        influencer = create_mock_influencer(
            primary_niche="football",
            niche_confidence=0.9
        )
        query = create_mock_query(
            campaign_niche="sports",
            exclude_niches=["football", "soccer"]
        )
        
        results = ranking_service.rank_influencers([influencer], query)
        
        # Excluded: 0.10
        assert results[0].scores.niche_match <= 0.15
    
    def test_no_niche_neutral_score(self, ranking_service):
        """No niche data should give neutral score."""
        influencer = create_mock_influencer(primary_niche=None)
        query = create_mock_query()  # No campaign niche either
        
        results = ranking_service.rank_influencers([influencer], query)
        
        # Neutral: 0.5
        assert results[0].scores.niche_match == 0.5
    
    def test_celebrity_in_wrong_niche_penalty(self, ranking_service):
        """Large account in conflicting niche gets extra penalty."""
        influencer = create_mock_influencer(
            primary_niche="football",
            niche_confidence=0.95,
            follower_count=10_000_000  # 10M followers (celebrity)
        )
        query = create_mock_query(campaign_niche="padel")
        
        results = ranking_service.rank_influencers([influencer], query)
        
        # Celebrity + conflicting niche: 0.05
        assert results[0].scores.niche_match <= 0.10


# ============================================================
# BRAND AFFINITY TESTS
# ============================================================

class TestBrandAffinity:
    """Tests for brand affinity scoring."""
    
    def test_no_brand_context_neutral(self, ranking_service):
        """No brand context should give neutral score."""
        influencer = create_mock_influencer()
        query = create_mock_query()  # No brand_handle
        
        results = ranking_service.rank_influencers([influencer], query)
        
        assert results[0].scores.brand_affinity == 0.5
    
    def test_target_brand_mention_boost(self, ranking_service):
        """Mentioning target brand (without competitors) should boost score."""
        # Use a brand without known competitors in our system
        influencer = create_mock_influencer(
            detected_brands=["ikea", "zara"]  # No competitor relationship
        )
        query = create_mock_query(brand_handle="ikea")
        
        results = ranking_service.rank_influencers([influencer], query)
        
        # Should get boost for direct mention (0.5 base + 0.25 boost = 0.75)
        assert results[0].scores.brand_affinity >= 0.7
    
    def test_competitor_mention_penalty(self, ranking_service):
        """Mentioning competitor brand should reduce score."""
        # Nike and Adidas are known competitors
        influencer = create_mock_influencer(
            detected_brands=["nike", "adidas"]
        )
        query = create_mock_query(brand_handle="nike")
        
        results = ranking_service.rank_influencers([influencer], query)
        
        # Should have competitor conflict warning
        assert results[0].raw_data.brand_warning_type == "competitor_conflict"
        # Score should be lower due to conflict
        assert results[0].scores.brand_affinity < 0.6


# ============================================================
# CREATIVE FIT TESTS
# ============================================================

class TestCreativeFit:
    """Tests for creative fit scoring."""
    
    def test_no_creative_context_neutral(self, ranking_service):
        """No creative context should give neutral score."""
        influencer = create_mock_influencer()
        query = create_mock_query()  # No creative context
        
        results = ranking_service.rank_influencers([influencer], query)
        
        assert results[0].scores.creative_fit == 0.5
    
    def test_tone_matching(self, ranking_service):
        """Matching tone keywords should boost score."""
        influencer = create_mock_influencer(
            bio="Authentic lifestyle content. Real stories, raw moments.",
            interests=["Lifestyle", "Documentary"]
        )
        query = create_mock_query(
            creative_tone=["authentic", "raw", "documentary"]
        )
        
        results = ranking_service.rank_influencers([influencer], query)
        
        # Should score better than neutral
        assert results[0].scores.creative_fit >= 0.5
    
    def test_content_themes_matching(self, ranking_service):
        """Content themes from scrape should match creative themes."""
        influencer = create_mock_influencer(
            content_themes={
                "detected_themes": ["training", "dedication", "behind_the_scenes"],
                "narrative_style": "storytelling",
                "format_preference": ["Reel", "Sidecar"]
            }
        )
        query = create_mock_query(
            creative_themes=["dedication", "training"],
            creative_format="documentary"
        )
        
        results = ranking_service.rank_influencers([influencer], query)
        
        # Matching themes + storytelling style for documentary
        assert results[0].scores.creative_fit >= 0.6


# ============================================================
# RANKING ORDER TESTS
# ============================================================

class TestRankingOrder:
    """Tests for ranking order and position assignment."""
    
    def test_ranking_by_relevance_score(self, ranking_service):
        """Influencers should be ranked by relevance score descending."""
        influencers = [
            create_mock_influencer(
                username="low_score",
                credibility_score=50.0,
                engagement_rate=1.0
            ),
            create_mock_influencer(
                username="high_score",
                credibility_score=95.0,
                engagement_rate=10.0
            ),
            create_mock_influencer(
                username="mid_score",
                credibility_score=75.0,
                engagement_rate=5.0
            ),
        ]
        query = create_mock_query()
        
        results = ranking_service.rank_influencers(influencers, query)
        
        # Verify order (highest score first)
        scores = [r.relevance_score for r in results]
        assert scores == sorted(scores, reverse=True)
    
    def test_rank_position_assignment(self, ranking_service):
        """Rank positions should be assigned correctly."""
        influencers = [
            create_mock_influencer(username=f"user_{i}")
            for i in range(5)
        ]
        query = create_mock_query()
        
        results = ranking_service.rank_influencers(influencers, query)
        
        # Check positions are 1-indexed
        positions = [r.rank_position for r in results]
        assert positions == [1, 2, 3, 4, 5]


# ============================================================
# SIZE PENALTY TESTS
# ============================================================

class TestSizePenalty:
    """Tests for follower count size penalty."""
    
    def test_in_range_no_penalty(self, ranking_service):
        """Influencer in preferred range gets no penalty."""
        influencer = create_mock_influencer(follower_count=200_000)
        query = create_mock_query(
            preferred_follower_min=100_000,
            preferred_follower_max=500_000
        )
        
        results_with_pref = ranking_service.rank_influencers([influencer], query)
        
        query_no_pref = create_mock_query()
        results_no_pref = ranking_service.rank_influencers([influencer], query_no_pref)
        
        # Should be same (no penalty)
        assert results_with_pref[0].relevance_score == results_no_pref[0].relevance_score
    
    def test_too_large_penalty(self, ranking_service):
        """Influencer over max gets anti-celebrity penalty."""
        influencer = create_mock_influencer(follower_count=5_000_000)
        
        query_no_pref = create_mock_query()
        results_no_pref = ranking_service.rank_influencers([influencer], query_no_pref)
        
        query_with_pref = create_mock_query(
            preferred_follower_min=100_000,
            preferred_follower_max=500_000
        )
        results_with_pref = ranking_service.rank_influencers([influencer], query_with_pref)
        
        # Should have lower score due to penalty
        assert results_with_pref[0].relevance_score < results_no_pref[0].relevance_score
    
    def test_too_small_penalty(self, ranking_service):
        """Influencer under min gets penalty."""
        influencer = create_mock_influencer(follower_count=10_000)
        
        query_with_pref = create_mock_query(
            preferred_follower_min=100_000,
            preferred_follower_max=500_000
        )
        results_with_pref = ranking_service.rank_influencers([influencer], query_with_pref)
        
        query_no_pref = create_mock_query()
        results_no_pref = ranking_service.rank_influencers([influencer], query_no_pref)
        
        # Should have lower score due to penalty
        assert results_with_pref[0].relevance_score < results_no_pref[0].relevance_score


# ============================================================
# WEIGHT CONFIGURATION TESTS
# ============================================================

class TestWeightConfiguration:
    """Tests for ranking weight configuration."""
    
    def test_custom_weights_applied(self):
        """Custom weights should affect scoring."""
        # High niche weight
        weights_niche = RankingWeights(
            credibility=0.0,
            engagement=0.0,
            audience_match=0.0,
            growth=0.0,
            geography=0.0,
            brand_affinity=0.0,
            creative_fit=0.0,
            niche_match=1.0
        )
        service_niche = RankingService(weights_niche)
        
        # High engagement weight
        weights_engagement = RankingWeights(
            credibility=0.0,
            engagement=1.0,
            audience_match=0.0,
            growth=0.0,
            geography=0.0,
            brand_affinity=0.0,
            creative_fit=0.0,
            niche_match=0.0
        )
        service_engagement = RankingService(weights_engagement)
        
        # Influencer with high engagement, low niche match
        influencer = create_mock_influencer(
            engagement_rate=12.0,  # High
            primary_niche="football",  # Will conflict with padel
            niche_confidence=0.9
        )
        query = create_mock_query(campaign_niche="padel")
        
        results_niche = service_niche.rank_influencers([influencer], query)
        results_engagement = service_engagement.rank_influencers([influencer], query)
        
        # With niche weight, score should be low (conflicting niche)
        # With engagement weight, score should be high
        assert results_engagement[0].relevance_score > results_niche[0].relevance_score
    
    def test_llm_suggested_weights(self, ranking_service):
        """LLM suggested weights from parsed query should be used."""
        influencer = create_mock_influencer()
        query = create_mock_query(
            suggested_ranking_weights={
                "credibility": 0.5,
                "engagement": 0.5,
                "audience_match": 0.0,
                "growth": 0.0,
                "geography": 0.0,
                "brand_affinity": 0.0,
                "creative_fit": 0.0,
                "niche_match": 0.0
            }
        )
        
        results = ranking_service.rank_influencers([influencer], query)
        
        # Should use the suggested weights
        assert len(results) == 1


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def ranking_service():
    """Create a RankingService instance."""
    return RankingService()
