"""Browser-based fetcher using Playwright."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from urllib.parse import urlparse

from playwright.async_api import Browser, Page, async_playwright

from tavily_scraper.config.constants import DEFAULT_MAX_CONTENT_BYTES
from tavily_scraper.config.proxies import ProxyManager
from tavily_scraper.core.models import (
    FetchResult,
    RunConfig,
    RunnerContext,
    UrlJob,
    make_initial_fetch_result,
)
from tavily_scraper.utils.captcha import detect_captcha_http
from tavily_scraper.utils.logging import get_logger

logger = get_logger(__name__)

MAX_BROWSER_RETRIES = 1
MAX_CONTENT_BYTES = DEFAULT_MAX_CONTENT_BYTES


@asynccontextmanager
async def browser_lifecycle(
    run_config: RunConfig,
    proxy_manager: ProxyManager | None,
) -> AsyncIterator[Browser]:
    """Manage Playwright browser lifecycle."""
    proxy_dict = proxy_manager.playwright_proxy() if proxy_manager is not None else None
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=run_config.playwright_headless,
            proxy=proxy_dict,  # type: ignore[arg-type]
        )
        try:
            yield browser
        finally:
            await browser.close()


async def create_page_with_blocking(browser: Browser) -> Page:
    """Create page with resource blocking."""
    context = await browser.new_context()

    async def route_handler(route, request):  # type: ignore[no-untyped-def]
        url = request.url
        # Block images, fonts, media
        if any(
            url.endswith(ext)
            for ext in (
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".svg",
                ".woff",
                ".woff2",
                ".mp4",
                ".webm",
            )
        ):
            await route.abort()
            return
        await route.continue_()

    await context.route("**/*", route_handler)
    return await context.new_page()


async def fetch_one(
    job: UrlJob, ctx: RunnerContext, browser: Browser
) -> FetchResult:
    """Fetch URL using Playwright browser."""
    result = make_initial_fetch_result(job, method="playwright", stage="fallback")

    url = str(job["url"])
    parsed = urlparse(url)
    domain = parsed.netloc
    result["domain"] = domain

    # Robots check
    can_fetch = await ctx.robots_client.can_fetch(url)
    if not can_fetch:
        result["status"] = "robots_blocked"
        result["robots_disallowed"] = True
        result["block_type"] = "robots"  # type: ignore[typeddict-unknown-key]
        return result

    attempt = 0
    backoff_base = 1.0

    while True:
        page = None
        try:
            page = await create_page_with_blocking(browser)

            await ctx.scheduler.acquire(domain)
            start = perf_counter()

            try:
                response = await page.goto(
                    url,
                    timeout=ctx.run_config.httpx_timeout_seconds * 1000,
                    wait_until="networkidle",
                )
                elapsed_ms = int((perf_counter() - start) * 1000)
                result["latency_ms"] = elapsed_ms

                if response:
                    result["http_status"] = response.status
                    result["status"] = (
                        "success" if 200 <= response.status < 400 else "http_error"
                    )
                else:
                    result["status"] = "http_error"

                # Get content
                content = await page.content()
                result["content"] = content
                result["content_len"] = len(content.encode("utf-8", errors="ignore"))

                # Size guardrail: classify very large responses as too_large
                if result["content_len"] > MAX_CONTENT_BYTES:
                    result["status"] = "too_large"
                    result["content"] = None
                    ctx.scheduler.release(domain)
                    return result

                # CAPTCHA detection (never retried)
                detection = detect_captcha_http(
                    result.get("http_status") or 0, url, {}, content
                )
                if detection["present"]:
                    result["captcha_detected"] = True
                    result["status"] = "captcha_detected"
                    result["block_type"] = "captcha"  # type: ignore[typeddict-unknown-key]
                    result["block_vendor"] = detection["vendor"]  # type: ignore[typeddict-unknown-key]
                    ctx.scheduler.record_captcha(domain)
                    ctx.scheduler.release(domain)
                    return result

            except Exception as exc:
                elapsed_ms = int((perf_counter() - start) * 1000)
                result["latency_ms"] = elapsed_ms
                is_timeout = "timeout" in str(exc).lower()
                result["status"] = "timeout" if is_timeout else "http_error"
                result["error_kind"] = type(exc).__name__
                result["error_message"] = str(exc)[:200]

                # Retry only timeouts
                if is_timeout and attempt < MAX_BROWSER_RETRIES:
                    attempt += 1
                    result["retries"] = attempt
                    ctx.scheduler.release(domain)
                    await asyncio.sleep(backoff_base * (2 ** (attempt - 1)))
                    continue

                ctx.scheduler.record_error(domain)
            finally:
                ctx.scheduler.release(domain)

            return result

        except Exception as exc:
            # Catch page creation errors (proxy issues, etc.)
            result["status"] = "http_error"
            result["error_kind"] = type(exc).__name__
            result["error_message"] = str(exc)[:200]
            ctx.scheduler.record_error(domain)
            return result
        finally:
            if page:
                await page.close()
                if page.context:
                    await page.context.close()
