"""
Core stealth techniques to evade basic bot detection.
"""

from playwright.async_api import Page

from tavily_scraper.stealth.config import StealthConfig


async def apply_core_stealth(page: Page, config: StealthConfig) -> None:
    """
    Apply core stealth techniques to the page.

    Args:
        page: Playwright page instance.
        config: Stealth configuration.
    """
    if not config.enabled:
        return

    if config.spoof_webdriver:
        await page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """
        )

    if config.spoof_user_agent:
        # Note: Playwright handles UA via context, but we can override/ensure here
        # or add more specific navigator property mocks if needed.
        # For now, we rely on the context-level UA string, but we can add
        # platform spoofing to match UA.
        await page.add_init_script(
            """
            // Mock languages to look like a normal user
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });

            // Mock plugins to look like a normal browser (deprecated but checked by some)
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            """
        )

    # Hide automation flags
    await page.add_init_script(
        """
        // Pass the "Chrome" test
        window.chrome = {
            runtime: {}
        };

        // Pass the "Permissions" test
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
        );
        """
    )
