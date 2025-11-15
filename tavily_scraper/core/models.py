"""Core data models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NewType, TypedDict

import msgspec

from tavily_scraper.config.constants import Method, Stage, Status

if TYPE_CHECKING:
    import httpx

    from tavily_scraper.config.proxies import ProxyManager
    from tavily_scraper.core.robots import RobotsClient
    from tavily_scraper.core.scheduler import DomainScheduler

UrlStr = NewType("UrlStr", str)


class RunConfig(msgspec.Struct, omit_defaults=True):
    """Runtime configuration."""

    env: Literal["local", "ci", "colab"] = "local"
    urls_path: Path = Path("data/urls.txt")
    data_dir: Path = Path("data")
    httpx_timeout_seconds: int = 10
    httpx_max_concurrency: int = 32
    playwright_headless: bool = True
    playwright_max_concurrency: int = 2
    shard_size: int = 500
    proxy_config_path: Path | None = None


class ShardConfig(msgspec.Struct, omit_defaults=True):
    """Shard configuration."""

    shard_size: int = 500


class ProxyConfig(msgspec.Struct, omit_defaults=True):
    """Proxy configuration."""

    host: str
    http_port: int
    https_port: int
    socks5_port: int
    username: str | None = None
    password: str | None = None


class UrlJob(TypedDict):
    """URL job for processing."""

    url: UrlStr
    is_dynamic_hint: bool | None
    shard_id: int
    index_in_shard: int


class FetchResult(TypedDict, total=False):
    """In-memory fetch result."""

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
    content: str | None  # in-memory only, never persisted


class UrlStats(TypedDict):
    """Per-URL statistics (persisted)."""

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


class RunSummary(TypedDict):
    """Run-level summary statistics."""

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
    """Shard checkpoint for resumability."""

    run_id: str
    shard_id: int
    urls_total: int
    urls_done: int
    last_updated_at: str
    status: Literal["pending", "in_progress", "completed", "failed"]


@dataclass
class RunnerContext:
    """Shared context for scraping runners."""

    run_config: RunConfig
    proxy_manager: ProxyManager | None
    scheduler: DomainScheduler
    robots_client: RobotsClient
    http_client: httpx.AsyncClient


def _utc_now_iso() -> str:
    """Get current UTC time as ISO string."""
    return datetime.now(UTC).isoformat()


def make_initial_fetch_result(
    url_job: UrlJob,
    method: Method,
    stage: Stage,
) -> FetchResult:
    """Create initial FetchResult for a URL job."""
    started_at = _utc_now_iso()
    return FetchResult(
        url=url_job["url"],
        domain="",  # filled by fetcher
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
    """Convert FetchResult to UrlStats (strips content)."""
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
