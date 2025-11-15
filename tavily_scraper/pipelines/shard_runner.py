"""Per-shard runner."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from playwright.async_api import Browser

from typing import Any, cast

from tavily_scraper.core.models import (
    FetchResult,
    RunnerContext,
    ShardCheckpoint,
    UrlJob,
    UrlStats,
    fetch_result_to_url_stats,
)
from tavily_scraper.pipelines.router import route_and_fetch
from tavily_scraper.utils.io import load_checkpoint, save_checkpoint


async def run_shard(
    run_id: str,
    shard_id: int,
    jobs: list[UrlJob],
    ctx: RunnerContext,
    checkpoint_path: Path,
    browser: Browser | None = None,
) -> list[UrlStats]:
    """
    Process a single shard of URL jobs with checkpoint support.

    Args:
        run_id: Unique run identifier
        shard_id: Shard number
        jobs: List of URL jobs in this shard
        ctx: Runner context with shared resources
        checkpoint_path: Path to checkpoint file
        browser: Optional browser instance for fallback

    Returns:
        List of URL statistics for processed jobs
    """
    existing = load_checkpoint(checkpoint_path)
    if existing and existing.get("status") == "completed":
        return []

    checkpoint: ShardCheckpoint = {
        "run_id": run_id,
        "shard_id": shard_id,
        "urls_total": len(jobs),
        "urls_done": 0,
        "last_updated_at": datetime.now(UTC).isoformat(),
        "status": "in_progress",
    }
    save_checkpoint(cast(dict[str, Any], checkpoint), checkpoint_path)

    semaphore = asyncio.Semaphore(ctx.run_config.httpx_max_concurrency)
    results: list[UrlStats] = []

    async def _process_job(job: UrlJob) -> None:
        nonlocal checkpoint
        async with semaphore:
            fetch_result: FetchResult = await route_and_fetch(job, ctx, browser)
            stats = fetch_result_to_url_stats(fetch_result)
            results.append(stats)

            checkpoint["urls_done"] += 1
            checkpoint["last_updated_at"] = datetime.now(UTC).isoformat()
            save_checkpoint(cast(dict[str, Any], checkpoint), checkpoint_path)

    await asyncio.gather(*(_process_job(job) for job in jobs))

    checkpoint["status"] = "completed"
    checkpoint["last_updated_at"] = datetime.now(UTC).isoformat()
    save_checkpoint(cast(dict[str, Any], checkpoint), checkpoint_path)

    return results

