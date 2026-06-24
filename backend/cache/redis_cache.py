"""
Redis caching utilities.

Provides get/set operations with graceful degradation — if Redis is
unavailable, the application continues to function without caching.
"""

import json
import logging
from typing import Any, Dict, Optional

import redis

import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

_redis_client: Optional[redis.Redis] = None
_connection_failed: bool = False  # Prevents repeated connection attempts


def get_redis_client() -> Optional[redis.Redis]:
    """
    Return a shared Redis client, or None if Redis is unavailable.

    After a failed connection attempt the client won't retry until
    ``reset_redis_connection`` is called (avoids log spam).
    """
    global _redis_client, _connection_failed

    if _connection_failed:
        return None

    if _redis_client is not None:
        return _redis_client

    try:
        _redis_client = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            password=config.REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        _redis_client.ping()
        logger.info("Redis connection established (%s:%s)", config.REDIS_HOST, config.REDIS_PORT)
    except (redis.ConnectionError, redis.TimeoutError) as exc:
        logger.warning("Redis unavailable — caching disabled (%s)", exc)
        _redis_client = None
        _connection_failed = True

    return _redis_client


def reset_redis_connection() -> None:
    """Allow the next ``get_redis_client`` call to retry the connection."""
    global _redis_client, _connection_failed
    _redis_client = None
    _connection_failed = False


# ---------------------------------------------------------------------------
# Public cache API
# ---------------------------------------------------------------------------


def cache_get(key: str) -> Optional[Dict[str, Any]]:
    """Retrieve a JSON-serialized value from Redis. Returns ``None`` on miss or error."""
    client = get_redis_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
        if raw is not None:
            return json.loads(raw)
    except (redis.RedisError, json.JSONDecodeError) as exc:
        logger.warning("Cache read failed for key '%s': %s", key, exc)
    return None


def cache_set(key: str, value: Dict[str, Any], ttl: int) -> None:
    """Store a JSON-serializable value in Redis with the given TTL (seconds)."""
    client = get_redis_client()
    if client is None:
        return
    try:
        client.setex(key, ttl, json.dumps(value, default=str))
    except redis.RedisError as exc:
        logger.warning("Cache write failed for key '%s': %s", key, exc)
