"""Fast HTTP fetcher using httpx."""

from __future__ import annotations

import asyncio
import random
from time import perf_counter
from urllib.parse import urlparse

import httpx

from tavily_scraper.config.constants import DEFAULT_MAX_CONTENT_BYTES
from tavily_scraper.config.proxies import ProxyManager
from tavily_scraper.core.models import (
    FetchResult,
    RunConfig,
    RunnerContext,
    UrlJob,
    make_initial_fetch_result,
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

ACCEPT_LANGUAGES = ["en-US,en;q=0.9", "en-GB,en;q=0.9"]

MAX_HTTP_RETRIES = 2
TRANSIENT_STATUS_CODES: set[int] = {502, 503, 504, 429}
MAX_CONTENT_BYTES = DEFAULT_MAX_CONTENT_BYTES


def build_headers() -> dict[str, str]:
    """Build randomized headers."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
    }


def make_http_client(
    run_config: RunConfig, proxy_manager: ProxyManager | None
) -> httpx.AsyncClient:
    """Create httpx AsyncClient with configuration."""
    proxy = proxy_manager.httpx_proxy() if proxy_manager is not None else None
    timeout = httpx.Timeout(run_config.httpx_timeout_seconds)
    limits = httpx.Limits(max_connections=run_config.httpx_max_concurrency * 2)
    return httpx.AsyncClient(
        http2=True,
        follow_redirects=True,
        timeout=timeout,
        limits=limits,
        proxy=proxy,
    )


async def fetch_one(job: UrlJob, ctx: RunnerContext) -> FetchResult:
    """Fetch URL using HTTP client."""
    result = make_initial_fetch_result(job, method="httpx", stage="primary")

    url = str(job["url"])
    parsed = urlparse(url)
    domain = parsed.netloc
    result["domain"] = domain

    # Robots check (never retried; treated as final decision)
    can_fetch = await ctx.robots_client.can_fetch(url, user_agent=USER_AGENTS[0])
    if not can_fetch:
        result["status"] = "robots_blocked"
        result["robots_disallowed"] = True
        result["block_type"] = "robots"  # type: ignore[typeddict-unknown-key]
        return result
    attempt = 0
    backoff_base = 0.5

    while True:
        await ctx.scheduler.acquire(domain)
        start = perf_counter()
        try:
            resp = await ctx.http_client.get(url, headers=build_headers())
        except httpx.TimeoutException as exc:
            elapsed_ms = int((perf_counter() - start) * 1000)
            result["latency_ms"] = elapsed_ms
            result["status"] = "timeout"
            result["error_kind"] = "Timeout"
            result["error_message"] = str(exc)[:200]

            if attempt < MAX_HTTP_RETRIES:
                attempt += 1
                result["retries"] = attempt
                ctx.scheduler.release(domain)
                await asyncio.sleep(backoff_base * (2 ** (attempt - 1)))
                continue

            ctx.scheduler.record_error(domain)
            ctx.scheduler.release(domain)
            return result
        except httpx.HTTPError as exc:
            elapsed_ms = int((perf_counter() - start) * 1000)
            result["latency_ms"] = elapsed_ms
            result["status"] = "http_error"
            result["error_kind"] = type(exc).__name__
            result["error_message"] = str(exc)[:200]

            # HTTP errors at client level (not response-based) are treated as non-transient
            ctx.scheduler.record_error(domain)
            ctx.scheduler.release(domain)
            return result
        except Exception as exc:
            # Catch proxy errors (ProtocolError, etc.) and other unexpected errors
            elapsed_ms = int((perf_counter() - start) * 1000)
            result["latency_ms"] = elapsed_ms
            result["status"] = "http_error"
            result["error_kind"] = type(exc).__name__
            result["error_message"] = str(exc)[:200]

            ctx.scheduler.record_error(domain)
            ctx.scheduler.release(domain)
            return result
        else:
            elapsed_ms = int((perf_counter() - start) * 1000)
            result["latency_ms"] = elapsed_ms
            result["http_status"] = resp.status_code
            result["status"] = (
                "success" if 200 <= resp.status_code < 400 else "http_error"
            )

            content_type = resp.headers.get("Content-Type", "")

            # Safely get text content
            try:
                body = resp.text
            except Exception:
                # Fallback to binary content if text decoding fails
                body = resp.content.decode("utf-8", errors="ignore")

            result["content_len"] = len(body.encode("utf-8", errors="ignore"))
            result["encoding"] = resp.encoding

            # Size guardrail: classify very large responses as too_large
            if result["content_len"] > MAX_CONTENT_BYTES:
                result["status"] = "too_large"
                result["content"] = None
                ctx.scheduler.release(domain)
                return result

            if "text/html" in content_type or "application/xhtml+xml" in content_type:
                result["content"] = body

                # CAPTCHA detection (never retried)
                from tavily_scraper.utils.captcha import detect_captcha_http

                detection = detect_captcha_http(
                    resp.status_code, str(resp.url), dict(resp.headers), body
                )
                if detection["present"]:
                    result["captcha_detected"] = True
                    result["status"] = "captcha_detected"
                    result["block_type"] = "captcha"  # type: ignore[typeddict-unknown-key]
                    result["block_vendor"] = detection["vendor"]  # type: ignore[typeddict-unknown-key]
                    ctx.scheduler.record_captcha(domain)
                    ctx.scheduler.release(domain)
                    return result
            else:
                result["content"] = None

            # Retry only for transient HTTP status codes when not already classified as CAPTCHA
            if (
                result["status"] == "http_error"
                and result.get("http_status") in TRANSIENT_STATUS_CODES
                and attempt < MAX_HTTP_RETRIES
            ):
                attempt += 1
                result["retries"] = attempt
                ctx.scheduler.release(domain)
                await asyncio.sleep(backoff_base * (2 ** (attempt - 1)))
                continue

            # Final classification for non-transient errors or success
            if result["status"] == "http_error":
                ctx.scheduler.record_error(domain)

            ctx.scheduler.release(domain)
            return result



def looks_incomplete_http(result: FetchResult) -> bool:
    """Check if HTTP result looks incomplete."""
    # Only inspect body for successful HTTP responses; errors are handled separately.
    if result.get("status") != "success":
        return False
    if result.get("content_len", 0) < 1024:
        return True
    html = result.get("content") or ""
    lower = html.lower()
    if "enable javascript" in lower or "please turn on javascript" in lower:
        return True
    return False
