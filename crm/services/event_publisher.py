import json

import redis.asyncio as aioredis

from crm.config import settings

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """获取 Redis 连接（懒加载单例）。"""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def publish_event(channel: str, payload: dict) -> None:
    """将事件以 JSON 格式发布到指定的 Redis 频道。"""
    r = await get_redis()
    await r.publish(channel, json.dumps(payload, ensure_ascii=False, default=str))


async def close_redis() -> None:
    """关闭 Redis 连接并重置单例。"""
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
