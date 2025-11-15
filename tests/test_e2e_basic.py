"""Basic E2E test with real URLs."""

from pathlib import Path

import pytest

from tavily_scraper.config.env import load_run_config
from tavily_scraper.core.models import RunnerContext
from tavily_scraper.core.robots import make_robots_client
from tavily_scraper.core.scheduler import DomainScheduler
from tavily_scraper.pipelines.fast_http_fetcher import fetch_one, make_http_client
from tavily_scraper.utils.io import load_urls_from_csv, make_url_jobs


@pytest.mark.asyncio
async def test_e2e_basic_http_fetch() -> None:
    """Test basic HTTP fetch with real URLs from raw directory."""
    # Load config
    config = load_run_config()

    # Load a few URLs from raw CSV
    raw_csv = Path(".sdd/raw/urls.csv")
    if not raw_csv.exists():
        pytest.skip("Raw URLs file not found")

    urls = load_urls_from_csv(raw_csv)[:3]  # Just test first 3
    jobs = make_url_jobs(urls)

    # Setup context (without proxy for now)
    scheduler = DomainScheduler(global_limit=config.httpx_max_concurrency)
    robots_client = await make_robots_client(config, None)
    http_client = make_http_client(config, None)

    ctx = RunnerContext(
        run_config=config,
        proxy_manager=None,
        scheduler=scheduler,
        robots_client=robots_client,
        http_client=http_client,
    )

    # Fetch first URL
    if jobs:
        result = await fetch_one(jobs[0], ctx)
        assert result["url"] == jobs[0]["url"]
        assert result["domain"]
        assert result["status"] in [
            "success",
            "http_error",
            "timeout",
            "robots_blocked",
        ]
        assert result["latency_ms"] is not None or result["status"] == "robots_blocked"

    await http_client.aclose()
    await robots_client._client.aclose()
