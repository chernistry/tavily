"""CAPTCHA detection utilities."""

from __future__ import annotations

from typing import Literal, TypedDict

CaptchaVendor = Literal[
    "recaptcha", "hcaptcha", "turnstile", "cloudflare_block", "generic_block", "unknown"
]


class CaptchaDetection(TypedDict):
    """CAPTCHA detection result."""

    present: bool
    vendor: CaptchaVendor | None
    confidence: float
    reason: str


def detect_captcha_http(
    status_code: int,
    url: str,
    headers: dict[str, str],
    body: str | None,
) -> CaptchaDetection:
    """Detect CAPTCHA from HTTP response."""
    if not body:
        return {"present": False, "vendor": None, "confidence": 0.0, "reason": ""}

    body_lc = body[:200_000].lower()
    vendor: CaptchaVendor | None = None
    confidence = 0.0
    reasons: list[str] = []

    # Vendor widget/script detection (high confidence)
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

    # Cloudflare challenge page
    if "checking your browser before accessing" in body_lc:
        vendor = vendor or "cloudflare_block"
        confidence = max(confidence, 0.9)
        reasons.append("cloudflare browser check")

    # Generic human verification (require multiple signals)
    generic_phrases = [
        "please verify you are a human",
        "are you a robot",
        "access has been denied",
        "automation tools to browse the website",
    ]
    generic_hits = sum(phrase in body_lc for phrase in generic_phrases)

    if generic_hits >= 2 and status_code in {403, 429, 503}:
        vendor = vendor or "generic_block"
        confidence = max(confidence, 0.8)
        reasons.append(f"generic verification text ({generic_hits} hits) + {status_code}")

    if vendor:
        return {
            "present": True,
            "vendor": vendor,
            "confidence": confidence,
            "reason": "; ".join(reasons),
        }

    return {"present": False, "vendor": None, "confidence": 0.0, "reason": ""}


def is_captcha_page(content: str | None) -> bool:
    """Simple CAPTCHA detection (legacy compatibility)."""
    if not content:
        return False
    detection = detect_captcha_http(200, "", {}, content)
    return detection["present"]
