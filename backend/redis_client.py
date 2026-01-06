"""Shared Redis client singleton for the application."""
import os
import redis

# Singleton Redis clients
_redis_client = None
_async_redis_client = None


def get_redis_client():
    """Get or create the Redis client singleton."""
    global _redis_client
    
    if _redis_client is None:
        if os.getenv('USE_FAKE_REDIS', '').lower() == 'true':
            import fakeredis
            _redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
            print("Initialized fakeredis client (singleton)")
        else:
            from app_config import settings
            _redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    
    return _redis_client


def get_async_redis_client():
    """Get or create the async Redis client singleton."""
    global _async_redis_client
    
    if _async_redis_client is None:
        if os.getenv('USE_FAKE_REDIS', '').lower() == 'true':
            import fakeredis
            _async_redis_client = fakeredis.FakeAsyncRedis(decode_responses=True)
        else:
            from app_config import settings
            _async_redis_client = redis.asyncio.Redis.from_url(settings.redis_url, decode_responses=True)
    
    return _async_redis_client
