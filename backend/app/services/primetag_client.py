import httpx
import time
import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable, TypeVar
from urllib.parse import quote, urlparse
from functools import wraps

from app.config import get_settings
from app.schemas.primetag import MediaKitSearchResponse, MediaKitDetailResponse, MediaKitSummary, MediaKit
from app.core.exceptions import PrimeTagAPIError

# Configure logger for PrimeTag API calls
logger = logging.getLogger(__name__)

# Type variable for generic return types
T = TypeVar('T')

# Country name to ISO 3166-1 alpha-2 code mapping
# PrimeTag API returns country names (e.g., "Spain") instead of codes (e.g., "ES")
COUNTRY_NAME_TO_ISO = {
    # Primary markets
    "Spain": "ES",
    "United States": "US",
    "Mexico": "MX",
    "Argentina": "AR",
    "Colombia": "CO",
    "Chile": "CL",
    "Peru": "PE",
    "Ecuador": "EC",
    "Venezuela": "VE",
    "Brazil": "BR",
    "Portugal": "PT",
    "France": "FR",
    "Italy": "IT",
    "Germany": "DE",
    "United Kingdom": "GB",
    "UK": "GB",
    "Canada": "CA",
    "Australia": "AU",
    # Additional common countries
    "India": "IN",
    "Indonesia": "ID",
    "Philippines": "PH",
    "Japan": "JP",
    "South Korea": "KR",
    "China": "CN",
    "Russia": "RU",
    "Turkey": "TR",
    "Poland": "PL",
    "Netherlands": "NL",
    "Belgium": "BE",
    "Switzerland": "CH",
    "Austria": "AT",
    "Sweden": "SE",
    "Norway": "NO",
    "Denmark": "DK",
    "Finland": "FI",
    "Ireland": "IE",
    "Greece": "GR",
    "Czech Republic": "CZ",
    "Romania": "RO",
    "Hungary": "HU",
    "Ukraine": "UA",
    "South Africa": "ZA",
    "Egypt": "EG",
    "Morocco": "MA",
    "Saudi Arabia": "SA",
    "United Arab Emirates": "AE",
    "UAE": "AE",
    "Israel": "IL",
    "Thailand": "TH",
    "Vietnam": "VN",
    "Malaysia": "MY",
    "Singapore": "SG",
    "New Zealand": "NZ",
    "Dominican Republic": "DO",
    "Puerto Rico": "PR",
    "Guatemala": "GT",
    "Costa Rica": "CR",
    "Panama": "PA",
    "Uruguay": "UY",
    "Paraguay": "PY",
    "Bolivia": "BO",
    "Honduras": "HN",
    "El Salvador": "SV",
    "Nicaragua": "NI",
    "Cuba": "CU",
}


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0
) -> Callable:
    """
    Decorator for exponential backoff retry on transient failures.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds (doubles each retry)
        max_delay: Maximum delay cap in seconds
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception: Optional[PrimeTagAPIError] = None
            
            for attempt in range(max_retries + 1):  # +1 for initial attempt
                try:
                    return await func(*args, **kwargs)
                except PrimeTagAPIError as e:
                    last_exception = e
                    
                    # Don't retry if error is not retryable
                    if not e.is_retryable:
                        logger.debug(f"Non-retryable error, not retrying: {e.message}")
                        raise
                    
                    # Don't retry if we've exhausted attempts
                    if attempt >= max_retries:
                        logger.warning(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff + jitter
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    # Add small jitter (10%) to prevent thundering herd
                    jitter = delay * 0.1 * (0.5 - asyncio.get_event_loop().time() % 1)
                    delay = max(0.1, delay + jitter)
                    
                    logger.info(
                        f"Retrying {func.__name__} in {delay:.2f}s "
                        f"(attempt {attempt + 1}/{max_retries}, error: {e.message})"
                    )
                    await asyncio.sleep(delay)
            
            # Should not reach here, but raise last exception if we do
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")
        
        return wrapper
    return decorator


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

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    async def search_media_kits(
        self,
        search_query: str,
        platform_type: int = PLATFORM_INSTAGRAM,
        limit: int = 50
    ) -> List[MediaKitSummary]:
        """
        Search for influencers by username (fulltext search).
        GET /media-kits?platform_type=1&search=query&limit=50
        
        Retries automatically on transient failures (timeouts, rate limits, 5xx).
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
                        response.text,
                        status_code=response.status_code
                    )

                data = response.json()
                # Parse response
                items = data.get("response", [])
                logger.info(f"PrimeTag search success: found {len(items)} results for query='{search_query}'")
                return [MediaKitSummary(**item) for item in items]

            except httpx.TimeoutException:
                logger.error(f"PrimeTag search timeout after 30s: url={url}")
                raise PrimeTagAPIError("Request timed out", None, is_timeout=True)
            except httpx.RequestError as e:
                logger.error(f"PrimeTag search request error: {type(e).__name__}: {str(e)}")
                raise PrimeTagAPIError(f"Request failed: {str(e)}", None)

    @with_retry(max_retries=3, base_delay=1.0, max_delay=30.0)
    async def get_media_kit_detail(
        self,
        username_encrypted: str,
        platform_type: int = PLATFORM_INSTAGRAM
    ) -> MediaKit:
        """
        Get full MediaKit data including audience metrics.
        GET /media-kits/{platform_type}/{username_encrypted}
        
        Retries automatically on transient failures (timeouts, rate limits, 5xx).
        404 errors are NOT retried (not found is a permanent state).
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
                        response.text,
                        status_code=404  # 404 is NOT retryable
                    )

                if response.status_code != 200:
                    logger.error(f"PrimeTag detail failed: status={response.status_code} | body={response.text[:500]}")
                    raise PrimeTagAPIError(
                        f"Detail fetch failed with status {response.status_code}",
                        response.text,
                        status_code=response.status_code
                    )

                data = response.json()
                logger.info(f"PrimeTag detail success for: {username_encrypted}")
                return MediaKit(**data.get("response", data))

            except httpx.TimeoutException:
                logger.error(f"PrimeTag detail timeout after 30s: url={url}")
                raise PrimeTagAPIError("Request timed out", None, is_timeout=True)
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
        # PrimeTag API returns country names (e.g., "Spain") in the "name" field,
        # not ISO codes. We need to map them to ISO codes for consistent storage.
        geography = {}
        if followers_data and followers_data.location_by_country:
            for loc_item in followers_data.location_by_country:
                if isinstance(loc_item, dict):
                    # PrimeTag returns "name" field with country name (e.g., "Spain")
                    country_name = loc_item.get("name", "")
                    # Handle both "percentage" and "value" field names
                    percentage = loc_item.get("percentage") or loc_item.get("value", 0)
                    
                    if country_name and percentage:
                        # Convert country name to ISO code
                        country_code = COUNTRY_NAME_TO_ISO.get(country_name)
                        if country_code:
                            geography[country_code] = percentage
                        else:
                            # Log unknown country for future mapping additions
                            logger.debug(f"Unknown country name in audience geography: {country_name}")
                            # Store with the original name as fallback (won't match ES filter but preserves data)
                            geography[country_name] = percentage

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

    @with_retry(max_retries=2, base_delay=0.5, max_delay=5.0)
    async def autocomplete(self, query: str) -> List[MediaKitSummary]:
        """
        Get autocomplete suggestions.
        GET /media-kit-auto-complete?search=query
        
        Uses lighter retry settings since autocomplete should be fast.
        Returns empty list on permanent failures (non-retryable errors).
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
                    # For autocomplete, we return empty on client errors (4xx)
                    # but raise retryable error on server errors (5xx) or rate limits
                    if response.status_code == 429 or response.status_code >= 500:
                        raise PrimeTagAPIError(
                            f"Autocomplete failed with status {response.status_code}",
                            response.text,
                            status_code=response.status_code
                        )
                    return []

                data = response.json()
                items = data.get("response", [])
                return [MediaKitSummary(**item) for item in items]

            except httpx.TimeoutException:
                raise PrimeTagAPIError("Autocomplete timed out", None, is_timeout=True)
            except PrimeTagAPIError:
                raise  # Re-raise our own errors for retry logic
            except Exception:
                return []
