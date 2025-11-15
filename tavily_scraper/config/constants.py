"""
Configuration constants and type aliases for the Tavily scraper.

This module defines:
- Type literals for method, stage, and status enumerations
- Default configuration values for HTTP and browser operations
- Resource limits and constraints
"""

from __future__ import annotations

from typing import Literal

# ==== TYPE DEFINITIONS ==== #

Method = Literal["httpx", "playwright"]
"""
Scraping method identifier.

- 'httpx': Fast HTTP-only path using async HTTP client
- 'playwright': Browser-based path using headless Chromium
"""


Stage = Literal["primary", "fallback"]
"""
Processing stage indicator.

- 'primary': Initial HTTP attempt
- 'fallback': Browser retry after HTTP failure
"""


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
"""
URL processing outcome status.

- 'success': Content successfully retrieved
- 'captcha_detected': CAPTCHA challenge encountered
- 'robots_blocked': Disallowed by robots.txt
- 'http_error': HTTP-level error (4xx, 5xx)
- 'timeout': Request exceeded time limit
- 'invalid_url': Malformed or unreachable URL
- 'too_large': Content exceeds size limit
- 'other_error': Unclassified error condition
"""




# ==== HTTP CLIENT DEFAULTS ==== #

DEFAULT_HTTPX_TIMEOUT_SECONDS: int = 10
"""Default timeout for HTTP requests in seconds."""

DEFAULT_HTTPX_MAX_CONCURRENCY: int = 32
"""Default maximum concurrent HTTP requests."""




# ==== BROWSER CLIENT DEFAULTS ==== #

DEFAULT_PLAYWRIGHT_MAX_CONCURRENCY: int = 2
"""Default maximum concurrent browser instances."""




# ==== BATCH PROCESSING DEFAULTS ==== #

DEFAULT_SHARD_SIZE: int = 500
"""Default number of URLs per processing shard."""




# ==== RESOURCE LIMITS ==== #

DEFAULT_MAX_CONTENT_BYTES: int = 5 * 1024 * 1024
"""
Maximum content size in bytes (5 MiB).

Content exceeding this limit will be marked as 'too_large'
to prevent memory exhaustion.
"""
