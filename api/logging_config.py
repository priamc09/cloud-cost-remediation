"""
Central logging configuration for the Cloud Cost Optimizer.

Call configure_logging() once at application startup (main.py).
All modules obtain their logger via:
    logger = logging.getLogger(__name__)

Log levels map to:
    DEBUG   – detailed per-resource metric calls, pagination, internal state
    INFO    – pipeline milestones, service init, blob sync, job status changes
    WARNING – recoverable issues: missing blob on first run, 404 from metrics API,
              empty metric series, individual analyzer failures
    ERROR   – unexpected exceptions in service calls that prevent partial results
    CRITICAL– unrecoverable startup failures (bad DB provider, missing credentials)

Format (console):
    2026-05-08 14:30:22 | INFO     | api.routers.jobs       | [run=abc12345] Pipeline started
"""
from __future__ import annotations

import logging
import logging.config
import sys
from typing import Any


_DEFAULT_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: str = "INFO") -> None:
    """
    Configure the root logger with a structured console handler.
    Safe to call multiple times (idempotent via dictConfig).

    Parameters
    ----------
    level : str
        Logging level for the application loggers (DEBUG/INFO/WARNING/ERROR).
        Third-party noisy loggers are pinned to WARNING regardless.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {
                "format": _DEFAULT_FORMAT,
                "datefmt": _DATE_FORMAT,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "console",
                "level": numeric_level,
            },
        },
        "loggers": {
            # Application root — covers all api.* modules
            "api": {
                "level": numeric_level,
                "handlers": ["console"],
                "propagate": False,
            },
            # Third-party: reduce noise
            "azure": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "httpx":  {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "httpcore": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "uvicorn.access": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        },
        "root": {
            "level": numeric_level,
            "handlers": ["console"],
        },
    }
    logging.config.dictConfig(config)
    logging.getLogger("api").info(
        "Logging configured | level=%s", level.upper()
    )