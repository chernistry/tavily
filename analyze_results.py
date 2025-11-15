#!/usr/bin/env python3
"""
Detailed analysis script for scraping results.

This script provides comprehensive analysis of stats.jsonl including:
- Status distribution breakdown
- Block type analysis
- CAPTCHA vendor identification
- HTTP status code patterns
- Top error-prone domains
- Method distribution (HTTP vs browser)
- Latency statistics per method
"""

# ==== STANDARD LIBRARY IMPORTS ==== #
import json
from collections import Counter
from pathlib import Path
from typing import Any

# ==== ANALYSIS LOGIC ==== #

def main() -> None:
    """
    Analyze stats.jsonl and display detailed breakdown.

    This function:
    1. Loads statistics from data/stats.jsonl
    2. Computes various breakdowns and aggregations
    3. Displays formatted analysis to console

    Returns:
        None

    Note:
        Exits early if stats file doesn't exist.
    """
    stats_file = Path("data/stats.jsonl")

    # --► FILE EXISTENCE CHECK
    if not stats_file.exists():
        print("No stats file found. Run the pipeline first.")
        return

    # --► LOAD STATISTICS
    stats: list[dict[str, Any]] = []

    with stats_file.open() as f:
        for line in f:
            if line.strip():
                stats.append(json.loads(line))

    # --► DISPLAY HEADER
    print(f"\n{'=' * 60}")
    print("DETAILED ANALYSIS")
    print(f"{'=' * 60}\n")

    # --► STATUS BREAKDOWN
    print("Status breakdown:")
    status_counts = Counter(s["status"] for s in stats)

    for status, count in status_counts.most_common():
        pct = count / len(stats) * 100
        print(f"  {status:20s} {count:5d} ({pct:5.1f}%)")

    # --► BLOCK TYPE ANALYSIS
    print("\nBlock types:")
    block_counts = Counter(s.get("block_type", "none") for s in stats)

    for block, count in block_counts.most_common():
        pct = count / len(stats) * 100
        print(f"  {block:20s} {count:5d} ({pct:5.1f}%)")

    # --► CAPTCHA VENDOR BREAKDOWN
    captcha_stats = [s for s in stats if s.get("captcha_detected")]

    if captcha_stats:
        print("\nCAPTCHA vendors:")
        vendors = Counter(s.get("block_vendor") for s in captcha_stats)

        for vendor, count in vendors.most_common():
            print(f"  {vendor:20s} {count:5d}")

    # --► HTTP STATUS CODE PATTERNS
    error_stats = [
        s
        for s in stats
        if s["status"] in ("http_error", "captcha_detected")
    ]

    if error_stats:
        print("\nHTTP status codes (errors):")
        codes = Counter(
            s.get("http_status")
            for s in error_stats
            if s.get("http_status")
        )

        for code, count in codes.most_common(10):
            print(f"  {code:5} {count:5d}")

    # --► TOP ERROR DOMAINS
    print("\nTop 10 domains with errors:")
    error_domains = Counter(s["domain"] for s in error_stats)

    for domain, count in error_domains.most_common(10):
        print(f"  {domain:40s} {count:3d}")

    # --► METHOD DISTRIBUTION
    print("\nMethod breakdown:")
    method_counts = Counter(s["method"] for s in stats)

    for method, count in method_counts.items():
        pct = count / len(stats) * 100
        print(f"  {method:20s} {count:5d} ({pct:5.1f}%)")

    # --► HTTP LATENCY STATISTICS
    httpx_latencies = [
        s["latency_ms"]
        for s in stats
        if s["method"] == "httpx" and s.get("latency_ms")
    ]

    if httpx_latencies:
        httpx_latencies.sort()
        print("\nHTTP latencies (ms):")
        print(f"  Min:  {min(httpx_latencies)}")
        print(f"  P50:  {httpx_latencies[len(httpx_latencies) // 2]}")
        print(f"  P95:  {httpx_latencies[int(len(httpx_latencies) * 0.95)]}")
        print(f"  Max:  {max(httpx_latencies)}")

    # --► BROWSER LATENCY STATISTICS
    playwright_latencies = [
        s["latency_ms"]
        for s in stats
        if s["method"] == "playwright" and s.get("latency_ms")
    ]

    if playwright_latencies:
        playwright_latencies.sort()
        print("\nBrowser latencies (ms):")
        print(f"  Min:  {min(playwright_latencies)}")
        print(f"  P50:  {playwright_latencies[len(playwright_latencies) // 2]}")
        print(
            f"  P95:  "
            f"{playwright_latencies[int(len(playwright_latencies) * 0.95)]}"
        )
        print(f"  Max:  {max(playwright_latencies)}")

    # --► DISPLAY FOOTER
    print(f"\n{'=' * 60}\n")




# ==== SCRIPT ENTRY POINT ==== #

if __name__ == "__main__":
    main()
