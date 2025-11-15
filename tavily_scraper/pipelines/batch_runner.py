"""Batch runner for sharded execution."""

from __future__ import annotations

import asyncio
import json

from playwright.async_api import Browser

from tavily_scraper.config.env import load_proxy_config_from_json, load_run_config
from tavily_scraper.config.proxies import ProxyManager
from tavily_scraper.core.models import (
    FetchResult,
    RunConfig,
    RunnerContext,
    RunSummary,
    UrlJob,
    fetch_result_to_url_stats,
)
from tavily_scraper.core.robots import make_robots_client
from tavily_scraper.core.scheduler import DomainScheduler
from tavily_scraper.pipelines.fast_http_fetcher import make_http_client
from tavily_scraper.pipelines.router import route_and_fetch
from tavily_scraper.utils.io import (
    load_urls_from_txt,
    make_url_jobs,
    write_stats_jsonl,
)
from tavily_scraper.utils.logging import get_logger
from tavily_scraper.utils.metrics import compute_run_summary

logger = get_logger(__name__)


async def _process_jobs(
    jobs: list[UrlJob],
    ctx: RunnerContext,
    browser: Browser | None,
    config: RunConfig,
    target_success: int | None,
) -> list[FetchResult]:
    """Process jobs with concurrency control."""
    semaphore = asyncio.Semaphore(config.httpx_max_concurrency)
    results: list[FetchResult] = []
    success_count = 0
    processed_count = 0
    stop_processing = False

    async def process_job(job: UrlJob) -> FetchResult | None:
        nonlocal success_count, processed_count, stop_processing

        if stop_processing:
            return None

        async with semaphore:
            if stop_processing:
                return None

            result = await route_and_fetch(job, ctx, browser)
            processed_count += 1

            if result.get("status") == "success":
                success_count += 1
                if target_success and success_count >= target_success:
                    stop_processing = True
                    logger.info("Reached target of %s successful URLs", target_success)
                else:
                    logger.info(
                        "Success %s/%s (processed %s)",
                        success_count,
                        target_success or "∞",
                        processed_count,
                    )

            return result

    tasks = [process_job(job) for job in jobs]
    completed_results = await asyncio.gather(*tasks)
    results = [r for r in completed_results if r is not None]

    logger.info(
        "Completed: %s successful out of %s processed",
        success_count,
        processed_count,
    )
    return results


async def run_batch(
    urls: list[str],
    config: RunConfig,
    max_urls: int | None = None,
    target_success: int | None = None,
    use_browser: bool = False,
) -> RunSummary:
    """Run batch scraping on URLs.

    Args:
        urls: List of URLs to process.
        config: Loaded RunConfig for this run.
        max_urls: Maximum URLs to attempt (optional).
        target_success: Stop after this many successful fetches (optional).
        use_browser: Enable Playwright browser fallback (optional).
    """
    # Load proxy if configured
    proxy_manager = None
    proxy_config = None
    if config.proxy_config_path and config.proxy_config_path.exists():
        proxy_config = load_proxy_config_from_json(config.proxy_config_path)
        proxy_manager = ProxyManager.from_proxy_config(proxy_config)

    # Create jobs
    if max_urls:
        urls = urls[:max_urls]
    jobs = make_url_jobs(urls)
    logger.info("Processing up to %s URLs (target_success=%s)", len(jobs), target_success)

    # Setup context
    scheduler = DomainScheduler(
        global_limit=config.httpx_max_concurrency,
        per_domain_limits={"www.google.com": 1, "www.bing.com": 1},
    )
    robots_client = await make_robots_client(config, proxy_config)
    http_client = make_http_client(config, proxy_manager)

    ctx = RunnerContext(
        run_config=config,
        proxy_manager=proxy_manager,
        scheduler=scheduler,
        robots_client=robots_client,
        http_client=http_client,
    )

    # Setup browser if needed and process jobs
    if use_browser:
        from tavily_scraper.pipelines.browser_fetcher import browser_lifecycle

        async with browser_lifecycle(config, proxy_manager) as browser:
            results = await _process_jobs(jobs, ctx, browser, config, target_success)
    else:
        results = await _process_jobs(jobs, ctx, None, config, target_success)

    # Convert to stats
    stats = [fetch_result_to_url_stats(r) for r in results]

    # Write stats
    stats_path = config.data_dir / "stats.jsonl"
    write_stats_jsonl(stats, stats_path)
    logger.info("Wrote %s stats to %s", len(stats), stats_path)

    # Compute summary and persist
    summary = compute_run_summary(stats)
    summary_path = config.data_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("Wrote run summary to %s", summary_path)

    # Cleanup
    await http_client.aclose()
    await robots_client._client.aclose()

    return summary


async def run_all(
    config: RunConfig | None = None,
    *,
    max_urls: int | None = None,
    target_success: int | None = None,
    use_browser: bool = True,
) -> RunSummary:
    """Canonical entrypoint for running the full batch.

    This function loads URLs from ``config.urls_path`` and writes:

    * ``data/stats.jsonl`` – per-URL UrlStats rows.
    * ``data/run_summary.json`` – aggregate RunSummary for the run.
    """
    config = config or load_run_config()
    urls = load_urls_from_txt(config.urls_path)
    if not urls:
        msg = f"No URLs found at {config.urls_path}"
        raise RuntimeError(msg)

    return await run_batch(
        urls=urls,
        config=config,
        max_urls=max_urls,
        target_success=target_success,
        use_browser=use_browser,
    )


async def main() -> None:
    """Main entry point for local runs."""
    summary = await run_all()

    print("\nResults:")
    print(f"  Total URLs processed: {summary['total_urls']}")
    print(f"  Successful: {int(summary['total_urls'] * summary['success_rate'])}")
    print(f"  Success rate: {summary['success_rate']:.2%}")
    print(f"  HTTP share: {summary['httpx_share']:.2%}")
    print(f"  P50 HTTP latency: {summary['p50_latency_httpx_ms']}ms")
    print(f"  CAPTCHA rate: {summary['captcha_rate']:.2%}")
    print(f"  Robots blocked: {summary['robots_block_rate']:.2%}")


if __name__ == "__main__":
    asyncio.run(main())
