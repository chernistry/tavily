"""
Tests for core stealth techniques.
"""

import pytest
from playwright.async_api import async_playwright

from tavily_scraper.stealth.config import StealthConfig
from tavily_scraper.stealth.core import apply_core_stealth


@pytest.mark.asyncio
async def test_stealth_webdriver_hidden() -> None:
    """Verify navigator.webdriver is hidden."""
    config = StealthConfig(enabled=True, spoof_webdriver=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await apply_core_stealth(page, config)
        
        webdriver = await page.evaluate("navigator.webdriver")
        assert webdriver is None
        
        await browser.close()


@pytest.mark.asyncio
async def test_stealth_permissions_mocked() -> None:
    """Verify permissions query is mocked."""
    config = StealthConfig(enabled=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await apply_core_stealth(page, config)
        
        # Should not throw error and return a result
        result = await page.evaluate(
            "navigator.permissions.query({name: 'notifications'}).then(r => r.state)"
        )
        assert result in ["granted", "denied", "prompt", "default"]
        
        await browser.close()
