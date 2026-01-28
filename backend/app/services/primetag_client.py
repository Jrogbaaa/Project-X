import httpx
import time
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import quote, urlparse

from app.config import get_settings
from app.schemas.primetag import MediaKitSearchResponse, MediaKitDetailResponse, MediaKitSummary, MediaKit
from app.core.exceptions import PrimeTagAPIError

# Configure logger for PrimeTag API calls
logger = logging.getLogger(__name__)


class PrimeTagClient:
    """Client for PrimeTag API interactions."""

    # Platform type mapping (per Primetag API docs)
    PLATFORM_YOUTUBE = 1
    PLATFORM_INSTAGRAM = 2
    PLATFORM_TIKTOK = 3
    PLATFORM_FACEBOOK = 4
    PLATFORM_PINTEREST = 5
    PLATFORM_LINKEDIN = 6

    def __init__(self):
        self.settings = get_settings()
        # Use the base URL from settings (configured in .env)
        self.base_url = self.settings.primetag_api_base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.settings.primetag_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        logger.info(f"PrimeTag client initialized with base URL: {self.base_url}")

    @staticmethod
    def extract_encrypted_username(mediakit_url: str) -> Optional[str]:
        """
        Extract the encrypted username from a mediakit URL.
        URL format: https://mediakit.primetag.com/instagram/Z0FBQUF...
        Returns the last path segment (the encrypted username).
        """
        if not mediakit_url:
            return None
        try:
            parsed = urlparse(mediakit_url)
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) >= 2:
                # Last part is the encrypted username
                return path_parts[-1]
            return None
        except Exception:
            return None

    async def search_media_kits(
        self,
        search_query: str,
        platform_type: int = PLATFORM_INSTAGRAM,
        limit: int = 50
    ) -> List[MediaKitSummary]:
        """
        Search for influencers by username (fulltext search).
        GET /media-kits?platform_type=1&search=query&limit=50
        """
        params = {
            "platform_type": platform_type,
            "search": search_query,
            "limit": min(limit, 50),  # Max 50 per API docs
        }

        start_time = time.time()

        url = f"{self.base_url}/media-kits"
        logger.info(f"PrimeTag search: GET {url} | params={params}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    params=params,
                    headers=self.headers,
                    timeout=30.0
                )

                response_time_ms = int((time.time() - start_time) * 1000)
                logger.info(f"PrimeTag search response: status={response.status_code} | time={response_time_ms}ms")

                if response.status_code != 200:
                    logger.error(f"PrimeTag search failed: status={response.status_code} | body={response.text[:500]}")
                    raise PrimeTagAPIError(
                        f"Search failed with status {response.status_code}",
                        response.text
                    )

                data = response.json()
                # Parse response
                items = data.get("response", [])
                logger.info(f"PrimeTag search success: found {len(items)} results for query='{search_query}'")
                return [MediaKitSummary(**item) for item in items]

            except httpx.TimeoutException:
                logger.error(f"PrimeTag search timeout after 30s: url={url}")
                raise PrimeTagAPIError("Request timed out", None)
            except httpx.RequestError as e:
                logger.error(f"PrimeTag search request error: {type(e).__name__}: {str(e)}")
                raise PrimeTagAPIError(f"Request failed: {str(e)}", None)

    async def get_media_kit_detail(
        self,
        username_encrypted: str,
        platform_type: int = PLATFORM_INSTAGRAM
    ) -> MediaKit:
        """
        Get full MediaKit data including audience metrics.
        GET /media-kits/{platform_type}/{username_encrypted}
        """
        # URL encode the username in case it contains special characters
        encoded_username = quote(username_encrypted, safe="")
        url = f"{self.base_url}/media-kits/{platform_type}/{encoded_username}"

        start_time = time.time()
        logger.info(f"PrimeTag detail: GET {url}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )

                response_time_ms = int((time.time() - start_time) * 1000)
                logger.info(f"PrimeTag detail response: status={response.status_code} | time={response_time_ms}ms")

                if response.status_code == 404:
                    logger.warning(f"PrimeTag media kit not found: {username_encrypted}")
                    raise PrimeTagAPIError(
                        f"Media kit not found for {username_encrypted}",
                        response.text
                    )

                if response.status_code != 200:
                    logger.error(f"PrimeTag detail failed: status={response.status_code} | body={response.text[:500]}")
                    raise PrimeTagAPIError(
                        f"Detail fetch failed with status {response.status_code}",
                        response.text
                    )

                data = response.json()
                logger.info(f"PrimeTag detail success for: {username_encrypted}")
                return MediaKit(**data.get("response", data))

            except httpx.TimeoutException:
                logger.error(f"PrimeTag detail timeout after 30s: url={url}")
                raise PrimeTagAPIError("Request timed out", None)
            except httpx.RequestError as e:
                logger.error(f"PrimeTag detail request error: {type(e).__name__}: {str(e)}")
                raise PrimeTagAPIError(f"Request failed: {str(e)}", None)

    def extract_metrics(self, detail: MediaKit) -> Dict[str, Any]:
        """Extract required metrics from MediaKit detail response."""
        audience_data = detail.audience_data
        followers_data = None

        if audience_data and audience_data.followers:
            followers_data = audience_data.followers

        # Extract genders
        genders = {}
        if followers_data and followers_data.genders:
            genders = followers_data.genders

        # Extract age distribution from average_age list
        age_distribution = {}
        if followers_data and followers_data.average_age:
            for age_item in followers_data.average_age:
                if isinstance(age_item, dict):
                    age_range = age_item.get("range", age_item.get("name", ""))
                    percentage = age_item.get("percentage", age_item.get("value", 0))
                    if age_range:
                        age_distribution[age_range] = percentage

        # Extract geography from location_by_country list
        geography = {}
        if followers_data and followers_data.location_by_country:
            for loc_item in followers_data.location_by_country:
                if isinstance(loc_item, dict):
                    country_code = loc_item.get("code", loc_item.get("country", ""))
                    percentage = loc_item.get("percentage", loc_item.get("value", 0))
                    if country_code:
                        geography[country_code] = percentage

        # Get credibility score
        credibility_score = None
        if followers_data:
            credibility_score = followers_data.audience_credibility_percentage

        # Extract interests/categories for niche matching
        interests = detail.interests or []

        # Extract brand mentions for creative fit scoring
        brand_mention_usernames = []
        if detail.brand_mentions:
            for mention in detail.brand_mentions:
                if hasattr(mention, 'username') and mention.username:
                    brand_mention_usernames.append(mention.username)
                elif isinstance(mention, dict) and mention.get('username'):
                    brand_mention_usernames.append(mention['username'])

        return {
            "credibility_score": credibility_score,
            "engagement_rate": detail.avg_engagement_rate,
            "follower_growth_rate_6m": detail.followers_last_6_month_evolution,
            "follower_count": detail.followers,
            "avg_likes": detail.avg_likes,
            "avg_comments": detail.avg_comments,
            "avg_views": detail.avg_views,
            "audience_genders": genders,
            "audience_age_distribution": age_distribution,
            "audience_geography": geography,
            "display_name": detail.fullname,
            "bio": detail.description,
            "profile_picture_url": detail.profile_pic,
            "profile_url": detail.profile_url,
            "is_verified": detail.is_verified,
            # New fields for brand/creative matching
            "interests": interests,
            "brand_mentions": brand_mention_usernames,
        }

    async def autocomplete(self, query: str) -> List[MediaKitSummary]:
        """
        Get autocomplete suggestions.
        GET /media-kit-auto-complete?search=query
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/media-kit-auto-complete",
                    params={"search": query},
                    headers=self.headers,
                    timeout=15.0
                )

                if response.status_code != 200:
                    return []

                data = response.json()
                items = data.get("response", [])
                return [MediaKitSummary(**item) for item in items]

            except Exception:
                return []
