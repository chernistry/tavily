Read .sdd/CODING_RULES.md first

# P0_05 – Proxy manager and fast HTTP fetcher

## Objective

Implement `ProxyManager` plus the HTTP-first scraping path using `httpx` and Selectolax, including proxy integration, header rotation, error mapping, and completeness heuristics. This forms the fast path for most URLs.

## Dependencies

- Depends on:
  - `P0_01_repo_bootstrap_structure.md`
  - `P0_02_config_env_and_input_loading.md`
  - `P0_03_core_models_and_stats_schema.md`
  - `P0_04_scheduler_and_robots.md`

## Scope

- Implement `ProxyManager` that adapts `ProxyConfig` for httpx and Playwright.
- Implement `fast_http_fetcher.fetch_one` with robots and scheduler integration.
- Implement basic parsing and HTTP-stage completeness heuristics.

## Implementation Steps

1. **Implement `ProxyManager`**

   In a new module `tavily_scraper/config/proxies.py` (or `tavily_scraper/utils/proxies.py`), implement:

   ```python
   from __future__ import annotations

   from dataclasses import dataclass

   from tavily_scraper.core.models import ProxyConfig


   @dataclass
   class ProxyManager:
       config: ProxyConfig

       @classmethod
       def from_proxy_config(cls, config: ProxyConfig) -> "ProxyManager":
           return cls(config=config)

       def httpx_proxies(self) -> dict[str, str]:
           host = self.config.host
           http_url = f"http://{host}:{self.config.http_port}"
           https_url = f"http://{host}:{self.config.https_port}"
           return {"http://": http_url, "https://": https_url}

       def playwright_proxy(self) -> dict[str, str] | None:
           host = self.config.host
           return {
               "server": f"http://{host}:{self.config.https_port}",
               "username": self.config.username or "",
               "password": self.config.password or "",
           }
   ```

   - Do not log credentials anywhere.

2. **Design a `RunnerContext` skeleton**

   In `tavily_scraper/core/models.py`, define:

   ```python
   from dataclasses import dataclass
   from typing import Optional

   import httpx

   from tavily_scraper.config.proxies import ProxyManager
   from tavily_scraper.core.robots import RobotsClient
   from tavily_scraper.core.scheduler import DomainScheduler


   @dataclass
   class RunnerContext:
       run_config: RunConfig
       proxy_manager: Optional[ProxyManager]
       scheduler: DomainScheduler
       robots_client: RobotsClient
       http_client: httpx.AsyncClient
   ```

   - Further fields (result store, logger, browser objects) will be added in later tickets.

3. **Implement HTTP client factory**

   In `tavily_scraper/pipelines/fast_http_fetcher.py`, add a helper to construct a shared `AsyncClient`:

   ```python
   from __future__ import annotations

   import httpx

   from tavily_scraper.config.proxies import ProxyManager
   from tavily_scraper.core.models import RunConfig


   def make_http_client(run_config: RunConfig, proxy_manager: ProxyManager | None) -> httpx.AsyncClient:
       proxies = proxy_manager.httpx_proxies() if proxy_manager is not None else None
       timeout = httpx.Timeout(run_config.httpx_timeout_seconds)
       limits = httpx.Limits(max_connections=run_config.httpx_max_concurrency * 2)
       return httpx.AsyncClient(
           http2=True,
           follow_redirects=True,
           timeout=timeout,
           limits=limits,
           proxies=proxies,
       )
   ```

4. **Implement header rotation**

   Add a small helper in `fast_http_fetcher.py`:

   ```python
   import random


   USER_AGENTS = [
       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
       "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
       "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
   ]

   ACCEPT_LANGUAGES = ["en-US,en;q=0.9", "en-GB,en;q=0.9"]


   def build_headers() -> dict[str, str]:
       return {
           "User-Agent": random.choice(USER_AGENTS),
           "Accept-Language": random.choice(ACCEPT_LANGUAGES),
       }
   ```

5. **Implement `fetch_one` HTTP path**

   In `fast_http_fetcher.py`, implement:

   ```python
   from time import perf_counter
   from urllib.parse import urlparse

   from selectolax.parser import HTMLParser

   from tavily_scraper.core.models import FetchResult, UrlJob, make_initial_fetch_result
   from tavily_scraper.utils.logging import get_logger


   logger = get_logger(__name__)


   async def fetch_one(job: UrlJob, ctx: RunnerContext) -> FetchResult:
       result = make_initial_fetch_result(job, method="httpx", stage="primary")

       url = str(job["url"])
       parsed = urlparse(url)
       domain = parsed.netloc
       result["domain"] = domain

       # Robots check
       can_fetch = await ctx.robots_client.can_fetch(url, user_agent=USER_AGENTS[0])
       if not can_fetch:
           result["status"] = "robots_blocked"
           result["robots_disallowed"] = True
           return result

       await ctx.scheduler.acquire(domain)
       start = perf_counter()
       try:
           resp = await ctx.http_client.get(url, headers=build_headers())
       except httpx.TimeoutException as exc:
           elapsed_ms = int((perf_counter() - start) * 1000)
           result["latency_ms"] = elapsed_ms
           result["status"] = "timeout"
           result["error_kind"] = "Timeout"
           result["error_message"] = str(exc)
           ctx.scheduler.record_error(domain)
           return result
       except httpx.HTTPError as exc:
           elapsed_ms = int((perf_counter() - start) * 1000)
           result["latency_ms"] = elapsed_ms
           result["status"] = "http_error"
           result["error_kind"] = type(exc).__name__
           result["error_message"] = str(exc)
           ctx.scheduler.record_error(domain)
           return result
       finally:
           ctx.scheduler.release(domain)

       elapsed_ms = int((perf_counter() - start) * 1000)
       result["latency_ms"] = elapsed_ms
       result["http_status"] = resp.status_code
       result["status"] = "success" if 200 <= resp.status_code < 400 else "http_error"

       content_type = resp.headers.get("Content-Type", "")
       body = resp.text
       result["content_len"] = len(body.encode(resp.encoding or "utf-8", errors="ignore"))
       result["encoding"] = resp.encoding

       if "text/html" in content_type or "application/xhtml+xml" in content_type:
           parser = HTMLParser(body)
           result["content"] = body
           # Additional extraction hooks can be added later
       else:
           result["content"] = None

       return result
   ```

   - Add retry logic with exponential backoff for transient errors (using a small helper and `asyncio.sleep`).

6. **Implement basic HTTP completeness heuristics**

   - In `fast_http_fetcher.py` or `router.py` (depending on design), add a helper:

     ```python
     def looks_incomplete_http(result: FetchResult) -> bool:
         if result.get("status") != "success":
             return True
         if result.get("content_len", 0) < 1024:
             return True
         html = result.get("content") or ""
         lower = html.lower()
         if "enable javascript" in lower or "please turn on javascript" in lower:
             return True
         return False
     ```

   - This will be used by the router in P0_07 to decide whether to escalate to Playwright.

7. **Ensure privacy in logging**

   - When logging URLs, strip query strings or truncate them.
   - Never log proxy credentials.
   - Do not log full HTML content.

## Example Usage

```python
import asyncio

from tavily_scraper.config.env import load_run_config, load_proxy_config_from_json
from tavily_scraper.config.proxies import ProxyManager
from tavily_scraper.core.models import RunnerContext
from tavily_scraper.core.robots import make_robots_client
from tavily_scraper.core.scheduler import DomainScheduler
from tavily_scraper.pipelines.fast_http_fetcher import make_http_client, fetch_one
from tavily_scraper.utils.io import make_url_jobs


async def main() -> None:
    config = load_run_config()
    jobs = make_url_jobs(["https://example.com"])

    proxy_config = None
    proxy_manager = None
    if config.proxy_config_path:
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

    result = await fetch_one(jobs[0], ctx)
    print(result)


asyncio.run(main())
```

## Acceptance Criteria

- `ProxyManager` can:

  - Convert `ProxyConfig` into httpx proxies and a Playwright proxy dict.
  - Be instantiated via `from_proxy_config`.

- `RunnerContext` is defined and includes `RunConfig`, `ProxyManager | None`, `DomainScheduler`, `RobotsClient`, and a shared `httpx.AsyncClient`.
- `make_http_client` creates a client with:

  - HTTP/2 enabled.
  - Timeouts and connection limits derived from `RunConfig`.
  - Proxies applied when `ProxyManager` is configured.

- `fast_http_fetcher.fetch_one`:

  - Checks robots.txt via `RobotsClient` before fetching.
  - Uses `DomainScheduler` for concurrency and records errors.
  - Sets `FetchResult` fields correctly (status, http_status, latency_ms, content_len, encoding).
  - Does not persist HTML to `UrlStats` but may keep it in `FetchResult.content`.

- A basic completeness helper (`looks_incomplete_http`) exists and is used later by the router.
- Unit tests cover:

  - Proxy dict generation from a sanitized `ProxyConfig`.
  - HTTP success path with a mocked `httpx` response.
  - Timeout and error paths with correct `Status` and `error_kind`.
  - Basic completeness heuristic behavior.

