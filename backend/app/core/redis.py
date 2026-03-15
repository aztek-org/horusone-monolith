"""Async Redis client singleton for caching and session management."""

from __future__ import annotations

import logging

import redis.asyncio as redis

from app.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None  # type: ignore[type-arg]


async def get_redis() -> redis.Redis:  # type: ignore[type-arg]
    """Get or create the async Redis client singleton.

    Returns:
        An async Redis client connected to the configured URL.
    """
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        logger.info("Redis client created for %s", settings.redis_url)
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection gracefully.

    Should be called during application shutdown.
    """
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection closed")
