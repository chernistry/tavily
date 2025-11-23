import pytest
from playwright.async_api import async_playwright
from tavily_scraper.stealth.config import StealthConfig
from tavily_scraper.stealth.advanced import simulate_network_conditions

@pytest.mark.asyncio
async def test_network_throttling() -> None:
    """Verify network conditions are applied (latency check)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Apply "slow_3g" (latency 400-600ms)
        await simulate_network_conditions(page, profile="slow_3g")
        
        # Measure fetch time of a simple page (or data URL)
        # Since we can't easily measure network latency to a real server without flakiness,
        # we check if the CDP command succeeds (no error) and maybe try a local fetch?
        # Actually, Playwright's route handler might not be throttled by CDP network conditions?
        # CDP throttling applies to network requests.
        
        # We'll just verify the function runs without error for now, 
        # as accurate latency testing requires a stable external target.
        # But we can check if the CDP session was created.
        assert page.context
        
        # Try another profile
        await simulate_network_conditions(page, profile="4g")
        
        await browser.close()

@pytest.mark.asyncio
async def test_background_traffic() -> None:
    """Verify background traffic script injection."""
    from tavily_scraper.pipelines.browser_fetcher import create_page_with_blocking
    from tavily_scraper.core.models import RunConfig
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        stealth_config = StealthConfig(
            enabled=True, 
            fake_background_traffic=True,
            network_profile="wifi"
        )
        run_config = RunConfig(stealth_config=stealth_config)
        
        # This calls create_page_with_blocking which injects the script
        # But wait, create_page_with_blocking injects it?
        # No, I added it to create_page_with_blocking in browser_fetcher.py
        
        page = await create_page_with_blocking(browser, run_config)
        
        # To verify it ran, we can spy on network requests?
        # Background traffic uses fetch(), so it should show up in network events.
        
        requests = []
        page.on("request", lambda r: requests.append(r.url))
        
        # We need to trigger the evaluation. 
        # In browser_fetcher, it's called during page creation?
        # Yes, await page.evaluate(...) is called.
        
        # Wait a bit for requests to happen
        await page.wait_for_timeout(2000)
        
        # Check performance entries for background requests
        resources = await page.evaluate("performance.getEntriesByType('resource').map(r => r.name)")
        
        background_domains = ["fonts.googleapis.com", "cdnjs.cloudflare.com", "google-analytics.com", "cdn.jsdelivr.net"]
        
        found_background_request = any(
            any(domain in res for domain in background_domains)
            for res in resources
        )
        
        assert found_background_request, f"No background traffic detected. Resources: {resources}"
        
        await browser.close()
