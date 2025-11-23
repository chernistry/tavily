"""
Captcha handling interfaces and default implementations.
"""

from typing import Protocol, runtime_checkable

from playwright.async_api import Page

from tavily_scraper.utils.captcha import detect_captcha_playwright
from tavily_scraper.utils.logging import get_logger

logger = get_logger(__name__)


@runtime_checkable
class CaptchaSolver(Protocol):
    """
    Protocol for CAPTCHA solvers.
    """

    async def solve(self, page: Page) -> bool:
        """
        Attempt to solve the CAPTCHA on the current page.

        Args:
            page: Playwright page instance.

        Returns:
            True if solved successfully, False otherwise.
        """
        ...


class NoOpSolver:
    """
    Default solver that logs detection but does not attempt to solve.
    """

    async def solve(self, page: Page) -> bool:
        """
        Log detection and return False.
        """
        detection = await detect_captcha_playwright(page)
        if detection["present"]:
            logger.warning(
                f"CAPTCHA detected ({detection['vendor']}): {detection['reason']}. "
                "No solver configured."
            )
        return False
