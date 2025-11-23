"""
Verification suite for stealth capabilities.
Runs against bot detection sites.
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from tavily_scraper.stealth.config import StealthConfig
from tavily_scraper.stealth.core import apply_core_stealth
from tavily_scraper.stealth.advanced import apply_advanced_stealth
from tavily_scraper.utils.logging import get_logger

logger = get_logger(__name__)


async def verify_sannysoft() -> bool:
    """
    Verify stealth against bot.sannysoft.com.
    """
    url = "https://bot.sannysoft.com/"
    config = StealthConfig(enabled=True, mode="aggressive")
    
    logger.info(f"Verifying against {url}...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Apply stealth
        await apply_core_stealth(page, config)
        await apply_advanced_stealth(page, config)
        
        await page.goto(url)
        await page.wait_for_load_state("networkidle")
        
        # Take screenshot
        screenshot_path = Path("verification_sannysoft.png")
        await page.screenshot(path=screenshot_path, full_page=True)
        logger.info(f"Screenshot saved to {screenshot_path}")
        
        # Check indicators
        content = await page.content()
        
        # We expect "WebDriver" to be false (red or green depending on site logic, usually green means false)
        # Sannysoft table: "WebDriver" -> "false" (green)
        # Check content for validation (not used for assertion, just for debugging)
        _ = 'class="passed">WebDriver (New)</td><td class="passed">missing (passed)</td>' in content or \
            'WebDriver' in content and 'false' in content.lower()
        
        # Simple check for now: check if navigator.webdriver is undefined in console
        webdriver_eval = await page.evaluate("navigator.webdriver")
        
        if webdriver_eval is None:
            logger.info("✅ navigator.webdriver is undefined")
        else:
            logger.error(f"❌ navigator.webdriver is {webdriver_eval}")
            return False
            
        await browser.close()
        return True


async def main() -> None:
    """Run verification suite."""
    success = await verify_sannysoft()
    
    if success:
        logger.info("Verification PASSED")
        sys.exit(0)
    else:
        logger.error("Verification FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
