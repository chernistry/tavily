"""
Behavioral stealth to simulate human interaction patterns.
"""

import asyncio
import random
import string

from playwright.async_api import Page

from tavily_scraper.stealth.config import StealthConfig


async def human_mouse_move(page: Page) -> None:
    """
    Simulate human-like mouse movement.

    Rather than a single jump, we move in a short path with pauses, letting
    Playwright interpolate between points with multiple steps.
    """
    viewport = page.viewport_size or {"width": 1280, "height": 800}
    width = viewport["width"]
    height = viewport["height"]

    # Start somewhere reasonably central on the screen
    current_x = random.randint(int(width * 0.2), int(width * 0.8))
    current_y = random.randint(int(height * 0.2), int(height * 0.8))

    await page.mouse.move(current_x, current_y, steps=random.randint(5, 15))

    # Perform a short "wandering" path with a few random points
    for _ in range(random.randint(1, 3)):
        target_x = random.randint(0, width)
        target_y = random.randint(0, height)
        steps = random.randint(10, 40)
        await asyncio.sleep(random.uniform(0.05, 0.2))
        await page.mouse.move(target_x, target_y, steps=steps)


async def human_scroll(page: Page) -> None:
    """
    Simulate human-like scrolling.

    Scrolls in smaller increments with pauses to mimic reading, and occasionally
    scrolls back a bit.
    """
    # Perform 1–3 scroll segments
    segments = random.randint(1, 3)
    for _ in range(segments):
        scroll_amount = random.randint(200, 600)
        await page.mouse.wheel(0, scroll_amount)
        await asyncio.sleep(random.uniform(0.4, 1.4))

    # Occasionally scroll back up a little (reading check)
    if random.random() < 0.3:
        await page.mouse.wheel(0, -random.randint(80, 180))
        await asyncio.sleep(random.uniform(0.2, 0.6))


async def human_type(page: Page, selector: str, text: str) -> None:
    """
    Simulate human-like typing with variable delays and occasional corrections.
    """
    element = page.locator(selector)
    await element.focus()

    for char in text:
        # Sometimes introduce a small typo and correct it
        if random.random() < 0.03:
            wrong_char = random.choice(string.ascii_letters)
            await page.keyboard.type(wrong_char, delay=random.uniform(30, 120))
            await page.keyboard.press("Backspace", delay=random.uniform(30, 120))

        delay_ms = random.uniform(50, 200)  # per-character delay in ms
        await page.keyboard.type(char, delay=delay_ms)

        # Occasional longer pause as if thinking
        if random.random() < 0.06:
            await asyncio.sleep(random.uniform(0.25, 0.8))


async def jitter_viewport(page: Page, config: StealthConfig) -> None:
    """
    Apply a small viewport change during the session to avoid static metrics.

    This should only be used when viewport_jitter is enabled; jitter is small
    enough to not break most responsive layouts.
    """
    if not (config.enabled and config.viewport_jitter):
        return

    viewport = page.viewport_size
    if not viewport:
        return

    width = viewport["width"]
    height = viewport["height"]

    # Tiny jitter to avoid pixel-identical fingerprints
    new_width = max(640, width + random.randint(-30, 30))
    new_height = max(480, height + random.randint(-30, 30))

    if new_width == width and new_height == height:
        return

    await page.set_viewport_size({"width": new_width, "height": new_height})
