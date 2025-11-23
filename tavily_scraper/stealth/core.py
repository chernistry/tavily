"""
Core stealth techniques to evade basic bot detection.
"""

from playwright.async_api import Page

from tavily_scraper.stealth.asset_loader import load_asset_text
from tavily_scraper.stealth.config import StealthConfig


async def apply_core_stealth(page: Page, config: StealthConfig) -> None:
    """
    Apply core stealth techniques to the page.

    This focuses on:
    * Hiding obvious automation flags (navigator.webdriver, window.chrome)
    * Normalizing navigator properties (languages, plugins, hardware hints)
    * Making the permissions API behave like a real browser

    All scripts are defensive: they swallow their own errors so we never break
    the page if a browser/vendor changes something.

    Args:
        page: Playwright page instance.
        config: Stealth configuration.
    """
    if not config.enabled:
        return

    # --- navigator.webdriver and basic automation flags ---
    if config.spoof_webdriver:
        await page.add_init_script(load_asset_text("core_automation.js"))

    # --- navigator languages, plugins, and basic hardware hints ---
    if config.spoof_user_agent:
        await page.add_init_script(load_asset_text("navigator_patch.js"))

    # --- Permissions API normalization ---
    await page.add_init_script(load_asset_text("permissions_patch.js"))
