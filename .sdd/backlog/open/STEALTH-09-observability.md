# Ticket: Stealth Observability & Verification

**ID**: STEALTH-09
**Type**: Feature
**Status**: Open
**Priority**: Medium
**Estimated Complexity**: S

## Objective
Add visibility into the effectiveness of stealth modules. We need to know *which* techniques are triggering blocks and *how often* we are passing bot checks. This involves better logging, metrics collection, and automated "canary" checks.

## Requirements
1.  **Stealth Metrics**: Track success/failure rates broken down by `StealthMode` (minimal/moderate/aggressive).
2.  **Block Classification**: Better classification of block types (IP block vs Fingerprint block vs Captcha).
3.  **Canary Mode**: A flag or scheduled task to run against known bot-check sites (Sannysoft, etc.) and report status.
4.  **Debug Logging**: Enhanced logging for stealth injections (e.g., "Injected WebGL spoof: Intel...").

## Implementation Details
-   **Files to Create/Modify**:
    -   `[MODIFY] tavily_scraper/core/models.py`: Add stealth-specific fields to `RunSummary`.
    -   `[MODIFY] tavily_scraper/utils/metrics.py`: Aggregate stealth stats.
    -   `[MODIFY] tavily_scraper/stealth/core.py`: Add detailed debug logs.
    -   `[NEW] tavily_scraper/canary.py`: Script to run verification suite and output JSON report.

## Acceptance Criteria
-   [ ] `run_summary.json` includes `stealth_mode` and success rates per mode.
-   [ ] Logs clearly indicate which stealth scripts were injected.
-   [ ] `canary.py` produces a machine-readable report of bot test results (e.g., `{"sannysoft": "passed", "areyouheadless": "failed"}`).

## Testing Approach
-   **Unit Test**: Verify metrics aggregation logic.
-   **Manual**: Run a scrape with `--stealth`, check logs and summary file for new fields.

## Dependencies
-   STEALTH-01, STEALTH-06
