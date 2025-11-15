#!/usr/bin/env python3
"""Run the scraping pipeline."""

import asyncio
import random
import sys
from pathlib import Path

from tavily_scraper.config.env import load_run_config
from tavily_scraper.pipelines.batch_runner import run_batch
from tavily_scraper.utils.io import load_urls_from_csv


async def main():
    """Run pipeline with configurable parameters."""
    # Parse arguments
    if len(sys.argv) < 2:
        print_usage()
        return
    
    target = int(sys.argv[1])
    use_browser = "--browser" in sys.argv
    use_random = "--random" in sys.argv
    target_mode = "--success" in sys.argv  # Default is total URLs
    
    # Load URLs
    urls_file = Path(".sdd/raw/urls.csv")
    urls = load_urls_from_csv(urls_file)
    print(f"Loaded {len(urls)} URLs from {urls_file}")
    
    # Shuffle if random
    if use_random:
        random.shuffle(urls)
        print("Shuffled URLs randomly")
    
    # Determine mode
    if target_mode:
        print(f"Mode: Process until {target} SUCCESSFUL URLs")
        max_urls = None
        target_success = target
    else:
        print(f"Mode: Process {target} URLs total")
        max_urls = target
        target_success = None
    
    print(f"Browser fallback: {'enabled' if use_browser else 'disabled'}")
    print("\nStarting pipeline...\n")
    
    # Load config for this run
    config = load_run_config()

    # Run pipeline
    summary = await run_batch(
        urls,
        config=config,
        max_urls=max_urls,
        target_success=target_success, 
        use_browser=use_browser
    )
    
    # Print results
    successful = int(summary['total_urls'] * summary['success_rate'])
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Total processed:     {summary['total_urls']}")
    print(f"Successful:          {successful} ({summary['success_rate']:.1%})")
    print(f"HTTP errors:         {int(summary['total_urls'] * summary['http_error_rate'])} ({summary['http_error_rate']:.1%})")
    print(f"Timeouts:            {int(summary['total_urls'] * summary['timeout_rate'])} ({summary['timeout_rate']:.1%})")
    print(f"CAPTCHAs:            {int(summary['total_urls'] * summary['captcha_rate'])} ({summary['captcha_rate']:.1%})")
    print(f"Robots blocked:      {int(summary['total_urls'] * summary['robots_block_rate'])} ({summary['robots_block_rate']:.1%})")
    print("\nMethod breakdown:")
    print(f"  HTTP only:         {summary['httpx_share']:.1%}")
    print(f"  Browser fallback:  {summary['playwright_share']:.1%}")
    print("\nLatency (HTTP):")
    print(f"  P50: {summary['p50_latency_httpx_ms']}ms")
    print(f"  P95: {summary['p95_latency_httpx_ms']}ms")
    if summary['playwright_share'] > 0:
        print("\nLatency (Browser):")
        print(f"  P50: {summary['p50_latency_playwright_ms']}ms")
        print(f"  P95: {summary['p95_latency_playwright_ms']}ms")
    print("\nStats saved to: data/stats.jsonl")
    print(f"{'='*60}\n")


def print_usage():
    """Print usage information."""
    print("""
Usage:
  python run_pipeline.py <number> [--success] [--browser] [--random]

Modes:
  <number>           Process N URLs total (default)
  <number> --success Process until N successful URLs
  
Options:
  --browser          Enable Playwright browser fallback for failed HTTP requests
  --random           Shuffle URLs randomly before processing

Examples:
  python run_pipeline.py 100                    # Process 100 URLs (HTTP only)
  python run_pipeline.py 100 --browser          # Process 100 URLs (with browser)
  python run_pipeline.py 100 --random           # Process 100 random URLs
  python run_pipeline.py 50 --success           # Process until 50 successful
  python run_pipeline.py 1000 --success --browser --random  # Full featured
""")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help"]:
        print_usage()
    else:
        asyncio.run(main())
