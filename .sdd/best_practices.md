# Best Practices for Web Scraping (2025)

Tavily Web Research Engineer Assignment — Design Notes

---

## TL;DR

**Hybrid pipeline, HTTP-first.**

* Use a **two-stage pipeline** for ~10000 assignment URLs:

  * Stage 1: async HTTP client (`httpx`) + fast HTML parser (Selectolax) for the **fast path**.
  * Stage 2: **Playwright** headless browser for **dynamic or blocked** pages only.
* This keeps most traffic cheap and fast (no JS engine), and reserves browsers for the minority of hard URLs.

**Compliance and anti-bot hygiene.**

* Respect **robots.txt** and site ToS whenever they’re accessible.
* Use **proxies + IP rotation** and **User-Agent rotation** to distribute load and avoid trivial IP or UA fingerprinting.
* Do **not** bypass CAPTCHAs: detect and classify them as `captcha` / `blocked` and move on.

**Observability and SLOs.**

* Emit **per-URL metrics** (`UrlStats`) and **per-run summaries** (`RunSummary`): latency percentiles per method, success/failure/robots/captcha counts, per-domain stats.
* Use a **Colab notebook** as the UI: visualize latency histograms, method split (HTTP vs browser), and domain error patterns.

**Modern stack, no dead tech.**

* `httpx` for HTTP (async + HTTP/2, good DX).
* Selectolax as a fast C-backed HTML5 parser (several-fold faster than BeautifulSoup / lxml on large pages).
* Playwright for JS-heavy pages (modern alternative to Selenium, multi-browser, robust auto-waits).
* Avoid **Requests-HTML** (depends on Pyppeteer, which Debian dropped as unmaintained) and **PhantomJS** (development effectively suspended after Chrome Headless; project considered obsolete).

**Shape the solution like a small production system.**

* **Package + notebook** split: `tavily_scraper/` for logic, `notebooks/tavily_assignment.ipynb` for orchestration and plots.
* Sharded batch runner, domain-aware concurrency, JSONL/Parquet outputs, tests + GitHub Actions CI.
* Explicit **SLOs** (e.g. P95 latency for HTTP vs Playwright, success rate ≥ 90% excluding robots/captcha) with guardrails.

---

## Background & Goals

The Tavily assignment asks for a scraper that processes **~10,000 URLs** (static + JS-heavy) with good trade-offs on **latency, accuracy, and cost**.

This guide assumes:

* You will **run the reference solution on ~10,000 URLs** in Colab as required.
* The core design should **align w ~10,000 URLs** 

High-level goals:

1. **Speed:** Finish ~1k URLs comfortably within a Colab session; shape for 10k if needed.
2. **Accuracy:** Capture dynamic content that only appears after JS execution.
3. **Cost:** Use HTTP where possible; use Playwright only where necessary.
4. **Compliance & ethics:** Respect robots.txt and anti-bot boundaries; no CAPTCHA solving.
5. **Transparency:** Provide clear metrics, error taxonomy, and reproducible runs.

---

## Requirements & Constraints

### Scale & Latency

* Target: ~1k URLs (design tested for 10k).
* Colab-class machine (few vCPUs, limited RAM).
* Aim for total runtime **≤ 20–30 minutes for 1k**, **≤ 2 hours for 10k** with sane concurrency.

### Accuracy

* Must handle:

  * Classic static HTML pages.
  * JS-rendered pages (e.g. SPA UIs, infinite scroll, content injected via XHR).
* Stage 1 must **detect** when HTML is incomplete or a bot wall, and escalate to Stage 2.

### Cost

* Use **open-source** tools only.
* Minimize:

  * CPU and RAM (browsers are expensive).
  * Bandwidth (block images/assets in Playwright).
  * Proxy usage (rotating IP providers often bill per GB).

### Compliance

* No **CAPTCHA solving** or external solving services.
* No stealth patches or undocumented hacks.
* Respect robots.txt where reachable; classify robots-disallowed pages as a distinct status.

### Proxies

* All traffic should be able to flow via **proxies from a JSON config** (`proxy.json`):

  * `httpx` configured via its `proxies` parameter.
  * Playwright configured via `proxy={"server": "...", "username": "...", "password": "..."}`.

### Multilingual

* Handle arbitrary languages and encodings transparently.
* Extraction should rely on **DOM structure**, not on English keywords.

### Logging & Visualization

* For each URL: status, method, latency, error classification, content length, flags (`captcha`, `robots`).
* At the end: summary tables + plots in the notebook.

### Environment

* Primary environment: **Google Colab** (Linux, no persistent disk between sessions).
* Everything must be installable via `pip` and runnable headless.

---

## Architecture Overview

### High-Level Shape

1. **Colab Notebook (UI/Glue)**

   * `pip install -r requirements.txt`
   * Load `urls.csv` and `proxy.json`.
   * Configure run (concurrency, timeouts, toggles).
   * Call `run_sharded(config)` from the package.
   * Use pandas/matplotlib to analyze output.

2. **Python Package (`tavily_scraper/`)**

   * **Config & models:** `RunConfig`, `ProxyConfig`, `UrlJob`, `UrlStats`, `RunSummary`, `ShardCheckpoint`.
   * **Infrastructure:**

     * `ProxyManager` – applies proxies to both HTTP and browser.
     * `RobotsClient` – fetches and caches robots.txt, answers `can_fetch`.
     * `DomainScheduler` – global + per-domain concurrency, jitter.
   * **Scraping:**

     * `FastHttpFetcher` (`httpx` + Selectolax).
     * `BrowserFetcher` (Playwright).
     * `StrategyRouter` – decides HTTP-only vs HTTP→browser.
   * **Persistence & metrics:**

     * `ResultStore` – JSONL/Parquet for UrlStats & error rows.
     * `CheckpointStore` – per-shard progress.
     * `metrics.compute_run_summary` – aggregates UrlStats → RunSummary.

3. **Execution**

   * `ShardedBatchRunner`:

     * Splits URLs into shards (e.g. 20×500).
     * Runs each shard with `ScrapeRunner` and checkpointing.
   * Async **per-URL orchestration**:

     * Obey `DomainScheduler`.
     * HTTP first; then optional browser fallback.
     * Emit UrlStats rows per stage.

---

## Technology Choices

### HTTP: `httpx`

* Modern HTTP client supporting sync **and async** APIs, HTTP/1.1 and **HTTP/2**, and easy proxy integration.
* Good choice for **high-throughput async scraping** with a Requests-like API.

### HTML Parser: Selectolax

* C-backed HTML5 parser; benchmarks show it can be **several times faster** than lxml/BeautifulSoup on large documents.
* Exposes CSS selectors helpers (`css`, `css_first`), ideal for scraping.

### Browser: Playwright

* Open-source automation library maintained by Microsoft; supports Chromium, Firefox, WebKit, and multiple languages including Python.
* Built-in auto-waits, robust headless mode, first-class support for test/scraping use cases.
* Lower overhead than Selenium’s WebDriver HTTP hop; integrates directly with browser DevTools.

### Avoided Tools

* **Requests-HTML:** relies on Pyppeteer, which Debian dropped due to being unmaintained; packaging and security concerns.
* **PhantomJS:** author effectively suspended development once Chrome Headless became standard; widely considered obsolete.

These choices minimize long-term risk and align with current ecosystem trends.

---

## HTTP Stage Best Practices (Fast Path)

### HTTP Client Setup

* Use a **single shared `httpx.AsyncClient`** per process:

  * `follow_redirects=True`.
  * `timeout` ~ 10 seconds (configurable, clamped).
  * HTTP/2 enabled (default when server supports it).
  * Proxies from `ProxyManager`.

* Rotate headers:

  * **User-Agent** from a small pool of modern browser UA strings.
  * **Accept-Language** from a small set (`en-US`, `en-GB`, optional extras).

  Rotating UA and IPs together is a standard anti-bot hygiene practice.

### Async Concurrency

* Use `asyncio` with a **global semaphore** for HTTP concurrency (e.g. 32) and **per-domain semaphores** (e.g. 1 for Google/Bing, 2–4 for others).
* This keeps throughput high while avoiding hammering any single domain.

### Parsing & Extraction

* Parse HTML bytes with Selectolax:

  * Confirm `Content-Type` is HTML or text before parsing.
  * Use structural selectors (`.class`, `[data-attr=val]`, etc.).

* Keep extraction logic **language-agnostic**: do not rely on English text labels.

### HTTP-Stage Success Heuristics

After parsing, decide if HTTP is “good enough”:

* Required fields present (e.g. title, key stats).
* `content_len` above a threshold (e.g. > a few KB).
* No obvious “JS required” markers:

  * Messages like “please enable JavaScript”.
  * SERP placeholders where JS is expected.

If any checks fail, mark the URL as `needs_browser=True`.

### Retries

* Retry transient HTTP errors (timeouts, connection resets, 502/503) up to 2 times with exponential backoff.
* Do **not** retry 4xx except maybe 429 with backoff.

---

## Browser Stage Best Practices (Fallback Path)

### Playwright Setup

* Install via `pip install playwright` and `playwright install` in Colab.
* Use Chromium headless mode; configure:

  * Viewport ≈ desktop (e.g. 1280×720).
  * UA string matching one of your HTTP UAs.
  * `locale="en-US"` or left default, unless locale matters.

Playwright is widely used in 2020s to automate browsers for testing and scraping tasks.

### Asset Blocking

* Before navigation, intercept requests and block:

  * Images (`*.png`, `*.jpg`, `*.jpeg`, `*.gif`, `*.svg`).
  * Fonts (`*.woff`, `*.woff2`).
  * Possibly CSS if you don’t rely on layout.

Blocking non-essential resources cuts page load times and bandwidth significantly on media-heavy sites.

### Waiting for Content

* Prefer **DOM-based waits** over `sleep()`:

  * `page.goto(url, wait_until="networkidle")` for typical SPAs.
  * Or `page.wait_for_selector(".main-content")` for specific content anchors.

Avoid arbitrary sleeps; use Playwright’s built-in waiting to reduce flakiness.

### Extraction Strategy

Two sensible patterns:

1. **Browser → HTML → Selectolax** (single extraction code path):

   * `html = page.content()`
   * Run same `parse_html_and_extract` as HTTP stage.

2. **Direct DOM queries from Playwright**:

   * `page.text_content("div.price")`, etc.

For an assignment and small library, **pattern 1** keeps data extraction in one place and simplifies testing.

### Resource Management

* Reuse a **single browser instance** for many pages.
* Create/close **pages or contexts** per URL; restart the browser after N pages (e.g. every 50) to avoid memory leaks.
* Limit browser parallelism:

  * 1–2 concurrent contexts on Colab to avoid CPU thrash.

---

## Hybrid Pipeline & Orchestration

### URL Lifecycle

For each URL:

1. **Robots check** (if robots.txt reachable and cache warm):

   * If disallowed → record `status="robots"` and skip network fetch.

2. **HTTP Stage**:

   * Acquire domain slot in `DomainScheduler`.
   * Fetch with `httpx`, parse with Selectolax.
   * Extract data; compute HTTP-stage `FetchResult`.

3. **Decision point**:

   * If HTTP result looks good → emit `UrlStats` with `method="httpx"`, `stage="primary"`.
   * If not → enqueue a **browser task**.

4. **Browser Stage** (for queued URLs):

   * Navigate with Playwright, block assets, wait for content.
   * Extract data; emit `UrlStats` with `method="playwright"`, `stage="fallback"`.
   * If page is still blocked/CAPTCHA, classify accordingly.

5. **Persistence**:

   * `ResultStore` appends UrlStats rows as JSONL.
   * `CheckpointStore` updates shard progress.

### Sharding & Checkpointing

* For 1k URLs, a single batch is fine, but using **shards** makes it scale to 10k:

  * Example: 20 shards × 500 URLs.
  * Each shard has its own UrlStats file and checkpoint.

* If Colab kernel dies mid-run, you can **resume** from last completed shard.

---

## Proxy & Anti-Bot Strategy

### IP Rotation & Proxies

* Proxies mitigate **IP-based rate limits** and allow traffic distribution.
* Strategy:

  * Use a **rotating residential or datacenter proxy endpoint** where one hostname provides many IPs, or maintain a small pool in `proxy.json`.
  * For httpx, set `proxies={"http://": proxy_url, "https://": proxy_url}`.
  * For Playwright, pass `proxy={"server": proxy_url, "username": ..., "password": ...}`.

### User-Agent & Header Rotation

* Many anti-bot systems rely on **User-Agent** as a first-line signal.
* Use a small curated list of modern UA strings, not random junk.
* Optionally vary `Accept-Language` and other harmless headers slightly.

### Headless & TLS Fingerprinting

* Modern headless Chromium (as used by Playwright) no longer sets certain obvious automation flags, and its network stack generates the same TLS fingerprint as a real browser.
* Pure Python HTTP clients (including `httpx`) expose different **JA3 fingerprints**, which sophisticated anti-bot services can detect.
* Practical rule:

  * Accept that some domains may **block HTTP but allow browsers**.
  * Funnel those domains directly to Playwright after a first failure.

### CAPTCHA & Bot Walls

* Implement `is_captcha_page(content)` using:

  * Known DOM patterns (reCAPTCHA widgets, common challenge templates).
  * Keywords like “captcha”, “are you a robot?” in HTML (with care for false positives).

* Policy:

  * If HTTP hits a CAPTCHA → escalate once to browser.
  * If browser still hits CAPTCHA / bot wall → record `status="captcha"` or `status="blocked"` and stop.

No external solving or hacky bypasses.

### Politeness & Rate Limiting

* Domain-level concurrencies (e.g. 1–2 for big search engines) and **random jitter** between requests reduce detection.
* Spread URLs chronologically; avoid spiky bursts to the same host.
* This is both “good citizenship” and a practical way to lower block rates.

---

## Multilingual & Data Handling

* **Encoding:** rely on `httpx`’s charset detection; if needed, override `response.encoding`. Selectolax can parse UTF-8 bytes; convert once and then treat everything as Unicode.

* **Structure over text:** target elements by **CSS classes, ids, `data-*` attributes**, not human text. This keeps extraction valid for multiple languages.

* **Locale-specific values:** for dates, numbers, prices:

  * In the scraper: **capture raw text**, do not normalize.
  * Downstream code can handle locale parsing.

* **Output encoding:** write JSONL/CSV in UTF-8; ensure your JSON dumps set `ensure_ascii=False` so non-ASCII characters are preserved.

---

## Security Considerations

### Target-Side

* Respect **robots.txt** and tone down concurrency for sensitive domains.
* Avoid scraping non-public or login-protected content unless explicitly authorized.

### TLS & Fingerprints

* Be aware that `httpx` identifies as a generic TLS client; some WAFs use JA3 fingerprints to flag such clients.
* Using **Playwright** on difficult domains ensures your requests look like Chrome over the network.

### Secrets

* Keep `proxy.json` out of version control (only commit `proxy.json.example`).
* In CI, store real credentials in secrets and inject them at runtime.

### Logging Hygiene

* Never log:

  * Full HTML (can contain PII).
  * Secrets or proxy credentials.

* Log only:

  * URL (or hash), HTTP code, latency, `status` classification, possibly truncated error messages.

---

## Observability & Metrics

Use the `UrlStats` / `RunSummary` model sketched in the architect prompt.

### Per-URL (`UrlStats`)

Store:

* `method`: `"httpx"` or `"playwright"`.
* `stage`: `"primary"` or `"fallback"`.
* `status`: `"success" | "captcha" | "robots" | "blocked" | "error"`.
* `latency_ms`, `content_len`, `http_status`.
* Flags: `captcha_detected`, `robots_disallowed`.

### Per-Run (`RunSummary`)

Aggregate:

* Total URLs, successes, failures.
* CAPTCHA and robots counts.
* HTTP vs Playwright counts.
* P50/P90/P95 latencies per method.
* Start/finish timestamps, library versions, `schema_version`.

### Notebook Visualizations

* **Latency histograms** for HTTP and Playwright.
* **Stacked bar**: method usage per domain.
* **Pie or bar**: status distribution (success / robots / captcha / errors).
* **Domain table**: top domains by URL count and failure/CAPTCHA rate.

### SLOs & Alerts (in notebook)

* Example SLOs for 1k–10k URLs:

  * Success rate (excluding robots/captcha) ≥ 90%.
  * HTTP P95 latency ≤ 1.5 s.
  * Playwright P95 latency ≤ 12–15 s.
  * Browser fallback share ≤ 40%.

* If SLOs are violated, print prominent warnings and suggested next steps (e.g. reduce concurrency, adjust timeouts, revisit heuristics).

---

## Performance Optimizations

### HTTP Path

* Exploit async concurrency:

  * ~16–32 in-flight requests is a good starting point.
  * Use HTTP/2 where available to reuse connections efficiently.

* Keep parsing tight:

  * Selectolax completes parses in milliseconds even for large SERPs, significantly faster than BS4/lxml.

### Browser Path

* Block heavy assets as described.
* Limit concurrent browser contexts (1–2).
* Restart the browser periodically (e.g. every 50–100 pages).
* Use specific selectors for waits instead of `networkidle` when possible; this often shortens load time on sites with background polling.

### Scheduling & Overlap

* Overlap work where practical:

  * While some URLs are in Playwright, keep HTTP fetches going for other shards.
  * At small scale you can keep it simple (Stage 1 then Stage 2), but the design can be extended to fully overlapped producer/consumer queues.

### Timeouts & Fail Fast

* Don’t let a single URL stall the run:

  * HTTP timeout ~ 10 s.
  * Playwright navigation timeout ~ 15–20 s.
  * Cap retries and then classify appropriately.

---

## Reliability & Error Handling

### Retry Policy

* HTTP:

  * Retry transient failures up to 2 times with backoff.
  * Classify final failure with an `error_code` (“timeout”, “dns_error”, etc).

* Browser:

  * At most 1 retry in a fresh context; if it fails again → classify as `error` or `blocked`.

### Decision Safety Nets

* If HTTP stage returns partial data (some fields missing) but heuristics mis-classify it as “complete”, you can still:

  * Detect missing critical fields and escalate to browser for verification.

* This reduces silent data loss at the cost of a few extra browser calls.

### Isolation

* Failures are isolated:

  * Each URL is wrapped in try/except; one crash never aborts the whole shard.
  * Shards are independent; failures in one shard never corrupt another.

### Robots & Anti-bot Stop Rules

* If a domain produces **only CAPTCHA/blocked** outcomes in early URLs, consider:

  * Downgrading concurrency or short-circuiting the rest of its URLs and clearly reporting that they are unsalvageable under current constraints.

---

## Testing Strategy

### Unit Tests

* Parsing & extraction:

  * Controlled HTML fixtures (static and dynamic final HTML) → assert extracted fields.

* CAPTCHA detection:

  * Fixture with normal HTML vs typical CAPTCHA page; assert classifier behavior.

* Heuristics (`needs_browser`, data completeness):

  * Synthetic inputs to test all branches.

### Integration Tests

* HTTP mode:

  * Use a known static page (e.g. example.com) to test full HTTP→parse path.

* Browser mode:

  * Use a simple JS-only test site such as the `/js/` variant of *quotes.toscrape.com*, which returns content only after JS executes, demonstrating browser necessity.

* Hybrid:

  * Small list of mixed URLs to assert that:

    * Static page goes HTTP-only.
    * Dynamic page escalates to browser.
    * Invalid page is classified as failure.

### E2E & Scale Smoke Test

* Run on a small subset (e.g. 50–100 URLs) to:

  * Check performance.
  * Validate metrics.
  * Ensure no resource leaks or crashes.

### CI Integration

* Use pytest in **GitHub Actions**:

  * Set up Python, install dependencies, `playwright install --with-deps`.
  * Run tests on every push/PR.

This guarantees a fresh environment continuously validates the stack.

---

## CI/CD & Colab

* **CI (GitHub Actions)**:

  * Lint (ruff), type-check (mypy), run tests.
  * Confirm Playwright can run headless with installed browsers.

* **Deployment targets**:

  * Colab notebook (primary).
  * Optional: Docker image for local/CI runs.

* Documentation:

  * `README.md` with:

    * Quickstart (Colab, local, Docker).
    * SLOs and configuration knobs.
    * Known limitations and extension ideas.

---

## Example Implementation Timeline (1 Week)

**Day 1 – Repo & skeleton**

* Initialize repo, `pyproject.toml` / `requirements.txt`.
* Set up base CI workflow.
* Sketch models & configuration types.

**Day 2 – HTTP stack**

* Implement `ProxyManager`, `RunConfig`, `UrlJob`, `FastHttpFetcher`.
* Add simple tests for HTTP fetch and parsing.

**Day 3 – Browser stack**

* Integrate Playwright; implement `BrowserFetcher`, asset blocking, basic extraction.
* Confirm dynamic test site works.

**Day 4 – Strategy & orchestration**

* Implement `StrategyRouter`, `RobotsClient`, `DomainScheduler`.
* Build `ScrapeRunner` for a single batch; run small mixed set.

**Day 5 – Sharding, persistence, metrics**

* Implement `ShardedBatchRunner`, `ResultStore`, `CheckpointStore`.
* Implement `compute_run_summary` and notebook visualizations.

**Day 6 – Hardening & tests**

* Add retries, error taxonomy, CAPTCHA detection.
* Expand unit/integration tests; validate on ~100 URLs.

**Day 7 – Polish & docs**

* Tune concurrency/timeouts based on trial run.
* Finalize notebook narrative, plots, and this best-practices doc.
* Prepare short one-pager summarizing results and trade-offs.

---

## Conclusion

This guide describes a **2025-appropriate**, production-shaped approach to Tavily’s Web Research assignment:

* **HTTP-first, browser-second** architecture with clear decision logic.
* Modern, well-maintained tools (`httpx`, Selectolax, Playwright).
* Built-in support for proxies, robots.txt, anti-bot hygiene, multilingual content, and observability.
* A structure that runs comfortably on ~1k URLs in Colab but generalizes to 10k+ with parameter changes.

The result is a scraper that is **fast, accurate, cost-aware, and transparent**—and that can be read, tested, and extended by other engineers without surprises.
