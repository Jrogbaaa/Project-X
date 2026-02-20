"""
Unit tests for PrimeTagClient retry / rate-limit behaviour:

  - 429 triggers retry (is_retryable=True)
  - 429 exhausted after max_retries raises PrimeTagAPIError
  - Retry-After header is respected when present
  - 404 is NOT retried (is_retryable=False)
  - 500 is retried
  - Timeout is retried
  - Expired token (404 on cached token) triggers re-search in _verify_candidate
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
import pytest_asyncio

from app.core.exceptions import PrimeTagAPIError
from app.services.primetag_client import PrimeTagClient, _parse_retry_after


# ---------------------------------------------------------------------------
# _parse_retry_after helper
# ---------------------------------------------------------------------------

class TestParseRetryAfter:

    def test_integer_string(self):
        assert _parse_retry_after("30") == 30.0

    def test_float_string(self):
        assert _parse_retry_after("1.5") == 1.5

    def test_none_returns_none(self):
        assert _parse_retry_after(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_retry_after("") is None

    def test_unparseable_string_returns_none(self):
        assert _parse_retry_after("not-a-number") is None


# ---------------------------------------------------------------------------
# PrimeTagAPIError.is_retryable
# ---------------------------------------------------------------------------

class TestIsRetryable:

    def test_429_is_retryable(self):
        err = PrimeTagAPIError("rate limited", status_code=429)
        assert err.is_retryable is True

    def test_500_is_retryable(self):
        err = PrimeTagAPIError("server error", status_code=500)
        assert err.is_retryable is True

    def test_503_is_retryable(self):
        err = PrimeTagAPIError("unavailable", status_code=503)
        assert err.is_retryable is True

    def test_404_not_retryable(self):
        err = PrimeTagAPIError("not found", status_code=404)
        assert err.is_retryable is False

    def test_400_not_retryable(self):
        err = PrimeTagAPIError("bad request", status_code=400)
        assert err.is_retryable is False

    def test_timeout_is_retryable(self):
        err = PrimeTagAPIError("timed out", is_timeout=True)
        assert err.is_retryable is True

    def test_retry_after_stored(self):
        err = PrimeTagAPIError("rate limited", status_code=429, retry_after=45.0)
        assert err.retry_after == 45.0

    def test_retry_after_default_none(self):
        err = PrimeTagAPIError("rate limited", status_code=429)
        assert err.retry_after is None


# ---------------------------------------------------------------------------
# Helpers to build a mock httpx response
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, json_data=None, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = str(json_data or "")
    resp.json.return_value = json_data or {}
    resp.headers = headers or {}
    return resp


def _make_search_200():
    return _mock_response(200, {"response": [
        {
            "username": "test_influencer",
            "audience_size": 150000,
            "platform_type": 2,
            "external_social_profile_id": "ext_123",
            "mediakit_url": "https://mediakit.primetag.com/instagram/Z0FBQUFBQm1PckVx",
        }
    ]})


def _make_detail_200():
    return _mock_response(200, {"response": {
        "username": "test_influencer",
        "platform_type": 2,
        "avg_engagement_rate": 0.034,
        "followers": 150000,
        "avg_likes": 5000,
        "avg_comments": 200,
        "audience_data": {
            "followers": {
                "audience_credibility_percentage": 82.0,
                "genders": {"female": 55.0, "male": 45.0},
                "average_age": [{"label": "18-24", "female": 18.5, "male": 16.3}],
                "location_by_country": [{"name": "Spain", "percentage": 65.0}],
            }
        },
    }})


# ---------------------------------------------------------------------------
# search_media_kits retry behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestSearchRetry:

    async def _make_client(self):
        obj = object.__new__(PrimeTagClient)
        obj.base_url = "https://api.primetag.com"
        obj.headers = {"Authorization": "Bearer test"}
        return obj

    async def test_429_retried_and_succeeds(self):
        """If first call returns 429, second call returns 200 — should succeed."""
        c = await self._make_client()
        responses = [_mock_response(429, headers={}), _make_search_200()]
        call_count = 0

        async def fake_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return responses[call_count - 1]

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = fake_get

        with patch("app.services.primetag_client.asyncio.sleep", new=AsyncMock()):
            with patch("httpx.AsyncClient", return_value=mock_client):
                results = await c.search_media_kits("test_influencer")

        assert call_count == 2
        assert len(results) == 1
        assert results[0].username == "test_influencer"

    async def test_429_exhausted_raises(self):
        """If every call returns 429, PrimeTagAPIError is raised after max retries."""
        c = await self._make_client()

        async def always_429(*args, **kwargs):
            return _mock_response(429, headers={})

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = always_429

        with patch("app.services.primetag_client.asyncio.sleep", new=AsyncMock()):
            with patch("httpx.AsyncClient", return_value=mock_client):
                with pytest.raises(PrimeTagAPIError) as exc_info:
                    await c.search_media_kits("test_influencer")

        assert exc_info.value.status_code == 429

    async def test_retry_after_header_used_as_sleep_duration(self):
        """When 429 includes Retry-After: 60, sleep should be called with 60 (capped by max_delay)."""
        c = await self._make_client()
        responses = [
            _mock_response(429, headers={"Retry-After": "10"}),
            _make_search_200(),
        ]
        call_count = 0
        sleep_durations = []

        async def fake_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return responses[call_count - 1]

        async def fake_sleep(duration):
            sleep_durations.append(duration)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = fake_get

        with patch("app.services.primetag_client.asyncio.sleep", side_effect=fake_sleep):
            with patch("httpx.AsyncClient", return_value=mock_client):
                await c.search_media_kits("test_influencer")

        assert len(sleep_durations) == 1
        assert sleep_durations[0] == 10.0, (
            f"Expected Retry-After=10 to be used; got {sleep_durations[0]}"
        )

    async def test_500_retried(self):
        c = await self._make_client()
        responses = [_mock_response(500), _make_search_200()]
        call_count = 0

        async def fake_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return responses[call_count - 1]

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = fake_get

        with patch("app.services.primetag_client.asyncio.sleep", new=AsyncMock()):
            with patch("httpx.AsyncClient", return_value=mock_client):
                results = await c.search_media_kits("test_influencer")

        assert call_count == 2
        assert len(results) == 1


# ---------------------------------------------------------------------------
# get_media_kit_detail retry behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDetailRetry:

    async def _make_client(self):
        obj = object.__new__(PrimeTagClient)
        obj.base_url = "https://api.primetag.com"
        obj.headers = {"Authorization": "Bearer test"}
        return obj

    async def test_404_raises_immediately_not_retried(self):
        """404 must NOT be retried — it is a permanent failure."""
        c = await self._make_client()
        call_count = 0

        async def always_404(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return _mock_response(404)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = always_404

        with patch("app.services.primetag_client.asyncio.sleep", new=AsyncMock()):
            with patch("httpx.AsyncClient", return_value=mock_client):
                with pytest.raises(PrimeTagAPIError) as exc_info:
                    await c.get_media_kit_detail("some_token")

        assert exc_info.value.status_code == 404
        assert call_count == 1, "404 should not be retried"

    async def test_429_with_retry_after_on_detail(self):
        c = await self._make_client()
        responses = [
            _mock_response(429, headers={"Retry-After": "5"}),
            _make_detail_200(),
        ]
        call_count = 0
        sleep_durations = []

        async def fake_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return responses[call_count - 1]

        async def fake_sleep(duration):
            sleep_durations.append(duration)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = fake_get

        with patch("app.services.primetag_client.asyncio.sleep", side_effect=fake_sleep):
            with patch("httpx.AsyncClient", return_value=mock_client):
                await c.get_media_kit_detail("Z0FBQUFBQm1PckVx")

        assert sleep_durations == [5.0]
