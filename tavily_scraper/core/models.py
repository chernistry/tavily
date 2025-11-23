"""
Core data models and type definitions for the Tavily scraper.

This module defines:
- Configuration structures (RunConfig, ProxyConfig, ShardConfig)
- Job and result types (UrlJob, FetchResult, UrlStats)
- Summary and checkpoint types (RunSummary, ShardCheckpoint)
- Shared runtime context (RunnerContext)
- Utility functions for model creation and conversion
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NewType, TypedDict

import msgspec

from tavily_scraper.config.constants import Method, Stage, Status
from tavily_scraper.stealth.config import StealthConfig

if TYPE_CHECKING:
    import httpx

    from tavily_scraper.config.proxies import ProxyManager
    from tavily_scraper.core.robots import RobotsClient
    from tavily_scraper.core.scheduler import DomainScheduler




# ==== TYPE ALIASES ==== #

UrlStr = NewType("UrlStr", str)
"""Type alias for URL strings with semantic meaning."""




# ==== CONFIGURATION MODELS ==== #

class RunConfig(msgspec.Struct, omit_defaults=True):
    """
    Runtime configuration for scraping pipeline.

    Attributes:
        env: Execution environment (local, ci, colab)
        urls_path: Path to input URLs file
        data_dir: Directory for output data
        httpx_timeout_seconds: HTTP request timeout
        httpx_max_concurrency: Maximum concurrent HTTP requests
        playwright_headless: Run browser in headless mode
        playwright_max_concurrency: Maximum concurrent browser instances
        shard_size: Number of URLs per processing shard
        proxy_config_path: Optional path to proxy configuration file
    """

    env: Literal["local", "ci", "colab"] = "local"
    urls_path: Path = Path("data/urls.txt")
    data_dir: Path = Path("data")
    httpx_timeout_seconds: int = 10
    httpx_max_concurrency: int = 32
    playwright_headless: bool = True
    playwright_max_concurrency: int = 2
    shard_size: int = 500
    proxy_config_path: Path | None = None
    stealth_config: StealthConfig | None = None




class ShardConfig(msgspec.Struct, omit_defaults=True):
    """
    Configuration for URL sharding strategy.

    Attributes:
        shard_size: Number of URLs to process per shard
    """

    shard_size: int = 500




class ProxyConfig(msgspec.Struct, omit_defaults=True):
    """
    Proxy server configuration.

    Attributes:
        host: Proxy server hostname
        http_port: Port for HTTP traffic
        https_port: Port for HTTPS traffic
        socks5_port: Port for SOCKS5 traffic
        username: Optional authentication username
        password: Optional authentication password
    """

    host: str
    http_port: int
    https_port: int
    socks5_port: int
    username: str | None = None
    password: str | None = None




# ==== JOB & RESULT MODELS ==== #

class UrlJob(TypedDict):
    """
    URL processing job specification.

    Attributes:
        url: Target URL to fetch
        is_dynamic_hint: Optional hint that URL requires JavaScript
        shard_id: Shard identifier for this job
        index_in_shard: Position within shard
    """

    url: UrlStr
    is_dynamic_hint: bool | None
    shard_id: int
    index_in_shard: int




class FetchResult(TypedDict, total=False):
    """
    In-memory fetch result with full content.

    This type contains all fetch metadata plus the actual content.
    Content is stripped when converting to UrlStats for persistence.

    Attributes:
        url: Target URL
        domain: Extracted domain name
        method: Fetch method used (httpx or playwright)
        stage: Processing stage (primary or fallback)
        status: Outcome status
        http_status: HTTP status code if available
        latency_ms: Request latency in milliseconds
        content_len: Content size in bytes
        encoding: Character encoding detected
        retries: Number of retry attempts
        captcha_detected: Whether CAPTCHA was encountered
        robots_disallowed: Whether blocked by robots.txt
        error_kind: Error type if failed
        error_message: Error description if failed
        started_at: ISO timestamp when fetch started
        finished_at: ISO timestamp when fetch completed
        shard_id: Shard identifier
        content: Full HTML content (in-memory only, never persisted)
    """

    url: UrlStr
    domain: str
    method: Method
    stage: Stage
    status: Status
    http_status: int | None
    latency_ms: int | None
    content_len: int
    encoding: str | None
    retries: int
    captcha_detected: bool
    robots_disallowed: bool
    error_kind: str | None
    error_message: str | None
    started_at: str
    finished_at: str
    shard_id: int
    content: str | None




class UrlStats(TypedDict):
    """
    Per-URL statistics for persistence.

    This is the persisted version of FetchResult with content stripped.
    Written to stats.jsonl for analysis.

    Attributes:
        url: Target URL
        domain: Extracted domain name
        method: Fetch method used
        stage: Processing stage
        status: Outcome status
        http_status: HTTP status code if available
        latency_ms: Request latency in milliseconds
        content_len: Content size in bytes
        encoding: Character encoding detected
        retries: Number of retry attempts
        captcha_detected: Whether CAPTCHA was encountered
        robots_disallowed: Whether blocked by robots.txt
        error_kind: Error type if failed
        error_message: Error description if failed
        timestamp: ISO timestamp of completion
        shard_id: Shard identifier
        block_type: Type of blocking encountered
        block_vendor: Vendor of blocking mechanism (e.g., Cloudflare)
    """

    url: str
    domain: str
    method: Method
    stage: Stage
    status: Status
    http_status: int | None
    latency_ms: int | None
    content_len: int
    encoding: str | None
    retries: int
    captcha_detected: bool
    robots_disallowed: bool
    error_kind: str | None
    error_message: str | None
    timestamp: str
    shard_id: int
    block_type: Literal["none", "captcha", "rate_limit", "robots", "other"] | None
    block_vendor: str | None




# ==== SUMMARY & CHECKPOINT MODELS ==== #

class RunSummary(TypedDict):
    """
    Aggregate statistics for entire run.

    Computed from all UrlStats rows and persisted to run_summary.json.

    Attributes:
        total_urls: Total number of URLs processed
        stats_rows: Number of statistics rows generated
        success_rate: Fraction of successful fetches
        http_error_rate: Fraction of HTTP errors
        timeout_rate: Fraction of timeouts
        captcha_rate: Fraction of CAPTCHA detections
        robots_block_rate: Fraction of robots.txt blocks
        httpx_share: Fraction using HTTP-only path
        playwright_share: Fraction requiring browser
        p50_latency_httpx_ms: HTTP P50 latency
        p95_latency_httpx_ms: HTTP P95 latency
        p50_latency_playwright_ms: Browser P50 latency
        p95_latency_playwright_ms: Browser P95 latency
        avg_content_len_httpx: Average HTTP content size
        avg_content_len_playwright: Average browser content size
    """

    total_urls: int
    stats_rows: int
    success_rate: float
    http_error_rate: float
    timeout_rate: float
    captcha_rate: float
    robots_block_rate: float
    httpx_share: float
    playwright_share: float
    p50_latency_httpx_ms: int | None
    p95_latency_httpx_ms: int | None
    p50_latency_playwright_ms: int | None
    p95_latency_playwright_ms: int | None
    avg_content_len_httpx: int | None
    avg_content_len_playwright: int | None




class ShardCheckpoint(TypedDict):
    """
    Checkpoint for shard processing resumability.

    Allows pipeline to resume from shard boundaries after interruption.

    Attributes:
        run_id: Unique run identifier
        shard_id: Shard identifier
        urls_total: Total URLs in shard
        urls_done: URLs completed in shard
        last_updated_at: ISO timestamp of last update
        status: Current shard status
    """

    run_id: str
    shard_id: int
    urls_total: int
    urls_done: int
    last_updated_at: str
    status: Literal["pending", "in_progress", "completed", "failed"]




# ==== RUNTIME CONTEXT ==== #

@dataclass
class RunnerContext:
    """
    Shared context for scraping pipeline execution.

    This dataclass holds all shared resources needed by fetchers:
    - Configuration
    - Proxy manager
    - Domain scheduler
    - Robots.txt client
    - HTTP client

    Attributes:
        run_config: Runtime configuration
        proxy_manager: Optional proxy manager for routing traffic
        scheduler: Domain-aware rate limiter
        robots_client: Robots.txt compliance checker
        http_client: Shared async HTTP client
    """

    run_config: RunConfig
    proxy_manager: ProxyManager | None
    scheduler: DomainScheduler
    robots_client: RobotsClient
    http_client: httpx.AsyncClient




# ==== UTILITY FUNCTIONS ==== #

def _utc_now_iso() -> str:
    """
    Get current UTC time as ISO 8601 string.

    Returns:
        ISO 8601 formatted timestamp string

    Example:
        '2025-11-15T10:30:45.123456+00:00'
    """
    return datetime.now(UTC).isoformat()




def make_initial_fetch_result(
    url_job: UrlJob,
    method: Method,
    stage: Stage,
) -> FetchResult:
    """
    Create initial FetchResult for a URL job.

    This function initializes a FetchResult with default values
    before the actual fetch attempt. Values are updated during
    and after the fetch operation.

    Args:
        url_job: URL job specification
        method: Fetch method to use (httpx or playwright)
        stage: Processing stage (primary or fallback)

    Returns:
        FetchResult with initialized default values

    Note:
        Status is initially set to 'other_error' and should be
        updated to reflect actual outcome.
    """
    started_at = _utc_now_iso()

    return FetchResult(
        url=url_job["url"],
        domain="",
        method=method,
        stage=stage,
        status="other_error",
        http_status=None,
        latency_ms=None,
        content_len=0,
        encoding=None,
        retries=0,
        captcha_detected=False,
        robots_disallowed=False,
        error_kind=None,
        error_message=None,
        started_at=started_at,
        finished_at=started_at,
        shard_id=url_job["shard_id"],
        content=None,
    )




def fetch_result_to_url_stats(result: FetchResult) -> UrlStats:
    """
    Convert FetchResult to UrlStats by stripping content.

    This function transforms the in-memory FetchResult (which includes
    full HTML content) into a UrlStats record suitable for persistence.
    The content field is intentionally omitted to reduce storage size.

    Args:
        result: FetchResult from fetch operation

    Returns:
        UrlStats record ready for persistence

    Note:
        Content is stripped to keep stats.jsonl file size manageable.
        Full content can be persisted separately if needed.
    """
    return UrlStats(
        url=str(result["url"]),
        domain=result["domain"],
        method=result["method"],
        stage=result["stage"],
        status=result["status"],
        http_status=result.get("http_status"),
        latency_ms=result.get("latency_ms"),
        content_len=result.get("content_len", 0),
        encoding=result.get("encoding"),
        retries=result.get("retries", 0),
        captcha_detected=result.get("captcha_detected", False),
        robots_disallowed=result.get("robots_disallowed", False),
        error_kind=result.get("error_kind"),
        error_message=result.get("error_message"),
        timestamp=result.get("finished_at", _utc_now_iso()),
        shard_id=result.get("shard_id", -1),
        block_type=result.get("block_type", "none"),  # type: ignore[typeddict-item]
        block_vendor=result.get("block_vendor"),  # type: ignore[typeddict-item]
    )
