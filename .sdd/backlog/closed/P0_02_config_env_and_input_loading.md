Read .sdd/CODING_RULES.md first

# P0_02 – Config, environment, and input loading

## Objective

Implement robust configuration loading and input ingestion that transforms environment variables plus the provided `urls.csv` / `proxy.json` into strongly-typed `RunConfig`, `ProxyConfig`, and `UrlJob` objects. This is the foundational plumbing for all subsequent components.

## Dependencies

- Depends on:
  - `P0_01_repo_bootstrap_structure.md` (package and tooling skeleton).

## Scope

- Implement `RunConfig`, `ShardConfig`, `ProxyConfig`, `UrlJob`.
- Implement `load_run_config()` and proxy loading helpers.
- Implement URL file loaders supporting both TXT and CSV formats.

## Implementation Steps

1. **Define core configuration models**

   In `tavily_scraper/core/models.py`:

   - Use `msgspec.Struct` (preferred) or `dataclasses` for configuration types. Example:

     ```python
     from __future__ import annotations

     from pathlib import Path
     from typing import Literal

     import msgspec


     class RunConfig(msgspec.Struct, omit_defaults=True):
         env: Literal["local", "ci", "colab"] = "local"
         urls_path: Path
         data_dir: Path

         httpx_timeout_seconds: int = 10
         httpx_max_concurrency: int = 32

         playwright_headless: bool = True
         playwright_max_concurrency: int = 2

         shard_size: int = 500
         proxy_config_path: Path | None = None
     ```

   - Define `ShardConfig`:

     ```python
     class ShardConfig(msgspec.Struct, omit_defaults=True):
         shard_size: int = 500
     ```

2. **Define `ProxyConfig`**

   Still in `core/models.py`, add:

   ```python
   class ProxyConfig(msgspec.Struct, omit_defaults=True):
       host: str
       http_port: int
       https_port: int
       socks5_port: int
       username: str | None = None
       password: str | None = None
   ```

   This should be compatible with the structure in `.sdd/raw/proxy.json`:

   ```json
   {
     "proxy": {
       "username": "...",
       "password": "...",
       "hostname": "network.joinmassive.com:65535",
       "port": {
         "http": 65534,
         "https": 65535,
         "socks5": 65533
       }
     }
   }
   ```

3. **Define URL-related models**

   In `core/models.py`, define:

   ```python
   from typing import NewType, TypedDict


   UrlStr = NewType("UrlStr", str)


   class UrlJob(TypedDict):
       url: UrlStr
       is_dynamic_hint: bool | None
       shard_id: int
       index_in_shard: int
   ```

   - `is_dynamic_hint` is optional and can later be filled from heuristics or a hints file.

4. **Create configuration constants**

   In `tavily_scraper/config/constants.py`, add default values and type aliases that other modules can reuse:

   ```python
   from __future__ import annotations

   from typing import Literal


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


   DEFAULT_HTTPX_TIMEOUT_SECONDS = 10
   DEFAULT_HTTPX_MAX_CONCURRENCY = 32
   DEFAULT_PLAYWRIGHT_MAX_CONCURRENCY = 2
   DEFAULT_SHARD_SIZE = 500
   ```

5. **Implement environment loading**

   In `tavily_scraper/config/env.py`, implement:

   ```python
   from __future__ import annotations

   import os
   from pathlib import Path

   from tavily_scraper.core.models import RunConfig
   from tavily_scraper.config.constants import (
       DEFAULT_HTTPX_MAX_CONCURRENCY,
       DEFAULT_HTTPX_TIMEOUT_SECONDS,
       DEFAULT_PLAYWRIGHT_MAX_CONCURRENCY,
       DEFAULT_SHARD_SIZE,
   )


   def _env_int(name: str, default: int) -> int:
       value = os.getenv(name)
       if value is None:
           return default
       return int(value)


   def load_run_config() -> RunConfig:
       env = os.getenv("TAVILY_ENV", "local")
       data_dir = Path(os.getenv("TAVILY_DATA_DIR", "data")).resolve()
       urls_path = data_dir / "urls.txt"

       httpx_timeout_seconds = _env_int("HTTPX_TIMEOUT_SECONDS", DEFAULT_HTTPX_TIMEOUT_SECONDS)
       httpx_max_concurrency = _env_int("HTTPX_MAX_CONCURRENCY", DEFAULT_HTTPX_MAX_CONCURRENCY)
       playwright_max_concurrency = _env_int(
           "PLAYWRIGHT_MAX_CONCURRENCY",
           DEFAULT_PLAYWRIGHT_MAX_CONCURRENCY,
       )
       shard_size = _env_int("SHARD_SIZE", DEFAULT_SHARD_SIZE)

       proxy_config_path_env = os.getenv("PROXY_CONFIG_PATH")
       proxy_config_path = Path(proxy_config_path_env).resolve() if proxy_config_path_env else None

       return RunConfig(
           env=env,  # type: ignore[arg-type]
           urls_path=urls_path,
           data_dir=data_dir,
           httpx_timeout_seconds=httpx_timeout_seconds,
           httpx_max_concurrency=httpx_max_concurrency,
           playwright_headless=os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true",
           playwright_max_concurrency=playwright_max_concurrency,
           shard_size=shard_size,
           proxy_config_path=proxy_config_path,
       )
   ```

   - For `TAVILY_ENV="ci"`, later tickets will enforce stricter checks; for now, ensure types are correct and defaults sane.

6. **Implement proxy JSON loader**

   Also in `config/env.py`, add:

   ```python
   import json
   from tavily_scraper.core.models import ProxyConfig


   def load_proxy_config_from_json(path: Path) -> ProxyConfig:
       raw = json.loads(path.read_text(encoding="utf-8"))
       proxy = raw["proxy"]
       host = proxy["hostname"].split(":")[0]
       ports = proxy["port"]
       return ProxyConfig(
           host=host,
           http_port=int(ports["http"]),
           https_port=int(ports["https"]),
           socks5_port=int(ports["socks5"]),
           username=proxy.get("username"),
           password=proxy.get("password"),
       )
   ```

7. **Implement URL loading helpers**

   In `tavily_scraper/utils/io.py`, implement:

   ```python
   from __future__ import annotations

   import csv
   from pathlib import Path
   from typing import Iterable


   def load_urls_from_txt(path: Path) -> list[str]:
       if not path.exists():
           return []
       return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


   def load_urls_from_csv(path: Path, url_column: str = "url") -> list[str]:
       urls: list[str] = []
       with path.open(encoding="utf-8") as f:
           reader = csv.DictReader(f)
           for row in reader:
               url = (row.get(url_column) or "").strip()
               if url:
                   urls.append(url)
       return urls


   def ensure_canonical_urls_file(raw_csv: Path, canonical_txt: Path) -> Path:
       if canonical_txt.exists():
           return canonical_txt
       urls = load_urls_from_csv(raw_csv)
       canonical_txt.parent.mkdir(parents=True, exist_ok=True)
       canonical_txt.write_text("\n".join(urls), encoding="utf-8")
       return canonical_txt
   ```

8. **Implement URL job creation**

   In `utils/io.py` or `core/models.py`, add a helper:

   ```python
   from yarl import URL

   from tavily_scraper.core.models import UrlJob, UrlStr


   def make_url_jobs(urls: list[str]) -> list[UrlJob]:
       jobs: list[UrlJob] = []
       for index, raw in enumerate(urls):
           try:
               URL(raw)  # validate
           except Exception:
               # invalid URLs will be handled later; skip or record separately
               continue
           jobs.append(
               UrlJob(
                   url=UrlStr(raw),
                   is_dynamic_hint=None,
                   shard_id=-1,  # filled in by sharding logic
                   index_in_shard=index,
               ),
           )
       return jobs
   ```

## Example Usage

```python
from pathlib import Path

from tavily_scraper.config.env import load_run_config, load_proxy_config_from_json
from tavily_scraper.utils.io import ensure_canonical_urls_file, load_urls_from_txt, make_url_jobs


config = load_run_config()
raw_csv = Path(".sdd/raw/urls.csv")
canonical = ensure_canonical_urls_file(raw_csv, config.urls_path)
urls = load_urls_from_txt(canonical)
jobs = make_url_jobs(urls)

if config.proxy_config_path is not None:
    proxy_config = load_proxy_config_from_json(config.proxy_config_path)
```

## Acceptance Criteria

- `RunConfig`, `ShardConfig`, `ProxyConfig`, and `UrlJob` are defined in `tavily_scraper/core/models.py`, fully typed and compatible with `mypy --strict`.
- `Method`, `Stage`, and `Status` literals plus sensible defaults are defined in `tavily_scraper/config/constants.py`.
- `load_run_config()` in `tavily_scraper/config/env.py`:

  - Reads environment variables with defaults.
  - Produces a valid `RunConfig` for local development without requiring any env variables.

- `load_proxy_config_from_json()` correctly parses a JSON file structurally compatible with `.sdd/raw/proxy.json` without logging secrets.
- URL helpers in `tavily_scraper/utils/io.py`:

  - Load URLs from TXT and CSV.
  - Create a canonical `data/urls.txt` from `.sdd/raw/urls.csv`.
  - Return a list of `UrlJob` objects for valid URLs.

- Unit tests cover:

  - Env var parsing (e.g., default vs non-default values).
  - Proxy JSON parsing with a sanitized sample.
  - URL loading from both TXT and CSV and correct canonicalization behavior.

