Read /Users/sasha/IdeaProjects/personal_projects/tavily/.sdd/CODING_RULES.md first

# P0_04 – Domain scheduler and robots client

## Objective

Implement `DomainScheduler` and `RobotsClient` to provide domain-aware concurrency control and robots.txt compliance across the scraping pipeline. These components enforce politeness and help reduce CAPTCHA/blocked responses.

## Dependencies

- Depends on:
  - `P0_01_repo_bootstrap_structure.md`
  - `P0_02_config_env_and_input_loading.md`
  - `P0_03_core_models_and_stats_schema.md`

## Scope

- `DomainScheduler` for global + per-domain concurrency and jitter.
- `RobotsClient` for fetching and caching robots.txt.
- Basic integration with config and logging utilities.

## Implementation Steps

1. **Design `DomainScheduler`**

   In `tavily_scraper/core/scheduler.py`, implement:

   ```python
   from __future__ import annotations

   import asyncio
   from collections import defaultdict
   from collections.abc import Mapping
   from typing import Final


   class DomainScheduler:
       def __init__(
           self,
           global_limit: int,
           per_domain_limits: Mapping[str, int] | None = None,
       ) -> None:
           self._global_semaphore = asyncio.Semaphore(global_limit)
           self._per_domain_limits = dict(per_domain_limits or {})
           self._domain_semaphores: dict[str, asyncio.Semaphore] = {}
           self._error_counts: dict[str, int] = defaultdict(int)
           self._captcha_counts: dict[str, int] = defaultdict(int)
           self._min_limit: Final[int] = 1
           self._max_limit: Final[int] = max(1, global_limit)

       async def acquire(self, domain: str) -> None:
           await self._global_semaphore.acquire()
           sem = self._domain_semaphores.setdefault(
               domain,
               asyncio.Semaphore(self._per_domain_limits.get(domain, 4)),
           )
           await sem.acquire()

       def release(self, domain: str) -> None:
           self._global_semaphore.release()
           sem = self._domain_semaphores.get(domain)
           if sem is not None:
               sem.release()

       def record_error(self, domain: str) -> None:
           self._error_counts[domain] += 1
           self._maybe_reduce_limit(domain)

       def record_captcha(self, domain: str) -> None:
           self._captcha_counts[domain] += 1
           self._maybe_reduce_limit(domain)

       def _maybe_reduce_limit(self, domain: str) -> None:
           # Example policy: after N errors, cap domain to 1
           if self._error_counts[domain] + self._captcha_counts[domain] < 5:
               return
           if domain not in self._domain_semaphores:
               return
           sem = self._domain_semaphores[domain]
           # Implementation note: reducing an existing semaphore's limit safely
           # may require a more elaborate mechanism; implement a simple approach first.
   ```

   - The exact adaptive policy can be simple, but it should be visible and testable.

2. **Enable optional jitter**

   - Optionally add a small sleep/jitter between requests per domain to reduce burstiness:

     ```python
     import random

     class DomainScheduler:
         def __init__(..., jitter_range: tuple[float, float] | None = None) -> None:
             ...
             self._jitter_range = jitter_range

         async def acquire(self, domain: str) -> None:
             await self._global_semaphore.acquire()
             sem = self._domain_semaphores.setdefault(...)
             await sem.acquire()
             if self._jitter_range:
                 low, high = self._jitter_range
                 await asyncio.sleep(random.uniform(low, high))
     ```

3. **Implement `RobotsClient`**

   In `tavily_scraper/core/robots.py`, implement an async client using `httpx.AsyncClient`:

   ```python
   from __future__ import annotations

   import asyncio
   from typing import Final
   from urllib.parse import urlparse
   from urllib.robotparser import RobotFileParser

   import httpx

   from tavily_scraper.utils.logging import get_logger


   class RobotsClient:
       def __init__(self, client: httpx.AsyncClient, user_agent: str = "TavilyScraper") -> None:
           self._client = client
           self._parsers: dict[str, RobotFileParser] = {}
           self._lock = asyncio.Lock()
           self._user_agent: Final[str] = user_agent
           self._logger = get_logger(__name__)

       async def can_fetch(self, url: str, user_agent: str | None = None) -> bool:
           ua = user_agent or self._user_agent
           parsed = urlparse(url)
           domain = parsed.netloc
           async with self._lock:
               parser = self._parsers.get(domain)
               if parser is None:
                   parser = await self._fetch_and_parse(domain, parsed.scheme)
                   self._parsers[domain] = parser
           try:
               return parser.can_fetch(ua, url)
           except Exception:
               # Be permissive but log; failing robots.txt lookup should not block scraping.
               self._logger.warning("robots_check_failed", extra={"domain": domain})
               return True

       async def _fetch_and_parse(self, domain: str, scheme: str) -> RobotFileParser:
           robots_url = f"{scheme}://{domain}/robots.txt"
           parser = RobotFileParser()
           try:
               resp = await self._client.get(robots_url, timeout=5.0)
           except httpx.HTTPError:
               parser.set_url(robots_url)
               parser.parse("")  # treat as empty robots (allow all)
               return parser
           if resp.status_code >= 400:
               parser.set_url(robots_url)
               parser.parse("")
               return parser
           parser.parse(resp.text.splitlines())
           return parser
   ```

4. **Provide factory to wire config and proxies**

   Still in `robots.py`, add:

   ```python
   from pathlib import Path

   from tavily_scraper.core.models import ProxyConfig, RunConfig


   async def make_robots_client(
       run_config: RunConfig,
       proxy_config: ProxyConfig | None,
   ) -> RobotsClient:
       proxies: dict[str, str] | None = None
       if proxy_config is not None:
           host = proxy_config.host
           proxies = {
               "http://": f"http://{host}:{proxy_config.http_port}",
               "https://": f"http://{host}:{proxy_config.https_port}",
           }
       client = httpx.AsyncClient(follow_redirects=True, proxies=proxies)
       return RobotsClient(client=client)
   ```

5. **Integrate with `RunConfig`**

   - Ensure that `RunConfig` has enough information to construct a `DomainScheduler` (global limit, default per-domain caps) and pass them from the batch/shard runner in later tickets.
   - For now, simply use `httpx_max_concurrency` as the global limit and a hard-coded per-domain limit dictionary for sensitive domains (e.g., `{"www.google.com": 1, "www.bing.com": 1}`).

## Example Usage

```python
from tavily_scraper.core.scheduler import DomainScheduler
from tavily_scraper.core.robots import make_robots_client
from tavily_scraper.config.env import load_run_config, load_proxy_config_from_json


config = load_run_config()
proxy_config = None
if config.proxy_config_path:
    proxy_config = load_proxy_config_from_json(config.proxy_config_path)

scheduler = DomainScheduler(global_limit=config.httpx_max_concurrency)
robots_client = asyncio.run(make_robots_client(config, proxy_config))
```

## Acceptance Criteria

- `DomainScheduler`:

  - Supports configurable global and per-domain concurrency limits.
  - Exposes `async acquire(domain: str)` and `release(domain: str)` methods.
  - Optionally supports configurable jitter between requests.
  - Provides `record_error` / `record_captcha` hooks that can down-tune domain limits when repeated errors/CAPTCHAs are observed.

- `RobotsClient`:

  - Fetches and caches robots.txt per domain using `httpx.AsyncClient`.
  - Exposes `async can_fetch(url: str, user_agent: str | None = None) -> bool`.
  - Uses proxies when configured.
  - Treats unreachable robots.txt as “allow all” but logs a warning.

- Unit tests cover:

  - Domain-level concurrency caps (e.g. domain A limited to 1 concurrent request).
  - Simple adaptation behavior when errors/CAPTCHAs are recorded.
  - robots.txt allow and disallow using mocked HTTP responses, including error status codes.

- All new code passes `ruff check .` and `mypy --strict tavily_scraper/`.

