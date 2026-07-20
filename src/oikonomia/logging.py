"""Plain logging setup.

Standard-library logging with a simple, greppable format. Honours the
``OIK_LOG_LEVEL`` environment variable (default ``INFO``). Put run context
directly in the log message (f-strings) rather than through structured extras —
easier to read at a glance both locally and in Modal container logs.
"""

from __future__ import annotations

import logging
import os

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger (configures root logging once, on first use)."""
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(level=os.environ.get("OIK_LOG_LEVEL", "INFO"), format=_FORMAT)
        _CONFIGURED = True
    return logging.getLogger(name)
