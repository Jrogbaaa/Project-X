#!/usr/bin/env python3
"""
Primetag API Test Script

Tests the Primetag MediaKit API endpoints to verify connectivity and responses.
Run this script to validate that the API integration is working correctly.

Usage:
    python scripts/test_primetag.py
"""

import asyncio
import httpx
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

# Configuration
BASE_URL = os.getenv("PRIMETAG_API_BASE_URL", "https://api.primetag.com")
API_KEY = os.getenv("PRIMETAG_API_KEY", "")

HEADERS = {
    "Authorization": f"Token {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# Platform types per Primetag API docs
PLATFORMS = {
    "youtube": 1,
    "instagram": 2,
    "tiktok": 3,
    "facebook": 4,
    "pinterest": 5,
    "linkedin": 6,
}


def extract_encrypted_username(mediakit_url: str) -> str | None:
    """Extract encrypted username from mediakit URL."""
    if not mediakit_url:
        return None
    try:
        parsed = urlparse(mediakit_url)
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) >= 2:
            return path_parts[-1]
        return None
    except Exception:
        return None


async def test_platforms_endpoint():
    """Test GET /media-kits/settings/platforms"""
    print("\n" + "=" * 60)
    print("TEST 1: Get Available Platforms")
    print("=" * 60)

    url = f"{BASE_URL}/media-kits/settings/platforms"
    print(f"URL: {url}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=HEADERS, timeout=30.0)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)}")
                print("✅ Platforms endpoint working!")
                return True
            else:
                print(f"❌ Error: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Exception: {e}")
            return False


async def test_search_endpoint(search_query: str = "cristiano", platform_type: int = 2):
    """Test GET /media-kits?platform_type=X&search=Y"""
    print("\n" + "=" * 60)
    print(f"TEST 2: Search MediaKits for '{search_query}'")
    print("=" * 60)

    url = f"{BASE_URL}/media-kits"
    params = {
        "platform_type": platform_type,
        "search": search_query,
        "limit": 5,
    }
    print(f"URL: {url}")
    print(f"Params: {params}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=HEADERS, params=params, timeout=30.0)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                results = data.get("response", [])
                print(f"Found {len(results)} creators")

                for i, creator in enumerate(results[:3], 1):
                    print(f"\n  {i}. {creator.get('display_name', 'N/A')} (@{creator.get('username', 'N/A')})")
                    print(f"     Followers: {creator.get('audience_size', 0):,}")
                    print(f"     Verified: {creator.get('is_verified', False)}")
                    print(f"     MediaKit URL: {creator.get('mediakit_url', 'N/A')[:80]}...")

                print("\n✅ Search endpoint working!")
                return data
            else:
                print(f"❌ Error: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Exception: {e}")
            return None


async def test_mediakit_detail(platform_type: int, encrypted_username: str):
    """Test GET /media-kits/{platform_type}/{encrypted_username}"""
    print("\n" + "=" * 60)
    print("TEST 3: Get MediaKit Detail")
    print("=" * 60)

    url = f"{BASE_URL}/media-kits/{platform_type}/{encrypted_username}"
    print(f"URL: {url[:100]}...")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=HEADERS, timeout=30.0)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                mediakit = data.get("response", {})

                print(f"\n  Profile: {mediakit.get('fullname', 'N/A')} (@{mediakit.get('username', 'N/A')})")
                print(f"  Followers: {mediakit.get('followers', 0):,}")
                print(f"  Avg Engagement Rate: {mediakit.get('avg_engagement_rate', 0):.2f}%")
                print(f"  Location: {mediakit.get('location', 'N/A')}")

                # Audience data
                audience = mediakit.get("audience_data", {})
                followers_data = audience.get("followers", {}) if audience else {}

                if followers_data:
                    credibility = followers_data.get("audience_credibility_percentage")
                    if credibility:
                        print(f"  Audience Credibility: {credibility:.1f}%")

                    genders = followers_data.get("genders", {})
                    if genders:
                        print(f"  Gender Split: Male {genders.get('male', 0):.1f}% / Female {genders.get('female', 0):.1f}%")

                    countries = followers_data.get("location_by_country", [])
                    if countries:
                        print("  Top Countries:")
                        for country in countries[:3]:
                            print(f"    - {country.get('name', 'N/A')}: {country.get('value', 0):.1f}%")

                print("\n✅ MediaKit detail endpoint working!")
                return data
            else:
                print(f"❌ Error: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Exception: {e}")
            return None


async def test_backend_search():
    """Test our backend's search endpoint"""
    print("\n" + "=" * 60)
    print("TEST 4: Test Backend Search API")
    print("=" * 60)

    url = "http://localhost:8000/api/search/"
    payload = {
        "query": "Find me Spanish Instagram influencers in fitness",
        "limit": 3,
    }
    print(f"URL: {url}")
    print(f"Payload: {payload}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=60.0)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"Search ID: {data.get('search_id', 'N/A')}")
                print(f"Found {len(data.get('results', []))} results")
                print("\n✅ Backend search endpoint working!")
                return data
            else:
                print(f"❌ Error: {response.text[:500]}")
                return None
        except Exception as e:
            print(f"❌ Exception: {e}")
            return None


async def main():
    """Run all tests"""
    print("\n" + "#" * 60)
    print("# PRIMETAG API TEST SUITE")
    print("#" * 60)
    print(f"\nBase URL: {BASE_URL}")
    print(f"API Key: {API_KEY[:20]}..." if API_KEY else "API Key: NOT SET!")

    if not API_KEY:
        print("\n❌ ERROR: PRIMETAG_API_KEY not set in .env file!")
        return

    results = {
        "platforms": False,
        "search": False,
        "detail": False,
        "backend": False,
    }

    # Test 1: Platforms
    results["platforms"] = await test_platforms_endpoint()

    # Test 2: Search
    search_data = await test_search_endpoint("cristiano", platform_type=2)
    results["search"] = search_data is not None

    # Test 3: MediaKit Detail (if search worked)
    if search_data:
        creators = search_data.get("response", [])
        if creators:
            first_creator = creators[0]
            mediakit_url = first_creator.get("mediakit_url", "")
            encrypted_username = extract_encrypted_username(mediakit_url)
            platform_type = first_creator.get("platform_type", 2)

            if encrypted_username:
                detail_data = await test_mediakit_detail(platform_type, encrypted_username)
                results["detail"] = detail_data is not None

    # Test 4: Backend search
    results["backend"] = await test_backend_search() is not None

    # Summary
    print("\n" + "#" * 60)
    print("# TEST SUMMARY")
    print("#" * 60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name.capitalize()}: {status}")

    all_passed = all(results.values())
    print("\n" + ("🎉 All tests passed!" if all_passed else "⚠️ Some tests failed!"))

    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
