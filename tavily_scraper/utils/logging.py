"""
Logging configuration and utilities.

This module provides:
- Centralized logger creation
- Consistent log formatting across modules
- Structured logging setup
"""

from __future__ import annotations

import logging




# ==== LOGGER FACTORY ==== #

def get_logger(name: str) -> logging.Logger:
    """
    Get or create logger with standardized formatting.

    This function ensures all loggers in the application
    use consistent formatting and configuration.

    Args:
        name: Logger name (typically __name__ from calling module)

    Returns:
        Configured logging.Logger instance

    Format:
        YYYY-MM-DD HH:MM:SS,mmm LEVEL module.name message

    Example:
        logger = get_logger(__name__)
        logger.info("Processing started")
        # Output: 2025-11-15 10:30:45,123 INFO tavily_scraper.core Processing started

    Note:
        Logger is configured only on first call for each name.
        Subsequent calls return the existing logger instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger
