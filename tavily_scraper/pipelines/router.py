"""Strategy router for HTTP vs browser fallback."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

from tavily_scraper.core.models import FetchResult, RunnerContext, UrlJob
from tavily_scraper.pipelines.fast_http_fetcher import fetch_one, looks_incomplete_http
from tavily_scraper.utils.logging import get_logger

if TYPE_CHECKING:
    from playwright.async_api import Browser

logger = get_logger(__name__)


def needs_browser(result: FetchResult) -> bool:
    """Determine if result needs browser fallback."""
    status = result.get("status")

    # Never retry robots or explicit CAPTCHA pages
    if status in ("robots_blocked", "captcha_detected"):
        return False

    # Successful HTTP but suspicious/incomplete HTML
    if status == "success":
        return looks_incomplete_http(result)

    # Timeouts may benefit from a browser attempt
    if status == "timeout":
        return True

    # Generic HTTP errors: only some are worth a browser try
    if status == "http_error":
        http_status = result.get("http_status") or 0
        # 401/403/404/410 are almost never improved by JS:
        # - 401: auth required
        # - 403: hard block
        # - 404/410: not found / gone
        if http_status in (401, 403, 404, 410):
            return False
        # Other 4xx/5xx might be WAFs or transient issues; allow a browser attempt
        return True

    # For any other status, default to no browser fallback
    return False


async def route_and_fetch(
    job: UrlJob, ctx: RunnerContext, browser: Browser | None = None
) -> FetchResult:
    """Route URL through HTTP-first strategy with optional browser fallback."""
    # Try HTTP first
    result = await fetch_one(job, ctx)

    # Check if browser fallback needed
    if needs_browser(result):
        domain = result.get("domain", "")
        # Consult scheduler to avoid wasting browser attempts on clearly blocked domains
        domain_ok_for_browser = not domain or ctx.scheduler.should_try_browser(domain)

        # Log a URL with query/fragment stripped and truncated for safety.
        raw_url = str(job["url"])
        parts = urlsplit(raw_url)
        safe_url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        safe_url = safe_url[:80]

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
                "Browser needed but not used for %s (status=%s, domain_ok_for_browser=%s)",
                safe_url,
                result.get("status"),
                domain_ok_for_browser,
            )

    return result
