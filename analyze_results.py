#!/usr/bin/env python3
"""Analyze scraping results."""

import json
from collections import Counter
from pathlib import Path


def main():
    """Analyze stats.jsonl and show detailed breakdown."""
    stats_file = Path("data/stats.jsonl")
    
    if not stats_file.exists():
        print("No stats file found. Run the pipeline first.")
        return
    
    # Load stats
    stats = []
    with stats_file.open() as f:
        for line in f:
            if line.strip():
                stats.append(json.loads(line))
    
    print(f"\n{'='*60}")
    print("DETAILED ANALYSIS")
    print(f"{'='*60}\n")
    
    # Status breakdown
    print("Status breakdown:")
    status_counts = Counter(s['status'] for s in stats)
    for status, count in status_counts.most_common():
        pct = count / len(stats) * 100
        print(f"  {status:20s} {count:5d} ({pct:5.1f}%)")
    
    # Block types
    print("\nBlock types:")
    block_counts = Counter(s.get('block_type', 'none') for s in stats)
    for block, count in block_counts.most_common():
        pct = count / len(stats) * 100
        print(f"  {block:20s} {count:5d} ({pct:5.1f}%)")
    
    # CAPTCHA vendors
    captcha_stats = [s for s in stats if s.get('captcha_detected')]
    if captcha_stats:
        print("\nCAPTCHA vendors:")
        vendors = Counter(s.get('block_vendor') for s in captcha_stats)
        for vendor, count in vendors.most_common():
            print(f"  {vendor:20s} {count:5d}")
    
    # HTTP status codes for errors
    error_stats = [s for s in stats if s['status'] in ('http_error', 'captcha_detected')]
    if error_stats:
        print("\nHTTP status codes (errors):")
        codes = Counter(s.get('http_status') for s in error_stats if s.get('http_status'))
        for code, count in codes.most_common(10):
            print(f"  {code:5} {count:5d}")
    
    # Top error domains
    print("\nTop 10 domains with errors:")
    error_domains = Counter(s['domain'] for s in error_stats)
    for domain, count in error_domains.most_common(10):
        print(f"  {domain:40s} {count:3d}")
    
    # Method breakdown
    print("\nMethod breakdown:")
    method_counts = Counter(s['method'] for s in stats)
    for method, count in method_counts.items():
        pct = count / len(stats) * 100
        print(f"  {method:20s} {count:5d} ({pct:5.1f}%)")
    
    # Latency stats
    httpx_latencies = [s['latency_ms'] for s in stats if s['method'] == 'httpx' and s.get('latency_ms')]
    if httpx_latencies:
        httpx_latencies.sort()
        print("\nHTTP latencies (ms):")
        print(f"  Min:  {min(httpx_latencies)}")
        print(f"  P50:  {httpx_latencies[len(httpx_latencies)//2]}")
        print(f"  P95:  {httpx_latencies[int(len(httpx_latencies)*0.95)]}")
        print(f"  Max:  {max(httpx_latencies)}")
    
    playwright_latencies = [s['latency_ms'] for s in stats if s['method'] == 'playwright' and s.get('latency_ms')]
    if playwright_latencies:
        playwright_latencies.sort()
        print("\nBrowser latencies (ms):")
        print(f"  Min:  {min(playwright_latencies)}")
        print(f"  P50:  {playwright_latencies[len(playwright_latencies)//2]}")
        print(f"  P95:  {playwright_latencies[int(len(playwright_latencies)*0.95)]}")
        print(f"  Max:  {max(playwright_latencies)}")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
