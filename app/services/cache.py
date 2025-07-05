import json
import redis.asyncio as redis
from typing import Any, Optional, Callable, TypeVar
from functools import wraps

from app.core.config import settings

# Type variable for the decorated function's return type
R = TypeVar('R')

class CacheService:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None

    async def connect(self):
        if not self.redis_client:
            self.redis_client = redis.from_url(
                settings.redis_url,
                password=settings.redis_password,
                max_connections=settings.redis_max_connections,
                decode_responses=True # Decode responses to Python strings
            )
            await self.redis_client.ping()

    async def disconnect(self):
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None

    async def get(self, key: str) -> Optional[Any]:
        if not self.redis_client:
            await self.connect()
        value = await self.redis_client.get(key)
        if value:
            return json.loads(value)
        return None

    async def set(self, key: str, value: Any, ex: Optional[int] = None):
        if not self.redis_client:
            await self.connect()
        await self.redis_client.set(key, json.dumps(value), ex=ex)

    async def delete(self, key: str):
        if not self.redis_client:
            await self.connect()
        await self.redis_client.delete(key)

    async def increment(self, key: str, amount: int = 1) -> int:
        if not self.redis_client:
            await self.connect()
        return await self.redis_client.incr(key, amount)

    async def decrement(self, key: str, amount: int = 1) -> int:
        if not self.redis_client:
            await self.connect()
        return await self.redis_client.decr(key, amount)

    async def exists(self, key: str) -> bool:
        if not self.redis_client:
            await self.connect()
        return await self.redis_client.exists(key)

    async def expire(self, key: str, ttl: int):
        if not self.redis_client:
            await self.connect()
        await self.redis_client.expire(key, ttl)

    async def get_set(self, key: str, value: Any) -> Optional[Any]:
        if not self.redis_client:
            await self.connect()
        old_value = await self.redis_client.getset(key, json.dumps(value))
        if old_value:
            return json.loads(old_value)
        return None

# Cache decorators
def cached(key_prefix: str, ex: int = 300):
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> R:
            cache_key = f"{key_prefix}:{func.__name__}:{json.dumps(args)}:{json.dumps(kwargs)}"
            cached_result = await cache_service.get(cache_key)
            if cached_result:
                return cached_result
            
            result = await func(*args, **kwargs)
            await cache_service.set(cache_key, result, ex=ex)
            return result
        return wrapper
    return decorator

# Global cache instance
cache_service = CacheService()