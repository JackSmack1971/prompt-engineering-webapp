import orjson
import redis.asyncio as redis
from typing import Any, Optional, Callable, TypeVar
from functools import wraps
import hashlib

from app.core.config import settings
from app.exceptions.custom_exceptions import InternalServerError # Import the custom exception

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

    def _check_connection(self):
        if not self.redis_client:
            raise InternalServerError(message="Redis client not connected. Ensure connect() is called during application startup.")

    async def get(self, key: str) -> Optional[Any]:
        self._check_connection()
        value = await self.redis_client.get(key)
        if value:
            return orjson.loads(value)
        return None

    async def set(self, key: str, value: Any, ex: Optional[int] = None):
        self._check_connection()
        await self.redis_client.set(key, orjson.dumps(value), ex=ex)

    async def delete(self, key: str):
        self._check_connection()
        await self.redis_client.delete(key)

    async def increment(self, key: str, amount: int = 1) -> int:
        self._check_connection()
        return await self.redis_client.incr(key, amount)

    async def decrement(self, key: str, amount: int = 1) -> int:
        self._check_connection()
        return await self.redis_client.decr(key, amount)

    async def exists(self, key: str) -> bool:
        self._check_connection()
        return await self.redis_client.exists(key)

    async def expire(self, key: str, ttl: int):
        self._check_connection()
        await self.redis_client.expire(key, ttl)

    async def get_set(self, key: str, value: Any) -> Optional[Any]:
        self._check_connection()
        old_value = await self.redis_client.getset(key, orjson.dumps(value))
        if old_value:
            return orjson.loads(old_value)
        return None

# Cache decorators
def cached(key_prefix: str, ex: int = 300):
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> R:
            # Generate a more efficient cache key using SHA256 hash
            hashed_args = hashlib.sha256(orjson.dumps(args)).hexdigest()[:16]
            hashed_kwargs = hashlib.sha256(orjson.dumps(kwargs)).hexdigest()[:16]
            cache_key = f"{key_prefix}:{func.__name__}:{hashed_args}:{hashed_kwargs}"
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