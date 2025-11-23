"""Tests for browser fetcher."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tavily_scraper.core.models import RunConfig, RunnerContext, UrlJob, UrlStr
from tavily_scraper.core.scheduler import DomainScheduler
from tavily_scraper.pipelines.browser_fetcher import browser_lifecycle, fetch_one


class _SimpleHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler serving a fixed HTML body."""

    # Body is injected via a class attribute for simplicity in tests.
    body: str = "<html><body>OK</body></html>"

    def do_GET(self) -> None:
        payload = self.body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        # Silence default HTTP server logging in tests.
        return


def _run_server(server: HTTPServer) -> None:
    with server:
        server.serve_forever()


def _make_test_server(html: str) -> tuple[HTTPServer, str]:
    """Start a simple local HTTP server that serves the given HTML."""
    _SimpleHandler.body = html
    server = HTTPServer(("127.0.0.1", 0), _SimpleHandler)
    thread = threading.Thread(target=_run_server, args=(server,), daemon=True)
    thread.start()
    addr = server.server_address
    host = addr[0] if isinstance(addr[0], str) else addr[0].decode()
    port = addr[1]
    return server, f"http://{host}:{port}"


class _AllowAllRobots:
    async def can_fetch(self, url: str, user_agent: str | None = None) -> bool:
        """Always allow fetching; used to avoid network in tests."""
        return True


def _make_runner_context() -> RunnerContext:
    """Create a minimal RunnerContext suitable for browser_fetcher tests."""
    run_config = RunConfig()
    scheduler = DomainScheduler(global_limit=4)
    robots_client = _AllowAllRobots()
    # browser_fetcher.fetch_one does not touch http_client, so a dummy value is safe.
    return RunnerContext(
        run_config=run_config,
        proxy_manager=None,
        scheduler=scheduler,
        robots_client=robots_client,  # type: ignore[arg-type]
        http_client=None,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_fetch_one_renders_dynamic_content() -> None:
    """Browser fetcher should see JS-rendered content not present in initial HTML."""
    # The literal string "Dynamic content" is only produced at runtime
    # by concatenating two substrings; it does not appear in the raw HTML.
    static_html = """
    <html>
      <body>
        <div id="root"></div>
        <script>
          document.addEventListener('DOMContentLoaded', function () {
            const el = document.getElementById('root');
            if (el) {
              el.textContent = 'Dynamic ' + 'content';
            }
          });
        </script>
      </body>
    </html>
    """
    assert "Dynamic content" not in static_html

    server, url = _make_test_server(static_html)
    ctx = _make_runner_context()

    try:
        async with browser_lifecycle(ctx.run_config, None) as browser:
            job: UrlJob = {
                "url": UrlStr(url),
                "is_dynamic_hint": None,
                "shard_id": 0,
                "index_in_shard": 0,
            }
            result = await fetch_one(job, ctx, browser)

        assert result["status"] == "success"
        assert result["method"] == "playwright"
        assert result["content_len"] > 0
        # Final HTML should contain the dynamically inserted text.
        assert "Dynamic content" in (result.get("content") or "")
    finally:
        server.shutdown()


@pytest.mark.asyncio
async def test_fetch_one_captcha_page_sets_status() -> None:
    """Pages that look like CAPTCHA/bot walls should be classified accordingly."""
    captcha_html = """
    <html><body>
    <h1>Access Denied</h1>
    <p>Please verify you are a human.</p>
    <div class="g-recaptcha" data-sitekey="abc"></div>
    </body></html>
    """
    server, url = _make_test_server(captcha_html)
    ctx = _make_runner_context()

    try:
        async with browser_lifecycle(ctx.run_config, None) as browser:
            job: UrlJob = {
                "url": UrlStr(url),
                "is_dynamic_hint": None,
                "shard_id": 0,
                "index_in_shard": 0,
            }
            result = await fetch_one(job, ctx, browser)

        assert result["status"] == "captcha_detected"
        assert result["captcha_detected"] is True
        # block_type and vendor are stored in optional fields.
        assert result.get("block_type") == "captcha"
        assert result.get("block_vendor") is not None
    finally:
        server.shutdown()

