# Ticket: Sticky Device Profiles & Fingerprint Consistency

**ID**: STEALTH-08
**Type**: Feature
**Status**: Open
**Priority**: High
**Estimated Complexity**: M

## Objective
Update the profile management system to support "sticky" identities. Currently, `device_profiles.py` returns a random profile every time. This ticket links a specific `DeviceProfile` (UA, Screen, WebGL vendor) to a persisted `session_id`. This ensures that when we resume a session, we don't suddenly change from "Chrome on MacOS" to "Firefox on Windows", which is a guaranteed ban flag.

## Requirements
1.  **Profile Persistence**: Store the `DeviceProfile` metadata alongside the session `storageState`.
2.  **Consistency Checks**: Ensure that the generated profile is internally consistent (e.g., if UA is MacOS, WebGL renderer should be Apple/Intel/AMD, not "Microsoft Basic Render Driver").
3.  **Profile Factory**: A mechanism to generate valid, consistent profiles based on a seed or requirements.

## Implementation Details
-   **Files to Create/Modify**:
    -   `[MODIFY] tavily_scraper/stealth/device_profiles.py`: Add serialization and consistency logic.
    -   `[MODIFY] tavily_scraper/stealth/session.py`: Update `SessionManager` to save/load profile data.
    -   `[MODIFY] tavily_scraper/pipelines/browser_fetcher.py`: Use the loaded profile for context creation.

-   **Key Logic**:
    -   `get_or_create_profile(session_id)`: Returns existing profile if session exists, else generates new one.
    -   Validate `navigator.platform` matches User-Agent OS.

## Acceptance Criteria
-   [ ] A session ID always yields the same User-Agent, Viewport, and WebGL parameters across restarts.
-   [ ] Generated profiles are internally consistent (OS matches UA, etc.).
-   [ ] "Sticky" behavior works in tandem with STEALTH-07 (Session Persistence).

## Testing Approach
-   **Unit Test**: Generate profile for `session_A`, save. Generate again for `session_A`, assert equality.
-   **Manual Verification**: Run with `--session-id sticky_test` against `https://bot.sannysoft.com/`. Restart. Verify fingerprints (Canvas hash, WebGL vendor) remain identical.

## Dependencies
-   STEALTH-07 (Session Persistence)
