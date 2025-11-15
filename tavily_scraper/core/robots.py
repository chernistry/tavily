"""Robots.txt handling."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from tavily_scraper.config.proxies import ProxyManager
from tavily_scraper.core.models import ProxyConfig, RunConfig
from tavily_scraper.utils.logging import get_logger


class RobotsClient:
    """Async robots.txt client with caching."""

    def __init__(
        self, client: httpx.AsyncClient, user_agent: str = "TavilyScraper"
    ) -> None:
        self._client = client
        self._parsers: dict[str, RobotFileParser] = {}
        self._lock = asyncio.Lock()
        self._user_agent = user_agent
        self._logger = get_logger(__name__)

    async def can_fetch(self, url: str, user_agent: str | None = None) -> bool:
        """Check if URL can be fetched per robots.txt."""
        ua = user_agent or self._user_agent
        parsed = urlparse(url)
        domain = parsed.netloc
        async with self._lock:
            parser = self._parsers.get(domain)
            if parser is None:
                parser = await self._fetch_and_parse(domain, parsed.scheme)
                self._parsers[domain] = parser
        try:
            return parser.can_fetch(ua, url)
        except Exception:
            self._logger.warning("robots_check_failed", extra={"domain": domain})
            return True

    async def _fetch_and_parse(self, domain: str, scheme: str) -> RobotFileParser:
        """Fetch and parse robots.txt for domain."""
        robots_url = f"{scheme}://{domain}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        
        try:
            resp = await self._client.get(robots_url, timeout=5.0)
            if resp.status_code >= 400:
                parser.parse([])
                return parser
            parser.parse(resp.text.splitlines())
        except Exception as e:
            # If robots.txt fetch fails (proxy issues, DNS, etc), allow by default
            self._logger.debug(f"robots_fetch_failed for {domain}: {type(e).__name__}")
            parser.parse([])
        
        return parser


async def make_robots_client(
    run_config: RunConfig,
    proxy_config: ProxyConfig | None,
) -> RobotsClient:
    """Create RobotsClient with optional proxy configuration."""
    client: httpx.AsyncClient
    if proxy_config is not None:
        proxy_manager = ProxyManager.from_proxy_config(proxy_config)
        proxy_url = proxy_manager.httpx_proxy()
        client = httpx.AsyncClient(follow_redirects=True, proxy=proxy_url)
    else:
        client = httpx.AsyncClient(follow_redirects=True)
    return RobotsClient(client=client)
