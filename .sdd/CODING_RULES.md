## Coding Rules & Project Conventions

*Tavily Web Research Engineer Scraper (2025)*

---

## 1. Language & Style

### Versions

* **Python**: `3.11` (minimum; target and CI default).
* **HTTP client**: `httpx` (0.2x) — async, HTTP/2, good timeouts/proxies.
* **Browser automation**: `playwright` for Python — Chromium as default engine.
* **Typing / validation**: `msgspec` (preferred) or `pydantic-core` for fast schema checks.

### Style, Linters, Formatters

* Single source of truth: **Ruff** (lint + format).
* Black optional; if both are enabled, Ruff format should match Black’s line length.

`pyproject.toml`:

```toml
[tool.black]
line-length = 88
target-version = ["py311"]

[tool.ruff]
line-length = 88
target-version = "py311"
fix = true
unsafe-fixes = false
src = ["tavily_scraper", "tests"]
select = ["E", "F", "I", "B", "UP", "C90"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["tavily_scraper"]
combine-as-imports = true
```

Commands:

```bash
ruff check .        # lint
ruff format .       # format
# optional:
# black .
```

### Naming, Structure, Typing

* **Naming**

  * Packages/modules: `snake_case` (e.g. `fast_http_fetcher.py`).
  * Functions: verbs (`fetch_url`, `run_shard`, `compute_summary`).
  * Data models: `PascalCase` (`UrlStats`, `RunSummary`, `RunConfig`).
  * Constants: `UPPER_SNAKE` (`DEFAULT_HTTP_TIMEOUT`).

* **Typing**

  * All public functions, methods, and models **must be fully typed**.
  * Use:

    * `TypedDict` / `msgspec.Struct` for JSON-like records (`UrlStats`, `RunSummary`).
    * `Literal[...]` for finite enums (`method`, `status`).
    * `NewType` for domain types where helpful (`UrlStr`, `DomainStr`).
  * `mypy` runs in CI with **`--strict`** on `tavily_scraper/`.

---

## 2. Framework & Project Layout

### Directory Layout

```text
tavily_scraper/
  __init__.py

  config/
    __init__.py
    env.py                 # env + .env loading → RunConfig/ProxyConfig
    constants.py           # defaults, status enums

  core/
    models.py              # UrlStats, RunSummary, RunConfig, ShardConfig
    errors.py              # ScraperError, error enums
    scheduler.py           # DomainScheduler, concurrency limits
    robots.py              # RobotsClient, robots cache

  pipelines/
    fast_http_fetcher.py   # HTTPX-based fetch + parse
    browser_fetcher.py     # Playwright-based fetch for JS-heavy
    router.py              # StrategyRouter: HTTP-only vs HTTP→browser
    shard_runner.py        # run_shard; per-shard orchestration
    batch_runner.py        # run_all; sharded, resumable

  utils/
    parsing.py             # HTML parsing helpers (Selectolax)
    captcha.py             # CAPTCHA / block-page detection
    metrics.py             # p50/p95 computation, aggregates → RunSummary
    logging.py             # structlog setup
    io.py                  # JSONL read/write, stats file helpers
    timing.py              # timing utilities

  notebooks/
    tavily_assignment.ipynb  # Colab entry: load config, run, visualize

  tests/
    test_fast_http_fetcher.py
    test_browser_fetcher.py
    test_router.py
    test_scheduler.py
    test_metrics.py
    test_captcha.py

  pyproject.toml
  requirements.txt
  README.md
  CODING_RULES.md
  .env.example
  .gitignore
```

### Notebook Rules

* `notebooks/tavily_assignment.ipynb` is **orchestration only**:

  * Install deps (if needed).
  * Load input URLs and env config.
  * Call `batch_runner.run_all(...)`.
  * Load `stats.jsonl` and `run_summary.json` for plots.
  * No core logic; no scraping implementation in notebook.

---

## 3. Configuration & Environment

### `.env` / Environment Variables

* No secrets in code. Use `.env` locally, GitHub Secrets in CI.

`.env.example`:

```env
TAVILY_ENV=local         # local / ci / colab
PROXY_HOST=proxy.example.com
PROXY_PORT=12345
PROXY_USER=your_user
PROXY_PASS=your_pass

HTTPX_TIMEOUT_SECONDS=10
HTTPX_MAX_CONCURRENCY=32

PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_MAX_CONCURRENCY=2

SHARD_SIZE=500
```

### `env.py` Rules

* Single function `load_run_config()` returns a fully-typed `RunConfig`.
* `TAVILY_ENV=ci`:

  * Missing critical envs (proxy auth, etc.) → raise at startup.
* No direct `os.getenv` calls in business logic; everything goes through `RunConfig`.

---

## 4. API & Internal Contracts

We treat the “API” as the Python contracts + stats files.

### Input

* Canonical input:

  * `data/urls.txt` — one URL per line.
* Optional hints file:

  * `data/url_hints.jsonl` — URL + flags (e.g. `is_dynamic_hint`, `domain_type`).

Loader converts to:

```python
UrlStr = NewType("UrlStr", str)

class UrlJob(TypedDict):
    url: UrlStr
    is_dynamic_hint: bool | None
    shard_id: int
    index_in_shard: int
```

* Use `yarl.URL` or `msgspec` validation to reject invalid URLs before running.
* Invalid URLs → recorded as `status="invalid_url"` without network activity.

### Per-URL Stats

```python
Method = Literal["httpx", "playwright"]
Stage = Literal["primary", "fallback"]
Status = Literal[
    "success",
    "captcha_detected",
    "robots_blocked",
    "http_error",
    "timeout",
    "invalid_url",
    "too_large",
    "other_error",
]

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

    error_kind: str | None       # "Timeout", "ConnectError", ...
    error_message: str | None    # truncated; safe for logs

    timestamp: str               # ISO 8601 UTC
    shard_id: int
```

* Every URL attempted **must** produce exactly one `UrlStats` record.

### Run Summary

Produced by `metrics.compute_run_summary(stats: Iterable[UrlStats])`:

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

* Persisted as `data/run_summary.json`.
* Never break compatibility: only **add** fields; do not rename or remove.

---

## 5. Error Handling & Exceptions

### Core Exception Type

```python
class ScraperError(Exception):
    def __init__(self, kind: str, url: str, detail: str | None = None):
        self.kind = kind
        self.url = url
        self.detail = detail
        super().__init__(f"{kind} for {url}: {detail or ''}")
```

Guidelines:

* Pipeline code catches low-level exceptions (`httpx.TimeoutException`, Playwright errors, etc.), maps them to:

  * `Status`
  * `error_kind`
  * `error_message` (truncated)
* `ScraperError` is used for **configuration or programming errors**, not for expected network issues.

### Per-URL Isolation

* Any per-URL failure **must not** crash the shard runner or batch runner.
* Always wrap URL processing in a `try/except` and emit a `UrlStats` with a non-`success` status.

---

## 6. Testing

### Tooling

* `pytest`
* `pytest-asyncio`
* `pytest-httpx`
* Optional: a thin wrapper around Playwright for integration tests.

Command:

```bash
pytest --asyncio-mode=auto --cov=tavily_scraper --cov-report=term-missing
```

### Coverage Targets

* **≥90%** overall on `tavily_scraper/` (notebooks excluded).
* Core modules (`fast_http_fetcher`, `browser_fetcher`, `router`, `metrics`, `scheduler`) as close to 100% as practical.

### Required Test Types

1. **Unit tests**

   * `fast_http_fetcher`:

     * Correct headers, timeouts, error mapping.
   * `browser_fetcher`:

     * Route-blocking logic for assets.
     * Timeout / error mapping.
   * `router`:

     * HTTP-only vs fallback decisions (using synthetic `FetchResult` objects).
   * `captcha`:

     * Classification of typical CAPTCHA HTML vs normal pages.
   * `metrics`:

     * P50/P95, rates, and shares from synthetic data.

2. **Integration tests**

   * HTTPX:

     * Real call to `https://example.com` or test endpoint.
   * Router “happy path”:

     * HTTP-only static page fixture.
     * Fixture that simulates missing data → flagged as `needs_browser`.

3. **E2E mini-run**

   * Small batch (5–20 URLs or fixtures).
   * Run `batch_runner.run_all` with a tiny shard size.
   * Assert:

     * `UrlStats` count == input count.
     * `RunSummary` fields populated.
     * Plots notebook can load the stats without errors.

4. **Regression tests**

   * Failing cases (e.g. a CAPTCHA HTML snippet, a robots-blocked URL) captured as fixtures and locked in.

---

## 7. Security & Privacy

### Secrets

* All secrets from env:

  * `PROXY_USER`, `PROXY_PASS`, any API keys.
* `.env` never committed; only `.env.example` with fake values.

### Logging

* Never log:

  * Passwords, tokens, cookies.
  * Full HTML content.
* When logging URLs:

  * Strip query string or redact: `https://example.com/path?...` → `https://example.com/path`.

### HTML & Data

* Do not persist full HTML for all URLs in Git.
* If snapshots are needed:

  * Keep a **small** sample under `data/debug/` and add them to `.gitignore`.
* Stats and summary files:

  * UTF-8, JSONL/JSON only; no binary blobs.

### Dependencies & Audit

* Pin versions in `requirements.txt` with narrow ranges.
* CI job to run:

  ```bash
  pip-audit
  ```

  or similar, at least on demand.

---

## 8. Observability & Metrics

### Logging

* `structlog` with JSON output.

`logging.configure_logging()` must be called once at startup.

* Log:

  * Per-URL events at INFO level.
  * Aggregate run summary at INFO.
  * Errors at WARNING/ERROR.

### Metrics & Files

* Stats:

  * `data/stats.jsonl` — one `UrlStats` record per line.
* Summary:

  * `data/run_summary.json` — single `RunSummary`.

### Notebook Visualizations

At minimum:

* Histogram of `latency_ms` split by `method`.
* Bar chart of `status` counts.
* Box/violin plot of `content_len` for HTTPX vs Playwright.
* Table:

  * per-domain counts and failure/captcha/robots rates.

---

## 9. Performance & Cost

### Defaults (can be tuned)

* HTTPX:

  * `MAX_CONCURRENCY_HTTPX=32`
  * Timeout 10 s (request), 30 s (overall).
* Playwright:

  * `MAX_CONCURRENCY_PLAYWRIGHT=2`
  * `page.goto` timeout 15–20 s.

### Guardrails

* Max content size per URL:

  * 1 MB; larger → `status="too_large"` and no body processing.
* Max retries:

  * HTTPX transient errors: up to 2 retries.
  * Playwright: 1 retry in a fresh page/context.

### Target SLOs (guideline)

* Success rate (excluding `robots_blocked` + `captcha_detected`) ≥ 90%.
* HTTPX P95 latency ≤ 2.5 s.
* Playwright P95 latency ≤ 15 s.
* Fallback share (Playwright) ideally ≤ 40% of URLs.

---

## 10. Git & PR Process

### Branching

* `main` — stable, green CI only.
* Feature branches: `feat/...`, `fix/...`, `chore/...`, `docs/...`.

### Commit Messages

Use short, descriptive subjects, e.g.:

```text
feat(router): add dynamic-content fallback heuristic
fix(browser_fetcher): handle navigation timeouts correctly
chore(ci): enable mypy strict mode
docs(rules): add coding rules for tavily scraper
```

### PR Checklist

Before merging into `main`:

* [ ] `ruff check .` passes.
* [ ] `ruff format .` (or `black .`) applied.
* [ ] `mypy --strict tavily_scraper/` passes.
* [ ] `pytest --cov=tavily_scraper` passes.
* [ ] `tavily_assignment.ipynb` runs end-to-end on a small URL set.
* [ ] No secrets or large data files in diff.
* [ ] `CODING_RULES.md` still accurate (update if behavior changed).

---

## 11. Tooling & Automation

### pre-commit

`pre-commit` required locally:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.0
    hooks:
      - id: ruff
        args: ["--fix"]
      - id: ruff-format

  - repo: https://github.com/psf/black
    rev: 24.8.0
    hooks:
      - id: black
        args: ["--line-length=88"]
```

Install:

```bash
pre-commit install
```

### CI (GitHub Actions)

Minimal pipeline:

```yaml
jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Install Playwright browsers
        run: |
          python -m playwright install --with-deps chromium
      - name: Lint
        run: ruff check .
      - name: Type check
        run: mypy tavily_scraper/
      - name: Tests
        run: pytest --asyncio-mode=auto --cov=tavily_scraper --cov-report=term-missing
```

---

## 12. Backend / Pipeline Standards

Even though this is a library + notebook, treat main flows like mini-services.

* `fast_http_fetcher.fetch_one(...)`:

  * No side effects except logging.
  * Returns a small, typed `FetchResult` or raises `ScraperError` only on programmer misuse.
* `browser_fetcher.fetch_one(...)`:

  * Same contract as HTTP fetcher; side effects limited to browser state and logs.
* `router.route_and_fetch(...)`:

  * Encapsulates HTTP-first / browser-fallback logic.
* `shard_runner.run_shard(...)`:

  * Idempotent with respect to `UrlJob` list + config; multiple runs produce consistent stats.

---

## 13. Design Decisions (ADR-style)

For major changes (e.g., swapping HTTP client, changing fallback logic):

* Create `docs/decisions/ADR-00X-short-title.md`:

  * Context
  * Options
  * Decision
  * Consequences
* Link ADRs from `README.md` or `CODING_RULES.md` when relevant.

---

## 14. Acceptance Criteria (for the assignment)

A solution is “done” when:

* [ ] Repo installs cleanly: `pip install -r requirements.txt` on fresh Python 3.11.
* [ ] `tavily_assignment.ipynb` runs start-to-finish in Colab with:

  * [ ] HTTPX-only mode works.
  * [ ] HTTPX+Playwright hybrid mode works.
* [ ] Outputs:

  * [ ] `data/stats.jsonl` with one row per URL.
  * [ ] `data/run_summary.json` with aggregate metrics.
  * [ ] Plots in the notebook based on these files.
* [ ] All coding rules in this document are satisfied or explicitly documented as exceptions.

---

## 15. File Hygiene

* Do not commit:

  * `__pycache__/`, `.ipynb_checkpoints/`, `.DS_Store`.
  * `data/*.html`, `data/*.raw`, large binary artifacts.
* Any single module >400 LOC should be considered for refactoring.
* Shared mutable global state is forbidden:

  * Use explicit parameters, `RunConfig`, or small dataclasses instead.

---

This document should live as `CODING_RULES.md` in the repository and govern all code written for the Tavily Web Research Engineer scraper project.
