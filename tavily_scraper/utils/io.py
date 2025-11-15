"""
I/O utilities for reading and writing scraping data.

This module provides:
- URL loading from text and CSV files
- URL validation and job creation
- JSONL statistics persistence
- Buffered writing for performance
- Checkpoint management for resumability
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from yarl import URL

from tavily_scraper.core.models import UrlJob, UrlStats, UrlStr

# ==== URL LOADING ==== #

def load_urls_from_txt(path: Path) -> list[str]:
    """
    Load URLs from text file (one per line).

    Args:
        path: Path to text file

    Returns:
        List of URL strings (empty lines skipped)

    Note:
        Returns empty list if file doesn't exist.
    """
    if not path.exists():
        return []

    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]




def load_urls_from_csv(path: Path, url_column: str = "url") -> list[str]:
    """
    Load URLs from CSV file.

    Args:
        path: Path to CSV file
        url_column: Name of column containing URLs (default: "url")

    Returns:
        List of URL strings from specified column

    Raises:
        FileNotFoundError: If path doesn't exist
        KeyError: If url_column not found in CSV
    """
    urls: list[str] = []

    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (row.get(url_column) or "").strip()
            if url:
                urls.append(url)

    return urls




def ensure_canonical_urls_file(raw_csv: Path, canonical_txt: Path) -> Path:
    """
    Ensure canonical URLs text file exists.

    If canonical file doesn't exist, creates it from CSV source.

    Args:
        raw_csv: Source CSV file path
        canonical_txt: Target text file path

    Returns:
        Path to canonical text file

    Note:
        This enables consistent URL format across runs.
    """
    if canonical_txt.exists():
        return canonical_txt

    urls = load_urls_from_csv(raw_csv)
    canonical_txt.parent.mkdir(parents=True, exist_ok=True)
    canonical_txt.write_text("\n".join(urls), encoding="utf-8")

    return canonical_txt




# ==== URL JOB CREATION ==== #

def make_url_jobs(urls: list[str]) -> list[UrlJob]:
    """
    Create UrlJob objects from URL strings with validation.

    This function:
    1. Validates each URL using yarl.URL
    2. Skips invalid URLs silently
    3. Creates UrlJob with metadata

    Args:
        urls: List of URL strings

    Returns:
        List of validated UrlJob objects

    Note:
        Invalid URLs are skipped rather than raising errors
        to allow processing of partially valid input.
    """
    jobs: list[UrlJob] = []

    for index, raw in enumerate(urls):
        try:
            URL(raw)
        except Exception:
            continue

        jobs.append(
            UrlJob(
                url=UrlStr(raw),
                is_dynamic_hint=None,
                shard_id=-1,
                index_in_shard=index,
            ),
        )

    return jobs




# ==== STATISTICS PERSISTENCE ==== #

def write_stats_jsonl(stats: list[UrlStats], path: Path) -> None:
    """
    Write statistics to JSONL file.

    Args:
        stats: List of UrlStats to write
        path: Output file path

    Note:
        Creates parent directories if needed.
        Each stat is written as one JSON line.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for stat in stats:
            f.write(json.dumps(stat) + "\n")




def read_stats_jsonl(path: Path) -> list[UrlStats]:
    """
    Read statistics from JSONL file.

    Args:
        path: Input file path

    Returns:
        List of UrlStats (empty if file doesn't exist)

    Note:
        Empty lines are skipped automatically.
    """
    if not path.exists():
        return []

    stats: list[UrlStats] = []

    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                stats.append(json.loads(line))

    return stats




# ==== BUFFERED WRITER ==== #

class ResultStore:
    """
    Buffered JSONL writer for UrlStats.

    This class provides efficient batch writing to reduce
    I/O overhead during high-throughput scraping.

    Attributes:
        path: Output file path
        buffer_size: Number of stats to buffer before flush
        buffer: In-memory buffer of pending stats
    """

    def __init__(self, path: Path, buffer_size: int = 100):
        """
        Initialize buffered writer.

        Args:
            path: Output file path
            buffer_size: Stats to buffer before auto-flush (default: 100)
        """
        self.path = path
        self.buffer_size = buffer_size
        self.buffer: list[UrlStats] = []
        path.parent.mkdir(parents=True, exist_ok=True)




    def write(self, stat: UrlStats) -> None:
        """
        Write single stat (buffered).

        Args:
            stat: UrlStats to write

        Note:
            Automatically flushes when buffer reaches buffer_size.
        """
        self.buffer.append(stat)

        if len(self.buffer) >= self.buffer_size:
            self.flush()




    def flush(self) -> None:
        """
        Flush buffer to disk.

        Writes all buffered stats and clears buffer.
        Safe to call multiple times.
        """
        if not self.buffer:
            return

        with self.path.open("a", encoding="utf-8") as f:
            for stat in self.buffer:
                f.write(json.dumps(stat) + "\n")

        self.buffer.clear()




    def close(self) -> None:
        """
        Flush and close writer.

        Should be called when done writing to ensure
        all buffered data is persisted.
        """
        self.flush()




# ==== CHECKPOINT MANAGEMENT ==== #

def save_checkpoint(checkpoint: dict[str, Any], path: Path) -> None:
    """
    Save checkpoint to JSON file.

    Args:
        checkpoint: Checkpoint data dictionary
        path: Output file path

    Note:
        Creates parent directories if needed.
        Formatted with indentation for readability.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")




def load_checkpoint(path: Path) -> dict[str, Any] | None:
    """
    Load checkpoint from JSON file.

    Args:
        path: Checkpoint file path

    Returns:
        Checkpoint dictionary or None if file doesn't exist

    Note:
        Returns None rather than raising error for missing files
        to simplify first-run logic.
    """
    if not path.exists():
        return None

    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data
