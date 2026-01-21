#!/usr/bin/env python3
"""
Test script to verify PrimeTag API connectivity and diagnose issues.
Run from the backend directory: python test_primetag_api.py
"""

import asyncio
import httpx
import os
import sys
from pathlib import Path

# Add the backend directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


async def test_api_connection():
    """Test basic API connectivity with detailed error logging."""

    print("=" * 60)
    print("PrimeTag API Connection Test")
    print("=" * 60)

    # Get config values
    base_url_from_env = os.getenv("PRIMETAG_API_BASE_URL", "NOT SET")
    api_key = os.getenv("PRIMETAG_API_KEY", "NOT SET")

    print(f"\n📋 Configuration:")
    print(f"   Base URL (from .env): {base_url_from_env}")
    print(f"   API Key: {api_key[:20]}..." if api_key != "NOT SET" else "   API Key: NOT SET")

    # The client currently uses a hardcoded URL - let's test both
    hardcoded_url = "https://api.primetag.com/v1"

    print(f"\n🔍 Testing URLs:")

    # Test 1: Hardcoded URL (what the client actually uses)
    print(f"\n--- Test 1: Hardcoded URL ({hardcoded_url}) ---")
    await test_url(hardcoded_url, api_key)

    # Test 2: URL from .env
    if base_url_from_env != "NOT SET" and base_url_from_env != hardcoded_url:
        print(f"\n--- Test 2: URL from .env ({base_url_from_env}) ---")
        await test_url(base_url_from_env, api_key)

    print("\n" + "=" * 60)


async def test_url(base_url: str, api_key: str):
    """Test a specific URL endpoint."""

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Test search endpoint
    search_url = f"{base_url}/media-kits"
    params = {
        "platform_type": 1,  # Instagram
        "search": "fashion",
        "limit": 5
    }

    print(f"   Testing: GET {search_url}")
    print(f"   Params: {params}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                search_url,
                params=params,
                headers=headers,
                timeout=30.0
            )

            print(f"\n   ✅ Response received!")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response Headers:")
            for key, value in list(response.headers.items())[:5]:
                print(f"      {key}: {value}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"\n   📦 Response Data (preview):")
                    if isinstance(data, dict):
                        print(f"      Keys: {list(data.keys())}")
                        if "response" in data:
                            items = data["response"]
                            print(f"      Results count: {len(items) if isinstance(items, list) else 'N/A'}")
                            if items and len(items) > 0:
                                print(f"      First item keys: {list(items[0].keys()) if isinstance(items[0], dict) else 'N/A'}")
                    else:
                        print(f"      Type: {type(data)}")
                        print(f"      Preview: {str(data)[:200]}...")
                except Exception as e:
                    print(f"   ⚠️  Could not parse JSON: {e}")
                    print(f"   Raw response: {response.text[:500]}...")
            else:
                print(f"\n   ❌ Error Response:")
                print(f"   Body: {response.text[:500]}")

        except httpx.TimeoutException:
            print(f"\n   ❌ TIMEOUT: Request took longer than 30 seconds")

        except httpx.ConnectError as e:
            print(f"\n   ❌ CONNECTION ERROR: Could not connect to server")
            print(f"   Details: {str(e)}")

        except httpx.RequestError as e:
            print(f"\n   ❌ REQUEST ERROR: {type(e).__name__}")
            print(f"   Details: {str(e)}")

        except Exception as e:
            print(f"\n   ❌ UNEXPECTED ERROR: {type(e).__name__}")
            print(f"   Details: {str(e)}")


async def test_detail_endpoint(base_url: str, api_key: str, username: str = "therock"):
    """Test the detail endpoint for a specific user."""

    print(f"\n--- Test Detail Endpoint ---")

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    detail_url = f"{base_url}/media-kits/1/{username}"

    print(f"   Testing: GET {detail_url}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                detail_url,
                headers=headers,
                timeout=30.0
            )

            print(f"   Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Got detail for user: {username}")
                if isinstance(data, dict):
                    print(f"   Keys: {list(data.keys())[:10]}")
            else:
                print(f"   Response: {response.text[:300]}")

        except Exception as e:
            print(f"   ❌ Error: {type(e).__name__}: {str(e)}")


if __name__ == "__main__":
    print("\n🚀 Starting PrimeTag API Tests...\n")
    asyncio.run(test_api_connection())
    print("\n✅ Tests complete!\n")
