"""
Command-line interface for the Tavily scraper.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from tavily_scraper.config.env import load_run_config
from tavily_scraper.pipelines.batch_runner import run_all
from tavily_scraper.stealth.config import StealthConfig
from tavily_scraper.utils.logging import get_logger

logger = get_logger(__name__)


async def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Tavily Scraper CLI")
    parser.add_argument(
        "--url",
        type=str,
        help="Single URL to scrape (overrides urls.txt)",
    )
    parser.add_argument(
        "--stealth",
        action="store_true",
        help="Enable stealth mode (anti-detection)",
    )
    parser.add_argument(
        "--stealth-mode",
        choices=["minimal", "moderate", "aggressive"],
        default="moderate",
        help="Stealth intensity mode (default: moderate)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default: True)",
    )
    parser.add_argument(
        "--no-headless",
        action="store_false",
        dest="headless",
        help="Run browser in headful mode",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        help="Session ID for persistent browser state (cookies, storage)",
    )

    args = parser.parse_args()

    # Load base config
    config = load_run_config()

    # Apply CLI overrides
    if args.stealth:
        if config.stealth_config is None:
            config.stealth_config = StealthConfig()
        
        config.stealth_config.enabled = True
        config.stealth_config.mode = args.stealth_mode
        logger.info(f"Stealth mode enabled: {args.stealth_mode}")

    # Headless override
    config.playwright_headless = args.headless
    if config.stealth_config:
        config.stealth_config.headless = args.headless

    # Session ID
    if args.session_id:
        config.session_id = args.session_id
        logger.info(f"Using session ID: {args.session_id}")

    # Single URL override (hack: write to temp file or handle in run_all)
    # For now, we'll just log it, as run_all expects a file. 
    # To support single URL properly, we'd need to modify run_all or write a temp file.
    # Given the constraints, we'll stick to the file-based approach or 
    # if the user really wants single URL, we can create a temp file.
    if args.url:
        logger.info(f"Scraping single URL: {args.url}")
        # Create a temporary file for this run
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            tmp.write(args.url)
            tmp_path = Path(tmp.name)
        
        config.urls_path = tmp_path

    try:
        await run_all(config=config)
    except Exception as e:
        logger.error(f"Run failed: {e}")
        sys.exit(1)
    finally:
        if args.url and 'tmp_path' in locals():
            import os
            os.unlink(tmp_path)


if __name__ == "__main__":
    asyncio.run(main())
