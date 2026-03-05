"""Celery task definitions – top-level module.

Start a worker with::

    cd scripts && celery -A tasks worker --loglevel=info

Or from the project root::

    celery -A scripts.tasks worker --loglevel=info

This module intentionally lives under ``scripts/`` per the project convention.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from celery_config import create_celery_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Celery app singleton
# ---------------------------------------------------------------------------
app = create_celery_app()

# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@app.task(bind=True, name="tasks.hello_task", max_retries=3, default_retry_delay=5)
def hello_task(self, name: str = "World") -> dict:
    """A simple verification task.

    Parameters
    ----------
    name:
        Whom to greet (default ``"World"``).

    Returns
    -------
    dict
        A greeting payload including a UTC timestamp.

    Raises
    ------
    Exception
        Any unexpected error is logged and re-raised after retry attempts
        are exhausted.

    Examples
    --------
    >>> result = hello_task.delay("Sirus")
    >>> result.get(timeout=10)
    {'message': 'Hello, Sirus!', 'timestamp': '...'}
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        greeting = f"Hello, {name}!"
        logger.info("hello_task executed: %s at %s", greeting, now)
        return {"message": greeting, "timestamp": now}
    except Exception as exc:
        logger.exception("hello_task failed: %s", exc)
        raise self.retry(exc=exc)
