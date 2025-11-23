import json
import shutil
import tempfile
from collections.abc import Generator
from unittest.mock import AsyncMock

import pytest

from tavily_scraper.stealth.session import SessionManager


class TestSessionManager:
    @pytest.fixture
    def temp_dir(self) -> Generator[str, None, None]:
        d = tempfile.mkdtemp()
        yield d
        shutil.rmtree(d)

    @pytest.fixture
    def manager(self, temp_dir: str) -> SessionManager:
        return SessionManager(data_dir=temp_dir)

    def test_get_session_path(self, manager: SessionManager) -> None:
        path = manager._get_session_path("test-user")
        assert path.name == "test-user.json"
        assert str(path.parent) == manager.data_dir.as_posix()

    def test_get_session_path_sanitization(self, manager: SessionManager) -> None:
        path = manager._get_session_path("../evil/path")
        # Should strip non-alnum chars except -_
        assert "evil" in path.name
        assert ".." not in path.name

    @pytest.mark.asyncio
    async def test_save_session(self, manager: SessionManager) -> None:
        context = AsyncMock()
        context.storage_state.return_value = {"cookies": [{"name": "foo", "value": "bar"}]}
        
        await manager.save_session(context, "user1")
        
        path = manager._get_session_path("user1")
        assert path.exists()
        
        with open(path) as f:
            data = json.load(f)
            assert data["cookies"][0]["name"] == "foo"

    def test_load_session_missing(self, manager: SessionManager) -> None:
        state = manager.load_session("nonexistent")
        assert state is None

    @pytest.mark.asyncio
    async def test_load_session_existing(self, manager: SessionManager) -> None:
        # Manually create a session file
        path = manager._get_session_path("user2")
        with open(path, "w") as f:
            json.dump({"cookies": [{"name": "baz", "value": "qux"}]}, f)
            
        state = manager.load_session("user2")
        assert state is not None
        assert state["cookies"][0]["value"] == "qux"
