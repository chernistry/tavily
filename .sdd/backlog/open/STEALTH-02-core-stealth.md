# Ticket: Core Stealth Techniques (Must-Have)

**ID**: STEALTH-02
**Type**: Feature
**Status**: Open
**Priority**: Critical
**Estimated Complexity**: M

## Objective
Implement the essential "must-have" stealth techniques that prevent immediate bot detection. These are the highest ROI techniques with the lowest performance overhead.

## Requirements
1.  **Random User-Agent**: Rotate User-Agent strings per browser context using `Faker` or a curated list.
2.  **Hide Automation Flags**:
    -   Remove `navigator.webdriver`.
    -   Disable `blink-features=AutomationControlled`.
3.  **Hide WebRTC/AudioContext**: Prevent IP leaks and fingerprinting via WebRTC and AudioContext.

## Implementation Details
-   **Files to Create/Modify**:
    -   `[NEW] tavily_scraper/stealth/core.py`: Core stealth functions.
    -   `[MODIFY] tavily_scraper/browser_fetcher.py`: Integrate `apply_stealth` hook.

-   **Key Functions**:
    ```python
    async def apply_core_stealth(page: Page, config: StealthConfig) -> None:
        """Applies essential stealth scripts."""
        # 1. Navigator webdriver
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        # 2. WebRTC/AudioContext
        await page.add_init_script("window.RTCPeerConnection = undefined; window.AudioContext = undefined;")
        # ...
    ```

-   **References**:
    -   `drafts/stealth.py`: `apply_stealth_scripts`.
    -   `drafts/stealth1.py`: `create_stealth_browser` (args), `apply_stealth_scripts`.
    -   `stealth.md`: "Must-Have Techniques" section.

## Acceptance Criteria
-   [ ] `navigator.webdriver` returns `undefined` in the browser console.
-   [ ] User-Agent is randomized and consistent with the platform (if possible).
-   [ ] WebRTC and AudioContext are disabled or spoofed.
-   [ ] Browser launches without "Chrome is being controlled by automated test software" banner (via args).

## Dependencies
-   STEALTH-01 (Architecture)
