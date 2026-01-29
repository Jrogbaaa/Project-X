"""
Apify Instagram Scraper Client

Integrates with apify/instagram-scraper actor to fetch post content
for niche detection enrichment.

Actor: apify/instagram-scraper
Pricing: ~$2.30 per 1000 results
Docs: https://apify.com/apify/instagram-scraper
"""

import httpx
import asyncio
import logging
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class InstagramPost:
    """Structured post data from Apify."""
    post_id: str
    shortcode: str
    post_url: str
    caption: str
    hashtags: List[str]
    mentions: List[str]
    post_type: str  # Image, Video, Sidecar, Reel
    posted_at: Optional[datetime]
    likes_count: int
    comments_count: int
    views_count: Optional[int]
    thumbnail_url: Optional[str]
    is_sponsored: bool
    owner_username: Optional[str] = None


class ApifyAPIError(Exception):
    """Apify API error."""
    pass


class ApifyInstagramClient:
    """Client for Apify Instagram Scraper.

    Uses the apify/instagram-scraper actor to fetch posts with captions,
    hashtags, and engagement metrics for niche detection.
    """

    ACTOR_ID = "apify/instagram-scraper"
    BASE_URL = "https://api.apify.com/v2"

    def __init__(self):
        settings = get_settings()
        self.api_token = settings.apify_api_token
        if not self.api_token:
            raise ApifyAPIError("APIFY_API_TOKEN not configured")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    async def scrape_user_posts(
        self,
        username: str,
        results_limit: int = 30,
        timeout_secs: int = 300
    ) -> List[InstagramPost]:
        """
        Scrape recent posts for a single user.

        Args:
            username: Instagram username (without @)
            results_limit: Number of posts to fetch (default 30)
            timeout_secs: Max wait time for actor run

        Returns:
            List of InstagramPost objects
        """
        # Clean username
        username = username.lstrip('@').lower()

        # Actor input configuration based on docs
        input_config = {
            "directUrls": [f"https://www.instagram.com/{username}/"],
            "resultsType": "posts",
            "resultsLimit": results_limit,
            "searchType": "user",
        }

        logger.info(f"Starting Apify scrape for user: {username}")

        # Start actor run
        run = await self._start_actor_run(input_config, timeout_secs)
        run_id = run.get("id")
        logger.info(f"Actor run started: {run_id}")

        # Wait for completion and fetch results
        results = await self._wait_and_get_results(run_id, timeout_secs)
        logger.info(f"Scraped {len(results)} posts for {username}")

        return self._parse_posts(results)

    async def scrape_users_batch(
        self,
        usernames: List[str],
        results_per_user: int = 30,
        timeout_secs: int = 600
    ) -> Dict[str, List[InstagramPost]]:
        """
        Scrape posts for multiple users in a single actor run.
        More cost-efficient than individual runs.

        Args:
            usernames: List of Instagram usernames
            results_per_user: Posts to fetch per user
            timeout_secs: Max wait time

        Returns:
            Dict mapping username -> List[InstagramPost]
        """
        # Clean usernames
        usernames = [u.lstrip('@').lower() for u in usernames]
        urls = [f"https://www.instagram.com/{u}/" for u in usernames]

        input_config = {
            "directUrls": urls,
            "resultsType": "posts",
            "resultsLimit": results_per_user * len(usernames),
            "searchType": "user",
        }

        logger.info(f"Starting batch Apify scrape for {len(usernames)} users")

        run = await self._start_actor_run(input_config, timeout_secs)
        run_id = run.get("id")
        logger.info(f"Batch actor run started: {run_id}")

        results = await self._wait_and_get_results(run_id, timeout_secs)
        logger.info(f"Scraped {len(results)} total posts")

        # Group posts by username
        posts_by_user: Dict[str, List[InstagramPost]] = {u: [] for u in usernames}

        for item in results:
            post = self._parse_single_post(item)
            if post and post.owner_username:
                owner = post.owner_username.lower()
                if owner in posts_by_user:
                    posts_by_user[owner].append(post)

        return posts_by_user

    async def _start_actor_run(
        self,
        input_config: Dict[str, Any],
        timeout_secs: int
    ) -> Dict[str, Any]:
        """Start an actor run and return run info."""
        # Apify requires ~ instead of / in actor ID for URL path
        actor_id_url = self.ACTOR_ID.replace("/", "~")
        url = f"{self.BASE_URL}/acts/{actor_id_url}/runs"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self._get_headers(),
                json=input_config,
                params={"timeout": timeout_secs},
                timeout=60.0
            )

            if response.status_code not in (200, 201):
                error_text = response.text
                logger.error(f"Failed to start Apify run: {response.status_code} - {error_text}")
                raise ApifyAPIError(f"Failed to start run: {error_text}")

            data = response.json()
            return data.get("data", data)

    async def _wait_and_get_results(
        self,
        run_id: str,
        timeout_secs: int
    ) -> List[Dict[str, Any]]:
        """Poll for run completion and fetch results."""
        url = f"{self.BASE_URL}/actor-runs/{run_id}"
        deadline = datetime.now(timezone.utc).timestamp() + timeout_secs
        poll_interval = 5  # seconds

        async with httpx.AsyncClient() as client:
            while datetime.now(timezone.utc).timestamp() < deadline:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    timeout=30.0
                )

                if response.status_code != 200:
                    logger.warning(f"Failed to check run status: {response.status_code}")
                    await asyncio.sleep(poll_interval)
                    continue

                data = response.json()
                run_data = data.get("data", data)
                status = run_data.get("status")

                logger.debug(f"Run {run_id} status: {status}")

                if status == "SUCCEEDED":
                    # Fetch results from dataset
                    dataset_id = run_data.get("defaultDatasetId")
                    if not dataset_id:
                        raise ApifyAPIError(f"No dataset ID in run response")
                    return await self._fetch_dataset(dataset_id)

                elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    error_msg = run_data.get("statusMessage", "Unknown error")
                    raise ApifyAPIError(f"Run {run_id} ended with status: {status} - {error_msg}")

                # Wait before polling again
                await asyncio.sleep(poll_interval)

            raise ApifyAPIError(f"Run {run_id} timed out after {timeout_secs}s")

    async def _fetch_dataset(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Fetch all items from a dataset."""
        url = f"{self.BASE_URL}/datasets/{dataset_id}/items"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._get_headers(),
                params={"format": "json"},
                timeout=120.0
            )

            if response.status_code != 200:
                raise ApifyAPIError(f"Failed to fetch dataset: {response.status_code}")

            return response.json()

    def _parse_posts(self, items: List[Dict]) -> List[InstagramPost]:
        """Parse raw Apify results into InstagramPost objects."""
        posts = []
        for item in items:
            post = self._parse_single_post(item)
            if post:
                posts.append(post)
        return posts

    def _parse_single_post(self, item: Dict) -> Optional[InstagramPost]:
        """Parse a single post item from Apify response."""
        try:
            caption = item.get("caption", "") or ""

            # Use hashtags from Apify if available, otherwise extract from caption
            hashtags = item.get("hashtags")
            if not hashtags:
                hashtags = self._extract_hashtags(caption)

            # Use mentions from Apify if available, otherwise extract from caption
            mentions = item.get("mentions")
            if not mentions:
                mentions = self._extract_mentions(caption)

            # Build post URL from shortcode
            shortcode = item.get("shortCode", "")
            post_url = item.get("url", "")
            if not post_url and shortcode:
                post_url = f"https://www.instagram.com/p/{shortcode}/"

            return InstagramPost(
                post_id=item.get("id", "") or item.get("shortCode", ""),
                shortcode=shortcode,
                post_url=post_url,
                caption=caption,
                hashtags=hashtags or [],
                mentions=mentions or [],
                post_type=item.get("type", "Image"),
                posted_at=self._parse_timestamp(item.get("timestamp")),
                likes_count=item.get("likesCount", 0) or 0,
                comments_count=item.get("commentsCount", 0) or 0,
                views_count=item.get("videoViewCount") or item.get("viewsCount"),
                thumbnail_url=item.get("displayUrl"),
                is_sponsored=item.get("isSponsored", False) or item.get("isAdvertisement", False),
                owner_username=item.get("ownerUsername")
            )
        except Exception as e:
            logger.warning(f"Failed to parse post: {e}")
            return None

    @staticmethod
    def _extract_hashtags(caption: str) -> List[str]:
        """Extract hashtags from caption text."""
        return re.findall(r'#(\w+)', caption.lower())

    @staticmethod
    def _extract_mentions(caption: str) -> List[str]:
        """Extract @mentions from caption text."""
        return re.findall(r'@(\w+)', caption.lower())

    @staticmethod
    def _parse_timestamp(ts) -> Optional[datetime]:
        """Parse timestamp from various formats."""
        if not ts:
            return None
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            try:
                # ISO format with Z
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                pass
            try:
                # Try parsing without timezone
                return datetime.fromisoformat(ts)
            except ValueError:
                pass
        return None
