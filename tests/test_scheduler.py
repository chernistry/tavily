"""Tests for domain scheduler."""

import asyncio

import pytest

from tavily_scraper.core.scheduler import DomainScheduler


@pytest.mark.asyncio
async def test_scheduler_global_limit() -> None:
    """Test global concurrency limit."""
    scheduler = DomainScheduler(global_limit=2)
    acquired = []

    async def acquire_and_hold(domain: str) -> None:
        await scheduler.acquire(domain)
        acquired.append(domain)
        await asyncio.sleep(0.1)
        scheduler.release(domain)

    tasks = [acquire_and_hold(f"domain{i}") for i in range(5)]
    await asyncio.gather(*tasks)
    assert len(acquired) == 5


@pytest.mark.asyncio
async def test_scheduler_per_domain_limit() -> None:
    """Test per-domain concurrency limit."""
    scheduler = DomainScheduler(global_limit=10, per_domain_limits={"test.com": 1})

    async def acquire_and_hold(domain: str) -> None:
        await scheduler.acquire(domain)
        await asyncio.sleep(0.05)
        scheduler.release(domain)

    # Multiple requests to same domain should be serialized
    tasks = [acquire_and_hold("test.com") for _ in range(3)]
    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_scheduler_record_errors() -> None:
    """Test error recording."""
    scheduler = DomainScheduler(global_limit=10)
    scheduler.record_error("test.com")
    scheduler.record_captcha("test.com")
    assert scheduler._error_counts["test.com"] == 1
    assert scheduler._captcha_counts["test.com"] == 1


def test_scheduler_should_try_browser() -> None:
    """Test browser gating based on error/captcha counts."""
    scheduler = DomainScheduler(global_limit=10, max_errors_for_browser=2, max_captchas_for_browser=2)

    # Initially allowed
    assert scheduler.should_try_browser("example.com")

    # After errors threshold reached, browser should be skipped
    scheduler.record_error("example.com")
    scheduler.record_error("example.com")
    assert not scheduler.should_try_browser("example.com")

    # Another domain with many CAPTCHAs should also be skipped
    other = DomainScheduler(global_limit=10, max_errors_for_browser=10, max_captchas_for_browser=1)
    assert other.should_try_browser("captcha.com")
    other.record_captcha("captcha.com")
    assert not other.should_try_browser("captcha.com")
