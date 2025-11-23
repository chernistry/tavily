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
        enabled: Whether stealth mode is enabled globally.
        mode: Stealth intensity mode (minimal, moderate, aggressive).
        headless: Whether to run in headless mode (overrides main config if set).
        spoof_user_agent: Whether to rotate/spoof User-Agent.
        spoof_webdriver: Whether to hide navigator.webdriver.
        simulate_human_behavior: Whether to add random delays and mouse movements.
        block_resources: Whether to block images/fonts for speed (and stealth trade-off).
    """

    enabled: bool = False
    mode: Literal["minimal", "moderate", "aggressive"] = "moderate"
    headless: bool = True
    spoof_user_agent: bool = True
    spoof_webdriver: bool = True
    simulate_human_behavior: bool = True
    block_resources: bool = True
