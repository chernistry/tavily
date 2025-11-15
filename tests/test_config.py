"""Tests for configuration loading."""

import os

from tavily_scraper.config.env import load_run_config


def test_load_run_config_defaults() -> None:
    """Test loading config with default values."""
    # Clear relevant env vars
    for key in [
        "TAVILY_ENV",
        "HTTPX_TIMEOUT_SECONDS",
        "HTTPX_MAX_CONCURRENCY",
        "PLAYWRIGHT_MAX_CONCURRENCY",
        "SHARD_SIZE",
    ]:
        os.environ.pop(key, None)

    config = load_run_config()
    assert config.env == "local"
    assert config.httpx_timeout_seconds == 10
    assert config.httpx_max_concurrency == 32
    assert config.playwright_max_concurrency == 2
    assert config.shard_size == 500


def test_load_run_config_custom() -> None:
    """Test loading config with custom env vars."""
    os.environ["TAVILY_ENV"] = "ci"
    os.environ["HTTPX_TIMEOUT_SECONDS"] = "15"
    os.environ["HTTPX_MAX_CONCURRENCY"] = "64"

    config = load_run_config()
    assert config.env == "ci"
    assert config.httpx_timeout_seconds == 15
    assert config.httpx_max_concurrency == 64

    # Cleanup
    os.environ.pop("TAVILY_ENV", None)
    os.environ.pop("HTTPX_TIMEOUT_SECONDS", None)
    os.environ.pop("HTTPX_MAX_CONCURRENCY", None)


def test_load_run_config_clamps_extreme_values() -> None:
    """Config values should be clamped into safe ranges."""
    os.environ["HTTPX_TIMEOUT_SECONDS"] = "1"  # below lower bound
    os.environ["HTTPX_MAX_CONCURRENCY"] = "1000"  # above upper bound
    os.environ["PLAYWRIGHT_MAX_CONCURRENCY"] = "10"  # above upper bound
    os.environ["SHARD_SIZE"] = "100000"  # above upper bound

    config = load_run_config()

    assert config.httpx_timeout_seconds == 5
    assert config.httpx_max_concurrency == 128
    assert config.playwright_max_concurrency == 4
    assert config.shard_size == 5000

    for key in [
        "HTTPX_TIMEOUT_SECONDS",
        "HTTPX_MAX_CONCURRENCY",
        "PLAYWRIGHT_MAX_CONCURRENCY",
        "SHARD_SIZE",
    ]:
        os.environ.pop(key, None)
