"""Tests for the Agent Engine skeleton — health endpoint and root info.

Run with::

    pytest tests/test_agent_health.py -v

These tests validate that the FastAPI app boots correctly and that
``/health`` conforms to ``contracts/agent-api.yaml → HealthResponse``.
"""

from __future__ import annotations

from datetime import datetime

import pytest

fastapi = pytest.importorskip("fastapi", reason="fastapi not installed — skip on orchestrator")
httpx_mod = pytest.importorskip("httpx", reason="httpx not installed")

from fastapi.testclient import TestClient

from agent.main import app


@pytest.fixture()
def client():
    """Synchronous test client — no Redis / vLLM required."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── Root info endpoint ──────────────────────────────────────────────


class TestRootEndpoint:
    """GET / should return basic service metadata."""

    def test_root_returns_200(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_root_returns_service_name(self, client: TestClient):
        body = client.get("/").json()
        assert body["service"] == "Sirus Agent Engine"

    def test_root_returns_version(self, client: TestClient):
        body = client.get("/").json()
        assert "version" in body


# ── Health endpoint ─────────────────────────────────────────────────


class TestHealthEndpoint:
    """GET /health must conform to contracts/agent-api.yaml HealthResponse."""

    def test_health_returns_200(self, client: TestClient):
        """GET /health must always return 200."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_required_fields(self, client: TestClient):
        """Response must include status, vllm, redis, timestamp, version."""
        body = client.get("/health").json()
        for field in ("status", "vllm", "redis", "timestamp", "version"):
            assert field in body, f"Missing field: {field}"

    def test_health_status_enum(self, client: TestClient):
        """status must be one of ok / degraded / error."""
        body = client.get("/health").json()
        assert body["status"] in {"ok", "degraded", "error"}

    def test_health_vllm_values(self, client: TestClient):
        """vllm must be 'connected' or 'disconnected'."""
        body = client.get("/health").json()
        assert body["vllm"] in ("connected", "disconnected")

    def test_health_redis_values(self, client: TestClient):
        """redis must be 'connected' or 'disconnected'."""
        body = client.get("/health").json()
        assert body["redis"] in ("connected", "disconnected")

    def test_health_timestamp_is_iso(self, client: TestClient):
        """timestamp must be a valid ISO-8601 datetime string."""
        ts = client.get("/health").json()["timestamp"]
        datetime.fromisoformat(ts)

    def test_health_version_present(self, client: TestClient):
        """version must be a non-empty string."""
        ver = client.get("/health").json()["version"]
        assert isinstance(ver, str) and len(ver) > 0


# ── Chat endpoint (supervisor unavailable) ──────────────────────────


class TestChatEndpoint:
    """POST /agent/chat should return 503 when supervisor is not loaded."""

    def test_chat_returns_503_when_supervisor_unavailable(self, client: TestClient):
        """Without a SupervisorAgent the endpoint must return 503."""
        import agent.main as main_mod

        original_sup = main_mod._supervisor
        original_getter = main_mod._get_supervisor

        main_mod._supervisor = None
        main_mod._get_supervisor = lambda: None
        try:
            resp = client.post("/agent/chat", json={"message": "hello"})
            assert resp.status_code == 503
        finally:
            main_mod._supervisor = original_sup
            main_mod._get_supervisor = original_getter


# ── Stub endpoints exist ────────────────────────────────────────────


class TestStubEndpoints:
    """Placeholder routes must be routable (not 404)."""

    def test_evaluate_endpoint_exists(self, client: TestClient):
        resp = client.post("/agent/evaluate", json={"test_message": "hi"})
        assert resp.status_code != 404
