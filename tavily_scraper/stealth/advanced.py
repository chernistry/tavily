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
    profile: Literal["fast_3g", "slow_3g", "4g"] = "fast_3g",
) -> None:
    """
    Simulate realistic network conditions (throttling).

    We use a small set of coarse profiles rather than fully random values so
    that behavior is realistic but still varied across runs.
    """

    if not page.context:
        return

    if profile == "slow_3g":
        download = 750 * 1024  # ~0.75 Mbps
        upload = 250 * 1024  # ~0.25 Mbps
        latency = random.randint(150, 400)
    elif profile == "4g":
        download = int(10 * 1024 * 1024)  # ~10 Mbps
        upload = int(3 * 1024 * 1024)  # ~3 Mbps
        latency = random.randint(20, 80)
    else:  # fast_3g default
        download = int(1.6 * 1024 * 1024)  # ~1.6 Mbps
        upload = int(750 * 1024)  # ~0.75 Mbps
        latency = random.randint(80, 200)

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
