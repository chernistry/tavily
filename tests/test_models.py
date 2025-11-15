"""Tests for core models."""

from tavily_scraper.core.models import (
    UrlJob,
    UrlStr,
    fetch_result_to_url_stats,
    make_initial_fetch_result,
)


def test_make_initial_fetch_result() -> None:
    """Test creating initial fetch result."""
    job: UrlJob = {
        "url": UrlStr("https://example.com"),
        "is_dynamic_hint": None,
        "shard_id": 0,
        "index_in_shard": 0,
    }
    result = make_initial_fetch_result(job, "httpx", "primary")
    assert result["url"] == "https://example.com"
    assert result["method"] == "httpx"
    assert result["stage"] == "primary"
    assert result["status"] == "other_error"
    assert result["shard_id"] == 0


def test_fetch_result_to_url_stats() -> None:
    """Test converting FetchResult to UrlStats."""
    job: UrlJob = {
        "url": UrlStr("https://example.com"),
        "is_dynamic_hint": None,
        "shard_id": 0,
        "index_in_shard": 0,
    }
    result = make_initial_fetch_result(job, "httpx", "primary")
    result["domain"] = "example.com"
    result["status"] = "success"
    result["http_status"] = 200
    result["latency_ms"] = 120
    result["content_len"] = 2048
    result["content"] = "<html>test</html>"  # should be stripped

    stats = fetch_result_to_url_stats(result)
    assert stats["url"] == "https://example.com"
    assert stats["domain"] == "example.com"
    assert stats["status"] == "success"
    assert stats["http_status"] == 200
    assert stats["latency_ms"] == 120
    assert stats["content_len"] == 2048
    assert "content" not in stats  # content should not be in UrlStats
