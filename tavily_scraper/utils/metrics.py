"""Metrics computation and aggregation."""

from __future__ import annotations

from collections.abc import Iterable
from statistics import mean

from tavily_scraper.core.models import RunSummary, UrlStats


def percentile(values: list[int], p: float) -> int | None:
    """Calculate percentile of integer values."""
    if not values:
        return None
    values_sorted = sorted(values)
    k = max(
        0, min(len(values_sorted) - 1, int(round((p / 100.0) * (len(values_sorted) - 1))))
    )
    return values_sorted[k]


def compute_run_summary(stats: Iterable[UrlStats]) -> RunSummary:
    """Compute run summary from URL stats."""
    rows = list(stats)
    total = len(rows)

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

    # Count by status
    success_count = sum(1 for r in rows if r["status"] == "success")
    http_error_count = sum(1 for r in rows if r["status"] == "http_error")
    timeout_count = sum(1 for r in rows if r["status"] == "timeout")
    captcha_count = sum(1 for r in rows if r["status"] == "captcha_detected")
    robots_count = sum(1 for r in rows if r["status"] == "robots_blocked")

    # Count by method
    httpx_count = sum(1 for r in rows if r["method"] == "httpx")
    playwright_count = sum(1 for r in rows if r["method"] == "playwright")

    # Latencies by method
    httpx_latencies = [
        r["latency_ms"] for r in rows if r["method"] == "httpx" and r["latency_ms"]
    ]
    playwright_latencies = [
        r["latency_ms"]
        for r in rows
        if r["method"] == "playwright" and r["latency_ms"]
    ]

    # Content lengths by method
    httpx_content_lens = [
        r["content_len"] for r in rows if r["method"] == "httpx" and r["content_len"]
    ]
    playwright_content_lens = [
        r["content_len"]
        for r in rows
        if r["method"] == "playwright" and r["content_len"]
    ]

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
        avg_content_len_httpx=int(mean(httpx_content_lens))
        if httpx_content_lens
        else None,
        avg_content_len_playwright=int(mean(playwright_content_lens))
        if playwright_content_lens
        else None,
    )
