"""Sirus AI CRM Agent Engine — FastAPI application.

Entrypoint for the Agent Engine.  Start with::

    uvicorn agent.main:app --host 0.0.0.0 --port 8100

The ``/health`` endpoint reports connectivity to **vLLM** and **Redis**
and conforms to ``contracts/health-api.yaml``.
"""

from __future__ import annotations

import uuid
import time
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import __version__
from agent.config import settings
from agent.logging_config import setup_logging
from agent.session import save_message, get_redis

# ── Logging ──
logger = setup_logging()

app = FastAPI(
    title="Sirus Agent Engine",
    version=__version__,
    description="AI Agent 引擎 — CRM 的大脑",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Lazy import for SupervisorAgent — keeps the skeleton bootable even when
# the full supervisor module is not yet implemented.
# ---------------------------------------------------------------------------
_supervisor: Any = None


def _get_supervisor() -> Any:
    """Return the singleton SupervisorAgent, importing lazily."""
    global _supervisor
    if _supervisor is None:
        try:
            from agent.supervisor import SupervisorAgent

            _supervisor = SupervisorAgent()
            logger.info("SupervisorAgent loaded successfully")
        except Exception as exc:
            logger.warning("SupervisorAgent unavailable: %s", exc)
            _supervisor = None
    return _supervisor


# ── Request / Response schemas ─────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Incoming chat message from a user (or the DingTalk gateway)."""

    message: str
    session_id: str | None = None
    user_id: str | None = None
    stream: bool = False


class ToolCallInfo(BaseModel):
    """Summary of a single Tool call executed during the conversation."""

    tool: str | None = None
    args: dict | None = None
    result_summary: str | None = None


class ChatResponse(BaseModel):
    """Agent reply returned to the caller."""

    reply: str
    session_id: str
    intent: str | None = None
    agent_used: str | None = None
    tool_calls: list[ToolCallInfo] = Field(default_factory=list)
    model_used: str | None = None
    latency_ms: int | None = None


class HealthResponse(BaseModel):
    """Health-check payload (``contracts/health-api.yaml``)."""

    status: str  # ok | degraded | error
    vllm: str | None = None  # connected | disconnected
    redis: str | None = None  # connected | disconnected
    timestamp: str
    version: str = __version__


class EvalRequest(BaseModel):
    """Evaluation harness request (``contracts/agent-api.yaml``)."""

    test_message: str
    expected_intent: str | None = None
    expected_tool: str | None = None
    session_id: str | None = None


class EvalResponse(BaseModel):
    """Evaluation harness response."""

    reply: str
    intent: str | None = None
    intent_correct: bool | None = None
    tool_calls: list[ToolCallInfo] = Field(default_factory=list)
    tool_correct: bool | None = None
    latency_ms: int | None = None
    model_used: str | None = None


# ── Endpoints ──────────────────────────────────────────────────────────────


@app.get("/", tags=["Info"])
async def root() -> dict:
    """Return basic service information."""
    return {
        "service": "Sirus Agent Engine",
        "version": __version__,
        "docs": "/docs",
    }


@app.post("/agent/chat", response_model=ChatResponse, tags=["Chat"])
async def agent_chat(req: ChatRequest) -> ChatResponse:
    """Send a message and receive the Agent reply.

    Workflow: message → Supervisor intent detection → delegate to sub-Agent
    → Tool Calling → structured reply.
    """
    start = time.monotonic()
    session_id = req.session_id or str(uuid.uuid4())

    try:
        await save_message(session_id, "user", req.message)
    except Exception:
        logger.warning("Failed to persist user message for session %s", session_id)

    supervisor = _get_supervisor()
    if supervisor is None:
        raise HTTPException(
            status_code=503,
            detail="Agent supervisor is not available. Please try again later.",
        )

    try:
        result: dict = await supervisor.route(req.message, session_id)
    except Exception as exc:
        logger.error("Supervisor error for session %s: %s", session_id, exc)
        raise HTTPException(
            status_code=502,
            detail="Agent processing failed. Please retry.",
        ) from exc

    reply = result.get("reply", "")

    try:
        await save_message(session_id, "assistant", reply)
    except Exception:
        logger.warning("Failed to persist assistant reply for session %s", session_id)

    elapsed_ms = int((time.monotonic() - start) * 1000)

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        intent=result.get("intent"),
        agent_used=result.get("agent_used"),
        tool_calls=[ToolCallInfo(**tc) for tc in result.get("tool_calls", [])],
        model_used=result.get("model_used"),
        latency_ms=result.get("latency_ms", elapsed_ms),
    )


@app.post("/agent/evaluate", response_model=EvalResponse, tags=["Evaluation"])
async def agent_evaluate(req: EvalRequest) -> EvalResponse:
    """Run a single evaluation case for automated quality testing.

    See ``contracts/agent-api.yaml`` ``/agent/evaluate``.
    """
    start = time.monotonic()
    session_id = req.session_id or str(uuid.uuid4())

    supervisor = _get_supervisor()
    if supervisor is None:
        raise HTTPException(status_code=503, detail="Agent supervisor unavailable.")

    try:
        result: dict = await supervisor.route(req.test_message, session_id)
    except Exception as exc:
        logger.error("Evaluation error: %s", exc)
        raise HTTPException(status_code=502, detail="Agent evaluation failed.") from exc

    detected_intent = result.get("intent")
    tool_calls_raw: list[dict] = result.get("tool_calls", [])
    tool_names = [tc.get("tool") for tc in tool_calls_raw]

    elapsed_ms = int((time.monotonic() - start) * 1000)

    return EvalResponse(
        reply=result.get("reply", ""),
        intent=detected_intent,
        intent_correct=(
            detected_intent == req.expected_intent
            if req.expected_intent is not None
            else None
        ),
        tool_calls=[ToolCallInfo(**tc) for tc in tool_calls_raw],
        tool_correct=(
            req.expected_tool in tool_names
            if req.expected_tool is not None
            else None
        ),
        latency_ms=elapsed_ms,
        model_used=result.get("model_used"),
    )


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Return the health status of the Agent Engine.

    Checks connectivity to **vLLM** and **Redis**.
    Response conforms to ``contracts/health-api.yaml``.
    """
    vllm_status = "disconnected"
    redis_status = "disconnected"

    # ── vLLM probe ──
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.VLLM_BASE_URL}/models")
            if resp.status_code == 200:
                vllm_status = "connected"
    except Exception as exc:
        logger.debug("vLLM health-check failed: %s", exc)

    # ── Redis probe ──
    try:
        r = await get_redis()
        await r.ping()
        redis_status = "connected"
    except Exception as exc:
        logger.debug("Redis health-check failed: %s", exc)

    # ── Aggregate ──
    if vllm_status == "connected" and redis_status == "connected":
        status = "ok"
    elif vllm_status == "connected" or redis_status == "connected":
        status = "degraded"
    else:
        status = "error"

    return HealthResponse(
        status=status,
        vllm=vllm_status,
        redis=redis_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
