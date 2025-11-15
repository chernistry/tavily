"""
Environment-based configuration loading with validation.

This module provides:
- Environment variable parsing with defaults
- Configuration value clamping for safety
- RunConfig construction from environment
- Proxy configuration loading from JSON files
"""

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

# ==== ENVIRONMENT VARIABLE HELPERS ==== #

def _env_int(name: str, default: int) -> int:
    """
    Read integer from environment variable with fallback.

    Args:
        name: Environment variable name
        default: Default value if variable not set

    Returns:
        Integer value from environment or default

    Note:
        Raises ValueError if environment value cannot be parsed as int.
    """
    value = os.getenv(name)

    if value is None:
        return default

    return int(value)




def _clamp(value: int, lower: int, upper: int) -> int:
    """
    Clamp integer value to safe range.

    Args:
        value: Value to clamp
        lower: Minimum allowed value
        upper: Maximum allowed value

    Returns:
        Clamped value within [lower, upper]

    Example:
        _clamp(150, 1, 128) -> 128
        _clamp(5, 10, 100) -> 10
    """
    return max(lower, min(upper, value))




# ==== CONFIGURATION LOADERS ==== #

def load_run_config() -> RunConfig:
    """
    Load runtime configuration from environment variables.

    This function:
    1. Reads environment variables with defaults
    2. Clamps values to safe ranges
    3. Constructs RunConfig instance

    Environment Variables:
        TAVILY_ENV: Execution environment (local/ci/colab)
        TAVILY_DATA_DIR: Data directory path
        HTTPX_TIMEOUT_SECONDS: HTTP request timeout (clamped 5-20)
        HTTPX_MAX_CONCURRENCY: HTTP concurrency (clamped 1-128)
        PLAYWRIGHT_HEADLESS: Browser headless mode (true/false)
        PLAYWRIGHT_MAX_CONCURRENCY: Browser concurrency (clamped 1-4)
        SHARD_SIZE: URLs per shard (clamped 50-5000)
        PROXY_CONFIG_PATH: Optional proxy config file path

    Returns:
        RunConfig with validated configuration values

    Note:
        All numeric values are clamped to prevent resource exhaustion
        or configuration errors from causing system instability.
    """
    # --► ENVIRONMENT & PATHS
    env = os.getenv("TAVILY_ENV", "local")
    data_dir = Path(os.getenv("TAVILY_DATA_DIR", "data")).resolve()
    urls_path = data_dir / "urls.txt"

    # --► HTTP TIMEOUT CONFIGURATION
    httpx_timeout_seconds_raw = _env_int(
        "HTTPX_TIMEOUT_SECONDS",
        DEFAULT_HTTPX_TIMEOUT_SECONDS,
    )
    # Hard clamp to reasonable range (5-20s) to avoid stalls
    httpx_timeout_seconds = _clamp(httpx_timeout_seconds_raw, 5, 20)

    # --► HTTP CONCURRENCY CONFIGURATION
    httpx_max_concurrency_raw = _env_int(
        "HTTPX_MAX_CONCURRENCY",
        DEFAULT_HTTPX_MAX_CONCURRENCY,
    )
    # Clamp to keep Colab and local environments safe
    httpx_max_concurrency = _clamp(httpx_max_concurrency_raw, 1, 128)

    # --► BROWSER CONCURRENCY CONFIGURATION
    playwright_max_concurrency_raw = _env_int(
        "PLAYWRIGHT_MAX_CONCURRENCY",
        DEFAULT_PLAYWRIGHT_MAX_CONCURRENCY,
    )
    # Playwright is expensive; keep concurrency very small
    playwright_max_concurrency = _clamp(playwright_max_concurrency_raw, 1, 4)

    # --► SHARD SIZE CONFIGURATION
    shard_size_raw = _env_int("SHARD_SIZE", DEFAULT_SHARD_SIZE)
    # Avoid pathological shard sizes while allowing tuning
    shard_size = _clamp(shard_size_raw, 50, 5_000)

    # --► PROXY CONFIGURATION
    proxy_config_path_env = os.getenv("PROXY_CONFIG_PATH")
    proxy_config_path: Path | None = (
        Path(proxy_config_path_env).resolve() if proxy_config_path_env else None
    )

    # --► CONSTRUCT RUNCONFIG
    return RunConfig(
        env=env,  # type: ignore[arg-type]
        urls_path=urls_path,
        data_dir=data_dir,
        httpx_timeout_seconds=httpx_timeout_seconds,
        httpx_max_concurrency=httpx_max_concurrency,
        playwright_headless=(
            os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
        ),
        playwright_max_concurrency=playwright_max_concurrency,
        shard_size=shard_size,
        proxy_config_path=proxy_config_path,
    )




def load_proxy_config_from_json(path: Path) -> ProxyConfig:
    """
    Load proxy configuration from JSON file.

    Expected JSON structure:
        {
            "proxy": {
                "hostname": "proxy.example.com:12345",
                "port": {
                    "http": 8080,
                    "https": 8443,
                    "socks5": 1080
                },
                "username": "user",
                "password": "pass"
            }
        }

    Args:
        path: Path to proxy configuration JSON file

    Returns:
        ProxyConfig with parsed proxy settings

    Raises:
        FileNotFoundError: If path does not exist
        json.JSONDecodeError: If file is not valid JSON
        KeyError: If required fields are missing

    Note:
        Username and password are optional fields.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    proxy = raw["proxy"]

    # Extract hostname (strip port if included)
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
