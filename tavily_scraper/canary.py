"""
Canary script to verify stealth effectiveness against bot detection sites.
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

# Configure logging
from typing import Literal

from tavily_scraper.config.env import load_run_config
from tavily_scraper.pipelines.browser_fetcher import (
    browser_lifecycle,
    create_page_with_blocking,
)
from tavily_scraper.stealth.config import StealthConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("canary")

async def run_canary(
    headless: bool = True, 
    mode: Literal["minimal", "moderate", "aggressive"] = "moderate"
) -> None:
    """
    Run a canary check against bot.sannysoft.com.
    """
    logger.info(f"Starting canary check (headless={headless}, mode={mode})...")
    
    config = load_run_config()
    config.playwright_headless = headless
    config.stealth_config = StealthConfig(
        enabled=True,
        mode=mode,
        headless=headless
    )
    
    # We don't need a full proxy manager for this simple check unless testing proxies
    proxy_manager = None # ProxyManager() if needed

    results = {
        "webdriver_hidden": False,
        "chrome_object": False,
        "permissions": False,
        "plugins_length": 0,
        "overall_score": 0
    }

    async with browser_lifecycle(config, proxy_manager) as browser:
        page = await create_page_with_blocking(browser, config)
        
        try:
            await page.goto("https://bot.sannysoft.com/", wait_until="networkidle")
            
            # Take a screenshot for manual verification
            screenshot_path = Path("canary_screenshot.png")
            await page.screenshot(path=screenshot_path)
            logger.info(f"Screenshot saved to {screenshot_path}")

            # Extract metrics from the page
            # Note: Sannysoft renders results in tables. We'll do some basic text extraction.
            content = await page.content()
            
            # Check for specific success indicators
            results["webdriver_hidden"] = "WebDriver (New)" not in content and "present (failed)" not in content
            results["chrome_object"] = "window.chrome" in content and "missing" not in content
            
            # Evaluate specific JS properties
            is_webdriver = await page.evaluate("navigator.webdriver")
            results["webdriver_prop"] = is_webdriver # Should be false/undefined
            
            plugins_len = await page.evaluate("navigator.plugins.length")
            results["plugins_length"] = plugins_len
            
            logger.info("Canary check completed.")
            print(json.dumps(results, indent=2))
            
        except Exception as e:
            logger.error(f"Canary check failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-headless", action="store_true", help="Run headful")
    parser.add_argument("--mode", default="moderate", choices=["minimal", "moderate", "aggressive"])
    args = parser.parse_args()
    
    asyncio.run(run_canary(headless=not args.no_headless, mode=args.mode))
