# Ticket: Captcha Handling (Detection & Hooks)

**ID**: STEALTH-05
**Type**: Feature
**Status**: Open
**Priority**: Medium
**Estimated Complexity**: S

## Objective
Implement a mechanism to detect CAPTCHAs and provide a standardized interface (hooks) for future solvers. **Do not implement interactive solving or external API integration yet.** The goal is to detect the block and allow for a clean failure or future extension.

## Requirements
1.  **Captcha Detection**: Detect common CAPTCHA signatures (Cloudflare, reCAPTCHA, etc.) in page content or URL.
2.  **Solver Interface**: Define a `CaptchaSolver` protocol/abstract base class.
3.  **Default Behavior**: Implement a default solver that logs the detection and raises a `CaptchaDetectedError` (or returns a failure status), without attempting to solve it.

## Implementation Details
-   **Files to Create/Modify**:
    -   `[NEW] tavily_scraper/stealth/captcha.py`: Detection logic and interfaces.
    -   `[MODIFY] tavily_scraper/strategy.py`: Call detection logic; handle the error/hook.

-   **Key Functions**:
    ```python
    class CaptchaSolver(Protocol):
        async def solve(self, page: Page) -> bool: ...

    async def detect_captcha(page: Page) -> str | None:
        """Returns 'cloudflare', 'recaptcha', or None."""
        # ... logic to check page content/url ...
    ```

-   **References**:
    -   `drafts/stealth2.py`: Detection logic (selectors).
    -   `stealth.md`: "Captcha Handling" section.

## Acceptance Criteria
-   [ ] `detect_captcha` correctly identifies Cloudflare/reCAPTCHA pages (mocked or real).
-   [ ] `CaptchaSolver` interface is defined.
-   [ ] Default behavior is to log and fail gracefully.
-   [ ] No interactive input or headful switching is implemented.

## Dependencies
-   STEALTH-01 (Architecture)
