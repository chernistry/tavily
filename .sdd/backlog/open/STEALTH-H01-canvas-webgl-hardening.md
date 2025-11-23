# Ticket: Canvas & WebGL Fingerprint Hardening

**ID**: STEALTH-H01  
**Type**: Feature  
**Status**: Open  
**Priority**: High  
**Estimated Complexity**: M  

---

## Objective

Strengthen the anti-fingerprinting layer for Canvas and WebGL so that:

- popular fingerprinting libraries cannot trivially cluster or link Tavily browser sessions based on default Playwright/Chromium fingerprints; and  
- the browser presents a **stable fingerprint within a session** and a **distinct but realistic fingerprint across sessions**, consistent with the configured device profiles.

This ticket builds on the existing `fingerprint_canvas.js` and `fingerprint_webgl.js` assets and extends them to cover more real-world fingerprinting techniques.

---

## Context & Rationale

Current state:

- **Canvas**:
  - `fingerprint_canvas.js` overrides `CanvasRenderingContext2D.getImageData` and injects small noise into the pixel buffer.
  - This helps against naive “pixel hash” approaches but does not affect:
    - `HTMLCanvasElement.toDataURL`  
    - `HTMLCanvasElement.toBlob`  
    - Offscreen canvases and alternate rendering paths.
- **WebGL**:
  - `fingerprint_webgl.js` is injected via `apply_advanced_stealth` and uses `choose_webgl_profile()` to spoof vendor/renderer.
  - Coverage of WebGL2 contexts and advanced fingerprint probes (extensions, precision formats) is unclear.

Risk:

- Modern fingerprinting scripts use **multiple APIs** to compute robust, multi-dimensional fingerprints:
  - canvas hashes via `toDataURL` and `getImageData`;
  - WebGL vendor/renderer, supported extensions, shader precision, etc.
- Partial coverage can still leak a consistent, unique fingerprint that is strongly associated with “Playwright automation”.

Goal: bring the Canvas/WebGL defenses closer to the “senior-level” best practices described in `.sdd/stealth.md` under “Advanced Fingerprint Defense”.

---

## Requirements

1. **Canvas Fingerprint Defense**
   - Intercept and harden:
     - `HTMLCanvasElement.prototype.toDataURL`
     - `HTMLCanvasElement.prototype.toBlob`
     - `CanvasRenderingContext2D.prototype.getImageData` (already patched but may be refined).
   - Ensure noise injection:
     - is **small enough** to avoid visible artifacts for typical UI pages;
     - is **stable within a single session** (i.e., same device profile + run → consistent output across calls);
     - varies **across sessions** (different seeded noise for different sessions / device profiles).
   - Consider offscreen canvas:
     - where available, ensure fingerprint-relevant paths (e.g. offscreen 2D contexts) also receive mild noise or reuse the same patching logic.

2. **WebGL Fingerprint Defense**
   - Extend `fingerprint_webgl.js` to cover:
     - WebGL2 contexts (if not already handled);
     - additional fingerprint-relevant calls, e.g.:
       - `getSupportedExtensions`
       - `getShaderPrecisionFormat`
       - `getParameter` for key constants beyond vendor/renderer.
   - Maintain a **consistent** WebGL profile per session:
     - vendor/renderer must match a realistic device profile from `config_data/webgl_profiles.json`;
     - optional: expose a small, controlled variability across independent sessions.

3. **Configurability & Safety**
   - All defenses must remain controlled by `StealthConfig`:
     - continue to require `fingerprint_evasions=True` (and `enabled=True`);
     - optional extra toggle if we introduce different “strength” levels.
   - Scripts must be **defensive**:
     - swallow errors and avoid breaking the page if browser APIs change;
     - detect and early-exit when running outside a standard canvas/WebGL environment.

4. **Testing & Verification**
   - Add or extend tests (e.g. `tests/test_stealth_consistency.py`) to:
     - compute simple canvas fingerprints (hash of `toDataURL` output) before and after enabling stealth:
       - the fingerprint should change from the default baseline;
       - repeated calls within one page/session should yield identical or near-identical values.
     - check that WebGL vendor/renderer and selected parameters match the spoofed profile and not the Playwright defaults.
   - Optional: add a small internal “fingerprint demo page” used only in tests to assert behavior.

---

## Implementation Details

**Files to Create/Modify**

- `tavily_scraper/stealth/assets/fingerprint_canvas.js`
- `tavily_scraper/stealth/assets/fingerprint_webgl.js`
- `tavily_scraper/stealth/advanced.py`
- `tests/test_stealth_consistency.py` (or a new dedicated test module)

**Suggested Steps**

1. **Canvas Hardening**
   - Extend `fingerprint_canvas.js`:
     - Wrap `HTMLCanvasElement.prototype.toDataURL` and `toBlob` to:
       - call the original implementation;
       - apply small deterministic perturbations (e.g. seed-based) to the pixel buffer before encoding (if technically feasible), or
       - add tiny, stable noise using an embedded deterministic function keyed by:
         - device profile name (from `device_profiles`),
         - or a random seed passed via `StealthConfig` and injected into the script.
   - Ensure we set a flag (e.g. `__tavily_canvas_patched__`) to avoid double-patching and guard for missing prototypes.

2. **WebGL Hardening**
   - Review and extend `fingerprint_webgl.js`:
     - confirm how it hooks `getParameter` and for which constants;
     - add coverage for WebGL2 where possible.
   - Use `choose_webgl_profile()` from `device_profiles.py` to:
     - select a profile per session/context;
     - serialize vendor/renderer names into the injected script to keep browser-side logic simple.

3. **Integration in `advanced.py`**
   - Keep `apply_advanced_stealth` as the single entry point:
     - ensure canvas & WebGL scripts are injected exactly once and only when `config.fingerprint_evasions` is true.

4. **Testing**
   - Update `tests/test_stealth_consistency.py` to:
     - spin up a Playwright context with and without stealth;
     - render a test canvas, compute hashes of `toDataURL` and/or `getImageData` results;
     - assert consistency within session and difference between stealth vs non-stealth.
   - Add minimal WebGL tests (guarded for environment availability) to verify vendor/renderer.

---

## Acceptance Criteria

- [ ] Canvas fingerprinting via `toDataURL` and `getImageData` produces:
      - consistent values within a single session; and
      - different, non-default values compared to baseline Playwright without stealth.
- [ ] WebGL fingerprint (vendor, renderer, selected parameters) matches a configured `WebGLProfile` and not the default Playwright GPU metadata.
- [ ] All new logic is covered by automated tests and does not break rendering on a small smoke set of sites.
- [ ] All hardening can be disabled by turning off `StealthConfig.fingerprint_evasions`.

---

## Dependencies

- Depends on baseline stealth architecture and configuration:
  - `STEALTH-01` (Architecture)  
  - `STEALTH-02` (Core Stealth Techniques)  
  - `STEALTH-04` (Advanced Stealth Techniques) as implemented so far.

