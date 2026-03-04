"""Redis session management for conversation history."""

import json
from datetime import datetime

import redis.asyncio as redis

from agent.config import settings

_redis_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_pool


async def save_message(session_id: str, role: str, content: str) -> None:
    r = await get_redis()
    message = json.dumps({
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    })
    key = f"session:{session_id}:messages"
    await r.rpush(key, message)
    await r.ltrim(key, -50, -1)
    await r.expire(key, 86400)


async def get_history(session_id: str, limit: int = 20) -> list[dict]:
    r = await get_redis()
    key = f"session:{session_id}:messages"
    raw = await r.lrange(key, -limit, -1)
    return [json.loads(m) for m in raw]
