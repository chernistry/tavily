Read .sdd/CODING_RULES.md first

# P0_03 – Core models and stats schema

## Objective

Define the core typed models that represent per-URL outcomes, run-level metrics, and in-memory fetch results. These models are the backbone of the pipeline, enabling consistent logging, persistence, and analysis while satisfying `CODING_RULES.md`.

## Dependencies

- Depends on:
  - `P0_01_repo_bootstrap_structure.md`
  - `P0_02_config_env_and_input_loading.md`

## Scope

- Implement `ScraperError`, `FetchResult`, `UrlStats`, `RunSummary`, and `ShardCheckpoint`.
- Implement helpers to transform `FetchResult` → `UrlStats`.
- Implement basic metrics helpers (`percentile` and `compute_run_summary` scaffolding).

## Implementation Steps

1. **Implement `ScraperError`**

   In `tavily_scraper/core/errors.py`:

   ```python
   from __future__ import annotations


   class ScraperError(Exception):
       def __init__(self, kind: str, url: str, detail: str | None = None) -> None:
           self.kind = kind
           self.url = url
           self.detail = detail
           message = f"{kind} for {url}: {detail or ''}"
           super().__init__(message)
   ```

   - Use this for configuration or programming errors (e.g. invalid `RunConfig`, unsupported mode), not normal network noise.

2. **Define `FetchResult`**

   In `tavily_scraper/core/models.py`, add:

   ```python
   from typing import TypedDict

   from tavily_scraper.config.constants import Method, Stage, Status
   from tavily_scraper.core.models import UrlStr  # from P0_02


   class FetchResult(TypedDict, total=False):
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

       # in-memory only; never persisted to UrlStats
       content: str | None
   ```

   - `FetchResult` is used internally by HTTP and browser fetchers before being transformed into `UrlStats`.

3. **Define `UrlStats` (persisted per-URL stats)**

   In `core/models.py`, implement `UrlStats` exactly as required by `CODING_RULES.md`:

   ```python
   class UrlStats(TypedDict):
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
   ```

   - `UrlStats` is JSON-serializable and used for `data/stats.jsonl`.
   - Every attempted URL must produce exactly one `UrlStats` row.

4. **Define `RunSummary`**

   In `core/models.py`, add:

   ```python
   class RunSummary(TypedDict):
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
   ```

   - This is persisted as `data/run_summary.json`.
   - As per rules, only **add** fields in future, never remove or rename.

5. **Define `ShardCheckpoint`**

   In `core/models.py`:

   ```python
   from typing import Literal


   class ShardCheckpoint(TypedDict):
       run_id: str
       shard_id: int
       urls_total: int
       urls_done: int
       last_updated_at: str
       status: Literal["pending", "in_progress", "completed", "failed"]
   ```

6. **Implement helper constructors**

   In `core/models.py` add:

   ```python
   from datetime import datetime, timezone


   def _utc_now_iso() -> str:
       return datetime.now(timezone.utc).isoformat()


   def make_initial_fetch_result(
       url_job: UrlJob,
       method: Method,
       stage: Stage,
   ) -> FetchResult:
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
       )
   ```

   - Ensure `content` in `FetchResult` never ends up in `UrlStats`.

7. **Implement metrics helpers**

   In `tavily_scraper/utils/metrics.py`:

   ```python
   from __future__ import annotations

   from collections.abc import Iterable
   from statistics import mean

   from tavily_scraper.config.constants import Method
   from tavily_scraper.core.models import RunSummary, UrlStats


   def percentile(values: list[int], p: float) -> int | None:
       if not values:
           return None
       values_sorted = sorted(values)
       k = max(0, min(len(values_sorted) - 1, int(round((p / 100.0) * (len(values_sorted) - 1)))))
       return values_sorted[k]


   def compute_run_summary(stats: Iterable[UrlStats]) -> RunSummary:
       rows = list(stats)
       total = len(rows)
       if total == 0:
           return RunSummary(
               total_urls=0,
               stats_rows=0,
               success_rate=0.0,
               http_error_rate=0.0,
               timeout_rate=0.0,
               captcha_rate=0.0,
               robots_block_rate=0.0,
               httpx_share=0.0,
               playwright_share=0.0,
               p50_latency_httpx_ms=None,
               p95_latency_httpx_ms=None,
               p50_latency_playwright_ms=None,
               p95_latency_playwright_ms=None,
               avg_content_len_httpx=None,
               avg_content_len_playwright=None,
           )

       # Implement simple aggregates; can be refined later
       # (rates, shares, and percentiles based on UrlStats.status/method).
       ...
   ```

   - Implement the full aggregation logic (counts, rates, percentiles) in the `...` section using the assignment rules.

## Example Usage

```python
from tavily_scraper.core.models import FetchResult, fetch_result_to_url_stats


result: FetchResult = {
    "url": "https://example.com",
    "domain": "example.com",
    "method": "httpx",
    "stage": "primary",
    "status": "success",
    "http_status": 200,
    "latency_ms": 120,
    "content_len": 2048,
    "encoding": "utf-8",
    "retries": 0,
    "captcha_detected": False,
    "robots_disallowed": False,
    "error_kind": None,
    "error_message": None,
    "started_at": "2025-01-01T00:00:00Z",
    "finished_at": "2025-01-01T00:00:00Z",
    "shard_id": 0,
}

stats_row = fetch_result_to_url_stats(result)
```

## Acceptance Criteria

- `ScraperError`, `FetchResult`, `UrlStats`, `RunSummary`, and `ShardCheckpoint` are defined in `tavily_scraper/core/models.py` and `core/errors.py` and pass `mypy --strict`.
- Every field required by `CODING_RULES.md` is present with correct type hints.
- Helper functions `make_initial_fetch_result` and `fetch_result_to_url_stats` exist and:

  - Never include HTML content in `UrlStats`.
  - Produce valid rows even when some optional fields are missing in `FetchResult`.

- `percentile` and `compute_run_summary` exist in `tavily_scraper/utils/metrics.py`:

  - Handle empty input gracefully.
  - Use simple but correct percentile and average calculations.

- Unit tests cover:

  - `UrlStats` structure and required keys.
  - Conversion from `FetchResult` to `UrlStats`.
  - Basic `compute_run_summary` behavior (e.g. success rate and httpx/playwright shares on small synthetic datasets).

