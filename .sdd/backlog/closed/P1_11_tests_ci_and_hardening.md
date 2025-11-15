Read /Users/sasha/IdeaProjects/personal_projects/tavily/.sdd/CODING_RULES.md first

# P1_11 – Tests, CI, and hardening

## Objective

Add comprehensive unit, integration, and E2E tests plus a minimal GitHub Actions CI pipeline, and harden the system as per `CODING_RULES.md` and `best_practices.md`.

## Dependencies

- Depends on:
  - All P0 tickets (P0_01 through P0_09).

## Scope

- Unit tests for core modules.
- Integration tests for HTTP and browser paths.
- E2E mini-run test for `run_all`.
- CI workflow with lint, type-check, and tests.
- Hardening (timeouts, logging hygiene).

## Implementation Steps

1. **Unit tests**

   Add or expand tests in `tests/`:

   - `test_fast_http_fetcher.py`:

     - Use `pytest-httpx` to mock responses for:

       - Successful HTML response (200).
       - Timeout (raise `httpx.TimeoutException`).
       - Connection error (raise a generic `httpx.HTTPError`).

     - Assert that:

       - `status`, `http_status`, `latency_ms`, `content_len`, and `error_kind` are set appropriately.
       - Robots-blocked URLs short-circuit to `status="robots_blocked"` and do not call HTTP.

   - `test_browser_fetcher.py`:

     - Use a minimal Playwright fixture or a local HTTP server to supply a JS-only page.
     - Assert that:

       - HTML returned by `browser_fetcher.fetch_one` contains dynamic content not present in the initial HTML.
       - CAPTCHAs are detected by `is_captcha_page` and status is set correctly.

   - `test_router.py`:

     - Use synthetic `FetchResult` objects to test `needs_browser`.
     - Mock HTTP and browser fetchers to ensure `route_and_fetch` chooses the correct path.

   - `test_scheduler.py`:

     - Use `asyncio` tasks to verify that `DomainScheduler` enforces per-domain and global concurrency caps.
     - Test adaptation when `record_error` / `record_captcha` is called.

   - `test_metrics.py`:

     - Provide synthetic `UrlStats` rows and assert `compute_run_summary` metrics (rates, shares, percentiles).

   - `test_captcha.py`:

     - Provide HTML snippets (normal vs CAPTCHA) and assert `is_captcha_page` behavior.

2. **Integration tests**

   - HTTP integration:

     - Use a known static URL (e.g., `https://example.com`) or a local HTTP server fixture.
     - Run `fast_http_fetcher.fetch_one` end-to-end (with real `httpx.AsyncClient`).
     - Ensure that `FetchResult` is correctly populated.

   - Browser integration:

     - Use a small test site or local HTML page that renders content only via JS.
     - Use `browser_lifecycle` + `browser_fetcher.fetch_one` to confirm final HTML contains expected content.

3. **E2E mini-run test**

   - In `tests/test_e2e_batch_runner.py`:

     - Use `pytest` and `pytest-asyncio`.
     - Configure environment variables to use a small set of URLs (could be local test server endpoints).
     - Run:

       ```python
       config = load_run_config()
       summary = asyncio.run(run_all(config))
       ```

     - Assert that:

       - `summary["total_urls"]` matches the number of input URLs.
       - `data/stats.jsonl` exists and has one line per URL.
       - `data/run_summary.json` exists and can be parsed as JSON.

4. **CI workflow**

   - Add `.github/workflows/ci.yml` with:

     ```yaml
     name: CI

     on:
       push:
       pull_request:

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
             run: python -m playwright install --with-deps chromium
           - name: Lint
             run: ruff check .
           - name: Type check
             run: mypy tavily_scraper/
           - name: Tests
             run: pytest --asyncio-mode=auto --cov=tavily_scraper --cov-report=term-missing
     ```

5. **Hardening**

   - Timeouts:

     - Ensure HTTP and browser timeouts are clamped to reasonable ranges (e.g., 5–20 seconds) using `RunConfig`.

   - Concurrency:

     - Validate `httpx_max_concurrency` and `playwright_max_concurrency` in `load_run_config()` and enforce maximum values to avoid overload in Colab.

   - Logging hygiene:

     - Double-check that no code logs:

       - Passwords, tokens, cookies.
       - Full HTML content.

     - Ensure URLs in logs are either truncated or have query strings removed.

   - Error handling:

     - Confirm that all per-URL processing is wrapped in try/except surfaces that emit `UrlStats` instead of letting exceptions crash the run.

## Acceptance Criteria

- Test coverage:

  - Unit tests for core modules (`fast_http_fetcher`, `browser_fetcher`, `router`, `metrics`, `scheduler`, `captcha`) achieve ≥90% coverage over `tavily_scraper/`.
  - Integration tests exercise real HTTP and Playwright flows (or well-structured local fixtures).
  - E2E test runs a tiny batch with `run_all` and verifies stats and summary artifacts.

- CI:

  - GitHub Actions workflow exists and:
    - Installs dependencies.
    - Installs Playwright browsers.
    - Runs Ruff, mypy, and pytest.

- Hardening:

  - Timeouts and concurrency limits are validated and clamped in configuration.
  - Logging never includes secrets or full HTML.
  - Failure of any single URL does not abort the batch; failures are visible only as non-`success` `UrlStats`.

- All tests pass locally with:

  - `pytest --asyncio-mode=auto --cov=tavily_scraper --cov-report=term-missing`

  and CI passes with no failing jobs.

