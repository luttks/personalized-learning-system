from functools import lru_cache

import redis.asyncio as redis

from app.core.config import settings


@lru_cache
def get_redis_client() -> redis.Redis:
    """Redis instance dùng chung cho các nhu cầu ngoài Celery (VD: rate limiting)."""
    return redis.from_url(settings.redis_url, decode_responses=True)
