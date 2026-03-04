"""Sirus AI CRM Agent Engine — FastAPI application."""

import uuid
import logging
from datetime import datetime, timezone

import httpx
import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.config import settings
from agent.session import save_message, get_redis
from agent.supervisor import SupervisorAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sirus Agent Engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supervisor = SupervisorAgent()


# ── Request / Response schemas ──

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str | None = None
    stream: bool = False


class ToolCallInfo(BaseModel):
    tool: str | None = None
    args: dict | None = None
    result_summary: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    intent: str | None = None
    agent_used: str | None = None
    tool_calls: list[ToolCallInfo] = Field(default_factory=list)
    model_used: str | None = None
    latency_ms: int | None = None


class HealthResponse(BaseModel):
    status: str
    vllm: str | None = None
    redis: str | None = None
    timestamp: str
    version: str = "0.1.0"


# ── Endpoints ──

@app.post("/agent/chat", response_model=ChatResponse)
async def agent_chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())

    await save_message(session_id, "user", req.message)

    result = await supervisor.route(req.message, session_id)

    reply = result.get("reply", "")
    await save_message(session_id, "assistant", reply)

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        intent=result.get("intent"),
        agent_used=result.get("agent_used"),
        tool_calls=[ToolCallInfo(**tc) for tc in result.get("tool_calls", [])],
        model_used=result.get("model_used"),
        latency_ms=result.get("latency_ms"),
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    vllm_status = "disconnected"
    redis_status = "disconnected"

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{settings.VLLM_BASE_URL}/models")
            if r.status_code == 200:
                vllm_status = "connected"
    except Exception:
        pass

    try:
        r = await get_redis()
        await r.ping()
        redis_status = "connected"
    except Exception:
        pass

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
