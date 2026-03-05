"""Tests for the Celery task infrastructure.

These tests verify:
1. The Celery app is configured correctly (broker URL, serialiser, etc.).
2. ``hello_task`` can be called **eagerly** (no running worker / broker needed).
3. ``hello_task`` returns the expected payload structure.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure ``scripts/`` is importable so ``tasks`` and ``celery_config`` resolve
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from celery_config import BROKER_URL, RESULT_BACKEND, create_celery_app  # noqa: E402
from tasks import app as celery_app, hello_task  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _eager_mode():
    """Run every task eagerly (in-process) so tests don't need a broker."""
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
    yield
    # Restore (not strictly necessary for isolated test runs, but tidy)
    celery_app.conf.update(
        task_always_eager=False,
        task_eager_propagates=False,
    )


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------


class TestCeleryConfig:
    """Validate Celery application configuration."""

    def test_broker_url_uses_redis(self):
        """Broker URL must point to a Redis instance."""
        assert BROKER_URL.startswith("redis://")

    def test_result_backend_uses_redis(self):
        """Result backend must point to a Redis instance."""
        assert RESULT_BACKEND.startswith("redis://")

    def test_serializer_is_json(self):
        """Task serialiser should be JSON for interoperability."""
        assert celery_app.conf.task_serializer == "json"

    def test_accept_content_json(self):
        """Only JSON content should be accepted."""
        assert "json" in celery_app.conf.accept_content

    def test_timezone(self):
        """Timezone should be Asia/Shanghai."""
        assert celery_app.conf.timezone == "Asia/Shanghai"

    def test_default_queue_name(self):
        """Default queue matches event-bus.yaml consumer group."""
        assert celery_app.conf.task_default_queue == "celery_workers"

    def test_create_celery_app_returns_celery_instance(self):
        """Factory should return a Celery app with correct name."""
        custom = create_celery_app("test_app")
        assert custom.main == "test_app"

    def test_task_acks_late(self):
        """Tasks should be acknowledged late for reliability."""
        assert celery_app.conf.task_acks_late is True

    def test_result_expires(self):
        """Results should expire after 1 hour."""
        assert celery_app.conf.result_expires == 3600


# ---------------------------------------------------------------------------
# Task tests
# ---------------------------------------------------------------------------


class TestHelloTask:
    """Validate ``hello_task`` behaviour (eager mode)."""

    def test_default_greeting(self):
        """Calling without arguments returns 'Hello, World!'."""
        result = hello_task.delay()
        payload = result.get(timeout=5)
        assert payload["message"] == "Hello, World!"
        assert "timestamp" in payload

    def test_custom_name(self):
        """Passing a name returns a personalised greeting."""
        result = hello_task.delay("Sirus")
        payload = result.get(timeout=5)
        assert payload["message"] == "Hello, Sirus!"

    def test_return_has_timestamp(self):
        """Result payload must include an ISO-format UTC timestamp."""
        result = hello_task.delay()
        payload = result.get(timeout=5)
        # Should be parseable as ISO datetime
        from datetime import datetime

        datetime.fromisoformat(payload["timestamp"])

    def test_direct_call(self):
        """Task can also be called synchronously (non-delay)."""
        payload = hello_task("CRM")
        assert payload["message"] == "Hello, CRM!"
        assert "timestamp" in payload

    def test_task_is_registered(self):
        """``hello_task`` must be registered in the Celery app."""
        assert "tasks.hello_task" in celery_app.tasks
