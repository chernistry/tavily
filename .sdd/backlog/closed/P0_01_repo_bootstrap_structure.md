Read /Users/sasha/IdeaProjects/personal_projects/tavily/.sdd/CODING_RULES.md first

# P0_01 – Bootstrap repo and core structure

## Objective

Create a clean, production-shaped Python 3.11 project for the Tavily hybrid scraper, with the required package layout, tooling (Ruff, mypy, pytest, Playwright), and initial test wiring. The result should be a minimal but runnable skeleton onto which all other tickets can safely build.

## Background

Architecture and coding rules specify:

- Package name: `tavily_scraper`.
- Layout with `config/`, `core/`, `pipelines/`, `utils/`, `notebooks/`, `tests/`.
- Tooling: Ruff (lint + format), mypy (`--strict`), pytest, Playwright.
- Data location: `data/` for `urls.txt`, `stats.jsonl`, `run_summary.json`, checkpoints, etc.

This ticket focuses on structure and tooling only; no real scraping logic is implemented yet.

## Dependencies

- None – this is the first ticket and must be completed before others.

## Scope

- Create Python package layout and empty/stub modules.
- Configure `pyproject.toml`, `requirements.txt`, `.gitignore`, `.env.example`.
- Add placeholder tests and ensure the test, lint, and type-check pipelines run.

## Out of Scope

- Implementing real HTTP or Playwright fetching.
- Implementing router, metrics, or notebook logic (later tickets).

## Implementation Steps

1. **Create base directory layout**

   Add the following directories and files:

   - Package and subpackages:

     - `tavily_scraper/__init__.py`
     - `tavily_scraper/config/__init__.py`
     - `tavily_scraper/config/env.py`
     - `tavily_scraper/config/constants.py`
     - `tavily_scraper/core/__init__.py`
     - `tavily_scraper/core/models.py`
     - `tavily_scraper/core/errors.py`
     - `tavily_scraper/core/scheduler.py`
     - `tavily_scraper/core/robots.py`
     - `tavily_scraper/pipelines/__init__.py`
     - `tavily_scraper/pipelines/fast_http_fetcher.py`
     - `tavily_scraper/pipelines/browser_fetcher.py`
     - `tavily_scraper/pipelines/router.py`
     - `tavily_scraper/pipelines/shard_runner.py`
     - `tavily_scraper/pipelines/batch_runner.py`
     - `tavily_scraper/utils/__init__.py`
     - `tavily_scraper/utils/parsing.py`
     - `tavily_scraper/utils/captcha.py`
     - `tavily_scraper/utils/metrics.py`
     - `tavily_scraper/utils/logging.py`
     - `tavily_scraper/utils/io.py`
     - `tavily_scraper/utils/timing.py`

   - Notebooks:

     - `tavily_scraper/notebooks/` (empty directory for now).

   - Data and docs:

     - `data/` directory for runtime artifacts (stats, run summary, checkpoints).
     - `docs/` directory for later ADRs and one-pager content.

2. **Initialize `__init__.py` and basic metadata**

   In `tavily_scraper/__init__.py`, add a minimal version and docstring:

   ```python
   """Hybrid HTTP + Playwright scraping package for Tavily assignment."""

   __all__ = ["__version__"]
   __version__ = "0.1.0"
   ```

3. **Create `pyproject.toml` with tooling configuration**

   - Set up project metadata:

     ```toml
     [project]
     name = "tavily-scraper"
     version = "0.1.0"
     description = "Hybrid HTTP + Playwright scraper for Tavily Web Research assignment"
     requires-python = ">=3.11"
     dependencies = []
     ```

   - Add Ruff and Black configuration aligned with `CODING_RULES.md`:

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

   - Add mypy configuration (either in `pyproject.toml` or `mypy.ini`); example snippet:

     ```toml
     [tool.mypy]
     python_version = "3.11"
     strict = true
     files = ["tavily_scraper"]
     ```

4. **Create `requirements.txt`**

   Include at least the following packages (exact versions can be pinned later):

   ```text
   httpx[http2]
   selectolax
   playwright
   msgspec

   pytest
   pytest-asyncio
   pytest-httpx

   mypy
   ruff
   ```

5. **Create `.gitignore`**

   Include typical Python and project-specific ignores:

   ```text
   __pycache__/
   .pytest_cache/
   .mypy_cache/
   .ruff_cache/
   .venv/
   .env
   .DS_Store

   data/
   proxy.json
   playwright-report/

   .idea/
   .vscode/
   ```

6. **Create `.env.example`**

   Follow `CODING_RULES.md`:

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

7. **Add minimal logging utility**

   In `tavily_scraper/utils/logging.py`, add a simple JSON-ish logger setup so later tickets can reuse it:

   ```python
   from __future__ import annotations

   import logging


   def get_logger(name: str) -> logging.Logger:
       logger = logging.getLogger(name)
       if not logger.handlers:
           handler = logging.StreamHandler()
           formatter = logging.Formatter(
               '%(asctime)s %(levelname)s %(name)s %(message)s',
           )
           handler.setFormatter(formatter)
           logger.addHandler(handler)
           logger.setLevel(logging.INFO)
       return logger
   ```

8. **Create initial tests directory**

   Add:

   - `tests/__init__.py`
   - `tests/test_fast_http_fetcher.py`
   - `tests/test_browser_fetcher.py`
   - `tests/test_router.py`
   - `tests/test_scheduler.py`
   - `tests/test_metrics.py`
   - `tests/test_captcha.py`

   Each can contain a trivial smoke test so pytest passes before real code is written:

   ```python
   def test_sanity() -> None:
       assert True
   ```

9. **Add optional pre-commit configuration**

   Create `.pre-commit-config.yaml` based on `CODING_RULES.md` so developers can enable automatic linting/formatting:

   ```yaml
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

10. **Smoke-test the skeleton**

    Run locally:

    - `python -m pip install -r requirements.txt`
    - `ruff check .`
    - `mypy tavily_scraper/`
    - `pytest --asyncio-mode=auto`

    All should pass, with tests being trivial placeholders.

## Example Code Snippets

Minimal `tavily_scraper/config/env.py` stub that will be expanded later:

```python
from __future__ import annotations

from tavily_scraper.core.models import RunConfig


def load_run_config() -> RunConfig:
    """Return a placeholder RunConfig; will be fully implemented in P0_02."""
    raise NotImplementedError("load_run_config must be implemented in P0_02")
```

Minimal `tavily_scraper/core/models.py` stub:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RunConfig:
    """Placeholder RunConfig; detailed fields will be added in P0_02."""

    pass
```

## Acceptance Criteria

- Project uses the `tavily_scraper` package structure with all stub modules and subpackages created as listed.
- `pyproject.toml`, `requirements.txt`, `.gitignore`, `.env.example`, and `.pre-commit-config.yaml` exist and are broadly aligned with `CODING_RULES.md`.
- `tavily_scraper/__init__.py` defines `__version__` and a package docstring.
- `tests/` contains placeholder tests for the main modules, and running `pytest --asyncio-mode=auto` succeeds.
- `ruff check .` and `mypy tavily_scraper/` run successfully (even if some functions are `NotImplementedError` but correctly typed).
- No real secrets (such as the actual `proxy.json` credentials from `.sdd`) are stored in the repo; only `.env.example` and configuration templates are present.

