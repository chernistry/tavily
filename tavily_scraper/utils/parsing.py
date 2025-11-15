"""HTML parsing helpers using Selectolax."""

from __future__ import annotations

from selectolax.parser import HTMLParser


def parse_html(html: str) -> HTMLParser:
    """Parse HTML string into a Selectolax HTMLParser tree."""
    return HTMLParser(html)


def extract_visible_text_lower(html: str) -> str:
    """
    Extract visible text (lowercased) from HTML, ignoring script/style tags.

    Selectolax's text() includes script contents, so we manually walk
    the tree and skip script/style nodes.
    """
    tree = HTMLParser(html)
    parts: list[str] = []

    for node in tree.root.traverse():  # type: ignore[union-attr]
        if node.tag in {"script", "style"}:
            continue
        # text(deep=False) to avoid re-traversing children
        txt = node.text(deep=False, strip=True)
        if txt:
            parts.append(txt)

    text = " ".join(parts)
    return text.lower()
