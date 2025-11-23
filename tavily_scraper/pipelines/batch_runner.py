"""
Batch runner for sharded URL processing execution.

This module orchestrates the hybrid scraping pipeline, managing:
- Concurrent job processing with configurable limits
- Browser lifecycle management
- Statistics collection and persistence
- Success-based early termination
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from playwright.async_api import Browser

from tavily_scraper.config.env import load_proxy_config_from_json, load_run_config
from tavily_scraper.config.proxies import ProxyManager
from tavily_scraper.core.models import (
    FetchResult,
    RunConfig,
    RunnerContext,
    RunSummary,
    UrlJob,
    UrlStats,
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




# ==== CONCURRENT JOB PROCESSING ==== #

async def _process_jobs(
    jobs: list[UrlJob],
    ctx: RunnerContext,
    browser: Browser | None,
    config: RunConfig,
    target_success: int | None,
) -> list[FetchResult]:
    """
    Process URL jobs with concurrency control and optional early termination.

    This function:
    1. Creates a semaphore to limit concurrent requests
    2. Processes jobs asynchronously with configurable parallelism
    3. Tracks success count for early termination
    4. Logs progress at regular intervals

    Args:
        jobs: List of URL jobs to process
        ctx: Runner context containing shared resources
        browser: Optional Playwright browser instance for fallback
        config: Runtime configuration
        target_success: Optional success count threshold for early stop

    Returns:
        List of fetch results for all processed jobs

    Note:
        When target_success is reached, remaining jobs are cancelled
        to avoid unnecessary processing.
    """
    semaphore = asyncio.Semaphore(config.httpx_max_concurrency)
    results: list[FetchResult] = []
    success_count = 0
    processed_count = 0
    stop_processing = False
    target_reached_logged = False

    async def process_job(job: UrlJob) -> FetchResult | None:
        """
        Process a single URL job with early termination support.

        Args:
            job: URL job to process

        Returns:
            FetchResult if processed, None if skipped due to early termination
        """
        nonlocal success_count, processed_count, stop_processing, target_reached_logged

        if stop_processing:
            return None

        async with semaphore:
            if stop_processing:
                return None

            result = await route_and_fetch(job, ctx, browser)
            processed_count += 1

            if result.get("status") == "success":
                success_count += 1

                # Early-stop condition: log once when we first hit the target.
                if target_success and success_count >= target_success:
                    stop_processing = True
                    if not target_reached_logged:
                        target_reached_logged = True
                        logger.info(
                            "Reached target of %s successful URLs",
                            target_success,
                        )
                elif not target_reached_logged:
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




# ==== BATCH EXECUTION ORCHESTRATION ==== #

async def run_batch(
    urls: list[str],
    config: RunConfig,
    max_urls: int | None = None,
    target_success: int | None = None,
    use_browser: bool = False,
) -> RunSummary:
    """
    Execute batch scraping on a list of URLs.

    This function orchestrates the complete scraping workflow:
    1. Loads proxy configuration if available
    2. Creates URL jobs from input list
    3. Initializes shared resources (scheduler, robots client, HTTP client)
    4. Optionally launches browser for fallback
    5. Processes all jobs concurrently
    6. Persists statistics and summary

    Args:
        urls: List of URLs to process
        config: Runtime configuration
        max_urls: Maximum number of URLs to attempt (optional)
        target_success: Stop after this many successful fetches (optional)
        use_browser: Enable Playwright browser fallback (default: False)

    Returns:
        RunSummary containing aggregate metrics for the batch

    Note:
        Either max_urls or target_success can be specified, not both.
        If neither is specified, all URLs will be processed.
    """
    # --► PROXY CONFIGURATION
    proxy_manager: ProxyManager | None = None
    proxy_config = None

    if config.proxy_config_path and config.proxy_config_path.exists():
        proxy_config = load_proxy_config_from_json(config.proxy_config_path)
        proxy_manager = ProxyManager.from_proxy_config(proxy_config)

    # --► JOB CREATION
    if max_urls:
        urls = urls[:max_urls]

    jobs = make_url_jobs(urls)
    logger.info(
        "Processing up to %s URLs (target_success=%s)",
        len(jobs),
        target_success,
    )

    # --► CONTEXT INITIALIZATION
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

    # --► JOB PROCESSING
    if use_browser:
        from tavily_scraper.pipelines.browser_fetcher import browser_lifecycle

        async with browser_lifecycle(config, proxy_manager) as browser:
            results = await _process_jobs(
                jobs,
                ctx,
                browser,
                config,
                target_success,
            )
    else:
        results = await _process_jobs(jobs, ctx, None, config, target_success)

    # --► STATISTICS PERSISTENCE
    stats = [fetch_result_to_url_stats(r) for r in results]

    stealth_suffix = ""
    if config.stealth_config and config.stealth_config.enabled:
        stealth_suffix = "_stealth"

    stats_path = config.data_dir / f"stats{stealth_suffix}.jsonl"
    write_stats_jsonl(stats, stats_path)
    logger.info("Wrote %s stats to %s", len(stats), stats_path)

    # --► SUMMARY COMPUTATION
    summary = compute_run_summary(stats)
    summary_path = config.data_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("Wrote run summary to %s", summary_path)

    # --► RESOURCE CLEANUP
    await http_client.aclose()
    await robots_client._client.aclose()

    return summary




# ==== HIGH-LEVEL ENTRY POINTS ==== #

async def run_all(
    config: RunConfig | None = None,
    *,
    max_urls: int | None = None,
    target_success: int | None = None,
    use_browser: bool = True,
) -> RunSummary:
    """
    Canonical entry point for running the full batch pipeline.

    This function:
    1. Loads configuration from environment
    2. Reads URLs from configured path
    3. Executes batch processing
    4. Writes output files:
       - data/stats.jsonl: Per-URL statistics
       - data/run_summary.json: Aggregate metrics

    Args:
        config: Optional pre-loaded configuration (defaults to env-based)
        max_urls: Maximum number of URLs to process (optional)
        target_success: Stop after N successful fetches (optional)
        use_browser: Enable browser fallback (default: True)

    Returns:
        RunSummary containing aggregate metrics

    Raises:
        RuntimeError: If no URLs found at configured path
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


async def run_all_sharded(
    config: RunConfig | None = None,
    *,
    use_browser: bool = True,
) -> RunSummary:
    """
    Sharded batch runner with checkpoint support.

    Processes URLs in shards with resumability via checkpoints.

    Args:
        config: Optional pre-loaded configuration
        use_browser: Enable browser fallback

    Returns:
        RunSummary containing aggregate metrics
    """
    from tavily_scraper.pipelines.shard_runner import run_shard
    from tavily_scraper.utils.io import make_shards

    config = config or load_run_config()
    urls = load_urls_from_txt(config.urls_path)

    if not urls:
        msg = f"No URLs found at {config.urls_path}"
        raise RuntimeError(msg)

    jobs = make_url_jobs(urls)
    shards = make_shards(jobs, config.shard_size)

    # Setup context
    proxy_config = None
    proxy_manager = None
    if config.proxy_config_path and config.proxy_config_path.exists():
        proxy_config = load_proxy_config_from_json(config.proxy_config_path)
        proxy_manager = ProxyManager.from_proxy_config(proxy_config)

    scheduler = DomainScheduler(global_limit=config.httpx_max_concurrency)
    robots_client = await make_robots_client(config, proxy_config)
    http_client = make_http_client(config, proxy_manager)

    ctx = RunnerContext(
        run_config=config,
        proxy_manager=proxy_manager,
        scheduler=scheduler,
        robots_client=robots_client,
        http_client=http_client,
    )

    all_stats: list[UrlStats] = []
    run_id = datetime.now(UTC).isoformat()
    checkpoints_dir = config.data_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    if use_browser:
        from tavily_scraper.pipelines.browser_fetcher import browser_lifecycle

        async with browser_lifecycle(config, proxy_manager) as browser:
            for shard_id, shard_jobs in enumerate(shards):
                checkpoint_path = checkpoints_dir / f"{run_id}_shard_{shard_id}.json"
                shard_stats = await run_shard(
                    run_id, shard_id, shard_jobs, ctx, checkpoint_path, browser
                )
                all_stats.extend(shard_stats)
    else:
        for shard_id, shard_jobs in enumerate(shards):
            checkpoint_path = checkpoints_dir / f"{run_id}_shard_{shard_id}.json"
            shard_stats = await run_shard(
                run_id, shard_id, shard_jobs, ctx, checkpoint_path, None
            )
            all_stats.extend(shard_stats)

    # Write stats
    stats_path = config.data_dir / "stats.jsonl"
    write_stats_jsonl(all_stats, stats_path)

    # Compute summary
    summary = compute_run_summary(all_stats)
    summary_path = config.data_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Cleanup
    await http_client.aclose()
    await robots_client._client.aclose()

    return summary





# ==== STANDALONE EXECUTION ==== #

async def main() -> None:
    """
    Main entry point for standalone local execution.

    Runs the full pipeline and displays summary results to console.

    Returns:
        None
    """
    summary = await run_all()

    print("\nResults:")
    print(f"  Total URLs processed: {summary['total_urls']}")
    print(
        f"  Successful: {int(summary['total_urls'] * summary['success_rate'])}"
    )
    print(f"  Success rate: {summary['success_rate']:.2%}")
    print(f"  HTTP share: {summary['httpx_share']:.2%}")
    print(f"  P50 HTTP latency: {summary['p50_latency_httpx_ms']}ms")
    print(f"  CAPTCHA rate: {summary['captcha_rate']:.2%}")
    print(f"  Robots blocked: {summary['robots_block_rate']:.2%}")




if __name__ == "__main__":
    asyncio.run(main())
