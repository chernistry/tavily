"""
Browser-based fetcher using Playwright for JavaScript-heavy pages.

This module implements the fallback (slow path) browser fetching strategy with:
- Headless Chromium automation via Playwright
- Resource blocking to reduce bandwidth and improve performance
- Proxy support for browser traffic
- CAPTCHA detection on rendered content
- Content size guardrails
- Robots.txt compliance
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from urllib.parse import urlparse

from playwright.async_api import Browser, Page, Request, Route, async_playwright

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




# ==== BROWSER CONFIGURATION ==== #

MAX_BROWSER_RETRIES: int = 1
"""Maximum number of retry attempts for browser timeouts."""

MAX_CONTENT_BYTES: int = DEFAULT_MAX_CONTENT_BYTES
"""Maximum content size in bytes before marking as 'too_large'."""




# ==== BROWSER LIFECYCLE MANAGEMENT ==== #

@asynccontextmanager
async def browser_lifecycle(
    run_config: RunConfig,
    proxy_manager: ProxyManager | None,
) -> AsyncIterator[Browser]:
    """
    Manage Playwright browser instance lifecycle.

    This context manager:
    1. Launches headless Chromium with optional proxy
    2. Yields browser instance for use
    3. Ensures proper cleanup on exit

    Args:
        run_config: Runtime configuration with browser settings
        proxy_manager: Optional proxy manager for routing browser traffic

    Yields:
        Browser: Configured Playwright browser instance

    Note:
        Browser is automatically closed when context exits,
        even if exceptions occur during usage.
    """
    proxy_dict = (
        proxy_manager.playwright_proxy() if proxy_manager is not None else None
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=run_config.playwright_headless,
            proxy=proxy_dict,  # type: ignore[arg-type]
        )

        try:
            yield browser
        finally:
            await browser.close()




# ==== PAGE CREATION WITH RESOURCE BLOCKING ==== #

async def create_page_with_blocking(browser: Browser) -> Page:
    """
    Create browser page with aggressive resource blocking.

    This function creates a new page with request interception
    to block heavy static assets that aren't needed for content
    extraction:
    - Images (png, jpg, jpeg, gif, svg)
    - Fonts (woff, woff2)
    - Media (mp4, webm)

    Args:
        browser: Playwright browser instance

    Returns:
        Page: Configured page with resource blocking enabled

    Note:
        Blocking these resources significantly reduces:
        - Bandwidth usage
        - Page load time
        - Memory consumption
    """
    context = await browser.new_context()

    async def route_handler(route: Route, request: Request) -> None:
        """
        Intercept and filter requests based on resource type.

        Args:
            route: Playwright route object
            request: Playwright request object

        Returns:
            None
        """
        url = request.url

        # Block heavy static assets
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




# ==== BROWSER FETCH LOGIC ==== #

async def fetch_one(
    job: UrlJob,
    ctx: RunnerContext,
    browser: Browser,
) -> FetchResult:
    """
    Fetch a single URL using Playwright browser with retry logic.

    This function implements the complete browser fetch workflow:
    1. Checks robots.txt compliance
    2. Creates page with resource blocking
    3. Acquires domain-level rate limit slot
    4. Navigates to URL with networkidle wait
    5. Extracts rendered HTML content
    6. Detects CAPTCHAs in rendered content
    7. Handles errors with limited retry

    Args:
        job: URL job to fetch
        ctx: Runner context with shared resources
        browser: Playwright browser instance

    Returns:
        FetchResult containing status, content, and metadata

    Note:
        Browser fetches are expensive (CPU, memory, time).
        Only one retry is attempted for timeouts.
    """
    result = make_initial_fetch_result(job, method="playwright", stage="fallback")

    url = str(job["url"])
    parsed = urlparse(url)
    domain = parsed.netloc
    result["domain"] = domain

    # --► ROBOTS.TXT COMPLIANCE CHECK
    can_fetch = await ctx.robots_client.can_fetch(url)

    if not can_fetch:
        result["status"] = "robots_blocked"
        result["robots_disallowed"] = True
        result["block_type"] = "robots"  # type: ignore[typeddict-unknown-key]
        return result

    # --► RETRY LOOP WITH EXPONENTIAL BACKOFF
    attempt = 0
    backoff_base = 1.0

    while True:
        page: Page | None = None

        try:
            page = await create_page_with_blocking(browser)

            await ctx.scheduler.acquire(domain)
            start = perf_counter()

            try:
                # --► BROWSER NAVIGATION
                response = await page.goto(
                    url,
                    timeout=ctx.run_config.httpx_timeout_seconds * 1000,
                    wait_until="networkidle",
                )

                elapsed_ms = int((perf_counter() - start) * 1000)
                result["latency_ms"] = elapsed_ms

                # --► RESPONSE STATUS CLASSIFICATION
                if response:
                    result["http_status"] = response.status
                    result["status"] = (
                        "success"
                        if 200 <= response.status < 400
                        else "http_error"
                    )
                else:
                    result["status"] = "http_error"

                # --► CONTENT EXTRACTION
                content = await page.content()
                result["content"] = content
                result["content_len"] = len(
                    content.encode("utf-8", errors="ignore")
                )

                # --► SIZE GUARDRAIL CHECK
                if result["content_len"] > MAX_CONTENT_BYTES:
                    result["status"] = "too_large"
                    result["content"] = None
                    ctx.scheduler.release(domain)
                    return result

                # --► CAPTCHA DETECTION
                detection = detect_captcha_http(
                    result.get("http_status") or 0,
                    url,
                    {},
                    content,
                )

                if detection["present"]:
                    result["captcha_detected"] = True
                    result["status"] = "captcha_detected"
                    result["block_type"] = "captcha"  # type: ignore[typeddict-unknown-key]
                    result["block_vendor"] = detection["vendor"]  # type: ignore[typeddict-unknown-key]
                    ctx.scheduler.record_captcha(domain)
                    ctx.scheduler.release(domain)
                    return result

            # ⚠️ NAVIGATION ERROR HANDLING
            except Exception as exc:
                elapsed_ms = int((perf_counter() - start) * 1000)
                result["latency_ms"] = elapsed_ms
                is_timeout = "timeout" in str(exc).lower()
                result["status"] = "timeout" if is_timeout else "http_error"
                result["error_kind"] = type(exc).__name__
                result["error_message"] = str(exc)[:200]

                # Retry only timeouts (once)
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

        # ⚠️ PAGE CREATION ERROR HANDLING
        except Exception as exc:
            result["status"] = "http_error"
            result["error_kind"] = type(exc).__name__
            result["error_message"] = str(exc)[:200]
            ctx.scheduler.record_error(domain)
            return result

        # --► RESOURCE CLEANUP
        finally:
            if page:
                await page.close()
                if page.context:
                    await page.context.close()
