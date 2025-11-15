Read .sdd/CODING_RULES.md first

# P0_06 – Playwright-based browser fetcher

## Objective

Implement the Playwright-based browser fallback path (`BrowserFetcher`) to retrieve JS-rendered content, with asset blocking, proxy support, and safe resource management. This is Stage 2 of the hybrid pipeline.

## Dependencies

- Depends on:
  - `P0_01_repo_bootstrap_structure.md`
  - `P0_02_config_env_and_input_loading.md`
  - `P0_03_core_models_and_stats_schema.md`
  - `P0_05_proxies_and_fast_http_fetcher.md`

## Scope

- Implement a reusable Playwright browser manager.
- Implement `browser_fetcher.fetch_one` that returns `FetchResult`.
- Integrate proxies and (optionally) `DomainScheduler`.

## Implementation Steps

1. **Design browser manager**

   In `tavily_scraper/pipelines/browser_fetcher.py`, implement an async context manager or helper class:

   ```python
   from __future__ import annotations

   from contextlib import asynccontextmanager
   from typing import AsyncIterator

   from playwright.async_api import Browser, async_playwright

   from tavily_scraper.config.proxies import ProxyManager
   from tavily_scraper.core.models import RunConfig


   @asynccontextmanager
   async def browser_lifecycle(
       run_config: RunConfig,
       proxy_manager: ProxyManager | None,
   ) -> AsyncIterator[Browser]:
       proxy = proxy_manager.playwright_proxy() if proxy_manager is not None else None
       async with async_playwright() as p:
           browser = await p.chromium.launch(
               headless=run_config.playwright_headless,
               proxy=proxy,
           )
           try:
               yield browser
           finally:
               await browser.close()
   ```

2. **Implement asset blocking**

   - When creating pages, intercept requests and block heavy resources:

     ```python
     from playwright.async_api import BrowserContext, Page


     async def create_page_with_blocking(browser: Browser) -> Page:
         context = await browser.new_context()

         async def _route_handler(route, request) -> None:  # type: ignore[no-untyped-def]
             url = request.url
             if any(url.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".woff", ".woff2")):
                 await route.abort()
                 return
             await route.continue_()

         await context.route("**/*", _route_handler)
         return await context.new_page()
     ```

   - Ensure `context` is closed after use to avoid leaks.

3. **Implement `fetch_one` browser path**

   In `browser_fetcher.py`, implement:

   ```python
   from time import perf_counter
   from urllib.parse import urlparse

   from tavily_scraper.core.models import FetchResult, UrlJob, make_initial_fetch_result, RunnerContext
   from tavily_scraper.utils.captcha import is_captcha_page
   from tavily_scraper.utils.logging import get_logger


   logger = get_logger(__name__)


   async def fetch_one(job: UrlJob, ctx: RunnerContext, browser: Browser) -> FetchResult:
       result = make_initial_fetch_result(job, method="playwright", stage="fallback")

       url = str(job["url"])
       parsed = urlparse(url)
       domain = parsed.netloc
       result["domain"] = domain

       # Optional: check robots again, even though router should enforce it already.
       can_fetch = await ctx.robots_client.can_fetch(url, user_agent=None)
       if not can_fetch:
           result["status"] = "robots_blocked"
           result["robots_disallowed"] = True
           return result

       page = await create_page_with_blocking(browser)
       start = perf_counter()
       try:
           await page.goto(url, wait_until="networkidle", timeout=15_000)
           html = await page.content()
       except Exception as exc:  # narrow down to Playwright errors in implementation
           elapsed_ms = int((perf_counter() - start) * 1000)
           result["latency_ms"] = elapsed_ms
           result["status"] = "http_error"
           result["error_kind"] = type(exc).__name__
           result["error_message"] = str(exc)
           ctx.scheduler.record_error(domain)
           return result
       finally:
           await page.context.close()

       elapsed_ms = int((perf_counter() - start) * 1000)
       result["latency_ms"] = elapsed_ms
       result["status"] = "success"
       result["content"] = html
       result["content_len"] = len(html.encode("utf-8"))
       result["encoding"] = "utf-8"

       if is_captcha_page(html):
           result["status"] = "captcha_detected"
           result["captcha_detected"] = True
           ctx.scheduler.record_captcha(domain)

       return result
   ```

   - Keep browser parallelism limited (will be enforced at the sharding/batch level by `RunnerContext` and concurrency settings).

4. **Integrate with `RunnerContext`**

   - Extend `RunnerContext` from P0_05 to optionally hold a browser or browser manager if appropriate; alternatively, pass the browser explicitly to `fetch_one` as shown.
   - Ensure the batch/shard runner manages the browser lifecycle:

     ```python
     async with browser_lifecycle(config, proxy_manager) as browser:
         # pass `browser` into browser_fetcher.fetch_one(...)
     ```

5. **Retry behavior**

   - For browser failures (navigation timeout, network error), optionally:

     - Retry once with a fresh page/context.
     - If it fails again, classify as `"http_error"` or `"other_error"`, not success.

6. **Privacy and logging**

   - Never log HTML content.
   - Never log proxy username/password.
   - Log high-level events: `browser_error`, `captcha_detected`, `fallback_to_browser`.

## Example Usage

```python
import asyncio

from tavily_scraper.config.env import load_run_config
from tavily_scraper.config.proxies import ProxyManager
from tavily_scraper.core.models import RunnerContext
from tavily_scraper.core.robots import make_robots_client
from tavily_scraper.core.scheduler import DomainScheduler
from tavily_scraper.pipelines.browser_fetcher import browser_lifecycle, fetch_one
from tavily_scraper.utils.io import make_url_jobs


async def main() -> None:
    config = load_run_config()
    jobs = make_url_jobs(["https://example.com/js-only"])

    proxy_manager = None  # load via env if needed
    scheduler = DomainScheduler(global_limit=config.playwright_max_concurrency)
    robots_client = await make_robots_client(config, None)

    # http_client is still required in RunnerContext but unused here
    ctx = RunnerContext(
        run_config=config,
        proxy_manager=proxy_manager,
        scheduler=scheduler,
        robots_client=robots_client,
        http_client=None,  # type: ignore[arg-type]
    )

    async with browser_lifecycle(config, proxy_manager) as browser:
        result = await fetch_one(jobs[0], ctx, browser)
        print(result)


asyncio.run(main())
```

## Acceptance Criteria

- Browser manager:

  - Can create and close a Playwright Chromium browser with or without proxies.
  - Implements asset blocking for images and fonts at minimum.

- `browser_fetcher.fetch_one`:

  - Uses the provided `Browser` instance.
  - Respects robots.txt (even if second check).
  - Returns a `FetchResult` with:

    - `method="playwright"`, `stage="fallback"`.
    - `latency_ms`, `content_len`, and `encoding` populated.
    - `status` properly set to `"success"`, `"captcha_detected"`, or error statuses on failure.

- CAPTCHAs:

  - When `is_captcha_page(html)` returns `True`, `status="captcha_detected"` and `captcha_detected=True` are set.

- Unit or integration tests:

  - A minimal dynamic page (fixture or public test URL) shows different content only with browser path.
  - Error conditions (e.g. navigation timeout) are mapped to appropriate `status` and `error_kind`.

- All new code passes `ruff check .` and `mypy --strict`.

