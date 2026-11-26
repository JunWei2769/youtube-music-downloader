"""
Purpose: Configure package logging.

- Keep routine provider chatter silent by default
- Send warnings and verbose diagnostics to stderr

Responsibility: Logging configuration
"""

import logging

LOGGER_NAME = "ytmusic_dl"

def configure_logging(verbose: bool = False) -> None:
    """Configure package logging for CLI use."""

    logger = logging.getLogger(LOGGER_NAME)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
    logger.propagate = False

def get_logger(name: str) -> logging.Logger:
    """Return a logger inside the package namespace."""

    return logging.getLogger(f"{LOGGER_NAME}.{name}")
