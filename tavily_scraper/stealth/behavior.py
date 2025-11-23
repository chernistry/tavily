"""
Behavioral stealth to simulate human interaction patterns.
"""

import asyncio
import random

from playwright.async_api import Page


async def human_mouse_move(page: Page) -> None:
    """
    Simulate human-like mouse movement.
    Moves the mouse to random coordinates with a curve.
    """
    width = page.viewport_size["width"] if page.viewport_size else 1280
    height = page.viewport_size["height"] if page.viewport_size else 800

    # Random target
    x = random.randint(0, width)
    y = random.randint(0, height)

    # Playwright's mouse.move already simulates steps if provided
    # We add some randomness to steps to make it look less robotic
    steps = random.randint(5, 25)
    await page.mouse.move(x, y, steps=steps)


async def human_scroll(page: Page) -> None:
    """
    Simulate human-like scrolling.
    Scrolls down a bit, maybe pauses, maybe scrolls up a tiny bit.
    """
    # Scroll down a random amount
    scroll_amount = random.randint(300, 800)
    await page.mouse.wheel(0, scroll_amount)
    
    # Random pause to simulate reading
    await asyncio.sleep(random.uniform(0.5, 1.5))

    # Occasionally scroll back up a little (reading check)
    if random.random() < 0.3:
        await page.mouse.wheel(0, -random.randint(50, 150))
        await asyncio.sleep(random.uniform(0.2, 0.5))


async def human_type(page: Page, selector: str, text: str) -> None:
    """
    Simulate human-like typing with variable delays.
    """
    element = page.locator(selector)
    await element.focus()
    
    for char in text:
        delay = random.uniform(0.05, 0.2)  # 50ms to 200ms per keystroke
        await page.keyboard.type(char, delay=delay * 1000)
        
        # Occasional longer pause
        if random.random() < 0.05:
            await asyncio.sleep(random.uniform(0.3, 0.8))
