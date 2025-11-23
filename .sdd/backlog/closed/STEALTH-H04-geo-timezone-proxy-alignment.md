# Ticket: Geo / Timezone / Proxy Alignment & Session Consistency

**ID**: STEALTH-H04  
**Type**: Feature  
**Status**: Open  
**Priority**: Medium  
**Estimated Complexity**: M  

---

## Objective

Align geolocation, timezone, device profile, and proxy configuration so that:

- a given scraping session presents a **coherent regional identity** (UA, locale, timezone, geolocation, IP all point to the same general region); and  
- repeated runs with the same session ID reuse the same profile, while different session IDs get plausibly different but valid profiles.

This increases realism and reduces the risk of detection by systems that correlate:

- IP region (from proxy)  
- browser’s timezone and locale  
- geolocation coordinates and accuracy  
- repeated visits from the same “user”.

---

## Current Behavior (Baseline)

Relevant pieces:

- `StealthConfig`:
  - `random_geolocation: bool` — if true, `device_profiles.build_context_options` may attach a geolocation payload and grant `geolocation` permission.
- `device_profiles.py`:
  - `DeviceProfile`:
    - `user_agent`, `viewport_width/height`, `locale`, `timezone_id`.
  - `GeoProfile`:
    - `latitude`, `longitude`, `accuracy`.
  - `_device_profiles()`, `_geo_profiles()` load static lists from `config_data`.
  - `build_context_options(config, profile=None)`:
    - chooses a `DeviceProfile` (random if not provided),
    - optionally sets geolocation with small noise,
    - sets `locale` and `timezone_id`.
- `SessionManager` in `stealth/session.py`:
  - stores and loads browser `storage_state()` and a `profile` JSON per `session_id`.

Missing:

- No explicit connection between:
  - proxy region (if known) and chosen `DeviceProfile` / `GeoProfile`;
  - persisted profile and subsequent runs (i.e., the code exists but is not leveraged for geo/timezone alignment).

---

## Requirements

1. **Proxy-Aware Profile Selection**
   - When proxy configuration includes a region/country hint (e.g., `US`, `DE`, `EU-West`):
     - select `DeviceProfile` and `GeoProfile` that are consistent with that region, if available;
     - fall back to generic profiles when no region match exists.
   - Define a minimal interface (in run config or a small helper) for exposing the proxy’s target region to the stealth layer.

2. **Session-Consistent Profiles**
   - For a given `session_id`:
     - reuse the same `DeviceProfile` and `GeoProfile` across runs (persisted via `SessionManager.save_profile` / `load_profile`);
     - ensure that:
       - `user_agent`, `viewport`, `locale`, `timezone_id`, and `geolocation` are stable.
   - For different session IDs:
     - samples can differ (within the global set of profiles) but should respect proxy regions when available.

3. **Noise Within Profiles**
   - Keep small noise on geolocation (as currently implemented) but:
     - ensure it remains near the base `GeoProfile` and does not cross into obviously different regions;
     - avoid drifting over time for the same session (noise should be re-applied deterministically or within a tight bound).

4. **Configurability & Backwards Compatibility**
   - All new behavior should be toggleable:
     - example: `StealthConfig.random_geolocation` + optional `align_with_proxy: bool`.
   - When no proxy region is known:
     - retain current behavior (random profile from `device_profiles` / `geo_profiles`).
   - When no `GeoProfile` is available:
     - gracefully skip geolocation rather than failing.

5. **Testing**
   - Add tests to confirm:
     - `SessionManager` correctly persists and restores profile data for a given `session_id`;
     - when a proxy region is provided, the chosen profile has:
       - a matching or at least compatible timezone and locale;
       - geolocation coordinates within the expected region bounds.
   - Consider adding simple invariants (e.g., if proxy region is “US”, timezone_id should be one of “America/...”, etc.) using test fixtures.

---

## Implementation Details

**Files to Create/Modify**

- `tavily_scraper/stealth/device_profiles.py`
- `tavily_scraper/stealth/session.py`
- Parts of the run configuration / proxy handling code that feed region info into stealth (where appropriate).
- `tests/test_stealth_session.py` and/or a new dedicated test module.

**Suggested Steps**

1. **Extend Profile Data**
   - If not already present, augment `DeviceProfile` / `GeoProfile` config data to include:
     - region/country codes (e.g. `us`, `de`, `eu`, etc.).
   - Ensure that the JSON under `config_data` can represent this without breaking current consumers.

2. **Region-Aware Selection Logic**
   - Add helper functions (e.g., `choose_device_profile_for_region(region: str)`) that:
     - attempt to pick from profiles matching the provided region;  
     - fall back to the generic `choose_device_profile` if none match.
   - Do the same for `GeoProfile` selection.

3. **Wire Through SessionManager**
   - When building context options:
     - check if `SessionManager.load_profile(session_id)` returns a stored profile; if so, reuse it instead of random selection.
     - on first run, choose a profile (possibly using region-aware selection), then persist it via `save_profile`.

4. **Tests**
   - Extend `test_stealth_session.py`:
     - simulate runs with and without existing profile files;
     - verify that the same `session_id` yields identical profile attributes after round-trip save/load.
   - Add tests for region-aware selection using a small set of synthetic profiles.

---

## Acceptance Criteria

- [ ] Given a known proxy region and a non-empty set of region-tagged profiles, Tavily chooses a device/geo profile that is consistent with that region.
- [ ] For a given `session_id`, repeated runs reuse the same profile (UA, viewport, locale, timezone, geolocation) via `SessionManager`.
- [ ] Random geolocation noise stays within the expected region for the session and does not drift significantly across runs.
- [ ] When proxy region or geo profiles are unavailable, the system gracefully falls back to current behavior.

---

## Dependencies

- Depends on:
  - `STEALTH-01` (Architecture)  
  - `STEALTH-02` (Core Stealth Techniques) for base navigator/UA logic.

