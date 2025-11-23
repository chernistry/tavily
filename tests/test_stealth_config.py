"""
Tests for stealth configuration.
"""

import os
from unittest import mock

from tavily_scraper.config.env import load_run_config
from tavily_scraper.stealth.config import StealthConfig


def test_stealth_config_defaults() -> None:
    """Verify default values."""
    config = StealthConfig()
    assert config.enabled is False
    assert config.mode == "moderate"
    assert config.headless is True


def test_run_config_integration() -> None:
    """Verify RunConfig includes StealthConfig."""
    with mock.patch.dict(os.environ, {}, clear=True):
        config = load_run_config()
        assert config.stealth_config is not None
        assert config.stealth_config.enabled is False
