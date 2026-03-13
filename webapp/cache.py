"""
Redis caching layer for KMD.

Falls back to in-memory LRU cache when Redis is unavailable.
"""
import os
import json
import hashlib
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "")
_redis = None
_redis_checked = False
_fallback_cache: dict[str, tuple[float, str]] = {}  # key -> (expiry_ts, value_json)

DEFAULT_TTL = 3600  # 1 hour


async def get_redis():
    """Get or create Redis connection. Returns None if unavailable."""
    global _redis, _redis_checked
    if _redis is not None:
        return _redis
    if _redis_checked:
        return None
    if not REDIS_URL:
        _redis_checked = True
        return None
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        await _redis.ping()
        logger.info("[CACHE] Redis connected at %s", REDIS_URL)
        return _redis
    except Exception as e:
        logger.warning("[CACHE] Redis unavailable, using in-memory fallback: %s", e)
        _redis = None
        _redis_checked = True
        return None


def _make_key(prefix: str, *args, **kwargs) -> str:
    """Create a cache key from prefix and arguments."""
    raw = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"kmd:{prefix}:{h}"


async def cache_get(key: str) -> Optional[str]:
    """Get value from cache (Redis or fallback)."""
    r = await get_redis()
    if r:
        try:
            return await r.get(key)
        except Exception:
            pass
    # Fallback: in-memory
    if key in _fallback_cache:
        expiry, val = _fallback_cache[key]
        if expiry > time.time():
            return val
        del _fallback_cache[key]
    return None


async def cache_set(key: str, value: str, ttl: int = DEFAULT_TTL):
    """Set value in cache with TTL."""
    r = await get_redis()
    if r:
        try:
            await r.setex(key, ttl, value)
            return
        except Exception:
            pass
    # Fallback: in-memory
    _fallback_cache[key] = (time.time() + ttl, value)
    # Bound fallback cache size — evict oldest entries when over limit
    if len(_fallback_cache) > 1000:
        oldest = sorted(_fallback_cache.items(), key=lambda x: x[1][0])[:100]
        for k, _ in oldest:
            _fallback_cache.pop(k, None)


async def cache_invalidate(prefix: str):
    """Invalidate all keys with given prefix."""
    r = await get_redis()
    if r:
        try:
            keys = []
            async for key in r.scan_iter(f"kmd:{prefix}:*"):
                keys.append(key)
            if keys:
                await r.delete(*keys)
        except Exception:
            pass
    # Fallback
    to_remove = [k for k in _fallback_cache if k.startswith(f"kmd:{prefix}:")]
    for k in to_remove:
        _fallback_cache.pop(k, None)
