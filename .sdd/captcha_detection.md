# CAPTCHA Detection Best Practices (Tavily Scraper, 2025)

## 1. Scope & Assumptions

**Goal:**
Detect when a request hit a CAPTCHA / anti-bot challenge and:

* classify it (vendor / type),
* log it in `UrlStats` / metrics,
* stop retries / “hammering” that URL,
* optionally downgrade that domain for future runs.

**Non-goals:**

* No CAPTCHA solving (no 2Captcha, no “bypass Akamai/Cloudflare” hacks).
* No stealth hackery (undetected-chromedriver, low-level TLS spoofing).

**Stack:**

* Python 3.11+
* HTTPX (async) + Selectolax
* Playwright (Chromium) headless
* Rotating proxies

The guidance below is tuned specifically to this stack and the Tavily assignment.

---

## 2. CAPTCHA & Anti-Bot Landscape (2025)

Modern “CAPTCHA pages” are usually one of:

1. **Traditional widget CAPTCHAs**

   * Google reCAPTCHA v2 (`g-recaptcha`, script `www.google.com/recaptcha/api.js`)
   * hCaptcha (`h-captcha`, script `hcaptcha.com/1/api.js`)
   * Cloudflare Turnstile (`cf-turnstile` widget, script from `challenges.cloudflare.com/turnstile`)

2. **Vendor block / challenge pages**

   * Cloudflare “Checking your browser before accessing …” interstitial
   * Generic “Please verify you are a human. Access to this page has been denied because we believe you are using automation tools to browse the website.”

3. **Invisible / behavioral systems**

   * reCAPTCHA v3, Turnstile, Akamai Bot Manager, PerimeterX, Arkose, etc., which score the session and, on low trust, serve:

     * block page (`Access denied`, 403/429/503),
     * or hard redirect to a human-verification page.

Our detection therefore must look for:

* **Widget markers** (reCAPTCHA, hCaptcha, Turnstile),
* **Block/challenge copy** (“are you a robot/human”, “checking your browser”),
* **Vendor-specific scripts / DOM / URLs**,
* **Blocking patterns** (status codes + response shape).

---

## 3. Detection Surfaces & Signals

Detection happens in **two places**:

1. **HTTPX stage** — we only have `response.status_code`, headers, URL, and HTML text.
2. **Playwright stage** — we also have DOM, frames, JS execution and final URL.

### 3.1 HTTP-Level Signals

Use these as **weak signals** (they alone do not prove CAPTCHA, but raise suspicion):

* Status codes:

  * `403`, `429`, `503` combined with short bodies are common for bot blocks.
* Redirect patterns:

  * Redirect chains to paths like `/captcha`, `/challenge`, `/blocked`, or to separate challenge domains (e.g. `challenges.cloudflare.com`).
* Headers:

  * `Server: cloudflare`, `cf-ray`, `cf-chl-bypass`, etc. → suspect Cloudflare challenge.
  * Other anti-bot vendors (Akamai, PerimeterX) often expose `akamai-` or `x-perimeterx` headers.

### 3.2 URL / Domain Signals

* Request URL or final URL contains typical patterns:

  * `captcha`, `challenge`, `robot`, `are-you-a-human`, `verify-human`.
* Known “challenge” domains:

  * `challenges.cloudflare.com`, `hcaptcha.com`, `google.com/recaptcha`.

Keep a **vendor registry** (config) so rules are declarative, not hard-coded all over.

### 3.3 HTML / DOM Signals (Static Text Markers)

In HTTPX stage (raw HTML string), search for **robust phrases**:

Examples from real block pages:

* “Please verify you are a human”
* “Are you a robot?” / “Are you human?”
* “Access to this page has been denied because we believe you are using automation tools to browse the website.”
* “Checking your browser before accessing” (Cloudflare)

Implementation:

* Lowercase the body and search for **multiple** keyword hits (to reduce false positives).
* Combine with suspicious status (`403/429/503`) or known anti-bot vendor headers.

### 3.4 Widget & Script Markers (Vendor-Specific)

These are the most precise signals.

#### Google reCAPTCHA

Typical markers:

* HTML:

  * `<div class="g-recaptcha" data-sitekey="…">`
* Script:

  * `<script src="https://www.google.com/recaptcha/api.js"...>`
  * `<script src="https://www.gstatic.com/recaptcha/..."...>`

Detection:

* Regex or substring on:

  * `"g-recaptcha"`, `"data-sitekey"`, `"recaptcha/api.js"`.

#### hCaptcha

Markers:

* HTML:

  * `<div class="h-captcha" data-sitekey="…">`
* Script:

  * `<script src="https://hcaptcha.com/1/api.js"...>`

Detection:

* Substrings: `"h-captcha"`, `"hcaptcha.com/1/api.js"`.

#### Cloudflare Turnstile

Markers:

* HTML:

  * `<div class="cf-turnstile" data-sitekey="…">`
  * Hidden field `name="cf-turnstile-response"`.
* Script:

  * `<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>`

Detection:

* Substrings: `"cf-turnstile"`, `"cf-turnstile-response"`, `"challenges.cloudflare.com/turnstile"`.

#### Generic Vendor Pages

Some anti-bot vendors don’t expose a widget, but a full-screen “human verification” page:

* Repeated phrases like:

  * “Please verify you are a human”
  * “Access denied”, “You are being rate limited” (Akamai / WAF)
* Minimal or no actual site content; one form / checkbox in the body.

Detection:

* Short body length + above phrases + 4xx/5xx status.

---

## 4. Classification Model

Define a small, shared enum type for all stages:

```python
from typing import Literal, TypedDict

CaptchaVendor = Literal["recaptcha", "hcaptcha", "turnstile", "cloudflare_block",
                        "generic_block", "unknown"]

class CaptchaDetection(TypedDict):
    present: bool
    vendor: CaptchaVendor | None
    confidence: float  # 0..1
    reason: str        # short human-readable summary
```

Add to `UrlStats`:

```python
class UrlStats(TypedDict):
    ...
    block_type: Literal["none", "captcha", "rate_limit", "robots", "other"]
    block_vendor: CaptchaVendor | None
```

---

## 5. Implementation – HTTPX Stage

### 5.1 Design

Implement a pure function:

```python
def detect_captcha_http(
    status_code: int,
    url: str,
    headers: Mapping[str, str],
    body: str | None,
) -> CaptchaDetection:
    ...
```

**Steps:**

1. Normalization:

   * `body_lc = (body or "").lower()[:200_000]` (cap to avoid scanning 10 MB pages).
   * `host = urlparse(url).hostname or ""`.

2. Fast vendor checks (widget / scripts):

   * If `"g-recaptcha"` in `body_lc` or `"recaptcha/api.js"` → `vendor="recaptcha"`.
   * If `"h-captcha"` or `"hcaptcha.com/1/api.js"` → `vendor="hcaptcha"`.
   * If `"cf-turnstile"` or `"cf-turnstile-response"` or `"challenges.cloudflare.com/turnstile"` → `vendor="turnstile"`.

3. Cloudflare challenge page:

   * If `"checking your browser before accessing"` in `body_lc` or host contains `"cloudflare"` in server headers → `vendor="cloudflare_block"`.

4. Generic human-verification page:

   * Count hits across:

     * `"please verify you are a human"`,
     * `"are you a robot"`,
     * `"access has been denied"`,
     * `"automation tools to browse the website"`.
   * If ≥2 matches AND `status_code in {403, 429, 503}` → `vendor="generic_block"`.

5. Confidence:

   * Vendor widget/script: 0.95
   * Cloudflare phrase: 0.9
   * Generic text + 4xx/5xx: 0.8
   * Single weak signal: 0.5 (log as “suspected”, but you can still try Playwright once).

6. Result:

```python
if vendor:
    return {"present": True, "vendor": vendor, "confidence": confidence, "reason": "..."}
return {"present": False, "vendor": None, "confidence": 0.0, "reason": ""}
```

### 5.2 Integration with Pipeline

* After every HTTPX fetch:

  ```python
  detection = detect_captcha_http(
      response.status_code,
      str(response.url),
      response.headers,
      response.text,
  )

  if detection["present"]:
      stats.block_type = "captcha"
      stats.block_vendor = detection["vendor"]
      stats.status = "captcha_detected"
      # important: do NOT blindly retry; at most change method to Playwright once
  ```

* **Retry policy:**

  * If HTTPX got a CAPTCHA page:

    * Option A (strict): mark as blocked, no Playwright.
    * Option B (more generous): try Playwright **exactly once** for that URL; if still CAPTCHA, mark blocked.
  * Never infinite retry loops; no solver integration.

---

## 6. Implementation – Playwright Stage

Playwright adds extra signals:

* Frame URLs (`page.frames`),
* Final `page.url`,
* Post-JS DOM, which may include the widget inserted dynamically.

### 6.1 Detection Function

```python
from playwright.async_api import Page

async def detect_captcha_playwright(page: Page) -> CaptchaDetection:
    url = page.url
    content = (await page.content()).lower()
    frames = page.frames

    # 1. Frame / URL based detection
    frame_urls = " ".join(f.url.lower() for f in frames if f.url)
    vendor = None
    reason_parts: list[str] = []
    conf = 0.0

    if "google.com/recaptcha" in content or "g-recaptcha" in content:
        vendor = "recaptcha"
        conf = 0.95
        reason_parts.append("recaptcha widget/script found")

    elif "hcaptcha.com" in frame_urls or "h-captcha" in content:
        vendor = "hcaptcha"
        conf = 0.95
        reason_parts.append("hcaptcha widget found")

    elif "cf-turnstile" in content or "challenges.cloudflare.com/turnstile" in content:
        vendor = "turnstile"
        conf = 0.95
        reason_parts.append("turnstile widget found")

    if "checking your browser before accessing" in content:
        vendor = vendor or "cloudflare_block"
        conf = max(conf, 0.9)
        reason_parts.append("cloudflare browser check text")

    # generic phrases (same as HTTP)
    generic_hits = sum(
        kw in content
        for kw in (
            "please verify you are a human",
            "are you a robot",
            "access has been denied",
            "automation tools to browse the website",
        )
    )
    if generic_hits >= 2 and conf < 0.8:
        vendor = vendor or "generic_block"
        conf = 0.8
        reason_parts.append("generic human-verification text")

    if vendor:
        return {
            "present": True,
            "vendor": vendor,
            "confidence": conf,
            "reason": "; ".join(reason_parts),
        }
    return {"present": False, "vendor": None, "confidence": 0.0, "reason": ""}
```

### 6.2 When to Call It

Call after page load and (optionally) after trying to wait for the main content:

```python
await page.goto(url, timeout=page_timeout, wait_until="networkidle")

# try to find real content selector first
try:
    await page.wait_for_selector(MAIN_SELECTOR, timeout=short_timeout)
except TimeoutError:
    # didn't find our target; maybe it's a block page
    pass

detection = await detect_captcha_playwright(page)
if detection["present"]:
    stats.block_type = "captcha"
    stats.block_vendor = detection["vendor"]
    stats.status = "captcha_detected"
    # stop further attempts for this URL
```

**Best practice:** If neither content nor CAPTCHA is clearly detected (everything is weird but no markers), log as `status="unknown_error"` with HTML length and move on.

---

## 7. Metrics, Logging & Tuning

### 7.1 Metrics to Track

Per run:

* `captcha_count`, `captcha_rate` (% URLs where block_type == "captcha")
* By vendor (`recaptcha`, `hcaptcha`, `turnstile`, `cloudflare_block`, `generic_block`)
* Stage of detection:

  * `http_captcha_count`,
  * `playwright_only_captcha_count`.

Use these to answer:

* Are we frequently reaching CAPTCHA pages?
* Does HTTPX already see them (bad for IP / TLS fingerprints), or only Playwright?

### 7.2 Logging

For each detected CAPTCHA:

* Log structured JSON with:

  ```json
  {
    "event": "captcha_detected",
    "url": "...",
    "method": "httpx" | "playwright",
    "vendor": "hcaptcha",
    "status_code": 403,
    "confidence": 0.95
  }
  ```

* Do **not** log:

  * full HTML body,
  * cookies,
  * querystrings with tokens.

Instead, store:

* `content_len`,
* maybe a short hash of body for debugging collisions.

### 7.3 Reducing False Positives

* Require **≥2 signals** when using generic text markers.
* Vendor widget/script markers alone are strong enough.
* Maintain **allow-list** exceptions per domain if needed (if a site legitimately mentions “are you a robot” in user content).

---

## 8. Testing CAPTCHA Detection

### 8.1 Unit Tests

Feed known HTML snippets into detection functions.

* Positive cases:

  * Minimal reCAPTCHA widget snippet from docs.
  * Minimal hCaptcha snippet.
  * Cloudflare Turnstile example.
  * Cloudflare browser check text.
  * “Please verify you are a human…” block snippet.

* Negative cases:

  * Normal pages with partial phrases (“we deny automation tools in our TOS”) → expect `present=False`.

### 8.2 Integration Tests

* HTTPX:

  * Use `pytest-httpx` to simulate:

    * `403` with block HTML → expect `captcha_detected`.
    * `200` static page → expect no CAPTCHA.

* Playwright (or mocked `Page` object):

  * A local HTML file with injected `<div class="g-recaptcha" ...>` → detection triggers.

### 8.3 Regression Tests

For any real URL where you see a CAPTCHA page in manual browsing:

1. Save minimal HTML snapshot (redacted).
2. Add to fixtures.
3. Ensure detection keeps working as vendors tweak markup.

---

## 9. Integration with Policy & Pipeline

* If `block_type="captcha"`:

  * **Do not** bump retry counters.
  * optional: throttle domain or downgrade it for the rest of the run.

* Surface in run summary:

  * “CAPTCHA-blocked URLs: 27 (2.7%), vendors: reCAPTCHA=10, hCaptcha=5, Turnstile=3, Cloudflare_block=9.”

* In final Tavily report:

  * Clearly state which portion of the dataset could not be scraped due to CAPTCHAs, and that no bypass was attempted (aligns with assignment + ethical expectations).

---

## 10. Checklist (Implementation)

**Minimal viable implementation:**

* [ ] Add `CaptchaDetection` model and `block_type/block_vendor` fields to `UrlStats`.
* [ ] Implement `detect_captcha_http(...)` with:

  * [ ] vendor widgets (reCAPTCHA, hCaptcha, Turnstile),
  * [ ] Cloudflare browser check phrase,
  * [ ] generic “verify human / automation tools” phrases + 4xx/5xx.
* [ ] Wire HTTPX stage to call detection and stop retries on positive.
* [ ] Implement `detect_captcha_playwright(page)` with:

  * [ ] frame URL scan,
  * [ ] widget scripts / classes,
  * [ ] generic text markers.
* [ ] Log all detections to `events.jsonl` and expose metrics in notebook.
* [ ] Add unit tests for detection logic + 1–2 integration tests.
* [ ] Include `captcha_rate` and vendor breakdown in final notebook plots / PDF.

