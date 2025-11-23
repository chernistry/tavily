"""
Utility for loading bundled stealth assets (JS snippets) with caching.
"""

from __future__ import annotations

from functools import cache
from importlib import resources


@cache
def load_asset_text(filename: str) -> str:
    """
    Load a JavaScript asset by filename from tavily_scraper.stealth.assets.

    Raises FileNotFoundError if the asset is missing.
    """
    package = "tavily_scraper.stealth.assets"
    data = resources.files(package).joinpath(filename)
    if not data.is_file():
        raise FileNotFoundError(f"Stealth asset not found: {filename}")
    return data.read_text(encoding="utf-8")
