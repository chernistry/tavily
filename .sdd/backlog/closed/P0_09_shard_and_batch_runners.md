Read /Users/sasha/IdeaProjects/personal_projects/tavily/.sdd/CODING_RULES.md first

# P0_09 – Shard runner and batch runner

## Objective

Implement the per-shard runner (`run_shard`) and sharded batch runner (`run_all`) that orchestrate URL jobs, apply the router, update checkpoints, and produce run summaries with resumability.

## Dependencies

- Depends on:
  - `P0_02_config_env_and_input_loading.md`
  - `P0_03_core_models_and_stats_schema.md`
  - `P0_04_scheduler_and_robots.md`
  - `P0_05_proxies_and_fast_http_fetcher.md`
  - `P0_06_browser_fetcher_playwright.md`
  - `P0_07_router_captcha_and_hybrid_strategy.md`
  - `P0_08_storage_checkpoints_and_metrics.md`

## Scope

- Implement `run_shard` and `run_all`.
- Integrate `RunnerContext`, `ResultStore`, checkpoints, and router.
- Provide a simple CLI entry point for running the batch.

## Implementation Steps

1. **Extend `RunnerContext`**

   In `tavily_scraper/core/models.py`, extend `RunnerContext` to include:

   ```python
   from tavily_scraper.utils.result_store import ResultStore


   @dataclass
   class RunnerContext:
       run_config: RunConfig
       proxy_manager: ProxyManager | None
       scheduler: DomainScheduler
       robots_client: RobotsClient
       http_client: httpx.AsyncClient
       result_store: ResultStore
   ```

   - Additional fields (logger, etc.) can be added as needed.

2. **Implement sharding helpers**

   In `tavily_scraper/utils/io.py` (or `core/models.py`), implement:

   ```python
   from collections.abc import Sequence

   from tavily_scraper.core.models import UrlJob


   def make_shards(jobs: Sequence[UrlJob], shard_size: int) -> list[list[UrlJob]]:
       shards: list[list[UrlJob]] = []
       for start in range(0, len(jobs), shard_size):
           shard_jobs = list(jobs[start : start + shard_size])
           shard_id = len(shards)
           for index, job in enumerate(shard_jobs):
               job["shard_id"] = shard_id
               job["index_in_shard"] = index
           shards.append(shard_jobs)
       return shards
   ```

3. **Implement `run_shard`**

   In `tavily_scraper/pipelines/shard_runner.py`:

   ```python
   import asyncio
   from collections.abc import Iterable
   from datetime import datetime, timezone
   from pathlib import Path

   from tavily_scraper.core.models import RunnerContext, UrlJob, UrlStats, ShardCheckpoint
   from tavily_scraper.pipelines.browser_fetcher import browser_lifecycle
   from tavily_scraper.pipelines.router import route_and_fetch
   from tavily_scraper.utils.checkpoints import load_checkpoint, save_checkpoint


   async def run_shard(
       run_id: str,
       shard_id: int,
       jobs: list[UrlJob],
       ctx: RunnerContext,
       checkpoint_path: Path,
   ) -> list[UrlStats]:
       existing = load_checkpoint(checkpoint_path)
       if existing and existing["status"] == "completed":
           # Shard already processed; nothing to do
           return []

       checkpoint: ShardCheckpoint = {
           "run_id": run_id,
           "shard_id": shard_id,
           "urls_total": len(jobs),
           "urls_done": 0,
           "last_updated_at": datetime.now(timezone.utc).isoformat(),
           "status": "in_progress",
       }
       save_checkpoint(checkpoint_path, checkpoint)

       semaphore = asyncio.Semaphore(ctx.run_config.httpx_max_concurrency)
       results: list[UrlStats] = []

       async with browser_lifecycle(ctx.run_config, ctx.proxy_manager) as browser:
           async def _run(job: UrlJob) -> None:
               nonlocal checkpoint
               async with semaphore:
                   stats = await route_and_fetch(job, ctx, browser)
                   results.append(stats)
                   ctx.result_store.write(stats)

                   checkpoint["urls_done"] += 1
                   checkpoint["last_updated_at"] = datetime.now(timezone.utc).isoformat()
                   save_checkpoint(checkpoint_path, checkpoint)

           await asyncio.gather(*(_run(job) for job in jobs))

       checkpoint["status"] = "completed"
       checkpoint["last_updated_at"] = datetime.now(timezone.utc).isoformat()
       save_checkpoint(checkpoint_path, checkpoint)

       return results
   ```

4. **Implement `run_all`**

   In `tavily_scraper/pipelines/batch_runner.py`:

   ```python
   import asyncio
   from datetime import datetime, timezone
   from pathlib import Path
   from typing import Iterable

   import httpx

   from tavily_scraper.config.env import load_run_config, load_proxy_config_from_json
   from tavily_scraper.config.proxies import ProxyManager
   from tavily_scraper.core.models import RunConfig, RunnerContext, UrlStats
   from tavily_scraper.core.robots import make_robots_client
   from tavily_scraper.core.scheduler import DomainScheduler
   from tavily_scraper.pipelines.fast_http_fetcher import make_http_client
   from tavily_scraper.pipelines.shard_runner import run_shard
   from tavily_scraper.utils.io import ensure_canonical_urls_file, load_urls_from_txt, make_url_jobs, make_shards
   from tavily_scraper.utils.metrics import compute_run_summary, write_run_summary
   from tavily_scraper.utils.result_store import ResultStore


   async def run_all(config: RunConfig) -> dict:
       data_dir = config.data_dir
       stats_path = data_dir / "stats.jsonl"
       run_summary_path = data_dir / "run_summary.json"
       checkpoints_dir = data_dir / "checkpoints"

       raw_csv = Path(".sdd/raw/urls.csv")  # or configurable
       canonical_urls_path = ensure_canonical_urls_file(raw_csv, config.urls_path)
       urls = load_urls_from_txt(canonical_urls_path)
       jobs = make_url_jobs(urls)
       shards = make_shards(jobs, config.shard_size)

       proxy_config = None
       proxy_manager = None
       if config.proxy_config_path:
           proxy_config = load_proxy_config_from_json(config.proxy_config_path)
           proxy_manager = ProxyManager.from_proxy_config(proxy_config)

       scheduler = DomainScheduler(global_limit=config.httpx_max_concurrency)
       robots_client = await make_robots_client(config, proxy_config)
       http_client = make_http_client(config, proxy_manager)

       async with http_client:
           with ResultStore(stats_path) as result_store:
               ctx = RunnerContext(
                   run_config=config,
                   proxy_manager=proxy_manager,
                   scheduler=scheduler,
                   robots_client=robots_client,
                   http_client=http_client,
                   result_store=result_store,
               )

               all_stats: list[UrlStats] = []
               run_id = datetime.now(timezone.utc).isoformat()

               for shard_id, shard_jobs in enumerate(shards):
                   checkpoint_path = checkpoints_dir / f"{run_id}_shard_{shard_id}.json"
                   shard_stats = await run_shard(run_id, shard_id, shard_jobs, ctx, checkpoint_path)
                   all_stats.extend(shard_stats)

       summary = compute_run_summary(all_stats)
       write_run_summary(run_summary_path, summary)
       return summary
   ```

5. **CLI entry point**

   - Add a simple CLI in `batch_runner.py`:

     ```python
     if __name__ == "__main__":
         config = load_run_config()
         summary = asyncio.run(run_all(config))
         print(summary)
     ```

## Example Usage

```bash
python -m tavily_scraper.pipelines.batch_runner
```

or from Python:

```python
import asyncio

from tavily_scraper.config.env import load_run_config
from tavily_scraper.pipelines.batch_runner import run_all


config = load_run_config()
summary = asyncio.run(run_all(config))
print(summary)
```

## Acceptance Criteria

- `make_shards`:

  - Splits `UrlJob` lists into shards of size `RunConfig.shard_size`.
  - Correctly sets `shard_id` and `index_in_shard` on jobs.

- `run_shard`:

  - Respects existing checkpoints and skips completed shards.
  - Uses `route_and_fetch` for each job.
  - Writes `UrlStats` rows to `ResultStore` and updates checkpoints as progress is made.
  - Returns a list of `UrlStats` produced for that shard.

- `run_all`:

  - Loads URLs from `.sdd/raw/urls.csv` via the canonicalization helpers.
  - Constructs `RunnerContext` once and reuses shared clients across shards.
  - Iterates over shards, handling checkpoints and resuming correctly.
  - Aggregates all `UrlStats` into a `RunSummary` and writes it to `data/run_summary.json`.

- A basic E2E test (with network mocked or directed to a local test server) verifies that:

  - `run_all` processes a handful of URLs.
  - Exactly one `UrlStats` row per URL is produced.
  - Checkpoint files are created and marked `completed`.

- All new code passes `ruff check .` and `mypy --strict`.

