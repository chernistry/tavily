"""Tests for CAPTCHA detection."""

from tavily_scraper.utils.captcha import detect_captcha_http


def test_detect_recaptcha() -> None:
    """Test reCAPTCHA detection."""
    html = '<div class="g-recaptcha" data-sitekey="abc123"></div>'
    result = detect_captcha_http(200, "https://example.com", {}, html)
    assert result["present"]
    assert result["vendor"] == "recaptcha"
    assert result["confidence"] >= 0.9


def test_detect_hcaptcha() -> None:
    """Test hCaptcha detection."""
    html = '<div class="h-captcha" data-sitekey="xyz789"></div>'
    result = detect_captcha_http(200, "https://example.com", {}, html)
    assert result["present"]
    assert result["vendor"] == "hcaptcha"
    assert result["confidence"] >= 0.9


def test_detect_turnstile() -> None:
    """Test Cloudflare Turnstile detection."""
    html = '<div class="cf-turnstile" data-sitekey="test"></div>'
    result = detect_captcha_http(200, "https://example.com", {}, html)
    assert result["present"]
    assert result["vendor"] == "turnstile"
    assert result["confidence"] >= 0.9


def test_detect_cloudflare_block() -> None:
    """Test Cloudflare browser check detection."""
    html = "<html><body>Checking your browser before accessing example.com</body></html>"
    result = detect_captcha_http(403, "https://example.com", {}, html)
    assert result["present"]
    assert result["vendor"] == "cloudflare_block"
    assert result["confidence"] >= 0.8


def test_detect_generic_block() -> None:
    """Test generic human verification detection."""
    html = """
    <html><body>
    <h1>Access Denied</h1>
    <p>Please verify you are a human.</p>
    <p>We believe you are using automation tools to browse the website.</p>
    </body></html>
    """
    result = detect_captcha_http(403, "https://example.com", {}, html)
    assert result["present"]
    assert result["vendor"] == "generic_block"
    assert result["confidence"] >= 0.7


def test_no_captcha_normal_page() -> None:
    """Test normal page without CAPTCHA."""
    html = "<html><body><h1>Welcome</h1><p>Normal content here</p></body></html>"
    result = detect_captcha_http(200, "https://example.com", {}, html)
    assert not result["present"]
    assert result["vendor"] is None


def test_no_false_positive_single_phrase() -> None:
    """Test that single phrase doesn't trigger false positive."""
    html = "<html><body><p>Our TOS: we deny automation tools.</p></body></html>"
    result = detect_captcha_http(200, "https://example.com", {}, html)
    assert not result["present"]  # Only 1 phrase, not 2+
