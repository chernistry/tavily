"""Tests for I/O utilities."""

from pathlib import Path
from tempfile import TemporaryDirectory

from tavily_scraper.utils.io import (
    ensure_canonical_urls_file,
    load_urls_from_csv,
    load_urls_from_txt,
    make_url_jobs,
)


def test_load_urls_from_txt() -> None:
    """Test loading URLs from text file."""
    with TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "urls.txt"
        path.write_text("https://example.com\nhttps://test.com\n\n")
        urls = load_urls_from_txt(path)
        assert urls == ["https://example.com", "https://test.com"]


def test_load_urls_from_csv() -> None:
    """Test loading URLs from CSV file."""
    with TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "urls.csv"
        path.write_text("url,other\nhttps://example.com,data\nhttps://test.com,more\n")
        urls = load_urls_from_csv(path)
        assert urls == ["https://example.com", "https://test.com"]


def test_ensure_canonical_urls_file() -> None:
    """Test canonical URL file creation."""
    with TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "urls.csv"
        txt_path = Path(tmpdir) / "urls.txt"
        csv_path.write_text("url\nhttps://example.com\n")

        result = ensure_canonical_urls_file(csv_path, txt_path)
        assert result == txt_path
        assert txt_path.exists()
        assert txt_path.read_text() == "https://example.com"


def test_make_url_jobs() -> None:
    """Test creating UrlJob objects."""
    urls = ["https://example.com", "https://test.com"]
    jobs = make_url_jobs(urls)
    assert len(jobs) == 2
    assert jobs[0]["url"] == "https://example.com"
    assert jobs[0]["shard_id"] == -1
    assert jobs[0]["is_dynamic_hint"] is None
