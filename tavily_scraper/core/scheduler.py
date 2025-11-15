"""Domain-aware scheduling and concurrency control."""

from __future__ import annotations

import asyncio
import random
from collections import defaultdict
from collections.abc import Mapping


class DomainScheduler:
    """Domain-aware concurrency scheduler with adaptive limits."""

    def __init__(
        self,
        global_limit: int,
        per_domain_limits: Mapping[str, int] | None = None,
        jitter_range: tuple[float, float] | None = None,
        max_errors_for_browser: int = 5,
        max_captchas_for_browser: int = 5,
    ) -> None:
        self._global_semaphore = asyncio.Semaphore(global_limit)
        self._per_domain_limits = dict(per_domain_limits or {})
        self._domain_semaphores: dict[str, asyncio.Semaphore] = {}
        self._error_counts: dict[str, int] = defaultdict(int)
        self._captcha_counts: dict[str, int] = defaultdict(int)
        self._jitter_range = jitter_range
        self._max_errors_for_browser = max_errors_for_browser
        self._max_captchas_for_browser = max_captchas_for_browser

    async def acquire(self, domain: str) -> None:
        """Acquire concurrency slot for domain."""
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
        """Release concurrency slot for domain."""
        self._global_semaphore.release()
        sem = self._domain_semaphores.get(domain)
        if sem is not None:
            sem.release()

    def record_error(self, domain: str) -> None:
        """Record error for domain (for adaptive limiting)."""
        self._error_counts[domain] += 1

    def record_captcha(self, domain: str) -> None:
        """Record CAPTCHA for domain (for adaptive limiting)."""
        self._captcha_counts[domain] += 1

    def should_try_browser(self, domain: str) -> bool:
        """Return whether browser fallback is still reasonable for this domain.

        If a domain has accumulated many errors or CAPTCHAs, it is likely
        being hard-blocked, so additional browser attempts are wasteful.
        """
        if self._error_counts[domain] >= self._max_errors_for_browser:
            return False
        if self._captcha_counts[domain] >= self._max_captchas_for_browser:
            return False
        return True
