"""Tests for fast HTTP fetcher."""

import pytest
from pytest_httpx import HTTPXMock

from tavily_scraper.core.models import (
    RunConfig,
    RunnerContext,
    UrlJob,
    UrlStr,
)
from tavily_scraper.core.robots import RobotsClient
from tavily_scraper.core.scheduler import DomainScheduler
from tavily_scraper.pipelines.fast_http_fetcher import (
    fetch_one,
    looks_incomplete_http,
    make_http_client,
)
from tavily_scraper.config.constants import DEFAULT_MAX_CONTENT_BYTES


def test_make_http_client() -> None:
    """Test HTTP client creation."""
    config = RunConfig()
    client = make_http_client(config, None)
    assert client is not None


def test_looks_incomplete_http() -> None:
    """Test incomplete HTTP detection."""
    from tavily_scraper.core.models import FetchResult

    result: FetchResult = {
        "url": UrlStr("https://example.com"),
        "domain": "example.com",
        "method": "httpx",
        "stage": "primary",
        "status": "success",
        "http_status": 200,
        "latency_ms": 100,
        "content_len": 500,  # too small
        "encoding": "utf-8",
        "retries": 0,
        "captcha_detected": False,
        "robots_disallowed": False,
        "error_kind": None,
        "error_message": None,
        "started_at": "2025-01-01T00:00:00Z",
        "finished_at": "2025-01-01T00:00:00Z",
        "shard_id": 0,
        "content": "<html>test</html>",
    }
    assert looks_incomplete_http(result)

    result["content_len"] = 2000
    assert not looks_incomplete_http(result)


@pytest.mark.asyncio
async def test_fetch_one_success(httpx_mock: HTTPXMock) -> None:
    """Test successful HTTP fetch."""
    httpx_mock.add_response(
        url="https://example.com/robots.txt",
        text="User-agent: *\nAllow: /\n",
    )
    httpx_mock.add_response(
        url="https://example.com/page",
        text="<html><body>Test content</body></html>",
        headers={"Content-Type": "text/html"},
    )

    import httpx

    config = RunConfig()
    scheduler = DomainScheduler(global_limit=10)
    robots_client = RobotsClient(httpx.AsyncClient())
    http_client = httpx.AsyncClient()

    ctx = RunnerContext(
        run_config=config,
        proxy_manager=None,
        scheduler=scheduler,
        robots_client=robots_client,
        http_client=http_client,
    )

    job: UrlJob = {
        "url": UrlStr("https://example.com/page"),
        "is_dynamic_hint": None,
        "shard_id": 0,
        "index_in_shard": 0,
    }

    result = await fetch_one(job, ctx)
    assert result["status"] == "success"
    assert result["http_status"] == 200
    assert result["domain"] == "example.com"
    assert result["content_len"] > 0
    await http_client.aclose()
    await robots_client._client.aclose()


@pytest.mark.asyncio
async def test_fetch_one_timeout_retries(httpx_mock: HTTPXMock) -> None:
    """Test that transient timeouts are retried."""
    import httpx

    # robots.txt allowed
    httpx_mock.add_response(
        url="https://example.com/robots.txt",
        text="User-agent: *\nAllow: /\n",
    )
    # First attempt: timeout
    httpx_mock.add_exception(
        url="https://example.com/page",
        exception=httpx.TimeoutException("simulated timeout"),
    )
    # Second attempt: success
    httpx_mock.add_response(
        url="https://example.com/page",
        text="<html><body>OK</body></html>",
        headers={"Content-Type": "text/html"},
    )

    config = RunConfig()
    scheduler = DomainScheduler(global_limit=10)
    robots_client = RobotsClient(httpx.AsyncClient())
    http_client = httpx.AsyncClient()

    ctx = RunnerContext(
        run_config=config,
        proxy_manager=None,
        scheduler=scheduler,
        robots_client=robots_client,
        http_client=http_client,
    )

    job: UrlJob = {
        "url": UrlStr("https://example.com/page"),
        "is_dynamic_hint": None,
        "shard_id": 0,
        "index_in_shard": 0,
    }

    result = await fetch_one(job, ctx)
    await http_client.aclose()
    await robots_client._client.aclose()

    assert result["status"] == "success"
    # At least one retry should have been attempted
    assert result.get("retries", 0) >= 1


@pytest.mark.asyncio
async def test_fetch_one_robots_blocked_short_circuits(httpx_mock: HTTPXMock) -> None:
    """Robots-disallowed URLs should short-circuit without issuing HTTP GET."""
    import httpx

    httpx_mock.add_response(
        url="https://example.com/robots.txt",
        text="User-agent: *\nDisallow: /page\n",
    )

    config = RunConfig()
    scheduler = DomainScheduler(global_limit=10)
    robots_client = RobotsClient(httpx.AsyncClient())
    http_client = httpx.AsyncClient()

    ctx = RunnerContext(
        run_config=config,
        proxy_manager=None,
        scheduler=scheduler,
        robots_client=robots_client,
        http_client=http_client,
    )

    job: UrlJob = {
        "url": UrlStr("https://example.com/page"),
        "is_dynamic_hint": None,
        "shard_id": 0,
        "index_in_shard": 0,
    }

    result = await fetch_one(job, ctx)
    await http_client.aclose()
    await robots_client._client.aclose()

    assert result["status"] == "robots_blocked"
    assert result["robots_disallowed"] is True
    assert result.get("http_status") is None
    assert result.get("content_len", 0) == 0


@pytest.mark.asyncio
async def test_fetch_one_connection_error_maps_to_http_error(
    httpx_mock: HTTPXMock,
) -> None:
    """Connection-level HTTP errors should be mapped to http_error status."""
    import httpx

    httpx_mock.add_response(
        url="https://example.com/robots.txt",
        text="User-agent: *\nAllow: /\n",
    )
    httpx_mock.add_exception(
        url="https://example.com/page",
        exception=httpx.ConnectError("simulated connection error"),
    )

    config = RunConfig()
    scheduler = DomainScheduler(global_limit=10)
    robots_client = RobotsClient(httpx.AsyncClient())
    http_client = httpx.AsyncClient()

    ctx = RunnerContext(
        run_config=config,
        proxy_manager=None,
        scheduler=scheduler,
        robots_client=robots_client,
        http_client=http_client,
    )

    job: UrlJob = {
        "url": UrlStr("https://example.com/page"),
        "is_dynamic_hint": None,
        "shard_id": 0,
        "index_in_shard": 0,
    }

    result = await fetch_one(job, ctx)
    await http_client.aclose()
    await robots_client._client.aclose()

    assert result["status"] == "http_error"
    assert result["error_kind"] == "ConnectError"
    # For client-level HTTP errors there is no HTTP status code
    assert result.get("http_status") is None
    assert result.get("latency_ms") is not None


@pytest.mark.asyncio
async def test_fetch_one_too_large_classification(httpx_mock: HTTPXMock) -> None:
    """Very large responses should be classified as too_large."""
    import httpx

    httpx_mock.add_response(
        url="https://example.com/robots.txt",
        text="User-agent: *\nAllow: /\n",
    )

    # Build a body just over the configured max size
    body = "a" * (DEFAULT_MAX_CONTENT_BYTES + 1)
    httpx_mock.add_response(
        url="https://example.com/big",
        text=body,
        headers={"Content-Type": "text/html; charset=utf-8"},
    )

    config = RunConfig()
    scheduler = DomainScheduler(global_limit=10)
    robots_client = RobotsClient(httpx.AsyncClient())
    http_client = httpx.AsyncClient()

    ctx = RunnerContext(
        run_config=config,
        proxy_manager=None,
        scheduler=scheduler,
        robots_client=robots_client,
        http_client=http_client,
    )

    job: UrlJob = {
        "url": UrlStr("https://example.com/big"),
        "is_dynamic_hint": None,
        "shard_id": 0,
        "index_in_shard": 0,
    }

    result = await fetch_one(job, ctx)
    await http_client.aclose()
    await robots_client._client.aclose()

    assert result["status"] == "too_large"
    assert result["content_len"] == DEFAULT_MAX_CONTENT_BYTES + 1
    # content should not be kept in memory or persisted
    assert result.get("content") is None
