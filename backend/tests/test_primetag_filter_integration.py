"""
Integration tests: extract_metrics() → FilterService._passes_spain_pct()

These tests prove the full pipeline from raw PrimeTag response data through
metric extraction to Spain% filter pass/fail — without needing a database.

Also covers:
  - strict vs lenient mode
  - España / Espana variants pass the filter after the mapping fix
  - Credibility filter integration
  - Username matching edge cases in _verify_candidate (mocked)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.filter_service import FilterService
from app.services.primetag_client import PrimeTagClient

from tests.fixtures.primetag_fixtures import make_media_kit, make_media_kit_summary


# Instantiate services once (stateless)
_client = object.__new__(PrimeTagClient)
_filter = FilterService()


def _geography(spain_pct: float) -> dict:
    """Build a minimal geography dict as extract_metrics would produce it."""
    kit = make_media_kit(location_by_country=[
        {"name": "Spain", "percentage": spain_pct},
        {"name": "Mexico", "percentage": max(0.0, 15.0 - spain_pct * 0.1)},
    ])
    return _client.extract_metrics(kit)["audience_geography"]


# ---------------------------------------------------------------------------
# Spain % threshold — pass / fail
# ---------------------------------------------------------------------------

class TestSpainFilterThreshold:

    def test_65_passes_60_threshold(self):
        geo = _geography(65.0)
        assert _filter._passes_spain_pct({"audience_geography": geo}, 60.0, False) is True

    def test_59_fails_60_threshold(self):
        geo = _geography(59.0)
        assert _filter._passes_spain_pct({"audience_geography": geo}, 60.0, False) is False

    def test_exactly_60_passes(self):
        geo = _geography(60.0)
        assert _filter._passes_spain_pct({"audience_geography": geo}, 60.0, False) is True

    def test_0_fails_strict(self):
        geo = _geography(0.0)
        # 0% — no ES key after filtering
        assert _filter._passes_spain_pct({"audience_geography": geo}, 60.0, False) is False

    def test_0_passes_lenient(self):
        geo = _geography(0.0)
        assert _filter._passes_spain_pct({"audience_geography": geo}, 60.0, True) is True

    def test_empty_geography_fails_strict(self):
        assert _filter._passes_spain_pct({"audience_geography": {}}, 60.0, False) is False

    def test_empty_geography_passes_lenient(self):
        assert _filter._passes_spain_pct({"audience_geography": {}}, 60.0, True) is True


# ---------------------------------------------------------------------------
# España / Espana variants reach ES key through filter
# ---------------------------------------------------------------------------

class TestSpainVariantsPassFilter:

    def _geo_from_name(self, country_name: str, pct: float) -> dict:
        kit = make_media_kit(location_by_country=[{"name": country_name, "percentage": pct}])
        return _client.extract_metrics(kit)["audience_geography"]

    def test_espana_accent_65_passes(self):
        geo = self._geo_from_name("España", 65.0)
        assert geo.get("ES") == 65.0
        assert _filter._passes_spain_pct({"audience_geography": geo}, 60.0, False) is True

    def test_espana_no_accent_65_passes(self):
        geo = self._geo_from_name("Espana", 65.0)
        assert geo.get("ES") == 65.0
        assert _filter._passes_spain_pct({"audience_geography": geo}, 60.0, False) is True

    def test_espana_59_fails(self):
        geo = self._geo_from_name("España", 59.0)
        assert _filter._passes_spain_pct({"audience_geography": geo}, 60.0, False) is False


# ---------------------------------------------------------------------------
# Credibility filter integration
# ---------------------------------------------------------------------------

class TestCredibilityFilterIntegration:

    def test_credibility_82_passes_70_threshold(self):
        kit = make_media_kit(platform_type=2, credibility=82.0)
        metrics = _client.extract_metrics(kit)
        assert _filter._passes_credibility(
            {"credibility_score": metrics["credibility_score"]}, 70.0, False
        ) is True

    def test_credibility_65_fails_70_threshold(self):
        kit = make_media_kit(platform_type=2, credibility=65.0)
        metrics = _client.extract_metrics(kit)
        assert _filter._passes_credibility(
            {"credibility_score": metrics["credibility_score"]}, 70.0, False
        ) is False

    def test_tiktok_null_credibility_fails_strict(self):
        """TikTok → credibility_score=None → strict mode rejects."""
        kit = make_media_kit(platform_type=6, credibility=80.0)
        metrics = _client.extract_metrics(kit)
        assert metrics["credibility_score"] is None
        assert _filter._passes_credibility(
            {"credibility_score": None}, 70.0, False
        ) is False

    def test_tiktok_null_credibility_passes_lenient(self):
        """TikTok → credibility_score=None → lenient mode accepts."""
        kit = make_media_kit(platform_type=6, credibility=80.0)
        metrics = _client.extract_metrics(kit)
        assert metrics["credibility_score"] is None
        assert _filter._passes_credibility(
            {"credibility_score": None}, 70.0, True
        ) is True


# ---------------------------------------------------------------------------
# _verify_candidate: expired token re-search (mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestExpiredTokenResearch:
    """
    Proves that _verify_candidate retries with a fresh token when the cached
    encrypted token returns 404 from the detail endpoint.
    """

    async def _make_search_service(self):
        """Build a SearchService with all external dependencies mocked."""
        from app.services.search_service import SearchService
        from app.core.exceptions import PrimeTagAPIError
        from tests.fixtures.primetag_fixtures import make_media_kit

        svc = object.__new__(SearchService)

        # Fresh detail response
        fresh_detail = make_media_kit(
            platform_type=2,
            location_by_country=[{"name": "Spain", "percentage": 65.0}],
        )

        # Summary returned by re-search
        fresh_summary = make_media_kit_summary(username="influencer_x")

        primetag_mock = AsyncMock()
        primetag_mock.search_media_kits = AsyncMock(return_value=[fresh_summary])

        call_count = {"detail": 0}

        async def detail_side_effect(token, platform_type):
            call_count["detail"] += 1
            if call_count["detail"] == 1:
                raise PrimeTagAPIError("expired", status_code=404)
            return fresh_detail

        primetag_mock.get_media_kit_detail = AsyncMock(side_effect=detail_side_effect)
        primetag_mock.extract_metrics = PrimeTagClient.extract_metrics.__get__(
            object.__new__(PrimeTagClient)
        )

        cache_mock = AsyncMock()
        cache_mock.upsert_influencer = AsyncMock(return_value=MagicMock(
            username="influencer_x",
            audience_geography={"ES": 65.0},
            credibility_score=82.0,
            engagement_rate=0.034,
        ))

        svc.primetag = primetag_mock
        svc.cache_service = cache_mock
        return svc, call_count

    async def test_404_on_cached_token_triggers_re_search_and_succeeds(self):
        from app.models.influencer import Influencer
        from datetime import datetime, timedelta

        svc, call_count = await self._make_search_service()

        # Influencer with a stale cached encrypted token
        inf = MagicMock(spec=Influencer)
        inf.username = "influencer_x"
        inf.primetag_encrypted_username = "STALE_TOKEN"
        inf.external_social_profile_id = None
        inf.follower_count = 150_000
        inf.cache_expires_at = datetime.utcnow() - timedelta(hours=1)  # expired cache

        # _has_full_metrics must return False to force re-verification
        with patch.object(svc, "_has_full_metrics", return_value=False):
            result = await svc._verify_candidate(inf)

        assert result is not None, "Should succeed after re-search with fresh token"
        # detail was called twice: once for stale token (404), once for fresh token
        assert call_count["detail"] == 2
        # search was called once (re-search after 404)
        svc.primetag.search_media_kits.assert_called_once()

    async def test_404_without_cached_token_returns_none(self):
        """If token wasn't cached and search found nobody, return None."""
        from app.models.influencer import Influencer
        from app.core.exceptions import PrimeTagAPIError
        from datetime import datetime, timedelta

        svc = object.__new__(
            __import__("app.services.search_service", fromlist=["SearchService"]).SearchService
        )
        primetag_mock = AsyncMock()
        primetag_mock.search_media_kits = AsyncMock(return_value=[])  # nobody found
        svc.primetag = primetag_mock
        svc.cache_service = AsyncMock()

        inf = MagicMock(spec=Influencer)
        inf.username = "ghost_user"
        inf.primetag_encrypted_username = None
        inf.cache_expires_at = datetime.utcnow() - timedelta(hours=1)

        with patch.object(svc, "_has_full_metrics", return_value=False):
            result = await svc._verify_candidate(inf)

        assert result is None
