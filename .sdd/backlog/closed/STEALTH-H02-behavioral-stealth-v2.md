# Ticket: Behavioral Stealth v2 (Physics-based Human Simulation)

**ID**: STEALTH-H02  
**Type**: Feature  
**Status**: Open  
**Priority**: High  
**Estimated Complexity**: M  

---

## Objective

Upgrade the current behavioral stealth layer from simple random movements/scrolls/typing into a more realistic, physics-inspired simulation that:

- better mimics human motor behavior (mouse trajectories, speed profiles);  
- exhibits reading-like scroll patterns (pauses, reversals, variable speed); and  
- keeps typing patterns realistically noisy without being obviously synthetic.

The implementation must remain configurable and safe so that behavior can be dialed up/down depending on performance and stealth requirements.

---

## Current Behavior (Baseline)

Implemented today in `tavily_scraper/stealth/behavior.py`:

- `human_mouse_move(page)`:
  - starts at a central location, then moves along a small set of random points with `Playwright`’s built-in interpolation and random `steps`.
- `human_scroll(page)`:
  - performs 1–3 scroll segments of fixed vertical ranges with random delays; occasionally scrolls back a bit.
- `human_type(page, selector, text)`:
  - types characters with random per-character delay and occasional typo+backspace.
- `jitter_viewport(page, config)`:
  - applies small viewport changes in `browser_fetcher` when `viewport_jitter` is enabled.

This is already a reasonable “basic humanization”, but still too simplistic to withstand more advanced behavioral models (e.g., those tracking mouse acceleration, direction changes, hover patterns, and context-aware scrolling).

---

## Requirements

1. **Mouse Trajectories & Physics**
   - Replace simplistic random line segments with:
     - polyline or Bezier-based paths between origin and target points;
     - a non-linear speed profile (acceleration → cruise → deceleration);
     - small, realistic noise in intermediate points.
   - Ensure:
     - the path respects viewport bounds;  
     - step count and timing are roughly in human ranges (no perfect linear motion at constant speed).

2. **Reading-like Scroll Patterns**
   - Make `human_scroll` simulate a user reading content:
     - scroll in smaller increments with variable spacing;
     - add “micro-scroll-back” behaviors more systematically (e.g., after a few forward scrolls);
     - inject pauses of varying length to emulate reading time.
   - Allow the number of segments and magnitude of scrolls to depend on page height (if cheaply available).

3. **Typing Behavior Enhancements**
   - Extend `human_type` with:
     - a low but non-zero probability of longer “thinking pauses” mid-word;
     - configurable ranges for per-character delays (e.g., 40–200 ms) based on a simple “skill” or “mood” profile;
     - slightly more structured typo behavior (e.g., bursts of characters followed by a correction).

4. **Configurability**
   - Keep behavior controlled by `StealthConfig`:
     - `simulate_human_behavior: bool` remains the master switch;
     - introduce an optional `behavior_profile` or similar field:
       - `minimal` (current lightweight behavior),
       - `default` (moderate realism, default for production),
       - `aggressive` (more movement/scrolling for highly protected sites).
   - Ensure “minimal” mode preserves roughly current behavior or a less intrusive subset.

5. **Integration**
   - Continue to integrate behavioral stealth through:
     - `browser_fetcher._handle_navigation` for mouse/scroll actions;
     - `jitter_viewport` at context creation (or early in session).
   - Do not introduce heavy behavior into tight loops (e.g. per small DOM action); keep it to “entry points” like page navigation and key interactions.

6. **Testing**
   - Extend `tests/test_stealth_behavior.py` to assert:
     - functions execute without errors under all supported `behavior_profile` values;
     - generated motion paths have:
       - more than a trivial number of steps;  
       - visibly varying per-step delays;  
     - typing logic still produces the expected final text even with typos/corrections enabled.
   - Consider adding a lightweight “sanity visualizer” (script or log) for manual QA when needed.

---

## Implementation Details

**Files to Create/Modify**

- `tavily_scraper/stealth/behavior.py`
- `tavily_scraper/stealth/config.py` (new behavior profile field)
- `tavily_scraper/pipelines/browser_fetcher.py` (ensure profile is respected)
- `tests/test_stealth_behavior.py`

**Suggested Steps**

1. **Introduce Behavior Profiles**
   - Extend `StealthConfig` to include something like:
     - `behavior_profile: Literal["minimal","default","aggressive"] = "default"`.
   - Thread this parameter through to `behavior.py` functions where needed.

2. **Mouse Movement Engine**
   - Implement a small helper (e.g. `generate_mouse_path`) that:
     - takes a start and end coordinate and a profile;  
     - returns a sequence of intermediate waypoints and per-step delays.
   - Update `human_mouse_move` to:
     - pick a small set of “destinations” based on viewport and profile;
     - call `page.mouse.move` over the generated path, applying delays between segments.

3. **Scroll Patterns**
   - Refine `human_scroll` to:
     - compute a scroll plan combining multiple forward scrolls, occasional backward scrolls, and varied pause durations.
   - Optionally, use a cheap heuristic for “page height” to avoid over-scrolling small pages.

4. **Typing Enhancements**
   - Adjust `human_type` to:
     - sample delays from different ranges depending on `behavior_profile`;
     - introduce rare, longer pauses (e.g. simulate “thinking”).

5. **Tests**
   - Extend tests to:
     - iterate over `behavior_profile` variants;
     - assert that at least some randomization is happening (e.g. repeated runs do not produce identical timestamps).

---

## Acceptance Criteria

- [ ] Behavioral functions (`human_mouse_move`, `human_scroll`, `human_type`) exhibit visibly more human-like trajectories, delays and scroll patterns compared to the previous implementation.
- [ ] Behavior is fully configurable via `StealthConfig` and can be dialed down to a minimal mode for performance-sensitive runs.
- [ ] All new logic is covered by tests and does not introduce flaky timing-dependent failures.
- [ ] Existing pipelines using `simulate_human_behavior=False` remain unaffected.

---

## Dependencies

- Depends on:
  - `STEALTH-01` (Architecture)  
  - `STEALTH-03` (Behavioral Stealth) as the baseline feature.

