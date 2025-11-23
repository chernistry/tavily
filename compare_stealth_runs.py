#!/usr/bin/env python3
"""
Run back-to-back baseline vs stealth batches and compare metrics.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Iterable
from pathlib import Path

from tavily_scraper.config.env import load_run_config
from tavily_scraper.pipelines.batch_runner import run_batch
from tavily_scraper.stealth.config import StealthConfig
from tavily_scraper.utils.io import load_urls_from_csv
from tavily_scraper.utils.metrics import compute_run_summary

URLS_FILE = Path(".sdd/raw/urls.csv")
DATA_DIR = Path("data")


async def run_once(
    urls: list[str],
    *,
    enable_stealth: bool,
    stats_suffix: str,
    use_browser: bool,
) -> dict[str, float]:
    """
    Run a single batch with the requested stealth configuration.
    """
    config = load_run_config()
    if config.stealth_config is None:
        config.stealth_config = StealthConfig()
    config.stealth_config.enabled = enable_stealth

    summary = await run_batch(
        urls,
        config=config,
        max_urls=len(urls),
        use_browser=use_browser,
        stats_suffix=stats_suffix,
    )
    return summary


def _load_stats(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Stats file not found: {path}")
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _format_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def compare_summaries(
    baseline: dict[str, float],
    stealth: dict[str, float],
) -> None:
    """
    Print a concise comparison of the two runs.
    """
    metrics: Iterable[tuple[str, str]] = [
        ("success_rate", "Success rate"),
        ("http_error_rate", "HTTP errors"),
        ("captcha_rate", "CAPTCHA rate"),
        ("robots_block_rate", "Robots blocks"),
        ("playwright_share", "Browser share"),
    ]

    print("\nComparison (baseline vs stealth):")
    print(f"{'Metric':25s} {'Baseline':>12s} {'Stealth':>12s} {'Delta':>12s}")
    for key, label in metrics:
        base = baseline.get(key, 0.0)
        ste = stealth.get(key, 0.0)
        delta = ste - base
        print(
            f"{label:25s} {_format_pct(base):>12s} "
            f"{_format_pct(ste):>12s} {_format_pct(delta):>12s}"
        )

    base_success = int(baseline["total_urls"] * baseline["success_rate"])
    ste_success = int(stealth["total_urls"] * stealth["success_rate"])
    print(
        f"\nSuccessful URLs: baseline={base_success}, "
        f"stealth={ste_success}, delta={ste_success - base_success}"
    )


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run baseline vs stealth batches and compare stats."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1000,
        help="Number of URLs to process per run (default: 1000)",
    )
    parser.add_argument(
        "--urls-file",
        default=str(URLS_FILE),
        help="CSV file with URLs (default: .sdd/raw/urls.csv)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Disable Playwright fallback (default: off)",
    )
    args = parser.parse_args()

    urls = load_urls_from_csv(Path(args.urls_file))
    if len(urls) < args.count:
        raise RuntimeError(
            f"Requested {args.count} URLs, but only {len(urls)} available."
        )
    subset = urls[: args.count]

    print(f"Running baseline (no stealth) for {args.count} URLs...")
    baseline_summary = await run_once(
        subset,
        enable_stealth=False,
        stats_suffix="",
        use_browser=not args.no_browser,
    )

    print(f"Running stealth for {args.count} URLs...")
    stealth_summary = await run_once(
        subset,
        enable_stealth=True,
        stats_suffix="_stealth",
        use_browser=not args.no_browser,
    )

    baseline_stats = _load_stats(DATA_DIR / "stats.jsonl")
    stealth_stats = _load_stats(DATA_DIR / "stats_stealth.jsonl")

    # Recompute summaries to make sure we compare on-disk stats
    baseline_summary = compute_run_summary(baseline_stats)
    stealth_summary = compute_run_summary(stealth_stats)

    compare_summaries(baseline_summary, stealth_summary)


if __name__ == "__main__":
    asyncio.run(main())
