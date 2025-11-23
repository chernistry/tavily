"""
Session management for persisting browser state (cookies, storage) across runs.
"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Manages persistence of browser sessions (cookies, local storage).
    """
    def __init__(self, data_dir: str = "data/sessions"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, session_id: str) -> Path:
        """Return the path to the session file."""
        # Sanitize session_id to prevent path traversal
        safe_id = "".join(c for c in session_id if c.isalnum() or c in ('-', '_'))
        return self.data_dir / f"{safe_id}.json"

    async def save_session(self, context: BrowserContext, session_id: str) -> None:
        """
        Save the current browser context state to disk.
        """
        if not session_id:
            return

        try:
            state = await context.storage_state()
            path = self._get_session_path(session_id)
            
            # Atomic write
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            temp_path.replace(path)
            
            logger.info(f"Saved session '{session_id}' to {path}")
        except Exception as e:
            logger.error(f"Failed to save session '{session_id}': {e}")

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a browser context state from disk.
        Returns None if session does not exist or is invalid.
        """
        if not session_id:
            return None

        path = self._get_session_path(session_id)
        if not path.exists():
            logger.info(f"Session '{session_id}' not found. Starting fresh.")
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            logger.info(f"Loaded session '{session_id}' from {path}")
            return state
        except Exception as e:
    def _get_profile_path(self, session_id: str) -> Path:
        """Return the path to the profile file."""
        safe_id = "".join(c for c in session_id if c.isalnum() or c in ('-', '_'))
        return self.data_dir / f"{safe_id}.profile.json"

    async def save_profile(self, session_id: str, profile_data: Dict[str, Any]) -> None:
        """Save the device profile associated with the session."""
        if not session_id:
            return
        
        try:
            path = self._get_profile_path(session_id)
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(profile_data, f, indent=2)
            temp_path.replace(path)
            logger.info(f"Saved profile for '{session_id}'")
        except Exception as e:
            logger.error(f"Failed to save profile for '{session_id}': {e}")

    def load_profile(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load the device profile associated with the session."""
        if not session_id:
            return None
            
        path = self._get_profile_path(session_id)
        if not path.exists():
            return None
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load profile for '{session_id}': {e}")
            return None
