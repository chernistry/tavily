"""
Tests for behavioral stealth.
"""

import pytest
from playwright.async_api import async_playwright

from tavily_scraper.stealth.behavior import human_mouse_move, human_scroll, human_type


@pytest.mark.asyncio
async def test_human_behavior_runs() -> None:
    """Verify behavior functions run without error."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # We can't easily verify the exact movement, but we can verify it doesn't crash
        await human_mouse_move(page)
        await human_scroll(page)
        
        # Test typing
        await page.set_content('<input id="test" type="text">')
        await human_type(page, "#test", "hello")
        
        value = await page.input_value("#test")
        assert value == "hello"
        
        await browser.close()
