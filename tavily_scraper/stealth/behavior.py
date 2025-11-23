"""
Behavioral stealth to simulate human interaction patterns.
"""

import asyncio
import random
import string

from playwright.async_api import Page

from tavily_scraper.stealth.config import StealthConfig


def _bezier_point(t: float, p0: tuple[int, int], p1: tuple[int, int], p2: tuple[int, int], p3: tuple[int, int]) -> tuple[int, int]:
    """Calculate point on a cubic Bezier curve at time t (0..1)."""
    u = 1 - t
    tt = t * t
    uu = u * u
    uuu = uu * u
    ttt = tt * t

    x = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
    y = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
    return int(x), int(y)


def generate_mouse_path(
    start: tuple[int, int],
    end: tuple[int, int],
    steps: int = 20,
    deviation: int = 50
) -> list[tuple[int, int]]:
    """
    Generate a human-like mouse path using a cubic Bezier curve.
    
    Args:
        start: (x, y) starting point
        end: (x, y) ending point
        steps: Number of points in the path
        deviation: Magnitude of control point deviation for curvature
    
    Returns:
        List of (x, y) coordinates
    """
    # Control points for Bezier curve
    # Randomly offset control points to create curvature
    # p1 is roughly 1/3 way, p2 is roughly 2/3 way
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    
    p0 = start
    p3 = end
    
    # Add randomness to control points
    p1 = (
        int(start[0] + dx * 0.33 + random.randint(-deviation, deviation)),
        int(start[1] + dy * 0.33 + random.randint(-deviation, deviation))
    )
    p2 = (
        int(start[0] + dx * 0.66 + random.randint(-deviation, deviation)),
        int(start[1] + dy * 0.66 + random.randint(-deviation, deviation))
    )

    path = []
    # Non-linear time steps (ease-in-out)
    for i in range(steps + 1):
        t = i / steps
        # Apply easing function to t for speed variation (slower at ends, faster in middle)
        # Sigmoid-like: t = t*t / (2* (t*t - t) + 1)
        # Or simple smoothstep: t * t * (3 - 2 * t)
        eased_t = t * t * (3 - 2 * t)
        path.append(_bezier_point(eased_t, p0, p1, p2, p3))
        
    return path


async def human_mouse_move(page: Page, config: StealthConfig | None = None) -> None:
    """
    Simulate human-like mouse movement using Bezier curves and variable speed.
    """
    profile = config.behavior_profile if config else "default"
    
    # Minimal profile: Use simple movement to save time
    if profile == "minimal":
        viewport = page.viewport_size or {"width": 1280, "height": 800}
        x = random.randint(0, viewport["width"])
        y = random.randint(0, viewport["height"])
        await page.mouse.move(x, y, steps=5)
        return

    viewport = page.viewport_size or {"width": 1280, "height": 800}
    width = viewport["width"]
    height = viewport["height"]

    # Current position? Playwright doesn't expose it directly easily without tracking.
    # We'll assume start is random or last known (but we don't track last known here).
    # Let's start from a random edge or center region.
    start_x = random.randint(int(width * 0.1), int(width * 0.9))
    start_y = random.randint(int(height * 0.1), int(height * 0.9))
    
    # Move to start first (instant or fast)
    # await page.mouse.move(start_x, start_y, steps=1) 
    # Actually, we should just move from wherever the mouse is. 
    # If we don't know, Playwright defaults to 0,0.
    # Let's just move to a target.
    
    target_x = random.randint(int(width * 0.1), int(width * 0.9))
    target_y = random.randint(int(height * 0.1), int(height * 0.9))

    # Generate path
    steps = random.randint(20, 50) if profile == "aggressive" else random.randint(15, 30)
    path = generate_mouse_path((start_x, start_y), (target_x, target_y), steps=steps)

    # Execute move along path
    for point in path:
        await page.mouse.move(point[0], point[1], steps=1)
        # Micro-sleeps between points for "physics" feel? 
        # Playwright's mouse.move already interpolates if steps > 1.
        # But we are doing steps=1 for each point in OUR path.
        # So we control the timing.
        # Fast in middle, slow at ends is handled by eased_t in path generation?
        # No, eased_t distributes points. 
        # If we sleep constant time, points closer together (ends) will be slower.
        # Points further apart (middle) will be faster.
        # So constant sleep is fine.
        await asyncio.sleep(random.uniform(0.001, 0.005))

    # "Overshoot" or "correction" behavior could be added here for aggressive mode.


async def human_scroll(page: Page, config: StealthConfig | None = None) -> None:
    """
    Simulate human-like scrolling with reading patterns.
    """
    profile = config.behavior_profile if config else "default"
    
    if profile == "minimal":
        await page.mouse.wheel(0, random.randint(300, 800))
        return

    # Reading pattern: Scroll -> Pause (Read) -> Scroll -> ... -> Occasional Scroll Back
    
    # Aggressive: More segments, more variable
    segments = random.randint(3, 6) if profile == "aggressive" else random.randint(2, 4)
    
    for _ in range(segments):
        # Scroll down
        scroll_amount = random.randint(150, 500)
        # Smooth scroll (simulated by multiple small wheels or just one wheel with steps? 
        # Playwright wheel is instant. We can break it up.)
        
        # Break up large scrolls
        steps = 5
        step_y = scroll_amount / steps
        for _ in range(steps):
            await page.mouse.wheel(0, step_y)
            await asyncio.sleep(random.uniform(0.01, 0.05))
            
        # Reading pause
        # Pause longer if it's a "long read"
        pause = random.uniform(0.5, 2.0)
        if random.random() < 0.2: # 20% chance of long pause
            pause += random.uniform(1.0, 3.0)
            
        await asyncio.sleep(pause)

        # Occasional scroll back (re-reading)
        if random.random() < 0.25:
            back_amount = random.randint(50, 200)
            await page.mouse.wheel(0, -back_amount)
            await asyncio.sleep(random.uniform(0.5, 1.5))


async def human_type(page: Page, selector: str, text: str, config: StealthConfig | None = None) -> None:
    """
    Simulate human-like typing with variable delays, thinking pauses, and typos.
    """
    profile = config.behavior_profile if config else "default"
    
    element = page.locator(selector)
    await element.focus()
    
    if profile == "minimal":
        await page.keyboard.type(text, delay=random.randint(10, 50))
        return

    # Typing speed profile
    # Fast typist: 30-80ms
    # Slow typist: 100-200ms
    # We'll mix it up.
    base_delay_min = 40
    base_delay_max = 150
    
    if profile == "aggressive":
        # More "human" noise
        typo_rate = 0.05
        thinking_rate = 0.08
    else:
        typo_rate = 0.02
        thinking_rate = 0.04

    for char in text:
        # Typo simulation
        if random.random() < typo_rate:
            wrong_char = random.choice(string.ascii_letters)
            await page.keyboard.type(wrong_char, delay=random.uniform(base_delay_min, base_delay_max))
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.keyboard.press("Backspace", delay=random.uniform(base_delay_min, base_delay_max))
            
        # Thinking pause (e.g. at word boundaries or random)
        if char == ' ' and random.random() < thinking_rate:
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
        # Variable delay
        delay = random.uniform(base_delay_min, base_delay_max)
        await page.keyboard.type(char, delay=delay)


async def jitter_viewport(page: Page, config: StealthConfig) -> None:
    """
    Apply a small viewport change during the session to avoid static metrics.
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

