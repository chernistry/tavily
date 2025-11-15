Read .sdd/CODING_RULES.md first

# P0_07 – Router, CAPTCHA detection, and hybrid strategy

## Objective

Implement the hybrid HTTP-first, browser-fallback strategy and CAPTCHA detection logic. The router decides, per URL, whether HTTP alone is sufficient or Playwright is required, and emits exactly one `UrlStats` record.

## Dependencies

- Depends on:
  - `P0_03_core_models_and_stats_schema.md`
  - `P0_04_scheduler_and_robots.md`
  - `P0_05_proxies_and_fast_http_fetcher.md`
  - `P0_06_browser_fetcher_playwright.md`

## Scope

- Implement `utils.captcha.is_captcha_page`.
- Implement router helpers `needs_browser` and `route_and_fetch`.
- Decide how invalid URLs and robots-blocked URLs are represented in `UrlStats`.

## Implementation Steps

1. **Implement `is_captcha_page`**

   In `tavily_scraper/utils/captcha.py`:

   ```python
   from __future__ import annotations


   CAPTCHA_KEYWORDS = (
       "captcha",
       "i am not a robot",
       "are you a robot",
       "recaptcha",
       "hcaptcha",
   )


   def is_captcha_page(html: str | None) -> bool:
       if not html:
           return False
       lower = html.lower()
       return any(keyword in lower for keyword in CAPTCHA_KEYWORDS)
   ```

2. **Implement `needs_browser`**

   In `tavily_scraper/pipelines/router.py`, add:

   ```python
   from tavily_scraper.core.models import FetchResult
   from tavily_scraper.utils.captcha import is_captcha_page


   def needs_browser(http_result: FetchResult) -> bool:
       # Already failed at HTTP level
       status = http_result.get("status")
       if status in {"captcha_detected", "http_error", "timeout"}:
           return True
       if http_result.get("robots_disallowed"):
           return False

       # Small content is suspicious
       if http_result.get("content_len", 0) < 1024:
           return True

       html = http_result.get("content")
       if is_captcha_page(html):
           return True

       # Additional heuristics can be added over time
       return False
   ```

3. **Handle invalid URLs**

   - Decide: invalid URLs should not reach network code.
   - Provide helper in `router.py` or `utils/io.py`:

     ```python
     from tavily_scraper.config.constants import Status
     from tavily_scraper.core.models import UrlJob, UrlStats
     from tavily_scraper.core.models import fetch_result_to_url_stats, make_initial_fetch_result


     def invalid_url_stats(job: UrlJob) -> UrlStats:
         result = make_initial_fetch_result(job, method="httpx", stage="primary")
         result["status"] = "invalid_url"
         result["http_status"] = None
         return fetch_result_to_url_stats(result)
     ```

4. **Implement `route_and_fetch`**

   In `tavily_scraper/pipelines/router.py`, implement:

   ```python
   import asyncio
   from contextlib import asynccontextmanager
   from typing import AsyncIterator

   from playwright.async_api import Browser

   from tavily_scraper.config.proxies import ProxyManager
   from tavily_scraper.core.models import FetchResult, RunnerContext, UrlJob, UrlStats, fetch_result_to_url_stats
   from tavily_scraper.pipelines.browser_fetcher import browser_lifecycle, fetch_one as browser_fetch_one
   from tavily_scraper.pipelines.fast_http_fetcher import fetch_one as http_fetch_one
   from tavily_scraper.utils.captcha import is_captcha_page
   from tavily_scraper.utils.logging import get_logger


   logger = get_logger(__name__)


   async def route_and_fetch(
       job: UrlJob,
       ctx: RunnerContext,
       browser: Browser | None = None,
   ) -> UrlStats:
       try:
           http_result = await http_fetch_one(job, ctx)
       except Exception as exc:  # narrow down in implementation
           # Per-URL isolation: never crash the shard
           logger.exception("http_fetch_unhandled_error")
           result = make_initial_fetch_result(job, method="httpx", stage="primary")
           result["status"] = "other_error"
           result["error_kind"] = type(exc).__name__
           result["error_message"] = str(exc)
           return fetch_result_to_url_stats(result)

       if not needs_browser(http_result):
           return fetch_result_to_url_stats(http_result)

       # Robots / invalid URL cases should not reach here, but guard anyway
       if http_result.get("robots_disallowed"):
           return fetch_result_to_url_stats(http_result)

       # Browser fallback
       if browser is None:
           # Fallback to creating a temporary browser; preferred path is to reuse
           logger.info("router_creating_temporary_browser")
           async with browser_lifecycle(ctx.run_config, ctx.proxy_manager) as tmp_browser:
               browser_result = await browser_fetch_one(job, ctx, tmp_browser)
       else:
           browser_result = await browser_fetch_one(job, ctx, browser)

       return fetch_result_to_url_stats(browser_result)
   ```

   - Ensure all exceptions are caught and converted into `UrlStats` to maintain per-URL isolation.

5. **Plan browser lifecycle ownership**

   - The preferred pattern is for shard/batch runner to own the browser lifecycle and pass the `Browser` instance into `route_and_fetch`.
   - The optional `browser is None` path exists mainly for convenience and should not be used in the main path once runners are implemented.

## Example Usage

```python
import asyncio

from tavily_scraper.config.env import load_run_config
from tavily_scraper.core.models import RunnerContext
from tavily_scraper.pipelines.router import route_and_fetch
from tavily_scraper.pipelines.browser_fetcher import browser_lifecycle
from tavily_scraper.utils.io import make_url_jobs


async def run_single() -> None:
    config = load_run_config()
    jobs = make_url_jobs(["https://example.com"])
    job = jobs[0]

    # Construct RunnerContext as per previous tickets
    ctx = ...

    async with browser_lifecycle(config, ctx.proxy_manager) as browser:
        stats = await route_and_fetch(job, ctx, browser)
        print(stats)


asyncio.run(run_single())
```

## Acceptance Criteria

- `is_captcha_page` correctly identifies typical CAPTCHA pages (based on fixtures) and returns `False` for normal HTML.
- `needs_browser`:

  - Returns `True` for:
    - HTTP timeouts and errors.
    - Very small HTML bodies.
    - CAPTCHA pages.
  - Returns `False` for large, successful HTML pages with no CAPTCHA markers.

- `invalid_url_stats` (or equivalent helper) can produce a valid `UrlStats` row for invalid URLs without performing network calls.
- `route_and_fetch`:

  - Uses HTTP-first, then browser fallback when `needs_browser` is `True`.
  - Returns exactly one `UrlStats` per input `UrlJob`.
  - Does not allow exceptions to escape; all errors are translated into `UrlStats` with appropriate `Status` and `error_kind`.

- Unit tests cover:

  - CAPTCHA detection.
  - Router decisions for:
    - Static-only page (HTTP-only).
    - Dynamic-only page (HTTP-incomplete, then browser).
    - Robots-blocked URL (no network).
    - Invalid URL (no network, `status="invalid_url"`).

- All new code passes `ruff check .` and `mypy --strict`.

