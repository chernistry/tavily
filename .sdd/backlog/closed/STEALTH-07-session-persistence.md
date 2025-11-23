# Ticket: Session Persistence & Trust Building

**ID**: STEALTH-07
**Type**: Feature
**Status**: Open
**Priority**: High
**Estimated Complexity**: M

## Objective
Implement a `SessionManager` to persist browser state (cookies, `localStorage`, `sessionStorage`, `IndexedDB`) across runs. Currently, every scraper execution starts with a clean slate, which is suspicious behavior for repeated visits to the same domain. Persisting state allows the scraper to "age" its accounts/fingerprints and build trust scores with anti-bot systems.

## Requirements
1.  **State Persistence**: Save Playwright's `storageState` to disk (JSON) after successful runs.
2.  **Session Loading**: Ability to initialize a browser context with a saved state.
3.  **Session Management**:
    -   Support named sessions (e.g., `--session-id <id>`).
    -   Auto-rotation policy: Retire sessions that get blocked or CAPTCHA'd too often.
4.  **Security**: Ensure session files (cookies) are stored securely and git-ignored.

## Implementation Details
-   **Files to Create/Modify**:
    -   `[NEW] tavily_scraper/stealth/session.py`: `SessionManager` class.
    -   `[MODIFY] tavily_scraper/pipelines/browser_fetcher.py`: Integrate session loading/saving.
    -   `[MODIFY] tavily_scraper/cli.py`: Add `--session-id` flag.

-   **Key Components**:
    -   `SessionManager.save_session(context, session_id)`
    -   `SessionManager.load_session(session_id) -> storage_state`
    -   `SessionManager.rotate_session(session_id)`

## Acceptance Criteria
-   [ ] Running the scraper with `--session-id test_user` twice results in the second run having the cookies from the first run.
-   [ ] `storageState` is correctly saved to `data/sessions/` after a scrape.
-   [ ] If a session file is corrupt or missing, the system gracefully falls back to a fresh session.
-   [ ] Session data includes cookies and local storage.

## Testing Approach
-   **Unit Test**: Mock Playwright context, save state, assert file exists. Load state, assert context is initialized with it.
-   **Integration**: Visit a site that sets a counter cookie (e.g., httpbin or a local test server). Run scraper twice. Verify counter increments instead of resetting.

## Dependencies
-   STEALTH-01 (Architecture)
