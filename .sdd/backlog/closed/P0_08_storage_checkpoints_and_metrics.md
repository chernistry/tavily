Read .sdd/CODING_RULES.md first

# P0_08 – Storage, checkpoints, and metrics

## Objective

Implement file-based persistence for per-URL stats, shard checkpoints, and run-level metrics using JSONL and JSON files. This enables resumability, post-hoc analysis, and notebook visualizations.

## Dependencies

- Depends on:
  - `P0_02_config_env_and_input_loading.md`
  - `P0_03_core_models_and_stats_schema.md`

## Scope

- JSONL writer for `UrlStats`.
- `ResultStore` for buffered writes.
- Checkpoint load/save for `ShardCheckpoint`.
- Run summary computation and persistence.

## Implementation Steps

1. **Implement JSONL helpers**

   In `tavily_scraper/utils/io.py`, implement:

   ```python
   import json
   from pathlib import Path
   from typing import Iterable


   def append_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
       path.parent.mkdir(parents=True, exist_ok=True)
       with path.open("a", encoding="utf-8") as f:
           for row in rows:
               f.write(json.dumps(row, ensure_ascii=False) + "\n")
   ```

2. **Implement `ResultStore`**

   Either in `utils/io.py` or a new `utils/result_store.py`:

   ```python
   from __future__ import annotations

   from dataclasses import dataclass, field
   from pathlib import Path
   from typing import List

   from tavily_scraper.core.models import UrlStats
   from tavily_scraper.utils.io import append_jsonl


   @dataclass
   class ResultStore:
       path: Path
       buffer_size: int = 100
       _buffer: List[UrlStats] = field(default_factory=list)

       def write(self, row: UrlStats) -> None:
           self._buffer.append(row)
           if len(self._buffer) >= self.buffer_size:
               self.flush()

       def flush(self) -> None:
           if not self._buffer:
               return
           append_jsonl(self.path, self._buffer)
           self._buffer.clear()

       def close(self) -> None:
           self.flush()

       def __enter__(self) -> "ResultStore":
           return self

       def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
           self.close()
   ```

3. **Implement checkpoint load/save**

   In `utils/io.py` or `utils/checkpoints.py`, add:

   ```python
   from tavily_scraper.core.models import ShardCheckpoint


   def load_checkpoint(path: Path) -> ShardCheckpoint | None:
       if not path.exists():
           return None
       data = json.loads(path.read_text(encoding="utf-8"))
       return ShardCheckpoint(
           run_id=data["run_id"],
           shard_id=data["shard_id"],
           urls_total=data["urls_total"],
           urls_done=data["urls_done"],
           last_updated_at=data["last_updated_at"],
           status=data["status"],
       )


   def save_checkpoint(path: Path, checkpoint: ShardCheckpoint) -> None:
       path.parent.mkdir(parents=True, exist_ok=True)
       path.write_text(json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8")
   ```

4. **Run summary persistence**

   In `tavily_scraper/utils/metrics.py`, extend `compute_run_summary` so that:

   - It can be used both in memory and as a persistence helper.
   - Add a helper:

     ```python
     from pathlib import Path


     def write_run_summary(path: Path, summary: RunSummary) -> None:
         path.parent.mkdir(parents=True, exist_ok=True)
         path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
     ```

   - `compute_run_summary` should compute:

     - Total URL count and stats rows.
     - Success, error, timeout, CAPTCHA, robots-block rates.
     - httpx/playwright shares.
     - P50/P95 latencies for both methods.
     - Average content length for each method.

5. **Define default file locations**

   - Decide and document file paths relative to `RunConfig.data_dir`:

     - `stats_path = data_dir / "stats.jsonl"`
     - `run_summary_path = data_dir / "run_summary.json"`
     - Checkpoints: `data_dir / "checkpoints" / f"{run_id}_shard_{shard_id}.json"`

   - Ensure `RunConfig` has fields or helper functions to derive these paths.

## Example Usage

```python
from pathlib import Path

from tavily_scraper.core.models import UrlStats
from tavily_scraper.utils.io import append_jsonl, load_checkpoint, save_checkpoint
from tavily_scraper.utils.result_store import ResultStore
from tavily_scraper.utils.metrics import compute_run_summary, write_run_summary


stats_rows: list[UrlStats] = [
    {
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
        "timestamp": "2025-01-01T00:00:00Z",
        "shard_id": 0,
    },
]

stats_path = Path("data/stats.jsonl")
append_jsonl(stats_path, stats_rows)

summary = compute_run_summary(stats_rows)
write_run_summary(Path("data/run_summary.json"), summary)
```

## Acceptance Criteria

- JSONL helpers:

  - Can append multiple `UrlStats` rows to `stats.jsonl`.
  - Produce valid UTF-8 JSON lines without corruption.

- `ResultStore`:

  - Buffers writes and flushes automatically after `buffer_size` rows or on `.close()`.
  - Creates parent directories as needed.

- Checkpoint helpers:

  - `save_checkpoint` writes a single JSON file per shard.
  - `load_checkpoint` returns `None` when no checkpoint exists.
  - Checkpoints can be updated multiple times without errors.

- `compute_run_summary` and `write_run_summary`:

  - Produce `RunSummary` matching the schema in `CODING_RULES.md`.
  - Persist `RunSummary` to `data/run_summary.json`.

- Unit tests cover:

  - Writing and reading JSONL files for small datasets.
  - Saving/loading checkpoints.
  - Run summary aggregation for a small synthetic dataset with both HTTPX and Playwright rows.

- All new code passes `ruff check .` and `mypy --strict`.

