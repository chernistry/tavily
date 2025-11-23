"""
Configuration models for the stealth module.
"""

from __future__ import annotations

from typing import Literal

import msgspec


class StealthConfig(msgspec.Struct, omit_defaults=True):
    """
    Configuration for stealth and anti-detection features.

    Attributes:
        enabled:
            Whether stealth mode is enabled globally.
        mode:
            Stealth intensity mode (minimal, moderate, aggressive).
            Higher modes enable more expensive techniques.
        headless:
            Whether to run in headless mode (overrides main config if set).
        spoof_user_agent:
            Whether to rotate/spoof User-Agent at the context level.
        spoof_webdriver:
            Whether to hide navigator.webdriver and related automation flags.
        simulate_human_behavior:
            Whether to add random delays and mouse movements / scrolling.
        block_resources:
            Whether to block heavy static assets (images, fonts, media) to
            reduce bandwidth. This is primarily a performance toggle, but it
            also keeps behavior closer to a "reader" than a full UI client.
        fingerprint_evasions:
            Whether to enable advanced fingerprinting evasions such as canvas,
            WebGL, and audio tweaks (applied in the advanced module).
        mask_webrtc:
            Whether to mask WebRTC surface (IP leakage, device list).
        random_geolocation:
            Whether to set a plausible geolocation on the context; useful when
            aligning timezone/locale with a location.
        viewport_jitter:
            Whether to apply small viewport resizes during the session so that
            window metrics are not perfectly static.
    """

    enabled: bool = False
    mode: Literal["minimal", "moderate", "aggressive"] = "moderate"
    headless: bool = True
    spoof_user_agent: bool = True
    spoof_webdriver: bool = True
    simulate_human_behavior: bool = True
    block_resources: bool = True
    fingerprint_evasions: bool = True
    mask_webrtc: bool = True
    random_geolocation: bool = False
    viewport_jitter: bool = True
    behavior_profile: Literal["minimal", "default", "aggressive"] = "default"
    network_profile: Literal["wifi", "dsl", "4g", "fast_3g", "slow_3g"] = "wifi"
    fake_background_traffic: bool = False
    target_region: Literal["US", "EU", "APAC"] | None = None
