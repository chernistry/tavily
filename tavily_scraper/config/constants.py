"""Constants and type aliases."""

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
DEFAULT_MAX_CONTENT_BYTES = 5 * 1024 * 1024  # 5 MiB
