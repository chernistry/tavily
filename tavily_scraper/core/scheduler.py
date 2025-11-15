"""
Domain-aware scheduling and concurrency control.

This module implements intelligent rate limiting with:
- Global concurrency limits across all domains
- Per-domain concurrency limits for high-volume targets
- Optional request jitter to avoid burst patterns
- Adaptive browser fallback decisions based on error rates
- CAPTCHA and error tracking per domain
"""

from __future__ import annotations

import asyncio
import random
from collections import defaultdict
from collections.abc import Mapping
from typing import Optional




# ==== DOMAIN-AWARE SCHEDULER ==== #

class DomainScheduler:
    """
    Domain-aware concurrency scheduler with adaptive rate limiting.

    This scheduler manages request concurrency at two levels:
    1. Global: Total concurrent requests across all domains
    2. Per-domain: Concurrent requests to specific domains

    It also tracks errors and CAPTCHAs per domain to make intelligent
    decisions about whether browser fallback is worth attempting.

    Attributes:
        _global_semaphore: Global concurrency limiter
        _per_domain_limits: Configured per-domain limits
        _domain_semaphores: Active per-domain semaphores
        _error_counts: Error count tracker per domain
        _captcha_counts: CAPTCHA count tracker per domain
        _jitter_range: Optional delay range for request jitter
        _max_errors_for_browser: Error threshold for browser attempts
        _max_captchas_for_browser: CAPTCHA threshold for browser attempts
    """

    def __init__(
        self,
        global_limit: int,
        per_domain_limits: Optional[Mapping[str, int]] = None,
        jitter_range: Optional[tuple[float, float]] = None,
        max_errors_for_browser: int = 5,
        max_captchas_for_browser: int = 5,
    ) -> None:
        """
        Initialize domain scheduler with concurrency limits.

        Args:
            global_limit: Maximum concurrent requests across all domains
            per_domain_limits: Optional dict mapping domains to their limits
            jitter_range: Optional (min, max) delay range in seconds
            max_errors_for_browser: Error threshold before disabling browser
            max_captchas_for_browser: CAPTCHA threshold before disabling browser

        Example:
            scheduler = DomainScheduler(
                global_limit=32,
                per_domain_limits={"google.com": 1, "bing.com": 1},
                jitter_range=(0.1, 0.5),
            )
        """
        self._global_semaphore = asyncio.Semaphore(global_limit)
        self._per_domain_limits = dict(per_domain_limits or {})
        self._domain_semaphores: dict[str, asyncio.Semaphore] = {}
        self._error_counts: dict[str, int] = defaultdict(int)
        self._captcha_counts: dict[str, int] = defaultdict(int)
        self._jitter_range = jitter_range
        self._max_errors_for_browser = max_errors_for_browser
        self._max_captchas_for_browser = max_captchas_for_browser




    # --► CONCURRENCY SLOT MANAGEMENT

    async def acquire(self, domain: str) -> None:
        """
        Acquire concurrency slot for domain.

        This method:
        1. Acquires global semaphore slot
        2. Acquires domain-specific semaphore slot
        3. Optionally adds random jitter delay

        Args:
            domain: Target domain name

        Returns:
            None

        Note:
            This method blocks until both global and domain slots
            are available. Always pair with release() in a try/finally.
        """
        await self._global_semaphore.acquire()

        sem = self._domain_semaphores.setdefault(
            domain,
            asyncio.Semaphore(self._per_domain_limits.get(domain, 4)),
        )
        await sem.acquire()

        if self._jitter_range:
            low, high = self._jitter_range
            await asyncio.sleep(random.uniform(low, high))




    def release(self, domain: str) -> None:
        """
        Release concurrency slot for domain.

        This method releases both global and domain-specific semaphores.

        Args:
            domain: Target domain name

        Returns:
            None

        Note:
            Should always be called in a finally block to ensure
            slots are released even if errors occur.
        """
        self._global_semaphore.release()

        sem = self._domain_semaphores.get(domain)
        if sem is not None:
            sem.release()




    # --► ERROR & CAPTCHA TRACKING

    def record_error(self, domain: str) -> None:
        """
        Record HTTP error for domain.

        Used for adaptive limiting - domains with many errors
        may be hard-blocked and not worth browser attempts.

        Args:
            domain: Target domain name

        Returns:
            None
        """
        self._error_counts[domain] += 1




    def record_captcha(self, domain: str) -> None:
        """
        Record CAPTCHA detection for domain.

        Used for adaptive limiting - domains with many CAPTCHAs
        are likely using anti-bot protection and browser attempts
        may not succeed.

        Args:
            domain: Target domain name

        Returns:
            None
        """
        self._captcha_counts[domain] += 1




    # --► ADAPTIVE BROWSER FALLBACK DECISION

    def should_try_browser(self, domain: str) -> bool:
        """
        Determine if browser fallback is worth attempting for domain.

        This method checks if the domain has accumulated too many
        errors or CAPTCHAs, indicating hard blocking where browser
        attempts are unlikely to succeed.

        Args:
            domain: Target domain name

        Returns:
            True if browser attempt is reasonable, False if wasteful

        Note:
            This prevents wasting expensive browser resources on
            domains that are clearly blocking all automated access.
        """
        if self._error_counts[domain] >= self._max_errors_for_browser:
            return False

        if self._captcha_counts[domain] >= self._max_captchas_for_browser:
            return False

        return True
