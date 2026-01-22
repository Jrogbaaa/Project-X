#!/usr/bin/env python3
"""
PrimeTag Audience Overlap API Test Script

Tests potential endpoints for audience overlap/brand affinity analysis.
This explores whether PrimeTag exposes APIs for measuring audience overlap
between influencers and brand accounts.

Usage:
    python scripts/test_audience_overlap.py
"""

import asyncio
import httpx
import json
import os
import sys
from pathlib import Path

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

# Test data
TEST_INFLUENCERS = ["cristiano", "leomessi"]
TEST_BRANDS = ["nike", "adidas"]


async def test_endpoint(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> dict:
    """Test an endpoint and return result info."""
    try:
        if method == "GET":
            response = await client.get(url, headers=HEADERS, timeout=30.0, **kwargs)
        elif method == "POST":
            response = await client.post(url, headers=HEADERS, timeout=30.0, **kwargs)
        else:
            return {"status": "error", "message": f"Unknown method: {method}"}

        result = {
            "status_code": response.status_code,
            "success": response.status_code == 200,
        }

        if response.status_code == 200:
            try:
                result["data_preview"] = str(response.json())[:500]
            except Exception:
                result["data_preview"] = response.text[:500]
        else:
            result["error"] = response.text[:300]

        return result

    except httpx.TimeoutException:
        return {"status": "timeout", "message": "Request timed out"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def probe_audience_overlap_endpoints():
    """Probe various potential audience overlap endpoints."""
    
    print("\n" + "=" * 70)
    print("PRIMETAG AUDIENCE OVERLAP API EXPLORATION")
    print("=" * 70)
    print(f"\nBase URL: {BASE_URL}")
    print(f"API Key: {API_KEY[:20]}..." if API_KEY else "API Key: NOT SET!")
    
    if not API_KEY:
        print("\n❌ ERROR: PRIMETAG_API_KEY not set!")
        return

    async with httpx.AsyncClient() as client:
        
        # ============================================================
        # 1. Test potential audience overlap endpoints
        # ============================================================
        print("\n" + "-" * 50)
        print("1. TESTING POTENTIAL AUDIENCE OVERLAP ENDPOINTS")
        print("-" * 50)
        
        overlap_endpoints = [
            # Common REST patterns for overlap analysis
            ("GET", f"{BASE_URL}/audience-overlap"),
            ("GET", f"{BASE_URL}/v1/audience-overlap"),
            ("GET", f"{BASE_URL}/audience/overlap"),
            ("GET", f"{BASE_URL}/v1/audience/overlap"),
            ("GET", f"{BASE_URL}/media-kits/audience-overlap"),
            ("GET", f"{BASE_URL}/v1/media-kits/audience-overlap"),
            ("GET", f"{BASE_URL}/analytics/audience-overlap"),
            ("GET", f"{BASE_URL}/v1/analytics/audience-overlap"),
            ("GET", f"{BASE_URL}/brand-affinity"),
            ("GET", f"{BASE_URL}/v1/brand-affinity"),
        ]
        
        for method, url in overlap_endpoints:
            result = await test_endpoint(client, method, url, params={
                "influencer": "cristiano",
                "brand": "nike",
                "platform_type": 2  # Instagram
            })
            status = "✅" if result.get("success") else f"❌ ({result.get('status_code', 'N/A')})"
            print(f"  {status} {method} {url}")
            if result.get("success"):
                print(f"      Preview: {result.get('data_preview', 'N/A')[:100]}...")

        # ============================================================
        # 2. Test comparison/batch endpoints
        # ============================================================
        print("\n" + "-" * 50)
        print("2. TESTING COMPARISON/BATCH ENDPOINTS")
        print("-" * 50)
        
        comparison_endpoints = [
            ("POST", f"{BASE_URL}/compare"),
            ("POST", f"{BASE_URL}/v1/compare"),
            ("POST", f"{BASE_URL}/media-kits/compare"),
            ("POST", f"{BASE_URL}/v1/media-kits/compare"),
            ("POST", f"{BASE_URL}/batch-analysis"),
            ("POST", f"{BASE_URL}/v1/batch-analysis"),
        ]
        
        for method, url in comparison_endpoints:
            result = await test_endpoint(client, method, url, json={
                "influencers": TEST_INFLUENCERS,
                "brands": TEST_BRANDS,
                "platform_type": 2
            })
            status = "✅" if result.get("success") else f"❌ ({result.get('status_code', 'N/A')})"
            print(f"  {status} {method} {url}")
            if result.get("success"):
                print(f"      Preview: {result.get('data_preview', 'N/A')[:100]}...")

        # ============================================================
        # 3. Check if brand accounts return audience data
        # ============================================================
        print("\n" + "-" * 50)
        print("3. TESTING IF BRANDS HAVE MEDIA KITS")
        print("-" * 50)
        
        for brand in TEST_BRANDS:
            print(f"\n  Testing @{brand}...")
            
            # Search for brand
            search_result = await test_endpoint(
                client, "GET", f"{BASE_URL}/media-kits",
                params={"search": brand, "platform_type": 2, "limit": 5}
            )
            
            if search_result.get("success"):
                print(f"    ✅ Search found results")
                try:
                    data = json.loads(search_result.get("data_preview", "{}").replace("...", ""))
                    # This won't work with truncated data, but shows the attempt
                except Exception:
                    pass
            else:
                print(f"    ❌ Search failed: {search_result.get('status_code', 'N/A')}")

        # ============================================================
        # 4. List all available endpoints (OpenAPI spec)
        # ============================================================
        print("\n" + "-" * 50)
        print("4. CHECKING FOR API DOCUMENTATION ENDPOINTS")
        print("-" * 50)
        
        doc_endpoints = [
            ("GET", f"{BASE_URL}/openapi.json"),
            ("GET", f"{BASE_URL}/v1/openapi.json"),
            ("GET", f"{BASE_URL}/swagger.json"),
            ("GET", f"{BASE_URL}/api-docs"),
            ("GET", f"{BASE_URL}/docs"),
        ]
        
        for method, url in doc_endpoints:
            result = await test_endpoint(client, method, url)
            status = "✅" if result.get("success") else f"❌ ({result.get('status_code', 'N/A')})"
            print(f"  {status} {method} {url}")
            if result.get("success"):
                print(f"      Found API documentation!")

        # ============================================================
        # 5. Test Universe AI endpoint (if exists)
        # ============================================================
        print("\n" + "-" * 50)
        print("5. TESTING UNIVERSE AI ENDPOINTS")
        print("-" * 50)
        
        universe_endpoints = [
            ("POST", f"{BASE_URL}/universe/query"),
            ("POST", f"{BASE_URL}/v1/universe/query"),
            ("POST", f"{BASE_URL}/ai/query"),
            ("POST", f"{BASE_URL}/v1/ai/query"),
            ("POST", f"{BASE_URL}/chat"),
            ("POST", f"{BASE_URL}/v1/chat"),
        ]
        
        for method, url in universe_endpoints:
            result = await test_endpoint(client, method, url, json={
                "query": "What is the audience overlap between @cristiano and @nike?"
            })
            status = "✅" if result.get("success") else f"❌ ({result.get('status_code', 'N/A')})"
            print(f"  {status} {method} {url}")
            if result.get("success"):
                print(f"      Preview: {result.get('data_preview', 'N/A')[:100]}...")

    # ============================================================
    # Summary
    # ============================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("""
Based on the exploration above:

If NO endpoints returned 200:
  - PrimeTag may not expose audience overlap via their standard API
  - Consider contacting PrimeTag support to inquire about:
    * Universe AI API access
    * Audience overlap/brand affinity endpoints
    * Higher API tiers with additional features

Alternative approaches if API unavailable:
  1. Use brand_mentions from MediaKit as a proxy for brand relationships
  2. Pre-compute overlap data for top brands manually
  3. Use LLM analysis of influencer content for brand affinity estimation
""")


async def main():
    """Run the exploration."""
    await probe_audience_overlap_endpoints()


if __name__ == "__main__":
    print("\n🚀 Starting PrimeTag Audience Overlap API Exploration...\n")
    asyncio.run(main())
    print("\n✅ Exploration complete!\n")
