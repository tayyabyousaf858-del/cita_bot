"""Redis connection and pub/sub manager."""
import json
from typing import Any, Optional
import redis.asyncio as aioredis
import structlog

from app.core.config import settings

logger = structlog.get_logger()

redis_client: Optional[aioredis.Redis] = None


async def init_redis():
    global redis_client
    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    await redis_client.ping()
    logger.info("Redis connected")


def get_redis() -> aioredis.Redis:
    return redis_client


async def publish_event(channel: str, event_type: str, data: dict):
    """Publish event to Redis pub/sub channel."""
    message = json.dumps({"type": event_type, "data": data})
    await redis_client.publish(channel, message)


async def cache_set(key: str, value: Any, ttl: int = 300):
    await redis_client.setex(key, ttl, json.dumps(value))


async def cache_get(key: str) -> Optional[Any]:
    val = await redis_client.get(key)
    return json.loads(val) if val else None


async def cache_delete(key: str):
    await redis_client.delete(key)
