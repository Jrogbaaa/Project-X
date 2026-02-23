"""
Unit tests for FilterService.

Tests the filtering logic for influencer candidates.
"""
import pytest
from typing import Dict, Any
from uuid import uuid4

from app.services.filter_service import FilterService
from app.schemas.search import FilterConfig
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
        "country": "Spain",
    }
    defaults.update(kwargs)
    return defaults


def create_mock_query(**kwargs) -> ParsedSearchQuery:
    """Create a mock parsed query for testing."""
    defaults = {
        "target_count": 5,
        "min_credibility_score": 70.0,
        "min_spain_audience_pct": 60.0,
        "min_engagement_rate": None,
    }
    defaults.update(kwargs)
    return ParsedSearchQuery(**defaults)


# ============================================================
# MAX FOLLOWERS FILTER TESTS
# ============================================================

class TestMaxFollowersFilter:
    """Tests for maximum follower count filter."""
    
    def test_under_max_passes(self, filter_service, default_config):
        """Influencer under max followers should pass."""
        influencers = [
            create_mock_influencer(follower_count=1_000_000),
            create_mock_influencer(follower_count=2_000_000),
        ]
        query = create_mock_query()
        
        results = filter_service.apply_filters(influencers, query, default_config)
        
        assert len(results) == 2
    
    def test_over_max_filtered(self, filter_service, default_config):
        """Influencer over max followers should be filtered."""
        influencers = [
            create_mock_influencer(follower_count=1_000_000),
            create_mock_influencer(follower_count=5_000_000),  # Over 2.5M default
        ]
        query = create_mock_query()
        
        results = filter_service.apply_filters(influencers, query, default_config)
        
        assert len(results) == 1
        assert results[0]["follower_count"] == 1_000_000
    
    def test_unknown_followers_passes(self, filter_service, default_config):
        """Influencer with unknown followers should pass."""
        influencers = [
            create_mock_influencer(follower_count=None),
        ]
        query = create_mock_query()
        
        results = filter_service.apply_filters(influencers, query, default_config)
        
        assert len(results) == 1


# ============================================================
# CREDIBILITY FILTER TESTS
# ============================================================

class TestCredibilityFilter:
    """Tests for credibility score filter."""
    
    def test_above_threshold_passes(self, filter_service, default_config):
        """Influencer above credibility threshold should pass."""
        influencers = [
            create_mock_influencer(credibility_score=85.0),
            create_mock_influencer(credibility_score=75.0),
        ]
        query = create_mock_query(min_credibility_score=70.0)
        
        results = filter_service.apply_filters(influencers, query, default_config)
        
        assert len(results) == 2
    
    def test_below_threshold_filtered(self, filter_service, default_config):
        """Influencer below credibility threshold should be filtered."""
        influencers = [
            create_mock_influencer(credibility_score=85.0),
            create_mock_influencer(credibility_score=65.0),  # Below 70
        ]
        query = create_mock_query(min_credibility_score=70.0)
        
        results = filter_service.apply_filters(influencers, query, default_config)
        
        assert len(results) == 1
        assert results[0]["credibility_score"] == 85.0
    
    def test_none_credibility_strict_filtered(self, filter_service, default_config):
        """None credibility should be filtered in strict mode."""
        influencers = [
            create_mock_influencer(credibility_score=None),
        ]
        query = create_mock_query()
        
        results = filter_service.apply_filters(influencers, query, default_config, lenient_mode=False)
        
        assert len(results) == 0
    
    def test_none_credibility_lenient_passes(self, filter_service, default_config):
        """None credibility should pass in lenient mode."""
        influencers = [
            create_mock_influencer(credibility_score=None),
        ]
        query = create_mock_query()
        
        results = filter_service.apply_filters(influencers, query, default_config, lenient_mode=True)
        
        assert len(results) == 1


# ============================================================
# SPAIN AUDIENCE FILTER TESTS
# ============================================================

class TestSpainAudienceFilter:
    """Tests for Spain audience percentage filter."""
    
    def test_above_threshold_passes(self, filter_service, default_config):
        """Influencer above Spain % threshold should pass."""
        influencers = [
            create_mock_influencer(audience_geography={"ES": 75.0}),
            create_mock_influencer(audience_geography={"ES": 65.0}),
        ]
        query = create_mock_query(min_spain_audience_pct=60.0)
        
        results = filter_service.apply_filters(influencers, query, default_config)
        
        assert len(results) == 2
    
    def test_below_threshold_filtered(self, filter_service, default_config):
        """Influencer below Spain % threshold should be filtered."""
        influencers = [
            create_mock_influencer(audience_geography={"ES": 75.0}),
            create_mock_influencer(audience_geography={"ES": 40.0}),  # Below 60
        ]
        query = create_mock_query(min_spain_audience_pct=60.0)
        
        results = filter_service.apply_filters(influencers, query, default_config)
        
        assert len(results) == 1
    
    def test_lowercase_es_key_works(self, filter_service, default_config):
        """Both 'ES' and 'es' keys should work."""
        influencers = [
            create_mock_influencer(audience_geography={"es": 70.0}),
        ]
        query = create_mock_query(min_spain_audience_pct=60.0)
        
        results = filter_service.apply_filters(influencers, query, default_config)
        
        assert len(results) == 1
    
    def test_spain_country_fallback(self, filter_service, default_config):
        """Spanish influencer without geography data should pass via country fallback."""
        influencers = [
            create_mock_influencer(
                audience_geography=None,
                country="Spain"
            ),
        ]
        query = create_mock_query()
        
        results = filter_service.apply_filters(influencers, query, default_config, lenient_mode=True)
        
        assert len(results) == 1


# ============================================================
# ENGAGEMENT FILTER TESTS
# ============================================================

class TestEngagementFilter:
    """Tests for engagement rate filter."""
    
    def test_no_engagement_filter_all_pass(self, filter_service, default_config):
        """Without engagement filter, all should pass."""
        influencers = [
            create_mock_influencer(engagement_rate=1.0),
            create_mock_influencer(engagement_rate=5.0),
        ]
        query = create_mock_query(min_engagement_rate=None)
        
        results = filter_service.apply_filters(influencers, query, default_config)
        
        assert len(results) == 2
    
    def test_above_engagement_passes(self, filter_service, default_config):
        """Influencer above engagement threshold should pass."""
        influencers = [
            create_mock_influencer(engagement_rate=0.05),  # 5%
        ]
        query = create_mock_query(min_engagement_rate=3.0)  # 3%
        
        results = filter_service.apply_filters(influencers, query, default_config)
        
        assert len(results) == 1
    
    def test_below_engagement_filtered(self, filter_service, default_config):
        """Influencer below engagement threshold should be filtered."""
        influencers = [
            create_mock_influencer(engagement_rate=0.01),  # 1%
        ]
        query = create_mock_query(min_engagement_rate=3.0)  # 3%
        
        results = filter_service.apply_filters(influencers, query, default_config)
        
        assert len(results) == 0


# ============================================================
# AUDIENCE GENDER FILTER TESTS
# ============================================================

class TestAudienceGenderFilter:
    """Tests for audience gender filter."""
    
    def test_no_gender_filter_all_pass(self, filter_service, default_config):
        """Without gender filter, all should pass."""
        influencers = [
            create_mock_influencer(audience_genders={"male": 70.0, "female": 30.0}),
            create_mock_influencer(audience_genders={"male": 30.0, "female": 70.0}),
        ]
        query = create_mock_query()
        
        results = filter_service.apply_filters(influencers, query, default_config)
        
        assert len(results) == 2
    
    def test_female_audience_filter(self, filter_service, default_config):
        """Female audience filter should keep majority female audiences."""
        influencers = [
            create_mock_influencer(audience_genders={"male": 70.0, "female": 30.0}),
            create_mock_influencer(audience_genders={"male": 30.0, "female": 70.0}),
        ]
        query = create_mock_query(target_audience_gender=GenderFilter.FEMALE)
        
        results = filter_service.apply_filters(influencers, query, default_config)
        
        assert len(results) == 1
        assert results[0]["audience_genders"]["female"] == 70.0
    
    def test_male_audience_filter(self, filter_service, default_config):
        """Male audience filter should keep majority male audiences."""
        influencers = [
            create_mock_influencer(audience_genders={"male": 70.0, "female": 30.0}),
            create_mock_influencer(audience_genders={"male": 30.0, "female": 70.0}),
        ]
        query = create_mock_query(target_audience_gender=GenderFilter.MALE)
        
        results = filter_service.apply_filters(influencers, query, default_config)
        
        assert len(results) == 1
        assert results[0]["audience_genders"]["male"] == 70.0


# ============================================================
# LENIENT MODE TESTS
# ============================================================

class TestLenientMode:
    """Tests for lenient mode filtering."""
    
    def test_strict_mode_filters_missing_data(self, filter_service, default_config):
        """Strict mode should filter influencers with missing metrics."""
        influencers = [
            create_mock_influencer(
                credibility_score=None,
                audience_geography=None
            ),
        ]
        query = create_mock_query()
        
        results = filter_service.apply_filters(
            influencers, query, default_config, lenient_mode=False
        )
        
        assert len(results) == 0
    
    def test_lenient_mode_allows_missing_data(self, filter_service, default_config):
        """Lenient mode should allow influencers with missing metrics."""
        influencers = [
            create_mock_influencer(
                credibility_score=None,
                audience_geography=None,
                country="Spain"
            ),
        ]
        query = create_mock_query()
        
        results = filter_service.apply_filters(
            influencers, query, default_config, lenient_mode=True
        )
        
        assert len(results) == 1


# ============================================================
# FOLLOWER RANGE FILTER TESTS (HARD FILTER)
# ============================================================

class TestFollowerRangeFilter:
    """Tests for preferred follower range hard filter."""

    def test_within_range_passes(self, filter_service, default_config):
        """Influencer within preferred range should pass."""
        influencers = [
            create_mock_influencer(follower_count=50_000),
            create_mock_influencer(follower_count=100_000),
        ]
        query = create_mock_query(preferred_follower_min=15_000, preferred_follower_max=150_000)
        results = filter_service.apply_filters(influencers, query, default_config)
        assert len(results) == 2

    def test_over_max_filtered(self, filter_service, default_config):
        """Influencer over preferred max should be hard-filtered."""
        influencers = [
            create_mock_influencer(follower_count=50_000),
            create_mock_influencer(follower_count=500_000),
            create_mock_influencer(follower_count=1_500_000),
        ]
        query = create_mock_query(preferred_follower_min=15_000, preferred_follower_max=150_000)
        results = filter_service.apply_filters(influencers, query, default_config)
        assert len(results) == 1
        assert results[0]["follower_count"] == 50_000

    def test_under_min_filtered(self, filter_service, default_config):
        """Influencer under preferred min should be hard-filtered."""
        influencers = [
            create_mock_influencer(follower_count=5_000),
            create_mock_influencer(follower_count=50_000),
        ]
        query = create_mock_query(preferred_follower_min=15_000, preferred_follower_max=150_000)
        results = filter_service.apply_filters(influencers, query, default_config)
        assert len(results) == 1
        assert results[0]["follower_count"] == 50_000

    def test_unknown_followers_passes(self, filter_service, default_config):
        """Influencer with unknown follower count should pass (can't verify)."""
        influencers = [
            create_mock_influencer(follower_count=None),
            create_mock_influencer(follower_count=0),
        ]
        query = create_mock_query(preferred_follower_min=15_000, preferred_follower_max=150_000)
        results = filter_service.apply_filters(influencers, query, default_config)
        assert len(results) == 2

    def test_no_range_specified_all_pass(self, filter_service, default_config):
        """Without preferred range, all should pass."""
        influencers = [
            create_mock_influencer(follower_count=1_000),
            create_mock_influencer(follower_count=5_000_000),
        ]
        query = create_mock_query()
        results = filter_service.apply_filters(influencers, query, default_config)
        # 5M still filtered by max_follower_count (2.5M default)
        assert len(results) == 1


# ============================================================
# INFLUENCER GENDER FILTER TESTS
# ============================================================

class TestInfluencerGenderFilter:
    """Tests for influencer's own gender filter."""

    def test_female_filter_removes_males_by_audience(self, filter_service, default_config):
        """Female filter should remove influencers with female-heavy audience (= likely male influencer)."""
        influencers = [
            create_mock_influencer(
                display_name="María García",
                audience_genders={"male": 70.0, "female": 30.0},
            ),
            create_mock_influencer(
                display_name="Carlos Ruiz",
                audience_genders={"male": 30.0, "female": 70.0},
            ),
        ]
        query = create_mock_query(influencer_gender=GenderFilter.FEMALE)
        results = filter_service.apply_filters(influencers, query, default_config)
        assert len(results) == 1
        assert results[0]["display_name"] == "María García"

    def test_female_filter_removes_males_by_name(self, filter_service, default_config):
        """Female filter should remove obvious male names when no audience data."""
        influencers = [
            create_mock_influencer(display_name="Belén Aguilera", audience_genders=None),
            create_mock_influencer(display_name="Facundo Hernández", audience_genders=None),
            create_mock_influencer(display_name="Jose Maria Manzanares", audience_genders=None),
        ]
        query = create_mock_query(influencer_gender=GenderFilter.FEMALE)
        results = filter_service.apply_filters(influencers, query, default_config, lenient_mode=True)
        assert len(results) == 1
        assert "Belén" in results[0]["display_name"]

    def test_male_filter_removes_females_by_name(self, filter_service, default_config):
        """Male filter should remove obvious female names when no audience data."""
        influencers = [
            create_mock_influencer(display_name="María López", audience_genders=None),
            create_mock_influencer(display_name="Carlos Ruiz", audience_genders=None),
        ]
        query = create_mock_query(influencer_gender=GenderFilter.MALE)
        results = filter_service.apply_filters(influencers, query, default_config, lenient_mode=True)
        assert len(results) == 1
        assert "Carlos" in results[0]["display_name"]

    def test_unknown_gender_passes(self, filter_service, default_config):
        """Influencer with indeterminate gender should pass through."""
        influencers = [
            create_mock_influencer(display_name="🌟 Creator 🌟", audience_genders=None, bio=""),
        ]
        query = create_mock_query(influencer_gender=GenderFilter.FEMALE)
        results = filter_service.apply_filters(influencers, query, default_config, lenient_mode=True)
        assert len(results) == 1

    def test_any_gender_all_pass(self, filter_service, default_config):
        """With gender=any, all should pass."""
        influencers = [
            create_mock_influencer(display_name="María"),
            create_mock_influencer(display_name="Carlos"),
        ]
        query = create_mock_query(influencer_gender=GenderFilter.ANY)
        results = filter_service.apply_filters(influencers, query, default_config)
        assert len(results) == 2

    def test_bio_pronouns_override_name(self, filter_service, default_config):
        """Bio pronouns should be used for gender inference."""
        influencers = [
            create_mock_influencer(
                display_name="Alex", bio="she/her | content creator", audience_genders=None
            ),
        ]
        query = create_mock_query(influencer_gender=GenderFilter.FEMALE)
        results = filter_service.apply_filters(influencers, query, default_config, lenient_mode=True)
        assert len(results) == 1


# ============================================================
# COMBINED FILTER TESTS
# ============================================================

class TestCombinedFilters:
    """Tests for multiple filters combined."""
    
    def test_all_filters_applied(self, filter_service, default_config):
        """All filters should be applied sequentially."""
        influencers = [
            # Passes all
            create_mock_influencer(
                username="passes_all",
                follower_count=500_000,
                credibility_score=85.0,
                audience_geography={"ES": 75.0}
            ),
            # Fails follower (too many)
            create_mock_influencer(
                username="too_many_followers",
                follower_count=5_000_000,
                credibility_score=85.0,
                audience_geography={"ES": 75.0}
            ),
            # Fails credibility
            create_mock_influencer(
                username="low_credibility",
                follower_count=500_000,
                credibility_score=50.0,
                audience_geography={"ES": 75.0}
            ),
            # Fails Spain %
            create_mock_influencer(
                username="low_spain",
                follower_count=500_000,
                credibility_score=85.0,
                audience_geography={"ES": 30.0}
            ),
        ]
        query = create_mock_query()
        
        results = filter_service.apply_filters(influencers, query, default_config)
        
        assert len(results) == 1
        assert results[0]["username"] == "passes_all"
    
    def test_filter_order_consistency(self, filter_service, default_config):
        """Filter order should be consistent regardless of input order."""
        influencers1 = [
            create_mock_influencer(username="a", credibility_score=85.0),
            create_mock_influencer(username="b", credibility_score=50.0),
        ]
        influencers2 = [
            create_mock_influencer(username="b", credibility_score=50.0),
            create_mock_influencer(username="a", credibility_score=85.0),
        ]
        query = create_mock_query()
        
        results1 = filter_service.apply_filters(influencers1, query, default_config)
        results2 = filter_service.apply_filters(influencers2, query, default_config)
        
        assert len(results1) == len(results2) == 1


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def filter_service():
    """Create a FilterService instance."""
    return FilterService()


@pytest.fixture
def default_config():
    """Create default filter config."""
    return FilterConfig(
        min_credibility_score=70.0,
        min_spain_audience_pct=60.0,
        max_follower_count=2_500_000,
    )
