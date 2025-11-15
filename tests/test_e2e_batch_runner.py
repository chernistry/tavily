"""E2E mini-run test for run_all."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from tavily_scraper.config.env import load_run_config
from tavily_scraper.pipelines.batch_runner import run_all


class _E2EHandler(BaseHTTPRequestHandler):
    """HTTP handler serving robots.txt and simple HTML pages."""

    def do_GET(self) -> None:  # type: ignore[override]
        if self.path == "/robots.txt":
            body = b"User-agent: *\nAllow: /\n"
            content_type = "text/plain; charset=utf-8"
        else:
            body = f"<html><body><h1>Page {self.path}</h1></body></html>".encode()
            content_type = "text/html; charset=utf-8"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        # Silence logging during tests.
        return


@pytest.fixture
def local_http_server() -> tuple[HTTPServer, str]:
    """Start a tiny local HTTP server for E2E tests."""
    server = HTTPServer(("127.0.0.1", 0), _E2EHandler)

    def _run() -> None:
        with server:
            server.serve_forever()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}"
    yield server, base_url
    server.shutdown()


@pytest.mark.asyncio
async def test_run_all_small_batch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, local_http_server: tuple[HTTPServer, str]) -> None:
    """End-to-end run_all over a tiny local URL set."""
    server, base_url = local_http_server
    del server  # unused, kept for fixture lifetime

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    urls_path = data_dir / "urls.txt"
    urls = [f"{base_url}/page-{i}" for i in range(5)]
    urls_path.write_text("\n".join(urls), encoding="utf-8")

    # Point the configuration at our temporary data directory.
    monkeypatch.setenv("TAVILY_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TAVILY_ENV", "ci")
    monkeypatch.delenv("PROXY_CONFIG_PATH", raising=False)

    config = load_run_config()
    summary = await run_all(config, use_browser=False)

    assert summary["total_urls"] == len(urls)

    stats_path = config.data_dir / "stats.jsonl"
    summary_path = config.data_dir / "run_summary.json"

    assert stats_path.exists()
    assert summary_path.exists()

    stats_lines = [ln for ln in stats_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(stats_lines) == len(urls)

    loaded_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert loaded_summary["total_urls"] == len(urls)
