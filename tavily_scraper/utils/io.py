"""I/O utilities for reading/writing data."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from yarl import URL

from tavily_scraper.core.models import UrlJob, UrlStats, UrlStr


def load_urls_from_txt(path: Path) -> list[str]:
    """Load URLs from a text file (one per line)."""
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_urls_from_csv(path: Path, url_column: str = "url") -> list[str]:
    """Load URLs from a CSV file."""
    urls: list[str] = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (row.get(url_column) or "").strip()
            if url:
                urls.append(url)
    return urls


def ensure_canonical_urls_file(raw_csv: Path, canonical_txt: Path) -> Path:
    """Ensure canonical URLs file exists, creating from CSV if needed."""
    if canonical_txt.exists():
        return canonical_txt
    urls = load_urls_from_csv(raw_csv)
    canonical_txt.parent.mkdir(parents=True, exist_ok=True)
    canonical_txt.write_text("\n".join(urls), encoding="utf-8")
    return canonical_txt


def make_url_jobs(urls: list[str]) -> list[UrlJob]:
    """Create UrlJob objects from URL strings, validating each."""
    jobs: list[UrlJob] = []
    for index, raw in enumerate(urls):
        try:
            URL(raw)  # validate
        except Exception:
            # invalid URLs will be handled later; skip for now
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


def write_stats_jsonl(stats: list[UrlStats], path: Path) -> None:
    """Write stats to JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for stat in stats:
            f.write(json.dumps(stat) + "\n")


def read_stats_jsonl(path: Path) -> list[UrlStats]:
    """Read stats from JSONL file."""
    if not path.exists():
        return []
    stats: list[UrlStats] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                stats.append(json.loads(line))
    return stats


class ResultStore:
    """Buffered JSONL writer for UrlStats."""

    def __init__(self, path: Path, buffer_size: int = 100):
        self.path = path
        self.buffer_size = buffer_size
        self.buffer: list[UrlStats] = []
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, stat: UrlStats) -> None:
        """Write a single stat (buffered)."""
        self.buffer.append(stat)
        if len(self.buffer) >= self.buffer_size:
            self.flush()

    def flush(self) -> None:
        """Flush buffer to disk."""
        if not self.buffer:
            return
        with self.path.open("a", encoding="utf-8") as f:
            for stat in self.buffer:
                f.write(json.dumps(stat) + "\n")
        self.buffer.clear()

    def close(self) -> None:
        """Flush and close."""
        self.flush()


def save_checkpoint(checkpoint: dict[str, any], path: Path) -> None:  # type: ignore[valid-type]
    """Save checkpoint to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")


def load_checkpoint(path: Path) -> dict[str, Any] | None:
    """Load checkpoint from JSON file."""
    if not path.exists():
        return None
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data
