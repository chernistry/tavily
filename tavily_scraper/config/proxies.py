"""Proxy manager for httpx and Playwright."""

from __future__ import annotations

from dataclasses import dataclass

from tavily_scraper.core.models import ProxyConfig


@dataclass
class ProxyManager:
    """Manages proxy configuration for different clients."""

    config: ProxyConfig

    @classmethod
    def from_proxy_config(cls, config: ProxyConfig) -> ProxyManager:
        """Create ProxyManager from ProxyConfig."""
        return cls(config=config)

    def httpx_proxy(self) -> str:
        """Get proxy URL for httpx - use SOCKS5 (works best)."""
        host = self.config.host
        port = self.config.socks5_port
        if self.config.username and self.config.password:
            return f"socks5://{self.config.username}:{self.config.password}@{host}:{port}"
        return f"socks5://{host}:{port}"

    def playwright_proxy(self) -> dict[str, str]:
        """Get proxy dict for Playwright - use HTTP (SOCKS5 auth not supported)."""
        host = self.config.host
        return {
            "server": f"http://{host}:{self.config.http_port}",
            "username": self.config.username or "",
            "password": self.config.password or "",
        }
