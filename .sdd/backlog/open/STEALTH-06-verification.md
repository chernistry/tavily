# Ticket: Verification & Testing Suite

**ID**: STEALTH-06
**Type**: Feature
**Status**: Open
**Priority**: High
**Estimated Complexity**: M

## Objective
Create a suite of tests to verify the effectiveness of the stealth modules. This ensures that the anti-detection techniques are working as expected and not regressing.

## Requirements
1.  **Bot Detection Tests**: Automated tests against known bot detection pages (e.g., Sannysoft, AreYouHeadless).
2.  **Browser State Verification**: Unit tests to inspect `navigator` properties and ensure they are correctly spoofed.
3.  **Behavioral Verification**: Tests to confirm that mouse movements and scrolling are randomized (e.g., measuring variance in timing/coordinates).
4.  **Integration Tests**: End-to-end tests with the full pipeline enabled (`--stealth`).

## Implementation Details
-   **Files to Create/Modify**:
    -   `[NEW] tests/test_stealth_core.py`: Unit tests for core stealth.
    -   `[NEW] tests/test_stealth_behavior.py`: Unit tests for behavior.
    -   `[NEW] tests/verification_suite.py`: Script to run against detection sites.

-   **Test Cases**:
    -   **Sannysoft**: Visit `https://bot.sannysoft.com/` and assert that "WebDriver" is false.
    -   **Navigator**: Assert `navigator.webdriver` is `undefined`.
    -   **User-Agent**: Assert UA matches the expected pattern.
    -   **Mouse**: Record mouse events and verify they follow a curve (not linear).

-   **References**:
    -   `stealth.md`: "Verification Techniques" section.

## Acceptance Criteria
-   [ ] `pytest` suite covers core stealth functions.
-   [ ] Verification script passes Sannysoft bot test (green status).
-   [ ] Behavioral tests confirm randomness in inputs.
-   [ ] CI integration (optional, if external sites are reliable).

## Dependencies
-   STEALTH-02, STEALTH-03, STEALTH-04
