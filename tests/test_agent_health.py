"""Tests for the Agent Engine skeleton — health endpoint and root info.

Run with::

    pytest tests/test_agent_health.py -v
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi", reason="fastapi not installed — skip on orchestrator")
httpx = pytest.importorskip("httpx", reason="httpx not installed")

from httpx import ASGITransport, AsyncClient
from agent.main import app


@pytest.fixture()
async def client():
    """Async test client bound to the Agent FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Root info endpoint ──


@pytest.mark.anyio
async def test_root_returns_service_info(client: AsyncClient):
    """GET / should return basic service metadata."""
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "Sirus Agent Engine"
    assert "version" in body


# ── Health endpoint ──


@pytest.mark.anyio
async def test_health_returns_200(client: AsyncClient):
    """GET /health must always return 200 with the required fields."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    # Required fields per contracts/health-api.yaml
    assert "status" in body
    assert body["status"] in ("ok", "degraded", "error")
    assert "timestamp" in body
    assert "version" in body


@pytest.mark.anyio
async def test_health_contains_vllm_and_redis(client: AsyncClient):
    """Health response should report vLLM and Redis connectivity."""
    resp = await client.get("/health")
    body = resp.json()
    assert "vllm" in body
    assert body["vllm"] in ("connected", "disconnected")
    assert "redis" in body
    assert body["redis"] in ("connected", "disconnected")


@pytest.mark.anyio
async def test_health_status_enum(client: AsyncClient):
    """Status must be one of the contract-defined values."""
    resp = await client.get("/health")
    body = resp.json()
    assert body["status"] in {"ok", "degraded", "error"}


# ── Chat endpoint (supervisor unavailable) ──


@pytest.mark.anyio
async def test_chat_returns_503_when_supervisor_unavailable(client: AsyncClient):
    """POST /agent/chat should return 503 if no supervisor is loaded."""
    import agent.main as main_mod

    original = main_mod._supervisor
    # Force _get_supervisor to return None by setting a sentinel
    main_mod._supervisor = None

    # Patch _get_supervisor to always return None
    original_getter = main_mod._get_supervisor
    main_mod._get_supervisor = lambda: None
    try:
        resp = await client.post(
            "/agent/chat",
            json={"message": "hello"},
        )
        # 503 when supervisor cannot be imported
        assert resp.status_code == 503
    finally:
        main_mod._supervisor = original
        main_mod._get_supervisor = original_getter
