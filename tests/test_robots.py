"""Tests for robots client."""

import pytest
from pytest_httpx import HTTPXMock

from tavily_scraper.core.robots import RobotsClient


@pytest.mark.asyncio
async def test_robots_allow(httpx_mock: HTTPXMock) -> None:
    """Test robots.txt allows URL."""
    httpx_mock.add_response(
        url="https://example.com/robots.txt",
        text="User-agent: *\nAllow: /\n",
    )

    import httpx

    client = httpx.AsyncClient()
    robots = RobotsClient(client)
    assert await robots.can_fetch("https://example.com/page")


@pytest.mark.asyncio
async def test_robots_disallow(httpx_mock: HTTPXMock) -> None:
    """Test robots.txt disallows URL."""
    httpx_mock.add_response(
        url="https://example.com/robots.txt",
        text="User-agent: *\nDisallow: /private\n",
    )

    import httpx

    client = httpx.AsyncClient()
    robots = RobotsClient(client)
    assert not await robots.can_fetch("https://example.com/private/page")
    assert await robots.can_fetch("https://example.com/public/page")


@pytest.mark.asyncio
async def test_robots_unreachable(httpx_mock: HTTPXMock) -> None:
    """Test unreachable robots.txt allows all."""
    httpx_mock.add_response(
        url="https://example.com/robots.txt",
        status_code=404,
    )

    import httpx

    client = httpx.AsyncClient()
    robots = RobotsClient(client)
    assert await robots.can_fetch("https://example.com/page")
