# Ticket: Behavioral Stealth (Human Simulation)

**ID**: STEALTH-03
**Type**: Feature
**Status**: Open
**Priority**: High
**Estimated Complexity**: M

## Objective
Implement human-like interaction patterns to evade behavioral analysis detection. This includes realistic mouse movements, scrolling, and typing.

## Requirements
1.  **Realistic Mouse Physics**: Implement Bezier curve-based mouse movements with variable speed, gravity, and wind simulation.
2.  **Human Reading Patterns**: Simulate reading by scrolling with random pauses and speed variations.
3.  **Human-like Typing**: Type text with random delays between keystrokes, occasional pauses, and error correction (optional).

## Implementation Details
-   **Files to Create/Modify**:
    -   `[NEW] tavily_scraper/stealth/behavior.py`: Human simulation logic.
    -   `[MODIFY] tavily_scraper/browser_fetcher.py`: Call behavior functions during interaction steps.

-   **Key Functions**:
    ```python
    async def human_mouse_move(page: Page, x: int, y: int):
        """Moves mouse to (x, y) using realistic physics."""
        # ... logic from drafts/stealth1.py ...

    async def human_scroll(page: Page):
        """Scrolls the page like a human reading."""
        # ... logic from drafts/stealth1.py ...

    async def human_type(page: Page, selector: str, text: str):
        """Types text with random delays."""
        # ... logic from drafts/stealth.py ...
    ```

-   **References**:
    -   `drafts/stealth1.py`: `generate_realistic_mouse_physics`, `simulate_reading_patterns`, `scroll_randomly`.
    -   `drafts/stealth.py`: `type_like_human`.
    -   `stealth.md`: "Human Emulation" section.

## Acceptance Criteria
-   [ ] Mouse moves in curves, not straight lines.
-   [ ] Scrolling includes pauses and variable speeds.
-   [ ] Typing has variable inter-key delays (e.g., 50-150ms).
-   [ ] All behaviors are toggleable via config (e.g., `simulate_human_behavior=True`).

## Dependencies
-   STEALTH-01 (Architecture)
