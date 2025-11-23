"""
Captcha handling interfaces and default implementations.
"""

import os
import asyncio
from typing import Protocol, runtime_checkable

import httpx
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


class TwoCaptchaSolver:
    """
    Simple integration with 2captcha-like services for token-based CAPTCHAs.

    Supported vendors:
    - recaptcha v2/v3 (method: 'userrecaptcha')
    - hcaptcha (method: 'hcaptcha')
    - turnstile (method: 'turnstile')

    Notes:
    - Requires CAPTCHA_API_KEY in env (2captcha-compatible).
    - Expects a sitekey on the page (data-sitekey or known selectors).
    """

    def __init__(self, api_key: str, polling_interval: float = 5.0, timeout: float = 120.0) -> None:
        self.api_key = api_key
        self.polling_interval = polling_interval
        self.timeout = timeout

    async def solve(self, page: Page) -> bool:
        detection = await detect_captcha_playwright(page)
        if not detection["present"]:
            return False

        vendor = detection["vendor"]
        sitekey = await _extract_sitekey(page, vendor)
        if not sitekey:
            logger.warning("CAPTCHA detected but sitekey not found; skipping solver.")
            return False

        method = _captcha_method(vendor)
        if not method:
            logger.warning(f"CAPTCHA vendor {vendor} not supported by TwoCaptchaSolver.")
            return False

        page_url = page.url
        logger.info(f"Submitting CAPTCHA to 2captcha ({vendor}) for {page_url}")

        token = await _submit_and_poll_2captcha(
            api_key=self.api_key,
            method=method,
            sitekey=sitekey,
            pageurl=page_url,
            polling_interval=self.polling_interval,
            timeout=self.timeout,
        )

        if not token:
            logger.warning("2captcha did not return a token in time.")
            return False

        # Inject token based on vendor
        try:
            if vendor == "recaptcha":
                await page.evaluate(
                    """(token) => {
                        const form = document.querySelector('form') || document.body;
                        const textarea = document.createElement('textarea');
                        textarea.name = 'g-recaptcha-response';
                        textarea.style.display = 'none';
                        textarea.value = token;
                        form.appendChild(textarea);
                    }""",
                    token,
                )
            elif vendor == "hcaptcha":
                await page.evaluate(
                    """(token) => {
                        const form = document.querySelector('form') || document.body;
                        const textarea = document.createElement('textarea');
                        textarea.name = 'h-captcha-response';
                        textarea.style.display = 'none';
                        textarea.value = token;
                        form.appendChild(textarea);
                    }""",
                    token,
                )
            elif vendor == "turnstile":
                await page.evaluate(
                    """(token) => {
                        const form = document.querySelector('form') || document.body;
                        const textarea = document.createElement('textarea');
                        textarea.name = 'cf-turnstile-response';
                        textarea.style.display = 'none';
                        textarea.value = token;
                        form.appendChild(textarea);
                    }""",
                    token,
                )
            else:
                logger.warning(f"Unsupported vendor for token injection: {vendor}")
                return False

            # Some pages need an explicit submit; try a gentle submit if form exists
            await page.evaluate(
                """
                () => {
                  const form = document.querySelector('form');
                  if (form) {
                    form.submit();
                  }
                }
                """
            )
            await page.wait_for_load_state("networkidle")
            return True
        except Exception as exc:  # pragma: no cover - best-effort
            logger.warning(f"Failed to inject CAPTCHA token: {exc}")
            return False


async def _extract_sitekey(page: Page, vendor: str | None) -> str | None:
    """
    Try to extract sitekey for recaptcha/hcaptcha/turnstile.
    """
    try:
        if vendor in {"recaptcha", "hcaptcha", "turnstile"}:
            # Common attributes
            selectors = [
                "[data-sitekey]",
                "div.g-recaptcha",
                "div.h-captcha",
                "div.cf-turnstile",
            ]
            for sel in selectors:
                el = page.locator(sel)
                if await el.count() > 0:
                    key = await el.first.get_attribute("data-sitekey")
                    if key:
                        return key
    except Exception:
        return None
    return None


def _captcha_method(vendor: str | None) -> str | None:
    if vendor == "recaptcha":
        return "userrecaptcha"
    if vendor == "hcaptcha":
        return "hcaptcha"
    if vendor == "turnstile":
        return "turnstile"
    return None


async def _submit_and_poll_2captcha(
    api_key: str,
    method: str,
    sitekey: str,
    pageurl: str,
    polling_interval: float,
    timeout: float,
) -> str | None:
    """
    Submit a CAPTCHA to 2captcha and poll until solved.
    """
    submit_url = "http://2captcha.com/in.php"
    poll_url = "http://2captcha.com/res.php"

    payload = {
        "key": api_key,
        "method": method,
        "sitekey": sitekey,
        "pageurl": pageurl,
        "json": 1,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(submit_url, data=payload)
        data = resp.json()
        if data.get("status") != 1:
            logger.warning(f"2captcha submit failed: {data}")
            return None

        request_id = data.get("request")
        if not request_id:
            return None

        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(polling_interval)
            poll_resp = await client.get(
                poll_url, params={"key": api_key, "action": "get", "id": request_id, "json": 1}
            )
            poll_data = poll_resp.json()
            if poll_data.get("status") == 1:
                return poll_data.get("request")
            if poll_data.get("request") != "CAPCHA_NOT_READY":
                logger.warning(f"2captcha polling error: {poll_data}")
                return None

    return None


def get_solver_from_env() -> CaptchaSolver:
    """
    Return a solver instance based on environment.

    If CAPTCHA_API_KEY is set, use TwoCaptchaSolver; otherwise NoOp.
    """
    api_key = os.getenv("CAPTCHA_API_KEY")
    if api_key:
        return TwoCaptchaSolver(api_key=api_key)
    return NoOpSolver()
