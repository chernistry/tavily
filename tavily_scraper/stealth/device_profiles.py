"""
Device profiles and helpers for creating Playwright contexts that look like
real browsers (UA + viewport + locale + timezone).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import random

from tavily_scraper.stealth.config import StealthConfig


@dataclass(frozen=True)
class DeviceProfile:
    """
    A coarse device profile used to configure Playwright contexts.

    The goal is not perfect impersonation, but to avoid obviously synthetic
    defaults (single UA, fixed viewport, no locale/timezone).
    """

    name: str
    user_agent: str
    viewport_width: int
    viewport_height: int
    locale: str
    timezone_id: str


_DESKTOP_PROFILES: List[DeviceProfile] = [
    DeviceProfile(
        name="desktop_chrome_win10_us",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport_width=1920,
        viewport_height=1080,
        locale="en-US",
        timezone_id="America/New_York",
    ),
    DeviceProfile(
        name="desktop_chrome_mac",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport_width=1440,
        viewport_height=900,
        locale="en-US",
        timezone_id="America/Los_Angeles",
    ),
    DeviceProfile(
        name="desktop_firefox_win10",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
            "Gecko/20100101 Firefox/125.0"
        ),
        viewport_width=1366,
        viewport_height=768,
        locale="en-US",
        timezone_id="Europe/Berlin",
    ),
]


def _choose_profile() -> DeviceProfile:
    """
    Pick a random desktop profile.

    For now we bias toward desktop, as it matches most scraping workloads in
    this project. Mobile profiles could be added later if needed.
    """

    return random.choice(_DESKTOP_PROFILES)


def build_context_options(config: StealthConfig) -> Dict[str, Any]:
    """
    Build kwargs for browser.new_context based on a device profile and config.

    The intent is to:
    * Avoid Playwright's static defaults (UA and viewport)
    * Keep viewport/locale/timezone consistent enough to look like a real user
    * Introduce small jitter so multiple contexts are not pixel-identical
    * Optionally set a plausible geolocation (with permission)
    """

    profile = _choose_profile()

    width = profile.viewport_width
    height = profile.viewport_height

    # Add small jitter in non-minimal modes so fingerprints are not identical
    if config.mode in ("moderate", "aggressive"):
        width = max(800, width + random.randint(-40, 40))
        height = max(600, height + random.randint(-40, 40))

    viewport = {"width": width, "height": height}

    options: Dict[str, Any] = {
        "viewport": viewport,
    }

    if config.spoof_user_agent:
        options["user_agent"] = profile.user_agent

    # Locale and timezone help line up with typical real-world profiles
    options["locale"] = profile.locale
    options["timezone_id"] = profile.timezone_id

    if config.random_geolocation:
        # Coarse, plausible geolocations; tied loosely to timezones above.
        geo_pool = [
            {"latitude": 40.7128, "longitude": -74.0060},   # New York
            {"latitude": 34.0522, "longitude": -118.2437},  # LA
            {"latitude": 52.5200, "longitude": 13.4050},    # Berlin
            {"latitude": 37.7749, "longitude": -122.4194},  # SF
        ]
        geo = random.choice(geo_pool)
        # Small jitter to avoid exact duplicates
        geo = {
            "latitude": geo["latitude"] + random.uniform(-0.02, 0.02),
            "longitude": geo["longitude"] + random.uniform(-0.02, 0.02),
            "accuracy": random.uniform(20, 120),
        }
        options["geolocation"] = geo
        options["permissions"] = ["geolocation"]

    return options
