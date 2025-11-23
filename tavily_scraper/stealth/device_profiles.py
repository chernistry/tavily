"""
Helpers for loading device, geolocation, and WebGL profiles from data files.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

from tavily_scraper.stealth.config import StealthConfig


@dataclass(frozen=True)
class DeviceProfile:
    name: str
    user_agent: str
    viewport_width: int
    viewport_height: int
    locale: str
    timezone_id: str
    region: str = "US"  # Default to US if missing

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "user_agent": self.user_agent,
            "viewport_width": self.viewport_width,
            "viewport_height": self.viewport_height,
            "locale": self.locale,
            "timezone_id": self.timezone_id,
            "region": self.region,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceProfile:
        return cls(**data)


@dataclass(frozen=True)
class GeoProfile:
    name: str
    latitude: float
    longitude: float
    accuracy: float
    region: str = "US"


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
def _device_profiles() -> list[DeviceProfile]:
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
                region="US",
            )
        ]


@lru_cache(maxsize=1)
def _geo_profiles() -> list[GeoProfile]:
    try:
        raw = _load_json_resource("geolocations.json")
        return [GeoProfile(**item) for item in raw]
    except Exception:
        return []


@lru_cache(maxsize=1)
def _webgl_profiles() -> list[WebGLProfile]:
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


def choose_device_profile(region: str | None = None) -> DeviceProfile:
    profiles = _device_profiles()
    if region:
        filtered = [p for p in profiles if p.region == region]
        if filtered:
            return random.choice(filtered)
    return random.choice(profiles)


def choose_geo_profile(region: str | None = None) -> GeoProfile | None:
    profiles = _geo_profiles()
    if not profiles:
        return None
    if region:
        filtered = [p for p in profiles if p.region == region]
        if filtered:
            return random.choice(filtered)
    return random.choice(profiles)


def choose_webgl_profile() -> WebGLProfile:
    profiles = _webgl_profiles()
    return random.choice(profiles)


def build_context_options(
    config: StealthConfig,
    profile: DeviceProfile | None = None,
    target_region: str | None = None,
) -> tuple[dict[str, Any], DeviceProfile]:
    """
    Build kwargs for browser.new_context based on a device profile and config.
    Returns the options dict and the profile used.
    """
    if profile is None:
        profile = choose_device_profile(region=target_region)

    width = profile.viewport_width
    height = profile.viewport_height

    if config.mode in ("moderate", "aggressive"):
        width = max(800, width + random.randint(-40, 40))
        height = max(600, height + random.randint(-40, 40))

    viewport = {"width": width, "height": height}

    options: dict[str, Any] = {"viewport": viewport}

    if config.spoof_user_agent:
        options["user_agent"] = profile.user_agent

    options["locale"] = profile.locale
    options["timezone_id"] = profile.timezone_id

    if config.random_geolocation:
        geo = choose_geo_profile(region=target_region)
        # If we have a target region but no geo profile found (unlikely), we might want to fallback?
        # But choose_geo_profile falls back to random if filtered is empty? 
        # No, my implementation above returns random.choice(profiles) if filtered is empty? 
        # No, it returns random.choice(profiles) only if region is None.
        # Wait, my implementation:
        # if region:
        #    filtered = ...
        #    if filtered: return random.choice(filtered)
        # return random.choice(profiles)
        # So if filtered is empty, it falls back to ANY profile. This is good.
        
        if geo:
            geo_payload = {
                "latitude": geo.latitude + random.uniform(-0.02, 0.02),
                "longitude": geo.longitude + random.uniform(-0.02, 0.02),
                "accuracy": max(20, geo.accuracy + random.uniform(-10, 10)),
            }
            options["geolocation"] = geo_payload
            options["permissions"] = ["geolocation"]

    return options, profile

