# Ticket: Captcha Handling & Interactive Solving

**ID**: STEALTH-05
**Type**: Feature
**Status**: Open
**Priority**: Medium
**Estimated Complexity**: M

## Objective
Implement a mechanism to detect CAPTCHAs and switch to an interactive mode for manual solving (or future automated solving integration). This ensures the scraper doesn't get permanently blocked by challenges.

## Requirements
1.  **Captcha Detection**: Detect common CAPTCHA signatures (Cloudflare, reCAPTCHA, etc.) in page content or URL.
2.  **Headless -> Headful Switch**:
    -   Pause the headless session.
    -   Launch a visible (headful) browser with the same session state (cookies, storage).
    -   Prompt the user to solve the CAPTCHA manually.
    -   Capture the updated session state (tokens) and resume the headless session.
3.  **Session Recovery**: Ensure the scraper can continue from where it left off after the CAPTCHA is solved.

## Implementation Details
-   **Files to Create/Modify**:
    -   `[NEW] tavily_scraper/stealth/captcha.py`: Captcha handling logic.
    -   `[MODIFY] tavily_scraper/strategy.py`: Integrate `handle_captcha` into the scraping flow.

-   **Key Functions**:
    ```python
    async def handle_captcha_challenge(page: Page, playwright: Playwright) -> Page:
        """
        Detects challenge, switches to headful, waits for solve, resumes.
        """
        # ... logic from drafts/stealth2.py and stealth.py ...
    ```

-   **References**:
    -   `drafts/stealth2.py`: `handle_cloudflare_challenge` (best reference for switching modes).
    -   `drafts/stealth.py`: `handle_manual_captcha`, `recover_browser_session`.
    -   `stealth.md`: "Captcha Handling" section.

## Acceptance Criteria
-   [ ] System detects Cloudflare/reCAPTCHA challenges.
-   [ ] Browser correctly switches to headful mode upon detection.
-   [ ] User can solve the CAPTCHA manually.
-   [ ] Session resumes in headless mode with the new clearance cookies/tokens.
-   [ ] Original request is retried successfully.

## Dependencies
-   STEALTH-01 (Architecture)
