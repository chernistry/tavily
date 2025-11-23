# Ticket: Network Fingerprint & Traffic Simulation

**ID**: STEALTH-H03  
**Type**: Feature  
**Status**: Open  
**Priority**: Medium  
**Estimated Complexity**: M  

---

## Objective

Enhance the network stealth layer so that Tavily’s browser traffic:

- matches realistic network conditions (latency, bandwidth) for a small set of named profiles; and  
- optionally includes low-volume “background traffic” that makes the overall pattern of requests closer to a real user browsing session.

All of this must remain:

- configurable via `StealthConfig`;  
- safe for target sites (strict bounds on extra traffic); and  
- compatible with existing `simulate_network_conditions` behavior.

---

## Current Behavior (Baseline)

Implemented in `tavily_scraper/stealth/advanced.py`:

- `simulate_network_conditions(page, profile="fast_3g")`:
  - selects coarse network profiles:
    - `slow_3g`, `fast_3g`, `4g`;
  - uses `page.context.new_cdp_session(page)` and `Network.emulateNetworkConditions` to apply:
    - `latency`,
    - `downloadThroughput`,
    - `uploadThroughput`.
  - Called in `browser_fetcher` when:
    - stealth is enabled and
    - `stealth_config.mode == "aggressive"`.

What is missing:

- more nuanced profiles (e.g. `wifi`, `dsl`, “mobile EU/US” variants);  
- any form of background noise traffic (fake but low-risk HTTP requests) that could make interaction traces less “single-request-focused”.

---

## Requirements

1. **Extended Network Profiles**
   - Define a small set of **named network profiles** (e.g. `slow_3g`, `fast_3g`, `4g`, `wifi`, `dsl`), each with:
     - realistic ranges for latency, downlink, uplink;
     - optional jitter (small random variation within safe bounds).
   - Make the profile:
     - configurable through `StealthConfig` (e.g. `network_profile: Literal[...]`);
     - default to a sensible value (e.g., `fast_3g` or `4g`) when stealth is enabled and a profile is not explicitly provided.

2. **Optional Background Traffic Simulation**
   - Implement an **optional** low-volume “background traffic” function, for example:
     - periodic `fetch` calls from the page to a small allowlist of innocuous URLs (e.g. static assets, public CDNs);
     - triggered only when explicitly enabled in `StealthConfig` (e.g. `fake_background_traffic=True`).
   - Constraints:
     - strictly limit the number of extra requests per page/session;
     - allow configuration of:
       - maximum requests (per page, per run),
       - maximum bytes (approx, via resource types/sizes if available),
       - domains (allowlist) for background noise.
   - Ensure background traffic:
     - runs asynchronously and does not block the main scraping flow;
     - is easy to disable when not needed.

3. **Configurability & Integration**
   - Extend `StealthConfig` with:
     - `network_profile: Literal["slow_3g","fast_3g","4g","wifi","dsl"] | None`
     - `fake_background_traffic: bool = False`
     - optionally, a numeric `background_noise_level` (low/medium/high or integer).
   - Integrate into `browser_fetcher`:
     - choose the network profile based on:
       - `stealth_config.network_profile` if set;
       - otherwise, fall back to existing logic for “aggressive” mode.
     - if `fake_background_traffic=True`, schedule background noise only after initial page load and within configured limits.

4. **Testing & Safety**
   - Add tests to ensure:
     - `simulate_network_conditions` accepts and applies the new profile names without throwing;
     - background traffic does not exceed configured limits;
     - disabling `fake_background_traffic` yields current behavior (no extra HTTP requests from the stealth layer).
   - Ideally, include a small metrics/logging hook (e.g., debug logs) to verify how often and where extra traffic is generated.

---

## Implementation Details

**Files to Create/Modify**

- `tavily_scraper/stealth/advanced.py`
- `tavily_scraper/stealth/config.py`
- `tavily_scraper/pipelines/browser_fetcher.py`
- `tests/test_stealth_config.py` (and/or another dedicated test module)

**Suggested Steps**

1. **Define Extended Profiles**
   - In `simulate_network_conditions`, define parameter ranges for each new profile:
     - `wifi`: higher bandwidth, low latency;
     - `dsl`: moderate bandwidth, moderate latency, more jitter; etc.
   - Ensure existing profiles keep their semantics to avoid regressions.

2. **Add Config Fields**
   - Extend `StealthConfig` with `network_profile` and `fake_background_traffic`.
   - Provide reasonable defaults and document them in `.sdd/stealth.md` and internal docstrings.

3. **Background Traffic Implementation**
   - Add a helper (e.g. `async def generate_background_traffic(page: Page, config: StealthConfig)`) that:
     - uses `page.evaluate` to issue a handful of `fetch` requests to lightweight targets;
     - respects limits from `config` (max requests, allowlist).
   - Invoke this helper from `browser_fetcher` after `page.goto`, guarded by:
     - stealth enabled,
     - `fake_background_traffic` flag,
     - possibly restricted to specific `network_profile` values.

4. **Tests**
   - Add unit tests that:
     - call `simulate_network_conditions` with each known profile and verify no exception is thrown;
     - mock or spy on background traffic to verify:
       - number of requests does not exceed threshold;
       - disabling the flag results in zero background traffic.

---

## Acceptance Criteria

- [ ] Network profiles can be selected via `StealthConfig` and applied consistently without breaking Playwright.
- [ ] Optional background traffic can be enabled/disabled via config, generates only bounded extra requests, and does not interfere with main scraping logic.
- [ ] Existing behavior for runs with stealth disabled (or background traffic disabled) remains unchanged.
- [ ] New behavior is covered by tests and documented (at least in `.sdd/stealth.md` or code docstrings).

---

## Dependencies

- Depends on:
  - `STEALTH-01` (Architecture)  
  - `STEALTH-04` (Advanced Stealth Techniques) for existing network throttling logic.

