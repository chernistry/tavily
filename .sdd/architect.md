## Goals & Non-Goals

### Goals

1. Build a **hybrid scraping pipeline** for ~**10,000 mixed static/JS-heavy URLs**, designed to scale further:

   * Stage 1: fast HTTP client for static / mostly static pages.
   * Stage 2: JS-enabled headless browser for dynamic / blocked pages.
2. Provide **clear, reproducible benchmarks**:

   * Latency distributions (P50/P90/P95) per method and per domain.
   * Success / failure rates with **error taxonomy** and CAPTCHA / robots buckets.
   * Split of HTTP vs browser usage, per-domain stats, and fallback rate.
3. Integrate **proxies, robots.txt, and CAPTCHA detection** end-to-end:

   * Respect robots.txt and site ToS by default.
   * Route all traffic through provided proxies (`proxy.json`).
   * Detect and log CAPTCHAs / hard bot walls; do not bypass.
4. Deliver a **Colab-first demo** backed by a reusable Python package:

   * Notebook = thin orchestration + visualization + flowchart.
   * Package = scraping, routing, metrics, configs, tests, CLI.
5. Make the implementation **production-shaped and scalable** from 10k upwards:

   * Sharded batch runner, domain-aware concurrency, checkpointing, resumability.
   * Typed APIs, tests, CI, observability hooks and SLO-driven guardrails.
   * Configuration-driven so concurrency / timeouts / thresholds can be tuned without code changes.

### Non-Goals

1. Building a **persistent distributed crawler** (no Airflow/Kafka/worker fleet).
2. Exposing a **multi-tenant HTTP API**; scope is batch job + notebook UI.
3. **Bypassing CAPTCHAs or advanced anti-bot** (no external solver services, no stealth hacks beyond standard browser behavior).
4. Designing a **search index / ranking engine**; output is per-URL content + metrics, not a queryable search product.
5. Implementing a full **data warehouse**; we persist to local files (`.jsonl`/`.parquet`) and analyze via pandas.

---

## Architecture Overview

### Components & Connections (Text Diagram)

```text
                 +------------------------------------+
                 |   Colab Notebook (UI / Glue)      |
                 | - installs deps                   |
                 | - mounts urls.csv, proxy.json     |
                 | - calls ShardedBatchRunner        |
                 | - renders charts + flowchart      |
                 +-----------------+------------------+
                                   |
                                   v
                    +--------------+----------------+
                    |          ShardedBatchRunner   |
                    |  - splits 10k into shards     |
                    |  - per-shard ScrapeRunner     |
                    |  - checkpointing + resume     |
                    +------+-----------+------------+
                           |           |
                           |           v
                           |  +--------+---------+
                           |  |  CheckpointStore |
                           |  |  - run & shard   |
                           |  |    progress      |
                           |  +------------------+
                           |
                           v
                  +--------+----------------------+
                  |          ScrapeRunner        |
                  |  - loads shard URLs          |
                  |  - builds RunnerContext      |
                  |  - runs StrategyRouter (async|
                  +------+----------+------------+
                         |          |
         +---------------+          +-------------------+
         |                                          |
         v                                          v
+--------+---------+                       +--------+----------+
| RobotsClient &   |                       |   ProxyManager    |
| DomainScheduler  |                       | - proxy.json      |
| - robots.txt     |                       |   parsing         |
| - per-domain     |                       | - httpx/Playw cfg |
|   concurrency    |                       +--------+----------+
+--------+---------+                                |
         |                                          |
         +----------------------+-------------------+
                                |
                                v
                      +---------+------------------+
                      |       StrategyRouter      |
                      | - for each UrlJob:        |
                      |   1) FastHttpFetcher      |
                      |   2) classify result      |
                      |   3) optional Browser     |
                      |      Fetcher fallback     |
                      +-----------+---------------+
                                  |
              +-------------------+---------------------+
              |                                         |
              v                                         v
+-------------+-------------------+        +-----------+-----------------+
| FastHttpFetcher (httpx +        |        | BrowserFetcher (Playwright) |
| Selectolax)                     |        | - headless Chromium         |
| - async HTTP/2 client           |        | - resource blocking         |
| - robots + rate aware           |        | - dynamic / blocked pages   |
+-------------+-------------------+        +-----------+-----------------+
              |                                         |
              +--------------------+--------------------+
                                   v
                         +---------+-------------------+
                         |        ResultStore         |
                         |  - stats.jsonl / errors    |
                         |  - optional HTML snapshots |
                         +--------------+-------------+
                                        |
                                        v
                             +----------+-----------+
                             | Metrics & Analytics  |
                             | - RunSummary         |
                             | - pandas/plots in    |
                             |   notebook           |
                             +----------------------+
```

### Data Schema (High-Level)

Logical entities (file-backed):

1. **UrlStats** – per URL and per stage (HTTP, optional browser).

   Stored as `stats.jsonl`, partitioned by shard:

   ```json
   {
     "run_id": "2025-11-15T10:00:00Z",
     "shard_id": 3,
     "url": "https://example.com",
     "domain": "example.com",
     "method": "httpx",              // "httpx" | "playwright"
     "stage": "primary",             // "primary" | "fallback"
     "status": "success",            // "success" | "captcha" | "robots" | "blocked" | "error"
     "http_status": 200,
     "error_code": null,             // "timeout" | "dns_error" | ...
     "latency_ms": 438,
     "content_len": 35219,
     "charset": "utf-8",
     "language_hint": "und",
     "captcha_detected": false,
     "robots_disallowed": false,
     "timestamp": "2025-11-15T10:00:00Z"
   }
   ```

2. **RunSummary** – single record per run.

   ```json
   {
     "run_id": "2025-11-15T10:00:00Z",
     "urls_total": 10000,
     "urls_success": 9325,
     "urls_failed": 675,
     "captcha_count": 420,
     "robots_disallowed_count": 50,
     "httpx_primary_count": 8400,
     "playwright_fallback_count": 1600,
     "p50_latency_httpx_ms": 320,
     "p90_latency_httpx_ms": 750,
     "p95_latency_httpx_ms": 1100,
     "p50_latency_playwright_ms": 2400,
     "p90_latency_playwright_ms": 7000,
     "p95_latency_playwright_ms": 12000,
     "started_at": "2025-11-15T09:00:00Z",
     "finished_at": "2025-11-15T10:40:00Z",
     "python_version": "3.11.9",
     "httpx_version": "x.y.z",
     "playwright_version": "x.y.z",
     "schema_version": "1.1.0"
   }
   ```

3. **ShardCheckpoint** – per shard, to allow resume.

   ```json
   {
     "run_id": "2025-11-15T10:00:00Z",
     "shard_id": 3,
     "urls_total": 1000,
     "urls_done": 640,
     "last_updated_at": "2025-11-15T10:15:00Z",
     "status": "in_progress"   // "pending" | "in_progress" | "completed" | "failed"
   }
   ```

4. **HTML snapshots** (optional for assignment):

   * If enabled:

     * Persist compressed HTML (`.html.gz`) in `data/raw/<run_id>/<shard_id>/<url_hash>.html.gz`.
     * Add `content_path` and `content_sha256` to a separate mapping file or to `UrlStats`.

### External Integrations

* `urls.csv` – ~10,000 target URLs.
* `proxy.json` – proxy credentials for provider (HTTP/HTTPS/SOCKS5).
* Remote websites (Google, Bing, real-estate sites, etc.).
* GitHub repo – code hosting and CI.
* Google Colab – reference execution environment.

---

## Discovery

No existing repo is assumed; this defines the target layout and integration boundaries for a greenfield project.

### Planned Repo Structure (10k-Aware)

```text
tavily-scraper/
  README.md
  architect.md
  pyproject.toml
  requirements.txt
  proxy.json.example
  urls.csv

  notebooks/
    tavily_assignment.ipynb

  tavily_scraper/
    __init__.py
    config.py             # RunConfig, ShardConfig, ProxyConfig
    models.py             # UrlJob, FetchResult, UrlStats, RunSummary, ShardCheckpoint
    robots.py             # RobotsClient + policy
    scheduling.py         # DomainScheduler + concurrency policies
    proxies.py            # ProxyManager
    http_fetcher.py       # FastHttpFetcher
    browser_fetcher.py    # BrowserFetcher (Playwright)
    strategy.py           # StrategyRouter, heuristics
    metrics.py            # aggregation, percentiles
    storage.py            # ResultStore, CheckpointStore
    logging_setup.py      # JSON logging
    run.py                # ScrapeRunner, ShardedBatchRunner
    cli.py                # optional CLI entry

  tests/
    conftest.py
    test_models.py
    test_config.py
    test_http_fetcher.py
    test_browser_fetcher.py
    test_strategy.py
    test_robots_and_sched.py
    test_storage_checkpoint.py
    test_e2e_small_batch.py

  backlog/
    open/
      01-bootstrap-repo.md
      02-config-and-models.md
      03-proxy-manager.md
      04-robots-and-scheduling.md
      05-http-fetcher.md
      06-browser-fetcher.md
      07-strategy-router.md
      08-storage-and-metrics.md
      09-notebook-and-viz.md
      10-hardening-and-docs.md
```

Boundaries:

* Notebook calls only into `tavily_scraper.run` and `metrics`.
* `scheduling.py` is the cross-cutting concern for **domain-aware concurrency** and **rate limiting**.
* `proxies.py` is the cross-cutting concern for HTTP and Playwright.
* Observability flows through `logging_setup` and `metrics`.

---

## MCDM for Major Choices

### Decision: Scraping Stack (HTTP client + parser + browser automation)

**Alternatives**

* A – `requests` + `BeautifulSoup` + `Selenium`.
* B – `httpx` + `Selectolax` + `Playwright` (proposed).
* C – `aiohttp` + `lxml` + `Playwright`.

**Context**

* `httpx` is a modern async HTTP client, supports HTTP/1.1 and HTTP/2, with a requests-like API and good performance for concurrent workloads.
* `Selectolax` is a fast HTML5 parser used in scraping pipelines, benchmarked as significantly faster than BeautifulSoup.
* Playwright is an actively maintained, multi-browser automation library widely used for testing and scraping.
* `requests-html` is archived/unmaintained and therefore avoided.

**Criteria & Weights** (1–9; higher = more important):

* PerfGain (w=9)
* SecRisk (w=8) – higher score = lower risk.
* DevTime (w=7)
* Maintainability (w=8)
* Cost (w=6)
* Scalability (w=8) – up to 10k and beyond.
* DX (w=7)

**Decision Matrix (Raw Scores 1–9)**

| Alternative | PerfGain | SecRisk | DevTime | Maintainability | Cost | Scalability | DX | Notes                                                         |
| ----------- | -------- | ------- | ------- | --------------- | ---- | ----------- | -- | ------------------------------------------------------------- |
| A           | 4        | 6       | 5       | 5               | 6    | 4           | 6  | Sync HTTP, slower Selenium, more brittle on modern JS apps.   |
| B           | 9        | 8       | 8       | 8               | 7    | 8           | 8  | Async HTTP/2, fast parser, modern browser tooling, good docs. |
| C           | 8        | 8       | 6       | 7               | 7    | 8           | 7  | Solid, but `aiohttp` ergonomics less friendly for assignment. |

Using TOPSIS-style ranking on weighted, normalized scores:

* B – Modern hybrid: closest to ideal.
* C – Async classic: second.
* A – Legacy: distant third.

**Recommendation**

* Use **B: `httpx` + `Selectolax` + `Playwright`**.
* Rollback: if Playwright is unavailable in the eval environment, swap `browser_fetcher` to Selenium 4, keeping `FetchResult`/`UrlStats` contracts unchanged.

---

## Key Decisions (ADR-Style)

### [ADR-001] Hybrid HTTP + Browser Strategy

* **Decision**: Two-stage pipeline:

  1. `FastHttpFetcher` for all URLs.
  2. `BrowserFetcher` fallback only when needed.
* **Why**: For 10k URLs, browser-only is too slow/costly; HTTP-only misses dynamic content.
* **Impact**:

  * StrategyRouter + metrics are first-class.
  * Every UrlStats row carries `method`/`stage` for analysis.

### [ADR-002] Package + Notebook Split

* **Decision**: Core logic in `tavily_scraper` package; notebook is orchestration and reporting.
* **Why**: Testability, CI, reuse, and clean separation between code and demo.
* **Impact**:

  * All behavior available via `run_batch` / CLI.
  * Notebook is thin, safe to re-run.

### [ADR-003] Sharded Batch Runner for 10k URLs

* **Decision**: Shard input into chunks (~500–1,000 URLs) and process shard-by-shard with checkpoints.
* **Why**: 10k URLs is large enough to:

  * need failure isolation per shard,
  * avoid memory bloat,
  * reduce re-work on rerun (resume from shard boundary).
* **Impact**:

  * Introduces `ShardedBatchRunner` and `CheckpointStore`.
  * Allows Colab runs to resume from mid-run shard if the kernel restarts.

### [ADR-004] Domain-Aware Scheduling

* **Decision**: Introduce `DomainScheduler` to enforce per-domain concurrency and politeness, especially for big sites (e.g., Google/Bing).
* **Why**: 10k URLs may contain many URLs from a few domains; naive global concurrency risks blocks and CAPTCHAs.
* **Impact**:

  * Config adds per-domain concurrency caps and delay ranges.
  * Scheduling is a separate module so heuristics are easy to adjust and tune.

### [ADR-005] Robots & CAPTCHA Policy

* **Decision**:

  * Always consult robots.txt when reachable.
  * Respect disallow rules by default.
  * Detect CAPTCHAs / hard bot walls and record them instead of bypassing.
* **Why**: Compliance, and explicitly required by the assignment.
* **Impact**:

  * `robots.py` and `is_captcha_page` are mandatory.
  * UrlStats reflects `status="robots"` or `"captcha"` distinctly.

### [ADR-006] File-Based Persistence Only

* **Decision**: Use JSONL/Parquet files for stats + optional HTML; no DB.
* **Why**: Simpler and sufficient for 10k; friendly to Colab and reviewers.
* **Impact**:

  * `storage.py` abstracts persistence; can be swapped to DB later if needed.

---

## Components

### Config & Models (`config.py`, `models.py`)

**Responsibilities**

* Describe all run-time configuration:

  * `RunConfig`: paths, concurrency, timeouts, feature toggles, shard size, browser limits, SLO thresholds.
  * `ShardConfig`: shard size, shard id ranges.
  * `ProxyConfig`: HTTP/HTTPS/SOCKS5 settings from `proxy.json`.
* Models:

  * `UrlJob`, `FetchResult`, `UrlStats`, `RunSummary`, `ShardCheckpoint`.
  * `RunnerContext`: shared holders for config, proxies, robots client, scheduler, logger.

**Key Interfaces**

* `RunConfig.from_env_and_args() -> RunConfig`
* `ProxyConfig.from_file(path: Path) -> ProxyConfig`
* `def make_shards(urls: list[str], shard_size: int) -> list[list[UrlJob]]`

---

### RobotsClient & DomainScheduler (`robots.py`, `scheduling.py`)

**Responsibilities**

* `RobotsClient`:

  * Fetch and cache robots.txt by domain.
  * `can_fetch(url, user_agent) -> bool`.
  * Simple backoff if robots requests frequently fail.

* `DomainScheduler`:

  * Domain-aware concurrency:

    * Global HTTP concurrency (e.g., 32).
    * Per-domain caps (e.g., 1–2 for Google/Bing).
  * Optional random jitter between requests per domain.
  * Optional dynamic tuning:

    * if domain-level error/captcha rate spikes, automatically lower concurrency for that domain.

**Key Interfaces**

* `class RobotsClient:`

  * `async def can_fetch(self, url: str, user_agent: str) -> bool`

* `class DomainScheduler:`

  * `async def acquire(self, domain: str) -> None`  (blocks with async sleep/semaphore)
  * `def release(self, domain: str) -> None`

---

### ProxyManager (`proxies.py`)

**Responsibilities**

* Parse `proxy.json` into a typed structure.
* Provide ready-to-use configs for:

  * `httpx.AsyncClient` (`proxies` dict).
  * Playwright (`proxy` dict for `launch()` or context).
* Centralize proxy rotation or stickiness strategy (simple round-robin / single rotating gateway).

**Key Interfaces**

* `class ProxyManager:`

  * `@classmethod def from_file(cls, path: Path) -> "ProxyManager"`
  * `def httpx_proxies(self) -> dict[str, str]`
  * `def playwright_proxy(self) -> dict[str, str] | None`

---

### FastHttpFetcher (`http_fetcher.py`)

**Responsibilities**

* Async HTTP GET using `httpx.AsyncClient` with:

  * HTTP/2 enabled when supported.
  * Timeouts, redirect handling, retry with backoff.
  * Proxy injection, User-Agent rotation, Accept-Language rotation.
* Optional content-type filter (only HTML / text are parsed).
* Parse HTML with Selectolax and produce `FetchResult`.

**Key Interfaces**

```python
async def fetch_http(job: UrlJob, ctx: RunnerContext) -> FetchResult
```

Behavior:

* Check robots via `RobotsClient` before issuing request.
* Acquire domain slot via `DomainScheduler`.
* Map common exception types to `error_code` (`timeout`, `dns_error`, `connection_reset`, etc.).
* Record `started_at`, `finished_at`, `latency_ms`, and `content_len`.
* Do not store full HTML in `UrlStats`; keep it in memory or optional snapshot only.

---

### BrowserFetcher (`browser_fetcher.py`)

**Responsibilities**

* Use Playwright (Chromium) headless to retrieve dynamic pages:

  * Proxy config from `ProxyManager`.
  * Resource blocking (images, fonts, CSS, media) by default.
  * Realistic UA, viewport, locale.

* Provide async wrapper:

  * Use `async_playwright` and a small pool of browser contexts or pages.

**Key Interfaces**

```python
async def fetch_dynamic(job: UrlJob, ctx: RunnerContext) -> FetchResult
```

Implementation notes:

* `page.goto(url, timeout=15_000, wait_until="networkidle")`.
* Optional `page.wait_for_selector("body", timeout=5_000)` or configured selector.
* Request interception to abort heavy static assets (images/fonts/media/CSS).
* Periodic browser restart (e.g., every 50–100 pages) to avoid memory leaks.
* Sequential by default, with optional small degree of parallelism (1–4 pages).

---

### StrategyRouter (`strategy.py`)

**Responsibilities**

* Drive the hybrid logic per URL:

  1. Check robots; if disallowed, emit `status="robots"`.
  2. Call `fetch_http`.
  3. Classify result:

     * complete vs incomplete vs blocked vs robots vs captcha.
  4. If `needs_browser` → call `fetch_dynamic`.
* Log decisions and reasons for metrics.

**Key Interfaces**

```python
def needs_browser(result: FetchResult) -> bool
def is_captcha_page(content: str | None) -> bool

async def run_for_url(job: UrlJob, ctx: RunnerContext, store: ResultStore) -> list[UrlStats]
```

Heuristics for `needs_browser` (configurable):

* `http_status` not in {200, 304}.
* `content_len` below configurable threshold.
* Body matches JS-required placeholder patterns.
* `captcha_detected` true.
* Domain is on an always-browser list (e.g. known SPA domains).
* For partially extracted data: if required fields missing according to a simple completeness check.

---

### Storage & Checkpoints (`storage.py`)

**Responsibilities**

* Append `UrlStats` rows to `stats.jsonl` (partitioned per shard).
* Append error-only rows to `errors.jsonl`.
* Manage `ShardCheckpoint` files.

**Key Interfaces**

```python
class ResultStore:
    def write_stats_row(self, row: UrlStats) -> None
    def write_error_row(self, row: UrlStats) -> None
    def close(self) -> None

class CheckpointStore:
    def load(self, run_id: str) -> list[ShardCheckpoint]
    def update(self, checkpoint: ShardCheckpoint) -> None
```

Details:

* Use line-delimited JSON for streaming writes.
* Flush buffers periodically (e.g., every N URLs) to be resilient to crashes.
* Ensure idempotency for shard-level reruns (checkpoint semantics).

---

### Metrics & Logging (`metrics.py`, `logging_setup.py`)

**Responsibilities**

* Structured JSON logging (one format across all modules).
* Aggregate UrlStats into RunSummary.
* Utility for percentiles, group-by domain/method/status.

**Key Interfaces**

```python
def compute_run_summary(stats: list[UrlStats]) -> RunSummary
def percentiles(values: list[float], ps: list[int]) -> dict[int, float]
```

---

### ScrapeRunner & ShardedBatchRunner (`run.py`)

**Responsibilities**

* `ScrapeRunner`:

  * Load a shard of URLs into UrlJobs.
  * Set up RunnerContext.
  * Use asyncio with bounded concurrency to run StrategyRouter for each URL.

* `ShardedBatchRunner`:

  * Split 10k URLs into shards (e.g., 10×1,000 or 20×500).
  * Track checkpoints per shard; resume incomplete shards.
  * Aggregate shard-level metrics into a global RunSummary.

**Key Interfaces**

```python
async def run_batch(config: RunConfig) -> RunSummary

async def run_sharded(config: RunConfig) -> RunSummary
```

---

### CLI & Notebook (`cli.py`, `notebooks/tavily_assignment.ipynb`)

**Responsibilities**

* CLI:

  * Optional: `python -m tavily_scraper.cli --config config.yaml`.
  * Expose flags for concurrency, timeouts, paths, and feature toggles (snapshots on/off).

* Notebook:

  * Install dependencies.
  * Load `urls.csv`, `proxy.json`.
  * Call `run_sharded`.
  * Load `stats.jsonl` into pandas and plot:

    * Latency histograms.
    * Success/failure by domain/status.
    * HTTP vs Playwright usage and fallback rate.
  * Include flowchart matching the Architecture Overview.
  * Summarize SLOs vs actual results in a compact table.

---

## API Contracts

These are internal Python APIs, not external HTTP endpoints.

### Core Types (Sketch)

```python
class UrlJob(TypedDict):
    url: str
    domain: str
    shard_id: int
    priority: int

class FetchResult(TypedDict):
    url: str
    domain: str
    method: Literal["httpx", "playwright"]
    stage: Literal["primary", "fallback"]
    status: Literal["success", "captcha", "robots", "blocked", "error"]
    http_status: int | None
    error_code: str | None
    latency_ms: int
    content: str | None
    content_len: int
    charset: str | None
    language_hint: str | None
    captcha_detected: bool
    robots_disallowed: bool
    started_at: str
    finished_at: str

class UrlStats(TypedDict):
    run_id: str
    shard_id: int
    url: str
    domain: str
    method: Literal["httpx", "playwright"]
    stage: Literal["primary", "fallback"]
    status: Literal["success", "captcha", "robots", "blocked", "error"]
    http_status: int | None
    error_code: str | None
    latency_ms: int
    content_len: int
    charset: str | None
    language_hint: str | None
    captcha_detected: bool
    robots_disallowed: bool
    timestamp: str

class RunSummary(TypedDict):
    run_id: str
    urls_total: int
    urls_success: int
    urls_failed: int
    captcha_count: int
    robots_disallowed_count: int
    httpx_primary_count: int
    playwright_fallback_count: int
    p50_latency_httpx_ms: int
    p90_latency_httpx_ms: int
    p95_latency_httpx_ms: int
    p50_latency_playwright_ms: int
    p90_latency_playwright_ms: int
    p95_latency_playwright_ms: int
    started_at: str
    finished_at: str
    python_version: str
    httpx_version: str
    playwright_version: str
    schema_version: str
```

### Main Functions

* `async run_sharded(config: RunConfig) -> RunSummary`
* `async run_batch(config: RunConfig) -> RunSummary` (for a single shard).
* `async fetch_http(job: UrlJob, ctx: RunnerContext) -> FetchResult`
* `async fetch_dynamic(job: UrlJob, ctx: RunnerContext) -> FetchResult`
* `def needs_browser(result: FetchResult) -> bool`
* `def is_captcha_page(content: str | None) -> bool`

**Versioning & Compatibility**

* `schema_version` increments on breaking changes.
* Readers should ignore unknown fields when loading UrlStats; new fields are additive and optional.

---

## Data Model

### Logical Models & Indexing

1. **UrlJob**

   * Key: `url`.
   * Derived fields: `domain`, `shard_id`.
   * Used only in memory.

2. **UrlStats**

   * Partitioning: `run_id`, `shard_id`.
   * Main analysis axes: `domain`, `method`, `status`.
   * Typical pandas indexes:

     * `(run_id, domain)`
     * `(run_id, status)`
     * `(run_id, method, stage)`

3. **RunSummary**

   * One per run.
   * Acts as header for run reports.

4. **ShardCheckpoint**

   * One per shard per run.
   * Allows restart from shard boundary.

### Migration Policies

* Additive schema evolution:

  * New fields added as nullable.
  * Old parsers must ignore unknown keys.
* If Parquet is used:

  * New nullable columns for new fields.
* Breaking removals or type changes:

  * Require `schema_version` bump and clear changelog note.

---

## Quality & Operations

### Testing Strategy

**Unit**

* `test_models.py`: ensure models serialize/deserialize and default correctly.
* `test_config.py`: env/CLI parsing and validation.
* `test_strategy.py`: `needs_browser` and `is_captcha_page` over representative HTML snippets.
* `test_robots_and_sched.py`:

  * robots allow/deny.
  * per-domain scheduling respecting concurrency caps and jitter.
* `test_http_fetcher.py`:

  * success, timeouts, retries via mocked httpx.
  * content-type filtering, error_code mapping.
* `test_browser_fetcher.py`:

  * minimal dynamic test page confirming HTML after JS is captured.

**Integration**

* Static flow:

  * Known static URL (e.g., example.com or similar) → HTTP path only.
* Dynamic flow:

  * Known JS-only page → HTTP incomplete, Playwright completes.
* Proxy integration:

  * Use simple endpoint to confirm proxies are applied in both HTTP and browser.

**End-to-End**

* `test_e2e_small_batch.py`:

  * Small mixed set (static, dynamic, invalid URL).
  * Assert:

    * `RunSummary.urls_total` matches.
    * No unhandled exceptions.
    * UrlStats written and parsable.

**Perf / Scale (sanity)**

* Run 200–500 URLs in test mode:

  * Assert run completes within reasonable budget for test env.
  * Capture approximate P95 latencies.

**Security**

* Tests asserting:

  * Proxy credentials do not appear in logs.
  * Robots-disallowed URLs are not actually fetched (only classified).

---

### Observability

**Logging**

* Use `logging` with JSON formatter.
* Context fields in every log:

  * `run_id`, `shard_id`, `url`, `domain`, `stage`, `method` (if known).
* Key events:

  * `run_started`, `run_finished`.
  * `shard_started`, `shard_completed`, `shard_resumed`.
  * `robots_disallow`, `captcha_detected`, `fallback_to_browser`.
  * `http_error`, `browser_error`.

**Metrics**

* `RunSummary` is the main machine-readable metric artifact.
* Notebook builds:

  * Latency histograms by method.
  * Success/failure breakdown by status.
  * Domain-level aggregation:

    * top domains by URL count.
    * per-domain success rate & CAPTCHA rate.
    * per-domain browser fallback share.

**Manual Alerts (Notebook)**

* Highlight in notebook if:

  * Overall success rate (excluding robots/captcha) < 90%.
  * Playwright P95 latency > configured max (e.g., 12–15s).
  * CAPTCHA/blocked share > threshold (e.g., 30% globally or per hot domain).

---

### Security

**AuthN/AuthZ**

* Not applicable (no external REST API).
* Batch job runs with developer privileges in Colab / local.

**Secrets Management**

* `proxy.json`:

  * `proxy.json.example` in repo; real file in `.gitignore`.
  * Load via `ProxyManager.from_file`, never echo raw content to logs.
* CI:

  * Proxies and any other secrets stored as CI secrets, not committed.

**Dependencies**

* Versions pinned in `requirements.txt`.
* Periodic local scans:

  * `pip-audit` and/or `safety check`.

**Network Fingerprinting**

* Acknowledge that HTTP clients have distinct TLS fingerprints; `httpx` may be more bot-like than a browser.
* For tough domains, Playwright traffic (real browser stack) is preferred and will naturally look closer to real users.
* No advanced JA3 spoofing implemented; could be a future ADR if needed.

**Content & PII**

* UrlStats only store metadata, not full HTML.
* HTML snapshots (if any) go to dedicated directory and are not logged.
* Avoid spilling full HTML or extracted PII into logs.

---

### CI/CD

* CI via GitHub Actions:

  ```yaml
  jobs:
    test:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with:
            python-version: "3.11"
        - name: Install deps
          run: |
            pip install -r requirements.txt
            playwright install --with-deps
        - name: Lint
          run: ruff check .
        - name: Type-check
          run: mypy tavily_scraper
        - name: Test
          run: pytest -q
  ```

* No automatic deployment; main execution environments are:

  * Local (CLI).
  * Colab notebook (with `!pip install -r requirements.txt`).

* Optional future: Dockerfile for fully reproducible container.

---

## Domain Doctrine & Grounding

* **Robots & ToS**

  * Fetch robots.txt once per domain when reachable.
  * Default policy: if robots explicitly disallows target path → do not scrape; record `status="robots"`.
  * If robots unreachable: configurable; default to allow but log.

* **CAPTCHA & Anti-bot**

  * Detect and classify CAPTCHA / JS challenge / block pages.

  * Never:

    * call external solver services,
    * use unofficial stealth patches beyond standard Playwright options.

  * If both HTTP and browser hit a hard wall:

    * mark `status="captcha"` or `"blocked"`; do not retry infinitely.

* **Scraping Doctrine**

  * Prefer structural selectors (CSS/XPath) over language-specific text heuristics.
  * Use HTTP path by default; escalate to browser only when required for accuracy.
  * Multilingual:

    * Do not assume language; rely on DOM.
    * Treat text as UTF-8; keep locale parsing out of scraping layer.

* **Provenance & Reproducibility**

  * For each run, persist:

    * `RunSummary` with library versions and `schema_version`.
    * Optional: current git commit hash (if available).

  * Enables exact reproduction of metrics and behavior.

---

## Affected Modules/Files

**Files to create**

* `pyproject.toml` / `requirements.txt` – dependency and tooling config.
* `tavily_scraper/` modules listed in the repo structure.
* `tests/` suite.
* `notebooks/tavily_assignment.ipynb`.
* `backlog/open/*.md` tickets.

**Files to modify**

* `README.md` – quickstart, SLOs, architecture summary.
* `architect.md` – this document (living ADR summary as project evolves).

---

## Implementation Steps

1. **Bootstrap & Tooling**

   * Create repo, `pyproject.toml` / `requirements.txt` with:

     * `httpx`, `selectolax`, `playwright`, `pydantic` or `msgspec`, `pandas`, `matplotlib`, `python-dotenv`, `pytest`, `pytest-asyncio`, `ruff`, `mypy`.

   * Add `.gitignore` (`proxy.json`, HTML dumps, `__pycache__`, `.ipynb_checkpoints`).

   * Add basic CI workflow with lint + empty tests.

2. **Config & Models**

   * Implement `RunConfig`, `ProxyConfig`, `ShardConfig`, `RunnerContext`.
   * Implement `UrlJob`, `FetchResult`, `UrlStats`, `RunSummary`, `ShardCheckpoint`.
   * Add validation for:

     * concurrency ranges,
     * timeouts,
     * shard size,
     * URLs file existence.

3. **ProxyManager**

   * Implement `ProxyManager.from_file('proxy.json')`.
   * Expose `httpx_proxies()` and `playwright_proxy()`.
   * Add minimal tests for invalid/missing fields.

4. **RobotsClient & DomainScheduler**

   * Implement `RobotsClient` based on `urllib.robotparser` or lightweight alternative.

   * Implement `DomainScheduler` with:

     * global semaphore for HTTP concurrency (e.g., 32).
     * per-domain semaphores for hot domains (e.g., Google/Bing), configurable.
     * optional jitter between requests to same domain.

   * Tests for:

     * allow/deny semantics.
     * concurrency caps per domain.

5. **FastHttpFetcher**

   * Implement `fetch_http(job, ctx)`:

     * Respect robots via `RobotsClient` before calling httpx.

     * Acquire domain slot via `DomainScheduler`.

     * Use shared `httpx.AsyncClient` with:

       * `timeout` ≈ 10s,
       * `follow_redirects=True`,
       * proxies from `ProxyManager`.

     * Rotate headers (UA, Accept-Language).

     * On errors:

       * classify `error_code`,
       * retry up to N times (e.g., 2) with exponential backoff for transient errors.

     * Detect non-HTML content; skip parsing but still record metrics.

     * Detect CAPTCHA / block patterns at HTML level.

6. **BrowserFetcher**

   * Implement `fetch_dynamic(job, ctx)`:

     * Use Playwright, with:

       * `headless=True`,
       * proxies from `ProxyManager`,
       * blocked resource types (images, fonts, media, CSS).

     * Implement safe closing and optional browser recycling (e.g., restart after N pages).

     * Time navigation and capture HTML.

   * Start with sequential Playwright calls; add small parallelism if needed and safe for Colab.

7. **StrategyRouter**

   * Implement `is_captcha_page` and `needs_browser`.

   * Implement `run_for_url` to:

     * respect robots before network calls,
     * call HTTP first,
     * branch to browser if needed,
     * transform FetchResult(s) to UrlStats and push to ResultStore.

   * Cover heuristics via unit tests.

8. **Storage & Checkpoints**

   * Implement `ResultStore` for JSONL writes with buffering.
   * Implement `CheckpointStore` for shard progress.
   * Ensure idempotent shard-level writes (leverage checkpoints to avoid double-processing).

9. **ScrapeRunner & ShardedBatchRunner**

   * Implement `run_batch(config)`:

     * Load subset of URLs for a shard.
     * Build UrlJobs with domain + shard_id.
     * Run StrategyRouter with bounded concurrency via `asyncio.Semaphore`.
     * Collect UrlStats and flush to ResultStore periodically.
     * Return RunSummary for the shard.

   * Implement `run_sharded(config)`:

     * Create shards from 10k URLs.
     * For each shard:

       * check checkpoint; skip if completed.
       * run `run_batch`.
       * merge shard summaries into global RunSummary.

10. **Notebook**

    * Build `tavily_assignment.ipynb`:

      * Install deps.
      * Mount `urls.csv`, `proxy.json`.
      * Run `run_sharded`.
      * Load `stats.jsonl` into pandas.
      * Plot required metrics; output flowchart diagram (Mermaid or ASCII).
      * Summarize SLOs vs actual metrics.

11. **Tests & CI**

    * Implement tests described in Testing Strategy.
    * Wire `pytest`, `ruff`, `mypy` into CI workflow.
    * Ensure Playwright browsers installed in CI.

12. **Tuning & Hardening**

    * Run on a pilot subset (e.g., 200–500 URLs).

    * Adjust:

      * global and per-domain concurrency,
      * timeouts,
      * browser asset blocking,
      * thresholds for `needs_browser`.

    * Validate against SLOs; update guardrails if needed.

13. **Final Polish**

    * Fill README with:

      * quickstart,
      * architecture diagram,
      * SLOs,
      * known limitations and future improvements.

    * Prepare one-pager content for PDF:

      * approach, trade-offs, key metrics, limitations, next steps.

---

## Backlog (Tickets)

Each ticket in `backlog/open/<nn>-<kebab>.md`:

* Title
* Objective
* Definition of Done
* Steps
* Affected files
* Tests
* Risks
* Dependencies

Example tickets:

1. `01-bootstrap-repo.md`

   * Objective: repo scaffolding, tooling, CI skeleton.

2. `02-config-and-models.md`

   * Objective: implement RunConfig, models, validation.

3. `03-proxy-manager.md`

   * Objective: parse `proxy.json`, integrate with httpx/Playwright.

4. `04-robots-and-scheduling.md`

   * Objective: robots + DomainScheduler with tests.

5. `05-http-fetcher.md`

   * Objective: HTTP pipeline with retries and metrics.

6. `06-browser-fetcher.md`

   * Objective: Playwright integration with resource blocking.

7. `07-strategy-router.md`

   * Objective: fallback heuristics, captcha detection, per-URL orchestration.

8. `08-storage-and-metrics.md`

   * Objective: JSONL persistence, RunSummary computation.

9. `09-notebook-and-viz.md`

   * Objective: Colab notebook with plots and flowchart.

10. `10-hardening-and-docs.md`

    * Objective: tune concurrency, finalize SLOs, README, one-pager support text.

---

## Interfaces & Contracts (Quick Reference)

* `RunConfig.from_env_and_args() -> RunConfig`
* `ProxyManager.from_file(path: Path) -> ProxyManager`
* `RobotsClient.can_fetch(url: str, user_agent: str) -> Awaitable[bool]`
* `DomainScheduler.acquire(domain: str) -> Awaitable[None]`
* `DomainScheduler.release(domain: str) -> None`
* `fetch_http(job: UrlJob, ctx: RunnerContext) -> Awaitable[FetchResult]`
* `fetch_dynamic(job: UrlJob, ctx: RunnerContext) -> Awaitable[FetchResult]`
* `needs_browser(result: FetchResult) -> bool`
* `is_captcha_page(content: str | None) -> bool`
* `ResultStore.write_stats_row(row: UrlStats) -> None`
* `CheckpointStore.update(checkpoint: ShardCheckpoint) -> None`
* `compute_run_summary(stats: list[UrlStats]) -> RunSummary`
* `run_batch(config: RunConfig) -> Awaitable[RunSummary]`
* `run_sharded(config: RunConfig) -> Awaitable[RunSummary]`

Compatibility: functions should allow additional optional fields in models without breaking callers; error codes should be documented and stable.

---

## Stop Rules & Preconditions

### Preconditions (Go / No-Go)

* `urls.csv` present, readable, and contains up to ~10,000 valid URL strings.
* `proxy.json` present (or explicit opt-out flag) and loadable.
* Dependencies installed; Playwright browsers installed (`playwright install`).
* Colab / local environment has enough RAM and CPU for headless Chromium.

### Stop / Escalation Conditions

* **Security / Compliance**

  * If robots.txt clearly disallows scraping of a domain’s paths:

    * Skip those URLs.
    * If many targets are disallowed, clearly call out in notebook and one-pager.

* **Operational**

  * If global CAPTCHA/blocked rate exceeds threshold (e.g., >40% of URLs):

    * Stop run early, log diagnostic summary (domains, error types).

  * If global error rate (excluding robots/captcha) exceeds 30% in an early shard:

    * Automatically reduce concurrency and retry one shard; if still high, halt run.

  * If runtime exceeds 2× configured max runtime:

    * Abort remaining shards and emit partial RunSummary with flag.

  * Optionally: if a single domain shows very high block/CAPTCHA rate, reduce its per-domain concurrency to 1 and/or skip remaining URLs from that domain, and log this decision.

---

## SLOs & Guardrails

### SLOs (for ~10,000 URLs)

On a reference Colab-like machine:

* **Success rate (excluding robots/captcha)**: ≥ 90%.

* **HTTP path latency**:

  * P95 ≤ 1.5s per URL.

* **Playwright path latency**:

  * P95 ≤ 12–15s per URL.

* **Fallback share (browser usage)**:

  * ≤ 40% of URLs require Playwright.

* **Total runtime**:

  * 10k URLs complete in ≤ 2 hours under default settings.

### Guardrails

* **Concurrency**

  * HTTP concurrency: default 32; configurable clamped to [8, 64].
  * Playwright pages: default 2; clamped to [1, 4].
  * Per-domain concurrency:

    * defaults like `{"google.com": 1, "bing.com": 1}`; others inherit global.

* **Timeouts**

  * HTTP: default 10s; clamped to [5, 30].
  * Playwright: default 15s; clamped to [10, 45].

* **Retries**

  * HTTP transient errors: ≤ 2 retries with exponential backoff.
  * Playwright: at most 1 retry for transient navigation failure.

* **Resource Limits**

  * Browser:

    * block images/fonts/media/CSS by default.
    * optional `max_content_mb` per page (e.g., 2–5MB) to avoid huge pages.

  * Periodic browser restart (e.g., every 50–100 pages) to avoid memory leaks.

* **Logging & Noise**

  * No full HTML in logs.
  * Per-URL logs are single-line JSON entries; notebook aggregates.

