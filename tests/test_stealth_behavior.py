"""
Tests for behavioral stealth.
"""

import pytest
from playwright.async_api import async_playwright

from tavily_scraper.stealth.behavior import human_mouse_move, human_scroll, human_type


@pytest.mark.asyncio
async def test_human_behavior_profiles() -> None:
    """Verify behavior functions run without error under different profiles."""
    from tavily_scraper.stealth.config import StealthConfig
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content('<input id="test" type="text">')

        # Test Minimal Profile
        config_minimal = StealthConfig(enabled=True, behavior_profile="minimal")
        await human_mouse_move(page, config_minimal)
        await human_scroll(page, config_minimal)
        await human_type(page, "#test", "minimal", config_minimal)
        assert await page.input_value("#test") == "minimal"
        await page.fill("#test", "")

        # Test Default Profile
        config_default = StealthConfig(enabled=True, behavior_profile="default")
        await human_mouse_move(page, config_default)
        await human_scroll(page, config_default)
        await human_type(page, "#test", "default", config_default)
        assert await page.input_value("#test") == "default"
        await page.fill("#test", "")

        # Test Aggressive Profile
        config_aggressive = StealthConfig(enabled=True, behavior_profile="aggressive")
        await human_mouse_move(page, config_aggressive)
        await human_scroll(page, config_aggressive)
        await human_type(page, "#test", "aggressive", config_aggressive)
        assert await page.input_value("#test") == "aggressive"
        
        await browser.close()
