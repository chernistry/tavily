"""
Fast HTTP fetcher using async httpx client.

This module implements the primary (fast path) HTTP fetching strategy with:
- Async HTTP/2 support for improved performance
- User-Agent and Accept-Language rotation
- Exponential backoff retry logic for transient errors
- CAPTCHA detection and classification
- Content size guardrails
- Robots.txt compliance
"""

from __future__ import annotations

import asyncio
import random
from time import perf_counter
from typing import Optional
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




# ==== USER AGENT ROTATION POOL ==== #

USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
    "Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]
"""
Pool of realistic User-Agent strings for rotation.

Includes major browsers (Chrome, Firefox, Safari) across
different operating systems to avoid trivial fingerprinting.
"""


ACCEPT_LANGUAGES: list[str] = ["en-US,en;q=0.9", "en-GB,en;q=0.9"]
"""Accept-Language header values for rotation."""




# ==== RETRY & LIMIT CONFIGURATION ==== #

MAX_HTTP_RETRIES: int = 2
"""Maximum number of retry attempts for transient errors."""

TRANSIENT_STATUS_CODES: set[int] = {502, 503, 504, 429}
"""
HTTP status codes considered transient and worth retrying.

- 502: Bad Gateway (upstream server error)
- 503: Service Unavailable (temporary overload)
- 504: Gateway Timeout (upstream timeout)
- 429: Too Many Requests (rate limit)
"""

MAX_CONTENT_BYTES: int = DEFAULT_MAX_CONTENT_BYTES
"""Maximum content size in bytes before marking as 'too_large'."""




# ==== HTTP CLIENT FACTORY ==== #

def build_headers() -> dict[str, str]:
    """
    Build randomized HTTP headers for request.

    Returns:
        Dictionary with User-Agent and Accept-Language headers

    Note:
        Headers are randomized on each call to avoid fingerprinting
        and distribute load across different apparent clients.
    """
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
    }




def make_http_client(
    run_config: RunConfig,
    proxy_manager: Optional[ProxyManager],
) -> httpx.AsyncClient:
    """
    Create configured httpx AsyncClient instance.

    Args:
        run_config: Runtime configuration with timeout and concurrency settings
        proxy_manager: Optional proxy manager for routing traffic

    Returns:
        Configured httpx.AsyncClient ready for use

    Note:
        Client is configured with:
        - HTTP/2 support enabled
        - Automatic redirect following
        - Configurable timeout
        - Connection pooling based on concurrency limits
        - Optional proxy routing
    """
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




# ==== PRIMARY HTTP FETCH LOGIC ==== #

async def fetch_one(job: UrlJob, ctx: RunnerContext) -> FetchResult:
    """
    Fetch a single URL using HTTP client with retry logic.

    This function implements the complete HTTP fetch workflow:
    1. Checks robots.txt compliance
    2. Acquires domain-level rate limit slot
    3. Performs HTTP GET with randomized headers
    4. Handles errors with exponential backoff retry
    5. Detects CAPTCHAs and oversized content
    6. Classifies result status

    Args:
        job: URL job to fetch
        ctx: Runner context with shared resources

    Returns:
        FetchResult containing status, content, and metadata

    Note:
        This function never raises exceptions - all errors are
        captured in the FetchResult status field.
    """
    result = make_initial_fetch_result(job, method="httpx", stage="primary")

    url = str(job["url"])
    parsed = urlparse(url)
    domain = parsed.netloc
    result["domain"] = domain

    # --► ROBOTS.TXT COMPLIANCE CHECK
    can_fetch = await ctx.robots_client.can_fetch(url, user_agent=USER_AGENTS[0])

    if not can_fetch:
        result["status"] = "robots_blocked"
        result["robots_disallowed"] = True
        result["block_type"] = "robots"  # type: ignore[typeddict-unknown-key]
        return result

    # --► RETRY LOOP WITH EXPONENTIAL BACKOFF
    attempt = 0
    backoff_base = 0.5

    while True:
        await ctx.scheduler.acquire(domain)
        start = perf_counter()

        try:
            resp = await ctx.http_client.get(url, headers=build_headers())

        # ⚠️ TIMEOUT EXCEPTION HANDLING
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

        # ⚠️ HTTP ERROR EXCEPTION HANDLING
        except httpx.HTTPError as exc:
            elapsed_ms = int((perf_counter() - start) * 1000)
            result["latency_ms"] = elapsed_ms
            result["status"] = "http_error"
            result["error_kind"] = type(exc).__name__
            result["error_message"] = str(exc)[:200]

            ctx.scheduler.record_error(domain)
            ctx.scheduler.release(domain)
            return result

        # ⚠️ CATCH-ALL FOR PROXY AND UNEXPECTED ERRORS
        except Exception as exc:
            elapsed_ms = int((perf_counter() - start) * 1000)
            result["latency_ms"] = elapsed_ms
            result["status"] = "http_error"
            result["error_kind"] = type(exc).__name__
            result["error_message"] = str(exc)[:200]

            ctx.scheduler.record_error(domain)
            ctx.scheduler.release(domain)
            return result

        # --► SUCCESSFUL RESPONSE PROCESSING
        else:
            elapsed_ms = int((perf_counter() - start) * 1000)
            result["latency_ms"] = elapsed_ms
            result["http_status"] = resp.status_code
            result["status"] = (
                "success" if 200 <= resp.status_code < 400 else "http_error"
            )

            content_type = resp.headers.get("Content-Type", "")

            # --► CONTENT EXTRACTION WITH FALLBACK
            try:
                body = resp.text
            except Exception:
                body = resp.content.decode("utf-8", errors="ignore")

            result["content_len"] = len(body.encode("utf-8", errors="ignore"))
            result["encoding"] = resp.encoding

            # --► SIZE GUARDRAIL CHECK
            if result["content_len"] > MAX_CONTENT_BYTES:
                result["status"] = "too_large"
                result["content"] = None
                ctx.scheduler.release(domain)
                return result

            # --► HTML CONTENT PROCESSING
            if "text/html" in content_type or "application/xhtml+xml" in content_type:
                result["content"] = body

                # --► CAPTCHA DETECTION
                from tavily_scraper.utils.captcha import detect_captcha_http

                detection = detect_captcha_http(
                    resp.status_code,
                    str(resp.url),
                    dict(resp.headers),
                    body,
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

            # --► TRANSIENT ERROR RETRY LOGIC
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

            # --► FINAL STATUS CLASSIFICATION
            if result["status"] == "http_error":
                ctx.scheduler.record_error(domain)

            ctx.scheduler.release(domain)
            return result




# ==== CONTENT COMPLETENESS HEURISTICS ==== #

def looks_incomplete_http(result: FetchResult) -> bool:
    """
    Determine if HTTP result appears incomplete or requires JavaScript.

    This heuristic checks for common indicators that content
    may be incomplete or require browser rendering:
    - Very small content size (< 1KB)
    - JavaScript requirement messages

    Args:
        result: FetchResult from HTTP attempt

    Returns:
        True if content appears incomplete, False otherwise

    Note:
        Only inspects successful HTTP responses. Errors are
        handled separately by the router logic.
    """
    if result.get("status") != "success":
        return False

    if result.get("content_len", 0) < 1024:
        return True

    html = result.get("content") or ""
    lower = html.lower()

    if "enable javascript" in lower or "please turn on javascript" in lower:
        return True

    return False
