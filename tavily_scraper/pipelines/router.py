"""
Strategy router for HTTP-first with browser fallback decision logic.

This module implements the hybrid scraping strategy by:
- Attempting HTTP fetch first for all URLs
- Analyzing results to determine if browser fallback is needed
- Routing to Playwright only when necessary
- Respecting domain-level browser attempt limits
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from urllib.parse import urlsplit, urlunsplit

from tavily_scraper.core.models import FetchResult, RunnerContext, UrlJob
from tavily_scraper.pipelines.fast_http_fetcher import fetch_one, looks_incomplete_http
from tavily_scraper.utils.logging import get_logger


if TYPE_CHECKING:
    from playwright.async_api import Browser


logger = get_logger(__name__)




# ==== BROWSER FALLBACK DECISION LOGIC ==== #

def needs_browser(result: FetchResult) -> bool:
    """
    Determine if a fetch result requires browser fallback.

    This function analyzes HTTP fetch results to decide whether
    a Playwright browser attempt would likely improve the outcome.

    Decision criteria:
    - Never retry: robots blocks, explicit CAPTCHAs
    - Retry on: incomplete HTML, timeouts, certain HTTP errors
    - Skip on: auth errors (401), hard blocks (403), not found (404/410)

    Args:
        result: FetchResult from HTTP attempt

    Returns:
        True if browser fallback should be attempted, False otherwise

    Note:
        This heuristic balances accuracy vs cost. Browser attempts
        are expensive, so we only retry when there's a reasonable
        chance of success.
    """
    status = result.get("status")

    # --► NEVER RETRY CONDITIONS
    # Robots blocks and CAPTCHAs won't improve with browser
    if status in ("robots_blocked", "captcha_detected"):
        return False

    # --► SUCCESSFUL BUT INCOMPLETE
    # HTTP succeeded but content looks suspicious or incomplete
    if status == "success":
        return looks_incomplete_http(result)

    # --► TIMEOUT RETRY
    # Timeouts may benefit from browser's longer wait capabilities
    if status == "timeout":
        return True

    # --► SELECTIVE HTTP ERROR RETRY
    if status == "http_error":
        http_status = result.get("http_status") or 0

        # These status codes are almost never improved by JavaScript:
        # - 401: Authentication required (credentials needed)
        # - 403: Hard block (permission denied)
        # - 404: Not found (resource doesn't exist)
        # - 410: Gone (resource permanently removed)
        if http_status in (401, 403, 404, 410):
            return False

        # Other 4xx/5xx might be WAFs or transient issues
        # Worth attempting with browser
        return True

    # --► DEFAULT: NO FALLBACK
    # For any other status, browser fallback unlikely to help
    return False




# ==== ROUTING ORCHESTRATION ==== #

async def route_and_fetch(
    job: UrlJob,
    ctx: RunnerContext,
    browser: Optional[Browser] = None,
) -> FetchResult:
    """
    Route URL through HTTP-first strategy with optional browser fallback.

    This function implements the core hybrid scraping logic:
    1. Always attempt HTTP fetch first (fast path)
    2. Analyze result to determine if browser needed
    3. If needed and available, attempt browser fetch
    4. Return final result (HTTP or browser)

    Args:
        job: URL job to process
        ctx: Runner context with shared resources
        browser: Optional Playwright browser instance

    Returns:
        FetchResult from either HTTP or browser attempt

    Note:
        Browser fallback is only attempted if:
        - needs_browser() returns True
        - Browser instance is provided
        - Domain hasn't exceeded browser attempt limits
    """
    # --► PRIMARY HTTP ATTEMPT
    result = await fetch_one(job, ctx)

    # --► BROWSER FALLBACK DECISION
    if needs_browser(result):
        domain = result.get("domain", "")

        # Check domain-level browser attempt limits
        domain_ok_for_browser = (
            not domain or ctx.scheduler.should_try_browser(domain)
        )

        # --► URL SANITIZATION FOR LOGGING
        # Strip query/fragment and truncate for safe logging
        raw_url = str(job["url"])
        parts = urlsplit(raw_url)
        safe_url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        safe_url = safe_url[:80]

        # --► BROWSER ATTEMPT
        if browser is not None and domain_ok_for_browser:
            logger.info(
                "Browser fallback for %s (status=%s)",
                safe_url,
                result.get("status"),
            )

            from tavily_scraper.pipelines import browser_fetcher

            result = await browser_fetcher.fetch_one(job, ctx, browser)

        else:
            logger.debug(
                "Browser needed but not used for %s "
                "(status=%s, domain_ok_for_browser=%s)",
                safe_url,
                result.get("status"),
                domain_ok_for_browser,
            )

    return result
