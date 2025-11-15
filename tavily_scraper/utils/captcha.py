"""
CAPTCHA detection utilities for identifying anti-bot challenges.

This module provides:
- Multi-vendor CAPTCHA detection (reCAPTCHA, hCaptcha, Turnstile)
- Cloudflare challenge page detection
- Generic bot verification pattern matching
- Confidence scoring for detections
"""

from __future__ import annotations

from typing import Literal, TypedDict

# ==== TYPE DEFINITIONS ==== #

CaptchaVendor = Literal[
    "recaptcha",
    "hcaptcha",
    "turnstile",
    "cloudflare_block",
    "generic_block",
    "unknown",
]
"""
CAPTCHA vendor identifiers.

- recaptcha: Google reCAPTCHA
- hcaptcha: hCaptcha service
- turnstile: Cloudflare Turnstile
- cloudflare_block: Cloudflare browser check
- generic_block: Generic bot verification
- unknown: Unidentified CAPTCHA
"""




class CaptchaDetection(TypedDict):
    """
    CAPTCHA detection result with metadata.

    Attributes:
        present: Whether CAPTCHA was detected
        vendor: Identified CAPTCHA vendor (if any)
        confidence: Detection confidence score (0.0-1.0)
        reason: Human-readable detection reason
    """

    present: bool
    vendor: CaptchaVendor | None
    confidence: float
    reason: str




# ==== DETECTION LOGIC ==== #

def detect_captcha_http(
    status_code: int,
    url: str,
    headers: dict[str, str],
    body: str | None,
) -> CaptchaDetection:
    """
    Detect CAPTCHA presence from HTTP response.

    This function analyzes HTTP response content for CAPTCHA indicators:
    1. Vendor-specific widget/script signatures (high confidence)
    2. Cloudflare challenge page patterns
    3. Generic bot verification text (requires multiple signals)

    Args:
        status_code: HTTP status code
        url: Request URL (currently unused, reserved for future heuristics)
        headers: Response headers (currently unused, reserved for future)
        body: Response body HTML content

    Returns:
        CaptchaDetection with presence flag, vendor, confidence, and reason

    Note:
        Only the first 200KB of body is analyzed to avoid performance
        issues with very large responses.
    """
    if not body:
        return {
            "present": False,
            "vendor": None,
            "confidence": 0.0,
            "reason": "",
        }

    # --► NORMALIZE BODY FOR PATTERN MATCHING
    body_lc = body[:200_000].lower()
    vendor: CaptchaVendor | None = None
    confidence = 0.0
    reasons: list[str] = []

    # --► URL PATTERN DETECTION
    url_lower = url.lower()
    if any(
        pattern in url_lower
        for pattern in ["captcha", "challenge", "robot", "verify-human", "challenges.cloudflare.com"]
    ):
        confidence = 0.6
        reasons.append("captcha/challenge in URL")

    # --► HEADER SIGNALS
    server = headers.get("server", "").lower()
    if "cloudflare" in server or "cf-ray" in headers:
        if status_code in {403, 503}:
            confidence = max(confidence, 0.7)
            reasons.append("cloudflare + blocking status")


    # --► VENDOR WIDGET/SCRIPT DETECTION (HIGH CONFIDENCE)

    if "g-recaptcha" in body_lc or "recaptcha/api.js" in body_lc:
        vendor = "recaptcha"
        confidence = 0.95
        reasons.append("recaptcha widget/script")

    elif "h-captcha" in body_lc or "hcaptcha.com/1/api.js" in body_lc:
        vendor = "hcaptcha"
        confidence = 0.95
        reasons.append("hcaptcha widget/script")

    elif (
        "cf-turnstile" in body_lc
        or "cf-turnstile-response" in body_lc
        or "challenges.cloudflare.com/turnstile" in body_lc
    ):
        vendor = "turnstile"
        confidence = 0.95
        reasons.append("turnstile widget")

    # --► CLOUDFLARE CHALLENGE PAGE DETECTION

    if "checking your browser before accessing" in body_lc:
        vendor = vendor or "cloudflare_block"
        confidence = max(confidence, 0.9)
        reasons.append("cloudflare browser check")

    # --► GENERIC HUMAN VERIFICATION (REQUIRES MULTIPLE SIGNALS)

    generic_phrases = [
        "please verify you are a human",
        "are you a robot",
        "access has been denied",
        "automation tools to browse the website",
    ]
    generic_hits = sum(phrase in body_lc for phrase in generic_phrases)

    # Require both text patterns AND suspicious status code
    if generic_hits >= 2 and status_code in {403, 429, 503}:
        vendor = vendor or "generic_block"
        confidence = max(confidence, 0.8)
        reasons.append(
            f"generic verification text ({generic_hits} hits) + {status_code}"
        )

    # --► RETURN DETECTION RESULT

    if vendor:
        return {
            "present": True,
            "vendor": vendor,
            "confidence": confidence,
            "reason": "; ".join(reasons),
        }

    return {
        "present": False,
        "vendor": None,
        "confidence": 0.0,
        "reason": "",
    }




# ==== LEGACY COMPATIBILITY ==== #

def is_captcha_page(content: str | None) -> bool:
    """
    Simple CAPTCHA detection for legacy compatibility.

    This is a simplified wrapper around detect_captcha_http()
    that returns only a boolean result.

    Args:
        content: HTML content to check

    Returns:
        True if CAPTCHA detected, False otherwise

    Note:
        Prefer detect_captcha_http() for new code as it provides
        richer detection metadata.
    """
    if not content:
        return False

    detection = detect_captcha_http(200, "", {}, content)
    return detection["present"]


async def detect_captcha_playwright(page) -> CaptchaDetection:  # type: ignore[no-untyped-def]
    """
    Detect CAPTCHA from Playwright page after JS execution.

    Provides enhanced detection using:
    - Frame URLs (for embedded CAPTCHA iframes)
    - Post-JS DOM content
    - Final page URL

    Args:
        page: Playwright Page object

    Returns:
        CaptchaDetection with presence, vendor, confidence, and reason
    """
    url = page.url
    content = (await page.content()).lower()
    frames = page.frames

    vendor: CaptchaVendor | None = None
    reasons: list[str] = []
    conf = 0.0

    # --► FRAME URL DETECTION
    frame_urls = " ".join(f.url.lower() for f in frames if f.url)

    if "google.com/recaptcha" in content or "g-recaptcha" in content:
        vendor = "recaptcha"
        conf = 0.95
        reasons.append("recaptcha widget/script")

    elif "hcaptcha.com" in frame_urls or "h-captcha" in content:
        vendor = "hcaptcha"
        conf = 0.95
        reasons.append("hcaptcha widget in frame")

    elif "cf-turnstile" in content or "challenges.cloudflare.com/turnstile" in content:
        vendor = "turnstile"
        conf = 0.95
        reasons.append("turnstile widget")

    # --► CLOUDFLARE CHALLENGE
    if "checking your browser before accessing" in content:
        vendor = vendor or "cloudflare_block"
        conf = max(conf, 0.9)
        reasons.append("cloudflare browser check")

    # --► GENERIC VERIFICATION TEXT
    generic_phrases = [
        "please verify you are a human",
        "are you a robot",
        "access has been denied",
        "automation tools to browse the website",
    ]
    generic_hits = sum(phrase in content for phrase in generic_phrases)

    if generic_hits >= 2 and conf < 0.8:
        vendor = vendor or "generic_block"
        conf = 0.8
        reasons.append(f"generic verification text ({generic_hits} hits)")

    # --► URL PATTERN DETECTION
    url_lower = url.lower()
    if any(
        pattern in url_lower
        for pattern in ["captcha", "challenge", "robot", "verify-human"]
    ):
        if not vendor:
            vendor = "unknown"
            conf = 0.7
        reasons.append("captcha/challenge in URL")

    if vendor:
        return {
            "present": True,
            "vendor": vendor,
            "confidence": conf,
            "reason": "; ".join(reasons),
        }

    return {
        "present": False,
        "vendor": None,
        "confidence": 0.0,
        "reason": "",
    }

