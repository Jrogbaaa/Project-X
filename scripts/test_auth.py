#!/usr/bin/env python3
"""Test different authentication header formats for Primetag API."""

import asyncio
import httpx
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_URL = "https://api.primetag.com"
API_KEY = os.getenv("PRIMETAG_API_KEY", "")

# Different auth header formats to try (based on Primetag docs showing X-User-ID and X-Auth-User-ID)
AUTH_FORMATS = [
    {"Authorization": f"Token {API_KEY}"},
    {"Authorization": f"Bearer {API_KEY}"},
    {"Authorization": API_KEY},
    {"X-API-Key": API_KEY},
    {"X-Auth-Token": API_KEY},
    {"Api-Key": API_KEY},
    {"apikey": API_KEY},
    # Custom headers from docs
    {"X-User-ID": API_KEY},
    {"X-Auth-User-ID": API_KEY},
    {"X-User-ID": API_KEY, "X-Auth-User-ID": API_KEY},
    # Try with Authorization + custom headers
    {"Authorization": f"Token {API_KEY}", "X-User-ID": "api-user"},
    {"Authorization": f"Bearer {API_KEY}", "X-User-ID": "api-user"},
]


async def test_auth_format(headers_extra: dict):
    """Test a specific auth format."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        **headers_extra,
    }

    url = f"{BASE_URL}/media-kits"
    params = {"platform_type": 2, "search": "cristiano", "limit": 1}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params, timeout=10.0)
            return response.status_code, response.text[:200]
        except Exception as e:
            return None, str(e)


async def main():
    print(f"Testing auth formats against {BASE_URL}/media-kits")
    print(f"API Key: {API_KEY[:20]}...\n")

    for auth_headers in AUTH_FORMATS:
        header_name = list(auth_headers.keys())[0]
        header_value = list(auth_headers.values())[0][:30] + "..."

        status, response = await test_auth_format(auth_headers)

        if status == 200:
            print(f"✅ {header_name}: {header_value}")
            print(f"   Status: {status} - SUCCESS!")
            print(f"   Response: {response[:100]}...")
            return auth_headers
        else:
            print(f"❌ {header_name}: Status {status}")

    print("\n⚠️ No auth format worked!")
    return None


if __name__ == "__main__":
    asyncio.run(main())
