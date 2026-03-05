"""Celery application configuration.

Uses Redis as both broker and result backend.
Redis connection follows ``contracts/event-bus.yaml``::

    host: 172.16.12.50
    port: 6379
    db:   0

Environment variables
---------------------
CELERY_BROKER_URL : str
    Override the default Redis broker URL.
CELERY_RESULT_BACKEND : str
    Override the default Redis result backend URL.
"""

import os

from celery import Celery

# ---------------------------------------------------------------------------
# Redis connection (defaults mirror contracts/event-bus.yaml)
# ---------------------------------------------------------------------------
_REDIS_HOST = os.getenv("REDIS_HOST", "172.16.12.50")
_REDIS_PORT = os.getenv("REDIS_PORT", "6379")
_REDIS_DB = os.getenv("REDIS_DB", "0")

BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    f"redis://{_REDIS_HOST}:{_REDIS_PORT}/{_REDIS_DB}",
)
RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    f"redis://{_REDIS_HOST}:{_REDIS_PORT}/{_REDIS_DB}",
)

# ---------------------------------------------------------------------------
# Celery application factory
# ---------------------------------------------------------------------------


def create_celery_app(name: str = "sirus_crm") -> Celery:
    """Create and configure a :class:`~celery.Celery` application.

    Parameters
    ----------
    name:
        Application / main module name used by Celery.

    Returns
    -------
    Celery
        A fully-configured Celery application instance.
    """
    app = Celery(name)

    app.conf.update(
        broker_url=BROKER_URL,
        result_backend=RESULT_BACKEND,
        # Serialisation
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        # Timezone
        timezone="Asia/Shanghai",
        enable_utc=True,
        # Reliability
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        # Result expiry – 1 hour
        result_expires=3600,
        # Queues matching event-bus.yaml consumer groups
        task_default_queue="celery_workers",
        task_routes={
            "tasks.hello_task": {"queue": "celery_workers"},
        },
    )

    return app
