"""Centralised logging configuration for the Agent Engine.

Produces structured JSON-style log records so they can be collected by
the monitoring stack on data_center (W4).
"""

import logging
import sys

from agent.config import settings


def setup_logging() -> logging.Logger:
    """Configure the root ``agent`` logger and return it.

    Call once at application startup (inside ``main.py``).  All modules
    under the ``agent`` package will inherit this configuration.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

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
