"""Centralised logging configuration for the Agent Engine.

Produces structured JSON-style log records so they can be collected by
the monitoring stack on data_center (W4).

Call :func:`setup_logging` once at application startup (inside
``main.py``).  All modules under the ``agent`` package will inherit
this configuration.
"""

import logging
import sys
from typing import Optional


def setup_logging(level: Optional[str] = None) -> logging.Logger:
    """Configure the root ``agent`` logger and return it.

    Parameters
    ----------
    level:
        Log level name (DEBUG / INFO / WARNING / ERROR).
        Falls back to ``settings.LOG_LEVEL`` when *None*.

    Returns
    -------
    logging.Logger
        The configured ``agent`` logger.
    """
    if level is None:
        # Deferred import to avoid circular dependency at module scope
        from agent.config import settings
        level = settings.LOG_LEVEL

    log_level = getattr(logging, level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt=(
            '{"time":"%(asctime)s",'
            '"level":"%(levelname)s",'
            '"name":"%(name)s",'
            '"message":"%(message)s"}'
        ),
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger("agent")
    root_logger.setLevel(log_level)
    # Avoid duplicate handlers when reloading
    if not root_logger.handlers:
        root_logger.addHandler(handler)

    return root_logger
