"""Tests for metrics computation."""

from tavily_scraper.core.models import UrlStats
from tavily_scraper.utils.metrics import compute_run_summary, percentile


def test_percentile() -> None:
    """Test percentile calculation."""
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert percentile(values, 50) == 5
    assert percentile(values, 95) == 10
    assert percentile([], 50) is None


def test_compute_run_summary_empty() -> None:
    """Test run summary with no stats."""
    summary = compute_run_summary([])
    assert summary["total_urls"] == 0
    assert summary["success_rate"] == 0.0


def test_compute_run_summary() -> None:
    """Test run summary computation."""
    stats: list[UrlStats] = [
        {
            "url": "https://example.com",
            "domain": "example.com",
            "method": "httpx",
            "stage": "primary",
            "status": "success",
            "http_status": 200,
            "latency_ms": 100,
            "content_len": 1000,
            "encoding": "utf-8",
            "retries": 0,
            "captcha_detected": False,
            "robots_disallowed": False,
            "error_kind": None,
            "error_message": None,
            "timestamp": "2025-01-01T00:00:00Z",
            "shard_id": 0,
            "block_type": None,
            "block_vendor": None,
        },
        {
            "url": "https://test.com",
            "domain": "test.com",
            "method": "playwright",
            "stage": "fallback",
            "status": "success",
            "http_status": 200,
            "latency_ms": 2000,
            "content_len": 5000,
            "encoding": "utf-8",
            "retries": 0,
            "captcha_detected": False,
            "robots_disallowed": False,
            "error_kind": None,
            "error_message": None,
            "timestamp": "2025-01-01T00:00:01Z",
            "shard_id": 0,
            "block_type": None,
            "block_vendor": None,
        },
    ]

    summary = compute_run_summary(stats)
    assert summary["total_urls"] == 2
    assert summary["success_rate"] == 1.0
    assert summary["httpx_share"] == 0.5
    assert summary["playwright_share"] == 0.5
    assert summary["p50_latency_httpx_ms"] == 100
    assert summary["p50_latency_playwright_ms"] == 2000
