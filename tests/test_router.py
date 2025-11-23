"""Tests for strategy router."""

from __future__ import annotations

from typing import cast

import pytest

from tavily_scraper.config.constants import Status
from tavily_scraper.core.models import (
    FetchResult,
    RunConfig,
    RunnerContext,
    UrlJob,
    UrlStr,
)
from tavily_scraper.core.scheduler import DomainScheduler
from tavily_scraper.pipelines import router


def _make_fetch_result(
    *,
    status: str,
    http_status: int | None = 200,
    content_len: int = 2_000,
) -> FetchResult:
    return FetchResult(
        url=UrlStr("https://example.com/page"),
        domain="example.com",
        method="httpx",
        stage="primary",
        status=cast(Status, status),
        http_status=http_status,
        latency_ms=100,
        content_len=content_len,
        encoding="utf-8",
        retries=0,
        captcha_detected=False,
        robots_disallowed=False,
        error_kind=None,
        error_message=None,
        started_at="2025-01-01T00:00:00Z",
        finished_at="2025-01-01T00:00:00Z",
        shard_id=0,
        content="<html></html>",
    )


def test_needs_browser_basic_cases() -> None:
    """Verify needs_browser decisions for common status combinations."""
    # Successful but very small content should trigger browser fallback.
    res_small = _make_fetch_result(status="success", content_len=100)
    assert router.needs_browser(res_small)

    # Successful and large enough should not need browser.
    res_ok = _make_fetch_result(status="success", content_len=10_000)
    assert not router.needs_browser(res_ok)

    # Timeouts should be retried via browser.
    res_timeout = _make_fetch_result(status="timeout")
    assert router.needs_browser(res_timeout)

    # Generic HTTP errors: 500 → allow browser, 404/403 → skip browser.
    res_500 = _make_fetch_result(status="http_error", http_status=500)
    assert router.needs_browser(res_500)

    res_404 = _make_fetch_result(status="http_error", http_status=404)
    assert not router.needs_browser(res_404)

    # Robots and explicit CAPTCHA should never trigger browser fallback.
    res_robots = _make_fetch_result(status="robots_blocked")
    res_captcha = _make_fetch_result(status="captcha_detected")
    assert not router.needs_browser(res_robots)
    assert not router.needs_browser(res_captcha)


def _make_runner_context() -> RunnerContext:
    run_config = RunConfig()
    scheduler = DomainScheduler(global_limit=4)

    class _RobotsStub:
        async def can_fetch(self, url: str, user_agent: str | None = None) -> bool:  # noqa: D401
            """Always allow fetch."""
            return True

    robots_client = _RobotsStub()
    return RunnerContext(
        run_config=run_config,
        proxy_manager=None,
        scheduler=scheduler,
        robots_client=robots_client,  # type: ignore[arg-type]
        http_client=None,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_route_and_fetch_http_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """router.route_and_fetch should not call browser when HTTP is sufficient."""
    calls: dict[str, int] = {"http": 0, "browser": 0}

    async def fake_http_fetch_one(job: UrlJob, ctx: RunnerContext) -> FetchResult:
        calls["http"] += 1
        return _make_fetch_result(status="success", content_len=10_000)

    async def fake_browser_fetch_one(job: UrlJob, ctx: RunnerContext, browser: object) -> FetchResult:
        calls["browser"] += 1
        return _make_fetch_result(status="success", content_len=20_000, http_status=200)

    monkeypatch.setattr(router, "fetch_one", fake_http_fetch_one)
    monkeypatch.setattr(
        "tavily_scraper.pipelines.browser_fetcher.fetch_one",
        fake_browser_fetch_one,
    )

    ctx = _make_runner_context()
    job: UrlJob = {
        "url": UrlStr("https://example.com/page"),
        "is_dynamic_hint": None,
        "shard_id": 0,
        "index_in_shard": 0,
    }

    # Pass a dummy browser object; needs_browser should return False so it is never used.
    dummy_browser = object()
    result = await router.route_and_fetch(job, ctx, dummy_browser)  # type: ignore[arg-type]

    assert calls["http"] == 1
    assert calls["browser"] == 0
    assert result["method"] == "httpx"
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_route_and_fetch_uses_browser_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """router.route_and_fetch should call browser when needs_browser is True."""
    calls: dict[str, int] = {"http": 0, "browser": 0}

    async def fake_http_fetch_one(job: UrlJob, ctx: RunnerContext) -> FetchResult:
        calls["http"] += 1
        # Simulate a timeout that should push us to browser.
        return _make_fetch_result(status="timeout", http_status=None)

    async def fake_browser_fetch_one(job: UrlJob, ctx: RunnerContext, browser: object) -> FetchResult:
        calls["browser"] += 1
        res = _make_fetch_result(status="success", http_status=200, content_len=30_000)
        res["method"] = "playwright"
        res["stage"] = "fallback"
        return res

    monkeypatch.setattr(router, "fetch_one", fake_http_fetch_one)
    monkeypatch.setattr(
        "tavily_scraper.pipelines.browser_fetcher.fetch_one",
        fake_browser_fetch_one,
    )

    ctx = _make_runner_context()
    job: UrlJob = {
        "url": UrlStr("https://example.com/page"),
        "is_dynamic_hint": None,
        "shard_id": 0,
        "index_in_shard": 0,
    }

    dummy_browser = object()
    result = await router.route_and_fetch(job, ctx, dummy_browser)  # type: ignore[arg-type]

    assert calls["http"] == 1
    assert calls["browser"] == 1
    assert result["method"] == "playwright"
    assert result["status"] == "success"
