# Ticket: Stealth Module Architecture & Configuration

**ID**: STEALTH-01
**Type**: Feature
**Status**: Open
**Priority**: High
**Estimated Complexity**: S

## Objective
Establish the foundational structure for the `stealth` module within `tavily_scraper`, including configuration management and CLI integration. This ticket sets the stage for all subsequent stealth implementation tickets.

## Requirements
1.  **Module Structure**: Create a new package `tavily_scraper/stealth/`.
2.  **Configuration**: Define a `StealthConfig` class in `tavily_scraper/stealth/config.py` (or integrated into main `config.py`) to manage stealth settings.
3.  **CLI Integration**: Add a `--stealth` flag to the CLI to enable/disable stealth mode globally.
4.  **Factory/Entry Point**: Create a `StealthContext` or factory in `tavily_scraper/stealth/__init__.py` that initializes the appropriate stealth components based on config.

## Implementation Details
-   **Files to Create/Modify**:
    -   `[NEW] tavily_scraper/stealth/__init__.py`: Entry point.
    -   `[NEW] tavily_scraper/stealth/config.py`: Configuration dataclasses.
    -   `[MODIFY] tavily_scraper/config.py`: Integrate `StealthConfig`.
    -   `[MODIFY] tavily_scraper/cli.py`: Add `--stealth` argument.

-   **Configuration Schema (Draft)**:
    ```python
    @dataclass
    class StealthConfig:
        enabled: bool = False
        mode: Literal["minimal", "moderate", "aggressive"] = "moderate"
        headless: bool = True
        # Toggles for specific features
        spoof_user_agent: bool = True
        spoof_webdriver: bool = True
        simulate_human_behavior: bool = True
        # ... other flags
    ```

-   **References**:
    -   `drafts/stealth.py`: See imports and basic config loading.
    -   `architect.md`: Follow the "Components" section style.

## Acceptance Criteria
-   [ ] `tavily_scraper/stealth/` package exists.
-   [ ] `StealthConfig` is defined and can be loaded from `config.toml` or env vars.
-   [ ] CLI accepts `--stealth` flag, which overrides the config to `enabled=True`.
-   [ ] Basic unit test confirms config loading works.

## Dependencies
-   None. This is the blocker for STEALTH-02 through STEALTH-06.
