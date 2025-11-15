"""
Robots.txt compliance checking with caching.

This module implements:
- Async robots.txt fetching and parsing
- Per-domain caching to avoid repeated fetches
- Graceful fallback when robots.txt is unavailable
- Proxy support for robots.txt requests
- Thread-safe access with async locks
"""

from __future__ import annotations

import asyncio
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from tavily_scraper.config.proxies import ProxyManager
from tavily_scraper.core.models import ProxyConfig, RunConfig
from tavily_scraper.utils.logging import get_logger




# ==== ROBOTS.TXT CLIENT ==== #

class RobotsClient:
    """
    Async robots.txt client with per-domain caching.

    This client:
    - Fetches robots.txt files asynchronously
    - Caches parsed rules per domain
    - Uses thread-safe locking for cache access
    - Falls back to "allow" if robots.txt unavailable

    Attributes:
        _client: Async HTTP client for fetching robots.txt
        _parsers: Cache of parsed robots.txt per domain
        _lock: Async lock for thread-safe cache access
        _user_agent: Default User-Agent for robots.txt checks
        _logger: Logger instance
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        user_agent: str = "TavilyScraper",
    ) -> None:
        """
        Initialize robots.txt client.

        Args:
            client: Configured async HTTP client
            user_agent: Default User-Agent string for checks

        Note:
            The client should be configured with appropriate
            timeout and proxy settings before passing here.
        """
        self._client = client
        self._parsers: dict[str, RobotFileParser] = {}
        self._lock = asyncio.Lock()
        self._user_agent = user_agent
        self._logger = get_logger(__name__)




    # --► PUBLIC API

    async def can_fetch(
        self,
        url: str,
        user_agent: Optional[str] = None,
    ) -> bool:
        """
        Check if URL can be fetched according to robots.txt.

        This method:
        1. Extracts domain from URL
        2. Fetches and caches robots.txt if not already cached
        3. Checks if URL is allowed for given User-Agent

        Args:
            url: Target URL to check
            user_agent: Optional User-Agent override (defaults to instance UA)

        Returns:
            True if fetch is allowed, False if disallowed

        Note:
            If robots.txt fetch fails or parsing errors occur,
            defaults to True (allow) to avoid blocking legitimate requests.
        """
        ua = user_agent or self._user_agent
        parsed = urlparse(url)
        domain = parsed.netloc

        # --► CACHE LOOKUP WITH LOCK
        async with self._lock:
            parser = self._parsers.get(domain)

            if parser is None:
                parser = await self._fetch_and_parse(domain, parsed.scheme)
                self._parsers[domain] = parser

        # --► PERMISSION CHECK
        try:
            return parser.can_fetch(ua, url)
        except Exception:
            self._logger.warning(
                "robots_check_failed",
                extra={"domain": domain},
            )
            return True




    # --► INTERNAL HELPERS

    async def _fetch_and_parse(
        self,
        domain: str,
        scheme: str,
    ) -> RobotFileParser:
        """
        Fetch and parse robots.txt for domain.

        This method:
        1. Constructs robots.txt URL
        2. Fetches content with timeout
        3. Parses rules using RobotFileParser
        4. Returns empty parser if fetch fails

        Args:
            domain: Target domain name
            scheme: URL scheme (http or https)

        Returns:
            RobotFileParser with parsed rules or empty rules on failure

        Note:
            Failures (404, timeout, proxy errors) result in empty
            parser which allows all requests by default.
        """
        robots_url = f"{scheme}://{domain}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)

        try:
            resp = await self._client.get(robots_url, timeout=5.0)

            # --► HANDLE HTTP ERRORS
            if resp.status_code >= 400:
                parser.parse([])
                return parser

            # --► PARSE SUCCESSFUL RESPONSE
            parser.parse(resp.text.splitlines())

        except Exception as e:
            # ⚠️ GRACEFUL FALLBACK ON FETCH FAILURE
            # If robots.txt fetch fails (proxy issues, DNS, timeout),
            # allow by default to avoid blocking legitimate requests
            self._logger.debug(
                f"robots_fetch_failed for {domain}: {type(e).__name__}"
            )
            parser.parse([])

        return parser




# ==== FACTORY FUNCTION ==== #

async def make_robots_client(
    run_config: RunConfig,
    proxy_config: Optional[ProxyConfig],
) -> RobotsClient:
    """
    Create RobotsClient with optional proxy configuration.

    This factory function:
    1. Creates HTTP client with or without proxy
    2. Configures redirect following
    3. Returns initialized RobotsClient

    Args:
        run_config: Runtime configuration
        proxy_config: Optional proxy configuration

    Returns:
        Configured RobotsClient instance

    Note:
        The HTTP client created here is separate from the main
        scraping client to avoid interference with rate limiting.
    """
    client: httpx.AsyncClient

    if proxy_config is not None:
        proxy_manager = ProxyManager.from_proxy_config(proxy_config)
        proxy_url = proxy_manager.httpx_proxy()
        client = httpx.AsyncClient(follow_redirects=True, proxy=proxy_url)
    else:
        client = httpx.AsyncClient(follow_redirects=True)

    return RobotsClient(client=client)
