import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from tavily_scraper.stealth.device_profiles import DeviceProfile
from tavily_scraper.stealth.session import SessionManager

class TestStickyProfiles:
    @pytest.fixture
    def temp_dir(self):
        d = tempfile.mkdtemp()
        yield d
        shutil.rmtree(d)

    @pytest.fixture
    def manager(self, temp_dir):
        return SessionManager(data_dir=temp_dir)

    def test_device_profile_serialization(self):
        profile = DeviceProfile(
            name="test_profile",
            user_agent="Mozilla/5.0 Test",
            viewport_width=1024,
            viewport_height=768,
            locale="en-US",
            timezone_id="UTC"
        )
        data = profile.to_dict()
        assert data["name"] == "test_profile"
        
        reconstructed = DeviceProfile.from_dict(data)
        assert reconstructed == profile

    @pytest.mark.asyncio
    async def test_save_load_profile(self, manager):
        profile_data = {
            "name": "sticky_profile",
            "user_agent": "StickyAgent/1.0",
            "viewport_width": 1920,
            "viewport_height": 1080,
            "locale": "fr-FR",
            "timezone_id": "Europe/Paris"
        }
        
        await manager.save_profile("user_sticky", profile_data)
        
        loaded = manager.load_profile("user_sticky")
        assert loaded is not None
        assert loaded["user_agent"] == "StickyAgent/1.0"
        
        # Verify file exists
        path = manager._get_profile_path("user_sticky")
        assert path.exists()
        assert path.name == "user_sticky.profile.json"

    def test_load_missing_profile(self, manager):
        loaded = manager.load_profile("ghost_user")
        assert loaded is None
