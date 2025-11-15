"""
Proxy manager for httpx and Playwright clients.

This module provides:
- Unified proxy configuration management
- Client-specific proxy URL formatting
- SOCKS5 support for httpx
- HTTP proxy support for Playwright
"""

from __future__ import annotations

from dataclasses import dataclass

from tavily_scraper.core.models import ProxyConfig

# ==== PROXY MANAGER ==== #

@dataclass
class ProxyManager:
    """
    Manages proxy configuration for different HTTP clients.

    This manager handles the differences between proxy formats
    required by httpx (URL string) and Playwright (dict).

    Attributes:
        config: Proxy configuration with host, ports, and credentials
    """

    config: ProxyConfig




    # --► FACTORY METHOD

    @classmethod
    def from_proxy_config(cls, config: ProxyConfig) -> ProxyManager:
        """
        Create ProxyManager from ProxyConfig.

        Args:
            config: Proxy configuration

        Returns:
            ProxyManager instance

        Example:
            config = ProxyConfig(
                host="proxy.example.com",
                http_port=8080,
                https_port=8443,
                socks5_port=1080,
                username="user",
                password="pass",
            )
            manager = ProxyManager.from_proxy_config(config)
        """
        return cls(config=config)




    # --► CLIENT-SPECIFIC PROXY FORMATTERS

    def httpx_proxy(self) -> str:
        """
        Get proxy URL for httpx client.

        Uses SOCKS5 protocol which provides better compatibility
        and performance for HTTP/HTTPS traffic.

        Returns:
            SOCKS5 proxy URL with optional authentication

        Format:
            With auth: socks5://user:pass@host:port
            Without auth: socks5://host:port

        Note:
            httpx supports SOCKS5 via the httpx[socks] extra.
        """
        host = self.config.host
        port = self.config.socks5_port

        if self.config.username and self.config.password:
            return (
                f"socks5://{self.config.username}:{self.config.password}"
                f"@{host}:{port}"
            )

        return f"socks5://{host}:{port}"




    def playwright_proxy(self) -> dict[str, str]:
        """
        Get proxy configuration dict for Playwright.

        Uses HTTP protocol because Playwright's SOCKS5 support
        doesn't handle authentication reliably.

        Returns:
            Dictionary with server, username, and password keys

        Format:
            {
                "server": "http://host:port",
                "username": "user",
                "password": "pass"
            }

        Note:
            Empty strings for username/password are acceptable
            when authentication is not required.
        """
        host = self.config.host

        return {
            "server": f"http://{host}:{self.config.http_port}",
            "username": self.config.username or "",
            "password": self.config.password or "",
        }
