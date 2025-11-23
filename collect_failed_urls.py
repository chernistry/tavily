#!/usr/bin/env python3
"""
Collect URLs that fail on HTTP-only path for browser stealth testing.

This script runs all URLs through httpx-only (no browser fallback),
then extracts failed URLs into a separate CSV for targeted browser testing.
"""

import json
from pathlib import Path

from tavily_scraper.config.env import load_run_config
from tavily_scraper.pipelines.batch_runner import run_batch
from tavily_scraper.utils.io import load_urls_from_csv


async def main() -> None:
    input_file = Path(".sdd/raw/urls.csv")
    output_file = Path(".sdd/raw/failed_urls.csv")
    stats_file = Path("data/stats_httpx_only.jsonl")
    
    print(f"Loading URLs from {input_file}...")
    urls = load_urls_from_csv(input_file)
    print(f"Loaded {len(urls)} URLs")
    
    # Run with browser disabled
    config = load_run_config()
    
    print("\n🔍 Running HTTP-only pass (no browser fallback)...")
    await run_batch(
        urls=urls,
        config=config,
        use_browser=False,
        stats_suffix="_httpx_only",
    )
    
    # Extract failed URLs
    print(f"\n📊 Analyzing results from {stats_file}...")
    failed_urls = []
    
    with open(stats_file) as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            # Collect anything that's not success
            if row["status"] != "success":
                failed_urls.append(row["url"])
    
    print(f"Found {len(failed_urls)} failed URLs")
    
    # Save to CSV
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        f.write("url\n")
        for url in failed_urls:
            f.write(f"{url}\n")
    
    print(f"✓ Saved failed URLs to {output_file}")
    print("\nNext steps:")
    print(f"  1. Test without stealth: ./run.sh compare-browser {output_file}")
    print("  2. Or run manually:")
    print(f"     python run_pipeline.py --urls {output_file}")
    print(f"     python run_pipeline.py --urls {output_file} --stealth")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
