"""Custom exceptions."""

from __future__ import annotations


class ScraperError(Exception):
    """Base exception for scraper errors."""

    def __init__(self, kind: str, url: str, detail: str | None = None) -> None:
        self.kind = kind
        self.url = url
        self.detail = detail
        message = f"{kind} for {url}: {detail or ''}"
        super().__init__(message)
