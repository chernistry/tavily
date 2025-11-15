"""Environment and configuration loading."""

from __future__ import annotations

import json
import os
from pathlib import Path

from tavily_scraper.config.constants import (
    DEFAULT_HTTPX_MAX_CONCURRENCY,
    DEFAULT_HTTPX_TIMEOUT_SECONDS,
    DEFAULT_PLAYWRIGHT_MAX_CONCURRENCY,
    DEFAULT_SHARD_SIZE,
)
from tavily_scraper.core.models import ProxyConfig, RunConfig


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _clamp(value: int, lower: int, upper: int) -> int:
    """Clamp integer configuration values into a safe range."""
    return max(lower, min(upper, value))


def load_run_config() -> RunConfig:
    """Load runtime configuration from environment variables."""
    env = os.getenv("TAVILY_ENV", "local")
    data_dir = Path(os.getenv("TAVILY_DATA_DIR", "data")).resolve()
    urls_path = data_dir / "urls.txt"

    httpx_timeout_seconds_raw = _env_int(
        "HTTPX_TIMEOUT_SECONDS",
        DEFAULT_HTTPX_TIMEOUT_SECONDS,
    )
    # Hard clamp HTTP timeout to a reasonable range (5–20s) to avoid stalls.
    httpx_timeout_seconds = _clamp(httpx_timeout_seconds_raw, 5, 20)

    httpx_max_concurrency_raw = _env_int(
        "HTTPX_MAX_CONCURRENCY",
        DEFAULT_HTTPX_MAX_CONCURRENCY,
    )
    # Clamp concurrency to keep Colab and local environments safe.
    httpx_max_concurrency = _clamp(httpx_max_concurrency_raw, 1, 128)

    playwright_max_concurrency_raw = _env_int(
        "PLAYWRIGHT_MAX_CONCURRENCY",
        DEFAULT_PLAYWRIGHT_MAX_CONCURRENCY,
    )
    # Playwright is expensive; keep concurrency very small.
    playwright_max_concurrency = _clamp(playwright_max_concurrency_raw, 1, 4)

    shard_size_raw = _env_int("SHARD_SIZE", DEFAULT_SHARD_SIZE)
    # Avoid pathological shard sizes while allowing tuning.
    shard_size = _clamp(shard_size_raw, 50, 5_000)

    proxy_config_path_env = os.getenv("PROXY_CONFIG_PATH")
    proxy_config_path = (
        Path(proxy_config_path_env).resolve() if proxy_config_path_env else None
    )

    return RunConfig(
        env=env,  # type: ignore[arg-type]
        urls_path=urls_path,
        data_dir=data_dir,
        httpx_timeout_seconds=httpx_timeout_seconds,
        httpx_max_concurrency=httpx_max_concurrency,
        playwright_headless=os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true",
        playwright_max_concurrency=playwright_max_concurrency,
        shard_size=shard_size,
        proxy_config_path=proxy_config_path,
    )


def load_proxy_config_from_json(path: Path) -> ProxyConfig:
    """Load proxy configuration from JSON file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    proxy = raw["proxy"]
    host = proxy["hostname"].split(":")[0]
    ports = proxy["port"]
    return ProxyConfig(
        host=host,
        http_port=int(ports["http"]),
        https_port=int(ports["https"]),
        socks5_port=int(ports["socks5"]),
        username=proxy.get("username"),
        password=proxy.get("password"),
    )
