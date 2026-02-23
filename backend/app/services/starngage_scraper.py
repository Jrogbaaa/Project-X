#!/usr/bin/env python3
"""
Starngage Spain Influencer Scraper — Helper Utilities

The actual scraping is done interactively via Cursor's Playwright MCP browser.
See directives/starngage-scraper.md for the full process.

This module provides:
  - parse_follower_count(): Convert '209.6K' / '1.2M' to numeric
  - extract_page(): Parse one page of Starngage HTML into dicts
  - combine_and_write_csv(): Merge batch JSON files, filter by threshold, write CSV

Usage (after extracting batches via Playwright MCP):
    cd backend && python -m app.services.starngage_scraper \\
        --batch-files file1.txt file2.txt file3.txt \\
        --min-followers 100000 \\
        --output ../starngage_spain_influencers_2026.csv
"""

import argparse
import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

BASE_URL = "https://starngage.com/plus/en-us/influencer/ranking/instagram/spain"
DEFAULT_MIN_FOLLOWERS = 100_000
DEFAULT_OUTPUT = "../starngage_spain_influencers_{year}.csv"


def parse_follower_count(text: str) -> float:
    """Convert '209.6K' or '1.2M' to a numeric value."""
    text = text.strip()
    if not text:
        return 0.0
    if text.endswith("M"):
        return float(text[:-1]) * 1_000_000
    if text.endswith("K"):
        return float(text[:-1]) * 1_000
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return 0.0


def extract_page(html: str) -> list[dict]:
    """Parse one page of Starngage HTML and return influencer dicts."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table tbody")
    if not table:
        return []

    rows = table.select("tr")
    results = []
    for row in rows:
        cells = row.select("td")
        if len(cells) < 4:
            continue

        rank = cells[0].get_text(strip=True)

        name_cell = cells[1]
        handle_link = name_cell.select_one("a")
        handle = handle_link.get_text(strip=True) if handle_link else ""
        name_container = name_cell.select_one("div > div:last-child")
        name = ""
        if name_container:
            first_div = name_container.select_one("div:first-child")
            name = first_div.get_text(strip=True) if first_div else ""

        followers = cells[2].get_text(strip=True)
        er = cells[3].get_text(strip=True) if len(cells) > 3 else ""

        topics = ""
        if len(cells) > 5:
            topic_links = cells[5].select("a")
            topics = ", ".join(
                a.get_text(strip=True) for a in topic_links if a.get_text(strip=True)
            )

        results.append({
            "rank": rank,
            "name": name,
            "handle": handle,
            "followers": followers,
            "er": er,
            "topics": topics,
        })

    return results


def load_batch_file(path: str) -> list[dict]:
    """Load influencer data from a Playwright MCP agent-tools output file."""
    with open(path, "r") as f:
        content = f.read()

    start = content.index('"{')
    end = content.index('}"', start) + 2
    json_str = content[start:end]
    parsed = json.loads(json_str)
    data = json.loads(parsed) if isinstance(parsed, str) else parsed
    return data["data"]


def combine_and_write_csv(
    batch_files: list[str],
    min_followers: int = DEFAULT_MIN_FOLLOWERS,
    output_path: str | None = None,
    existing_csv: str | None = None,
) -> list[dict]:
    """
    Combine batch JSON files, filter by follower threshold, write CSV.

    Args:
        batch_files: Paths to agent-tools output files from browser_evaluate
        min_followers: Minimum follower count to include
        output_path: Where to write the CSV
        existing_csv: Optional path to existing CSV to prepend (for appending batches)
    """
    if output_path is None:
        output_path = DEFAULT_OUTPUT.format(year=datetime.now().year)

    all_data: list[dict] = []

    if existing_csv:
        with open(existing_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            all_data.extend(reader)
        logger.info("Loaded %d existing rows from %s", len(all_data), existing_csv)

    for bf in batch_files:
        batch = load_batch_file(bf)
        logger.info(
            "Batch %s: %d rows, ranks %s-%s, last followers: %s",
            Path(bf).name,
            len(batch),
            batch[0]["rank"],
            batch[-1]["rank"],
            batch[-1]["followers"],
        )
        all_data.extend(batch)

    logger.info("Combined total: %d rows", len(all_data))

    filtered = [
        row for row in all_data
        if parse_follower_count(row["followers"]) >= min_followers
    ]
    logger.info(
        "After %s filter: %d influencers",
        f"{min_followers:,}",
        len(filtered),
    )

    if filtered:
        logger.info(
            "First: rank %s %s (%s)",
            filtered[0]["rank"], filtered[0]["name"], filtered[0]["followers"],
        )
        logger.info(
            "Last:  rank %s %s (%s)",
            filtered[-1]["rank"], filtered[-1]["name"], filtered[-1]["followers"],
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["rank", "name", "handle", "followers", "er", "topics"]
        )
        writer.writeheader()
        writer.writerows(filtered)

    logger.info("Wrote %d rows to %s", len(filtered), output)
    return filtered


def main():
    parser = argparse.ArgumentParser(
        description="Combine Starngage batch extracts into a single CSV",
    )
    parser.add_argument(
        "--batch-files",
        nargs="+",
        required=True,
        help="Paths to agent-tools output files from browser_evaluate batches",
    )
    parser.add_argument(
        "--min-followers",
        type=int,
        default=DEFAULT_MIN_FOLLOWERS,
        help=f"Minimum follower count to include (default: {DEFAULT_MIN_FOLLOWERS:,})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV path (default: ../starngage_spain_influencers_YEAR.csv)",
    )
    parser.add_argument(
        "--existing-csv",
        type=str,
        default=None,
        help="Path to existing CSV to prepend (for appending new batches)",
    )
    args = parser.parse_args()

    combine_and_write_csv(
        batch_files=args.batch_files,
        min_followers=args.min_followers,
        output_path=args.output,
        existing_csv=args.existing_csv,
    )


if __name__ == "__main__":
    main()
