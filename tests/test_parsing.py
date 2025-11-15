"""Tests for HTML parsing helpers."""

from tavily_scraper.utils.parsing import extract_visible_text_lower, parse_html


def test_parse_html_basic() -> None:
    """HTML parser should build a tree without errors."""
    html = "<html><body><h1>Title</h1><p>Hello</p></body></html>"
    tree = parse_html(html)
    assert tree is not None
    # Basic sanity: root node should exist and contain text.
    assert "Hello" in (tree.text() or "")


def test_extract_visible_text_lower_excludes_script() -> None:
    """Visible text helper should ignore script contents."""
    html = """
    <html>
      <head><title>Test</title></head>
      <body>
        <h1>Hello</h1>
        <script>var msg = 'enable javascript';</script>
        <p>World</p>
      </body>
    </html>
    """
    text = extract_visible_text_lower(html)
    assert "hello" in text
    assert "world" in text
    # Text that appears only inside <script> should not be present.
    assert "enable javascript" not in text

