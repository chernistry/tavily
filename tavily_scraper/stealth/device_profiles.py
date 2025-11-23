"""
Helpers for loading device, geolocation, and WebGL profiles from data files.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any, Dict, List

from tavily_scraper.stealth.config import StealthConfig


@dataclass(frozen=True)
class DeviceProfile:
    name: str
    user_agent: str
    viewport_width: int
    viewport_height: int
    locale: str
    timezone_id: str


@dataclass(frozen=True)
class GeoProfile:
    name: str
    latitude: float
    longitude: float
    accuracy: float


@dataclass(frozen=True)
class WebGLProfile:
    name: str
    vendor: str
    renderer: str


def _load_json_resource(filename: str) -> Any:
    pkg = "tavily_scraper.stealth.config_data"
    path = resources.files(pkg).joinpath(filename)
    if not path.is_file():
        raise FileNotFoundError(f"Stealth config data not found: {filename}")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _device_profiles() -> List[DeviceProfile]:
    try:
        raw = _load_json_resource("device_profiles.json")
        return [DeviceProfile(**item) for item in raw]
    except Exception:
        # Fallback to a minimal built-in profile if data files are unavailable
        return [
            DeviceProfile(
                name="fallback_desktop",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport_width=1366,
                viewport_height=768,
                locale="en-US",
                timezone_id="America/New_York",
            )
        ]


@lru_cache(maxsize=1)
def _geo_profiles() -> List[GeoProfile]:
    try:
        raw = _load_json_resource("geolocations.json")
        return [GeoProfile(**item) for item in raw]
    except Exception:
        return []


@lru_cache(maxsize=1)
def _webgl_profiles() -> List[WebGLProfile]:
    try:
        raw = _load_json_resource("webgl_profiles.json")
        return [WebGLProfile(**item) for item in raw]
    except Exception:
        return [
            WebGLProfile(
                name="fallback",
                vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
            )
        ]


def choose_device_profile() -> DeviceProfile:
    profiles = _device_profiles()
    return random.choice(profiles)


def choose_geo_profile() -> GeoProfile | None:
    profiles = _geo_profiles()
    if not profiles:
        return None
    return random.choice(profiles)


def choose_webgl_profile() -> WebGLProfile:
    profiles = _webgl_profiles()
    return random.choice(profiles)


def build_context_options(config: StealthConfig) -> Dict[str, Any]:
    """
    Build kwargs for browser.new_context based on a device profile and config.
    """
    profile = choose_device_profile()

    width = profile.viewport_width
    height = profile.viewport_height

    if config.mode in ("moderate", "aggressive"):
        width = max(800, width + random.randint(-40, 40))
        height = max(600, height + random.randint(-40, 40))

    viewport = {"width": width, "height": height}

    options: Dict[str, Any] = {"viewport": viewport}

    if config.spoof_user_agent:
        options["user_agent"] = profile.user_agent

    options["locale"] = profile.locale
    options["timezone_id"] = profile.timezone_id

    if config.random_geolocation:
        geo = choose_geo_profile()
        if geo:
            geo_payload = {
                "latitude": geo.latitude + random.uniform(-0.02, 0.02),
                "longitude": geo.longitude + random.uniform(-0.02, 0.02),
                "accuracy": max(20, geo.accuracy + random.uniform(-10, 10)),
            }
            options["geolocation"] = geo_payload
            options["permissions"] = ["geolocation"]

    return options

