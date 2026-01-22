#!/usr/bin/env python3
"""
Instagram Profile Enrichment Pipeline

Enriches influencer CSV data with profile information from Instagram's public API.
Extracts category_name (genre) and biography (details) for each profile.

Usage:
    python -m app.services.instagram_enrichment \
        --input "../top 4000 influencers in spain  - Influencers.csv" \
        --output "../influencers_enriched.csv" \
        --rate-limit 20

Features:
    - Async HTTP client for efficient requests
    - Rate limiting to avoid Instagram blocks
    - JSON cache for resumable runs
    - Progress tracking with ETA
    - Robust error handling
"""

import asyncio
import argparse
import csv
import json
import logging
import os
import random
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

import httpx

# Custom exception for rate limiting
class RateLimitException(Exception):
    """Raised when Instagram rate limits us."""
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class InstagramProfile:
    """Data extracted from Instagram profile."""
    username: str
    full_name: Optional[str] = None
    biography: Optional[str] = None
    category_name: Optional[str] = None
    follower_count: Optional[int] = None
    is_business: bool = False
    is_verified: bool = False
    fetched_at: Optional[str] = None
    error: Optional[str] = None


class InstagramEnrichmentPipeline:
    """Pipeline for enriching influencer data from Instagram."""
    
    INSTAGRAM_API_URL = "https://www.instagram.com/api/v1/users/web_profile_info/"
    INSTAGRAM_APP_ID = "936619743392459"
    
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "x-ig-app-id": INSTAGRAM_APP_ID,
    }
    
    def __init__(
        self,
        cache_dir: str = ".tmp",
        rate_limit: int = 20,
        max_retries: int = 3,
        timeout: float = 30.0,
        batch_size: int = 100,
        batch_pause: int = 1800  # 30 minutes between batches
    ):
        """
        Initialize the pipeline.
        
        Args:
            cache_dir: Directory for cache files
            rate_limit: Max requests per minute
            max_retries: Max retry attempts for failed requests
            timeout: Request timeout in seconds
            batch_size: Number of profiles to process per batch
            batch_pause: Seconds to pause between batches (default 30 min)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / "ig_cache.json"
        self.progress_file = self.cache_dir / "ig_progress.json"
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.timeout = timeout
        self.batch_size = batch_size
        self.batch_pause = batch_pause
        
        # Rate limiting state
        self.request_times: List[float] = []
        self.min_delay = 60.0 / rate_limit  # Minimum seconds between requests
        
        # Track consecutive errors for rate limit detection
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        
        # Statistics
        self.stats = {
            "total": 0,
            "processed": 0,
            "cached": 0,
            "success": 0,
            "not_found": 0,
            "errors": 0,
            "start_time": None,
        }
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing cache and progress
        self.cache: Dict[str, Dict[str, Any]] = self._load_cache()
        self.progress: Dict[str, Any] = self._load_progress()
    
    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    logger.info(f"Loaded {len(cache)} profiles from cache")
                    return cache
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load cache: {e}")
        return {}
    
    def _load_progress(self) -> Dict[str, Any]:
        """Load progress from disk to resume from last position."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
                    last_idx = progress.get('last_processed_index', 0)
                    if last_idx > 0:
                        logger.info(f"Resuming from row {last_idx}")
                    return progress
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load progress: {e}")
        return {"last_processed_index": 0}
    
    def _save_progress(self, index: int):
        """Save current progress index to disk."""
        self.progress["last_processed_index"] = index
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress, f)
        except IOError as e:
            logger.error(f"Failed to save progress: {e}")
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"Failed to save cache: {e}")
    
    def _save_profile_to_cache(self, username: str, profile: InstagramProfile):
        """Save a single profile to cache and persist."""
        self.cache[username.lower()] = asdict(profile)
        self._save_cache()
    
    async def _wait_for_rate_limit(self):
        """Enforce rate limiting with jitter."""
        now = time.time()
        
        # Remove request times older than 1 minute
        self.request_times = [t for t in self.request_times if now - t < 60]
        
        # If we've hit the rate limit, wait
        if len(self.request_times) >= self.rate_limit:
            oldest = min(self.request_times)
            wait_time = 60 - (now - oldest) + random.uniform(1, 3)
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
        
        # Add random jitter between requests (2-4 seconds)
        jitter = random.uniform(2.0, 4.0)
        await asyncio.sleep(jitter)
        
        # Record this request time
        self.request_times.append(time.time())
    
    async def fetch_profile(self, username: str, client: httpx.AsyncClient) -> InstagramProfile:
        """
        Fetch profile data from Instagram API.
        
        Args:
            username: Instagram username (without @)
            client: HTTP client instance
            
        Returns:
            InstagramProfile with fetched data or error
        """
        # Clean username
        clean_username = username.lstrip('@').strip()
        
        # Check cache first
        if clean_username.lower() in self.cache:
            cached = self.cache[clean_username.lower()]
            self.stats["cached"] += 1
            return InstagramProfile(**cached)
        
        # Rate limiting
        await self._wait_for_rate_limit()
        
        profile = InstagramProfile(
            username=clean_username,
            fetched_at=datetime.now(timezone.utc).isoformat()
        )
        
        for attempt in range(self.max_retries):
            try:
                response = await client.get(
                    self.INSTAGRAM_API_URL,
                    params={"username": clean_username},
                    headers=self.DEFAULT_HEADERS,
                    timeout=self.timeout
                )
                
                # Check for rate limiting (429 or 401 with "wait" message)
                if response.status_code == 429 or response.status_code == 401:
                    self.consecutive_errors += 1
                    try:
                        error_data = response.json()
                        if "wait" in str(error_data.get("message", "")).lower():
                            logger.warning(f"Rate limited! Message: {error_data.get('message')}")
                            if self.consecutive_errors >= self.max_consecutive_errors:
                                raise RateLimitException("Too many consecutive rate limit errors")
                            wait_time = 60 * (attempt + 1)
                            logger.warning(f"Waiting {wait_time}s before retry...")
                            await asyncio.sleep(wait_time)
                            continue
                    except json.JSONDecodeError:
                        pass
                    wait_time = 60 * (attempt + 1)
                    logger.warning(f"Rate limited on @{clean_username}, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                # Check for HTML response (profile not found)
                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type:
                    profile.error = "NOT_FOUND"
                    self.stats["not_found"] += 1
                    self.consecutive_errors = 0  # Reset on successful response
                    logger.debug(f"Profile not found: @{clean_username}")
                    break
                
                # Parse JSON response
                if response.status_code == 200:
                    try:
                        data = response.json()
                        user_data = data.get("data", {}).get("user", {})
                        
                        if user_data:
                            profile.full_name = user_data.get("full_name")
                            profile.biography = user_data.get("biography")
                            profile.category_name = user_data.get("category_name")
                            profile.follower_count = user_data.get("edge_followed_by", {}).get("count")
                            profile.is_business = user_data.get("is_business_account", False)
                            profile.is_verified = user_data.get("is_verified", False)
                            self.stats["success"] += 1
                            self.consecutive_errors = 0  # Reset on success
                            logger.debug(f"Fetched @{clean_username}: {profile.category_name}")
                        else:
                            profile.error = "NO_USER_DATA"
                            self.stats["errors"] += 1
                    except json.JSONDecodeError:
                        profile.error = "INVALID_JSON"
                        self.stats["errors"] += 1
                    break
                else:
                    logger.warning(f"Unexpected status {response.status_code} for @{clean_username}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(5 * (attempt + 1))
                    
            except httpx.TimeoutException:
                logger.warning(f"Timeout fetching @{clean_username} (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    profile.error = "TIMEOUT"
                    self.stats["errors"] += 1
                    
            except httpx.RequestError as e:
                logger.warning(f"Request error for @{clean_username}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    profile.error = f"REQUEST_ERROR: {str(e)}"
                    self.stats["errors"] += 1
        
        # Save to cache
        self._save_profile_to_cache(clean_username, profile)
        self.stats["processed"] += 1
        
        return profile
    
    def _print_progress(self, current: int, total: int, username: str):
        """Print progress with ETA."""
        elapsed = time.time() - self.stats["start_time"]
        if current > 0:
            rate = current / elapsed
            remaining = total - current
            eta_seconds = remaining / rate if rate > 0 else 0
            eta = str(timedelta(seconds=int(eta_seconds)))
        else:
            eta = "calculating..."
        
        # Clear line and print progress
        print(f"\r[{current}/{total}] Processing @{username[:20]:<20} | "
              f"Success: {self.stats['success']} | "
              f"Cached: {self.stats['cached']} | "
              f"Errors: {self.stats['errors']} | "
              f"ETA: {eta}     ", end="", flush=True)
    
    def _save_csv_checkpoint(self, rows: List[Dict], fieldnames: List[str], output_path: str, checkpoint_num: int):
        """Save CSV checkpoint during processing."""
        try:
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            logger.info(f"Checkpoint saved: {checkpoint_num} profiles processed -> {output_path}")
        except IOError as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    async def enrich_csv(
        self,
        input_path: str,
        output_path: str,
        force: bool = False,
        limit: Optional[int] = None
    ):
        """
        Enrich CSV file with Instagram profile data.
        Processes in batches and resumes from last position.
        
        Args:
            input_path: Path to input CSV
            output_path: Path for output CSV
            force: If True, re-fetch cached profiles and reset progress
            limit: Optional limit on number of profiles to process
        """
        self.stats["start_time"] = time.time()
        
        # Read input CSV
        logger.info(f"Reading input CSV: {input_path}")
        rows = []
        with open(input_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                rows.append(row)
        
        # Apply limit if specified
        if limit and limit > 0:
            rows = rows[:limit]
            logger.info(f"Limiting to first {limit} rows")
        
        self.stats["total"] = len(rows)
        logger.info(f"Found {len(rows)} rows to process")
        
        # If force, clear cache and progress
        if force:
            logger.info("Force mode: clearing cache and progress")
            self.cache = {}
            self.progress = {"last_processed_index": 0}
            self._save_progress(0)
        
        # Get starting position from progress
        start_index = self.progress.get("last_processed_index", 0)
        if start_index > 0:
            logger.info(f"Resuming from row {start_index} (skipping {start_index} already processed)")
        
        # Track batch progress
        batch_count = 0
        profiles_in_batch = 0
        
        # Process profiles
        async with httpx.AsyncClient() as client:
            for i, row in enumerate(rows):
                # Skip already processed rows
                if i < start_index:
                    # Still need to enrich from cache for CSV output
                    handle = row.get("Instagram Handle", "").strip()
                    if handle:
                        username = handle.lstrip('@').lower()
                        if username in self.cache:
                            cached = self.cache[username]
                            if cached.get("category_name") and not cached.get("error"):
                                if not row.get("GENRE") or row.get("GENRE").strip() == "":
                                    row["GENRE"] = cached["category_name"]
                            if cached.get("biography") and not cached.get("error"):
                                bio = cached["biography"][:500] if cached.get("biography") else ""
                                bio = bio.replace('\n', ' ').replace('\r', ' ').strip()
                                if not row.get("Details") or row.get("Details").strip() == "":
                                    row["Details"] = bio
                    continue
                
                handle = row.get("Instagram Handle", "").strip()
                if not handle or handle.startswith('#'):
                    self._save_progress(i + 1)
                    continue
                
                username = handle.lstrip('@')
                self._print_progress(i + 1, len(rows), username)
                
                try:
                    # Fetch profile
                    profile = await self.fetch_profile(username, client)
                    
                    # Update row with enriched data
                    if profile.category_name and not profile.error:
                        if not row.get("GENRE") or row.get("GENRE").strip() == "":
                            row["GENRE"] = profile.category_name
                    
                    if profile.biography and not profile.error:
                        bio = profile.biography[:500] if profile.biography else ""
                        bio = bio.replace('\n', ' ').replace('\r', ' ').strip()
                        if not row.get("Details") or row.get("Details").strip() == "":
                            row["Details"] = bio
                    
                    # Save progress after each profile
                    self._save_progress(i + 1)
                    profiles_in_batch += 1
                    
                    # Check if we've completed a batch
                    if profiles_in_batch >= self.batch_size:
                        batch_count += 1
                        print()  # New line before batch message
                        self._save_csv_checkpoint(rows, fieldnames, output_path, i + 1)
                        logger.info(f"Batch {batch_count} complete ({profiles_in_batch} profiles)")
                        
                        # Pause between batches to avoid rate limiting
                        if i + 1 < len(rows):
                            pause_minutes = self.batch_pause // 60
                            logger.info(f"Pausing for {pause_minutes} minutes before next batch...")
                            logger.info(f"(You can safely stop and restart - progress is saved)")
                            await asyncio.sleep(self.batch_pause)
                            self.consecutive_errors = 0  # Reset error counter after pause
                        
                        profiles_in_batch = 0
                
                except RateLimitException as e:
                    print()
                    logger.error(f"Rate limit hit: {e}")
                    logger.info(f"Saving progress at row {i + 1} and pausing...")
                    self._save_csv_checkpoint(rows, fieldnames, output_path, i + 1)
                    self._save_progress(i)  # Save current position to retry this row
                    
                    # Long pause on rate limit
                    pause_minutes = 30
                    logger.info(f"Waiting {pause_minutes} minutes due to rate limiting...")
                    logger.info(f"Progress saved. You can restart later with: --input ... --output ...")
                    await asyncio.sleep(pause_minutes * 60)
                    self.consecutive_errors = 0
        
        print()  # New line after progress
        
        # Final save
        logger.info(f"Writing final output CSV: {output_path}")
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        # Clear progress file on completion
        if self.progress_file.exists():
            self.progress_file.unlink()
            logger.info("Progress file cleared (job complete)")
        
        # Print final statistics
        elapsed = time.time() - self.stats["start_time"]
        logger.info(f"\n{'='*60}")
        logger.info(f"Enrichment Complete!")
        logger.info(f"{'='*60}")
        logger.info(f"Total profiles: {self.stats['total']}")
        logger.info(f"Processed (new): {self.stats['processed']}")
        logger.info(f"From cache: {self.stats['cached']}")
        logger.info(f"Successful: {self.stats['success']}")
        logger.info(f"Not found: {self.stats['not_found']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Time elapsed: {timedelta(seconds=int(elapsed))}")
        logger.info(f"Output saved to: {output_path}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Enrich influencer CSV with Instagram profile data"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to input CSV file"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Path for output CSV file"
    )
    parser.add_argument(
        "--rate-limit", "-r",
        type=int,
        default=20,
        help="Max requests per minute (default: 20)"
    )
    parser.add_argument(
        "--cache-dir",
        default=".tmp",
        help="Directory for cache files (default: .tmp)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-fetch all profiles (ignore cache)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of profiles to process (for testing)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=100,
        help="Number of profiles per batch (default: 100)"
    )
    parser.add_argument(
        "--batch-pause",
        type=int,
        default=1800,
        help="Seconds to pause between batches (default: 1800 = 30 min)"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Resolve paths relative to workspace root
    script_dir = Path(__file__).parent
    workspace_root = script_dir.parent.parent.parent
    
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = workspace_root / args.input
    
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = workspace_root / args.output
    
    cache_dir = Path(args.cache_dir)
    if not cache_dir.is_absolute():
        cache_dir = workspace_root / args.cache_dir
    
    # Validate input file exists
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)
    
    # Create pipeline and run
    pipeline = InstagramEnrichmentPipeline(
        cache_dir=str(cache_dir),
        rate_limit=args.rate_limit,
        batch_size=args.batch_size,
        batch_pause=args.batch_pause
    )
    
    await pipeline.enrich_csv(
        input_path=str(input_path),
        output_path=str(output_path),
        force=args.force,
        limit=args.limit
    )


if __name__ == "__main__":
    asyncio.run(main())
