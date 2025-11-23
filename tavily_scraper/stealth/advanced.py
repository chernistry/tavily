"""
Advanced stealth techniques including fingerprinting resistance and
network simulation.
"""

import random
from typing import Literal

from playwright.async_api import Page

from tavily_scraper.stealth.asset_loader import load_asset_text
from tavily_scraper.stealth.config import StealthConfig
from tavily_scraper.stealth.device_profiles import choose_webgl_profile


async def apply_advanced_stealth(page: Page, config: StealthConfig) -> None:
    """
    Apply advanced stealth techniques to the page.

    This focuses on:
    * Canvas and WebGL tweaks to make fingerprinting less stable
    * AudioContext noise to reduce audio fingerprint reliability
    * WebRTC surface masking to avoid IP/device leakage

    These techniques are more invasive than the core ones and should only be
    enabled when needed (typically in "moderate" or "aggressive" modes).
    """
    if not (config.enabled and config.fingerprint_evasions):
        return

    # Canvas noise injection.
    await page.add_init_script(load_asset_text("fingerprint_canvas.js"))

    # WebGL vendor spoofing based on configurable profiles.
    webgl_profile = choose_webgl_profile()
    webgl_script = (
        load_asset_text("fingerprint_webgl.js")
        .replace("__WEBGL_VENDOR__", webgl_profile.vendor)
        .replace("__WEBGL_RENDERER__", webgl_profile.renderer)
    )
    await page.add_init_script(webgl_script)

    # Audio fingerprint softening.
    await page.add_init_script(load_asset_text("fingerprint_audio.js"))

    # WebRTC masking (IP/device leakage) if enabled.
    if config.mask_webrtc:
        await page.add_init_script(load_asset_text("webrtc_mask.js"))


async def simulate_network_conditions(
    page: Page,
    profile: Literal["wifi", "dsl", "4g", "fast_3g", "slow_3g"] = "wifi",
) -> None:
    """
    Simulate realistic network conditions (throttling).

    We use a small set of coarse profiles rather than fully random values so
    that behavior is realistic but still varied across runs.
    """

    if not page.context:
        return

    if profile == "slow_3g":
        download = 400 * 1024
        upload = 150 * 1024
        latency = random.randint(400, 600)
    elif profile == "fast_3g":
        download = int(1.6 * 1024 * 1024)
        upload = int(750 * 1024)
        latency = random.randint(150, 300)
    elif profile == "4g":
        download = int(12 * 1024 * 1024)
        upload = int(4 * 1024 * 1024)
        latency = random.randint(50, 100)
    elif profile == "dsl":
        download = int(5 * 1024 * 1024)
        upload = int(1 * 1024 * 1024)
        latency = random.randint(30, 70)
    else:  # wifi (default)
        download = int(30 * 1024 * 1024)
        upload = int(15 * 1024 * 1024)
        latency = random.randint(10, 40)

    # CDP session is Chromium-specific; guard in case of future engine changes.
    try:
        client = await page.context.new_cdp_session(page)
        await client.send(
            "Network.emulateNetworkConditions",
            {
                "offline": False,
                "latency": latency,
                "downloadThroughput": int(download),
                "uploadThroughput": int(upload),
            },
        )
    except Exception:
        # If emulation fails, we simply continue without throttling.
        return
