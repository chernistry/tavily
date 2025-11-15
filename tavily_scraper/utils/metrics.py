"""
Metrics computation and aggregation for scraping runs.

This module provides:
- Percentile calculation for latency analysis
- Run summary computation from URL statistics
- Success/error rate calculations
- Method distribution analysis (HTTP vs browser)
- Content size statistics
"""

from __future__ import annotations

from collections.abc import Iterable
from statistics import mean
from typing import Optional

from tavily_scraper.core.models import RunSummary, UrlStats




# ==== STATISTICAL UTILITIES ==== #

def percentile(values: list[int], p: float) -> Optional[int]:
    """
    Calculate percentile of integer values.

    Uses nearest-rank method for percentile calculation.

    Args:
        values: List of integer values
        p: Percentile to calculate (0-100)

    Returns:
        Percentile value or None if list is empty

    Example:
        percentile([1, 2, 3, 4, 5], 50) -> 3  # median
        percentile([1, 2, 3, 4, 5], 95) -> 5  # P95
    """
    if not values:
        return None

    values_sorted = sorted(values)
    k = max(
        0,
        min(
            len(values_sorted) - 1,
            int(round((p / 100.0) * (len(values_sorted) - 1))),
        ),
    )

    return values_sorted[k]




# ==== RUN SUMMARY COMPUTATION ==== #

def compute_run_summary(stats: Iterable[UrlStats]) -> RunSummary:
    """
    Compute aggregate run summary from URL statistics.

    This function analyzes all URL statistics to produce:
    - Success/error/timeout/CAPTCHA/robots rates
    - HTTP vs browser method distribution
    - Latency percentiles per method
    - Average content sizes per method

    Args:
        stats: Iterable of UrlStats from scraping run

    Returns:
        RunSummary with aggregate metrics

    Note:
        Returns zero-filled summary if no stats provided.
    """
    rows = list(stats)
    total = len(rows)

    # --► HANDLE EMPTY INPUT
    if total == 0:
        return RunSummary(
            total_urls=0,
            stats_rows=0,
            success_rate=0.0,
            http_error_rate=0.0,
            timeout_rate=0.0,
            captcha_rate=0.0,
            robots_block_rate=0.0,
            httpx_share=0.0,
            playwright_share=0.0,
            p50_latency_httpx_ms=None,
            p95_latency_httpx_ms=None,
            p50_latency_playwright_ms=None,
            p95_latency_playwright_ms=None,
            avg_content_len_httpx=None,
            avg_content_len_playwright=None,
        )

    # --► COUNT BY STATUS
    success_count = sum(1 for r in rows if r["status"] == "success")
    http_error_count = sum(1 for r in rows if r["status"] == "http_error")
    timeout_count = sum(1 for r in rows if r["status"] == "timeout")
    captcha_count = sum(1 for r in rows if r["status"] == "captcha_detected")
    robots_count = sum(1 for r in rows if r["status"] == "robots_blocked")

    # --► COUNT BY METHOD
    httpx_count = sum(1 for r in rows if r["method"] == "httpx")
    playwright_count = sum(1 for r in rows if r["method"] == "playwright")

    # --► COLLECT LATENCIES BY METHOD
    httpx_latencies = [
        r["latency_ms"]
        for r in rows
        if r["method"] == "httpx" and r["latency_ms"]
    ]
    playwright_latencies = [
        r["latency_ms"]
        for r in rows
        if r["method"] == "playwright" and r["latency_ms"]
    ]

    # --► COLLECT CONTENT LENGTHS BY METHOD
    httpx_content_lens = [
        r["content_len"]
        for r in rows
        if r["method"] == "httpx" and r["content_len"]
    ]
    playwright_content_lens = [
        r["content_len"]
        for r in rows
        if r["method"] == "playwright" and r["content_len"]
    ]

    # --► CONSTRUCT SUMMARY
    return RunSummary(
        total_urls=total,
        stats_rows=total,
        success_rate=success_count / total if total > 0 else 0.0,
        http_error_rate=http_error_count / total if total > 0 else 0.0,
        timeout_rate=timeout_count / total if total > 0 else 0.0,
        captcha_rate=captcha_count / total if total > 0 else 0.0,
        robots_block_rate=robots_count / total if total > 0 else 0.0,
        httpx_share=httpx_count / total if total > 0 else 0.0,
        playwright_share=playwright_count / total if total > 0 else 0.0,
        p50_latency_httpx_ms=percentile(httpx_latencies, 50),
        p95_latency_httpx_ms=percentile(httpx_latencies, 95),
        p50_latency_playwright_ms=percentile(playwright_latencies, 50),
        p95_latency_playwright_ms=percentile(playwright_latencies, 95),
        avg_content_len_httpx=(
            int(mean(httpx_content_lens)) if httpx_content_lens else None
        ),
        avg_content_len_playwright=(
            int(mean(playwright_content_lens)) if playwright_content_lens else None
        ),
    )
