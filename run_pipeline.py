#!/usr/bin/env python3
"""
Main entry point for the Tavily web scraping pipeline.

This script orchestrates the hybrid HTTP + Playwright scraping workflow,
supporting both total URL count and success-based processing modes.
"""

# ==== STANDARD LIBRARY IMPORTS ==== #
import asyncio
import random
import sys
from pathlib import Path

# ==== PROJECT IMPORTS ==== #
from tavily_scraper.config.env import load_run_config
from tavily_scraper.core.models import RunSummary
from tavily_scraper.pipelines.batch_runner import run_batch
from tavily_scraper.utils.io import load_urls_from_csv

# ==== CORE PIPELINE ORCHESTRATION ==== #

async def main() -> None:
    """
    Execute the scraping pipeline with configurable parameters.

    This function:
    1. Parses command-line arguments
    2. Loads and optionally shuffles URLs
    3. Configures processing mode (total vs success-based)
    4. Runs the batch pipeline
    5. Displays formatted results

    Returns:
        None

    Raises:
        SystemExit: If invalid arguments are provided
    """
    # --► ARGUMENT PARSING
    use_browser: bool = "--browser" in sys.argv
    use_random: bool = "--random" in sys.argv
    target_mode: bool = "--success" in sys.argv
    stealth_enabled: bool = "--stealth" in sys.argv
    
    # Parse --urls
    urls_file: Path = Path(".sdd/raw/urls.csv")
    if "--urls" in sys.argv:
        idx = sys.argv.index("--urls")
        if idx + 1 < len(sys.argv):
            urls_file = Path(sys.argv[idx + 1])
    
    # Parse --count
    target: int | None = None
    if "--count" in sys.argv:
        idx = sys.argv.index("--count")
        if idx + 1 < len(sys.argv):
            target = int(sys.argv[idx + 1])
    elif len(sys.argv) >= 2 and sys.argv[1].isdigit():
        target = int(sys.argv[1])
    
    # Parse --stats-suffix
    custom_suffix: str | None = None
    if "--stats-suffix" in sys.argv:
        idx = sys.argv.index("--stats-suffix")
        if idx + 1 < len(sys.argv):
            custom_suffix = sys.argv[idx + 1]
    
    if target is None and not urls_file.exists():
        print_usage()
        return

    # --► URL LOADING & PREPARATION
    urls: list[str] = load_urls_from_csv(urls_file)
    print(f"Loaded {len(urls)} URLs from {urls_file}")

    if use_random:
        random.shuffle(urls)
        print("Shuffled URLs randomly")

    # --► MODE CONFIGURATION
    max_urls: int | None
    target_success: int | None

    if target_mode and target:
        print(f"Mode: Process until {target} SUCCESSFUL URLs")
        max_urls = None
        target_success = target
    elif target:
        print(f"Mode: Process {target} URLs total")
        max_urls = target
        target_success = None
    else:
        print(f"Mode: Process all URLs from {urls_file}")
        max_urls = None
        target_success = None

    print(f"Browser fallback: {'enabled' if use_browser else 'disabled'}")
    print(f"Stealth mode: {'enabled' if stealth_enabled else 'disabled'}")
    print("\nStarting pipeline...\n")

    # --► PIPELINE EXECUTION
    config = load_run_config()
    if config.stealth_config:
        config.stealth_config.enabled = stealth_enabled

    # Determine stats suffix
    if custom_suffix:
        stats_suffix = custom_suffix
    elif stealth_enabled:
        stats_suffix = "_stealth"
    else:
        stats_suffix = ""

    summary = await run_batch(
        urls,
        config,
        max_urls=max_urls,
        target_success=target_success,
        use_browser=use_browser,
        stats_suffix=stats_suffix,
    )

    # --► RESULTS DISPLAY
    stats_filename = f"stats{stats_suffix}.jsonl" if stats_suffix else "stats.jsonl"
    summary_filename = (
        f"run_summary{stats_suffix}.json"
        if stats_suffix
        else "run_summary.json"
    )
    _display_results(summary, stats_filename, summary_filename)




# ==== RESULTS FORMATTING & DISPLAY ==== #

def _display_results(
    summary: RunSummary,
    stats_filename: str,
    summary_filename: str,
) -> None:
    """
    Display formatted pipeline execution results.

    Args:
        summary: Dictionary containing execution metrics including:
            - total_urls: Total number of URLs processed
            - success_rate: Fraction of successful fetches
            - http_error_rate: Fraction of HTTP errors
            - timeout_rate: Fraction of timeouts
            - captcha_rate: Fraction of CAPTCHA detections
            - robots_block_rate: Fraction of robots.txt blocks
            - httpx_share: Fraction using HTTP-only path
            - playwright_share: Fraction requiring browser
            - p50_latency_httpx_ms: HTTP P50 latency
            - p95_latency_httpx_ms: HTTP P95 latency
            - p50_latency_playwright_ms: Browser P50 latency
            - p95_latency_playwright_ms: Browser P95 latency

    Returns:
        None
    """
    successful: int = int(summary["total_urls"] * summary["success_rate"])

    print(f"\n{'=' * 60}")
    print("RESULTS")
    print(f"{'=' * 60}")
    print(f"Total processed:     {summary['total_urls']}")
    print(
        f"Successful:          {successful} "
        f"({summary['success_rate']:.1%})"
    )
    print(
        f"HTTP errors:         "
        f"{int(summary['total_urls'] * summary['http_error_rate'])} "
        f"({summary['http_error_rate']:.1%})"
    )
    print(
        f"Timeouts:            "
        f"{int(summary['total_urls'] * summary['timeout_rate'])} "
        f"({summary['timeout_rate']:.1%})"
    )
    print(
        f"CAPTCHAs:            "
        f"{int(summary['total_urls'] * summary['captcha_rate'])} "
        f"({summary['captcha_rate']:.1%})"
    )
    print(
        f"Robots blocked:      "
        f"{int(summary['total_urls'] * summary['robots_block_rate'])} "
        f"({summary['robots_block_rate']:.1%})"
    )

    print("\nMethod breakdown:")
    print(f"  HTTP only:         {summary['httpx_share']:.1%}")
    print(f"  Browser fallback:  {summary['playwright_share']:.1%}")

    print("\nLatency (HTTP):")
    print(f"  P50: {summary['p50_latency_httpx_ms']}ms")
    print(f"  P95: {summary['p95_latency_httpx_ms']}ms")

    if summary["playwright_share"] > 0:
        print("\nLatency (Browser):")
        print(f"  P50: {summary['p50_latency_playwright_ms']}ms")
        print(f"  P95: {summary['p95_latency_playwright_ms']}ms")

    print(f"\nStats saved to: data/{stats_filename}")
    print(f"Summary saved to: data/{summary_filename}")
    print(f"{'=' * 60}\n")




# ==== USAGE DOCUMENTATION ==== #

def print_usage() -> None:
    """
    Display command-line usage information and examples.

    Returns:
        None
    """
    print(
        """
Usage:
  python run_pipeline.py [--count N] [--urls FILE] [OPTIONS]

Options:
  --count N              Process N URLs total (or use positional: python run_pipeline.py 100)
  --urls FILE            Use custom URLs file (default: .sdd/raw/urls.csv)
  --success              Process until N successful URLs (requires --count)
  --browser              Enable Playwright browser fallback
  --random               Shuffle URLs randomly
  --stealth              Enable stealth anti-detection
  --stats-suffix SUFFIX  Custom suffix for stats files

Examples:
  python run_pipeline.py 100                              # Process 100 URLs
  python run_pipeline.py --count 100 --stealth            # With stealth
  python run_pipeline.py --urls failed.csv                # Custom file
  python run_pipeline.py --urls failed.csv --stats-suffix _test  # Custom suffix
  python run_pipeline.py 50 --success --browser           # Until 50 successes
"""
    )




# ==== SCRIPT ENTRY POINT ==== #

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help"]:
        print_usage()
    else:
        asyncio.run(main())
