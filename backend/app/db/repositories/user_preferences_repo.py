"""Repository for user preferences with Redis caching."""

from __future__ import annotations

import copy
import json
import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.models.user_preferences import UserPreferences

logger = logging.getLogger(__name__)

# Redis key prefix and TTL
_CACHE_PREFIX = "prefs"
_CACHE_TTL_SECONDS = 3600  # 1 hour


def _cache_key(user_id: uuid.UUID) -> str:
    """Build the Redis cache key for a user's preferences.

    Args:
        user_id: The user's UUID.

    Returns:
        A string of the form ``prefs:{user_id}``.
    """
    return f"{_CACHE_PREFIX}:{user_id}"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into *base* (non-destructive).

    Nested dicts are merged; all other types are replaced.

    Args:
        base: The existing dictionary.
        override: Values to overlay.

    Returns:
        A new dictionary with merged values.
    """
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


class UserPreferencesRepository:
    """CRUD + caching repository for the ``user_preferences`` table.

    Read operations check Redis first, falling back to the database and
    warming the cache on miss.  Write operations update both the database
    and the cache atomically (best-effort for Redis).
    """

    # ── Read ───────────────────────────────────────────────────────

    async def get_by_user_id(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> UserPreferences | None:
        """Fetch preferences for a user, using the Redis cache when possible.

        Args:
            session: An async SQLAlchemy session.
            user_id: The user's UUID.

        Returns:
            The ``UserPreferences`` instance, or ``None`` if none exists.
        """
        # 1. Try Redis cache
        try:
            rd = await get_redis()
            cached = await rd.get(_cache_key(user_id))
            if cached is not None:
                logger.debug("Cache hit for prefs:%s", user_id)
                data = json.loads(cached)
                return self._dict_to_model(data)
        except Exception:
            logger.warning("Redis read failed for prefs:%s", user_id, exc_info=True)

        # 2. Fallback to DB
        result = await session.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )
        prefs = result.scalar_one_or_none()

        # 3. Warm cache on DB hit
        if prefs is not None:
            await self._set_cache(prefs)

        return prefs

    # ── Upsert ─────────────────────────────────────────────────────

    async def upsert(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        preferences: dict[str, Any],
    ) -> UserPreferences:
        """Create or deep-merge preferences for a user.

        If a row already exists the incoming *preferences* dict is deep-merged
        into the existing one.  Otherwise a new row is created.

        Args:
            session: An async SQLAlchemy session.
            user_id: The user's UUID.
            preferences: Preferences payload to merge.

        Returns:
            The updated (or newly created) ``UserPreferences`` row.
        """
        result = await session.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            merged = _deep_merge(existing.preferences or {}, preferences)
            existing.preferences = merged
            await session.flush()
            await session.refresh(existing)
            await self._set_cache(existing)
            return existing

        new_prefs = UserPreferences(
            user_id=user_id,
            preferences=preferences,
        )
        session.add(new_prefs)
        await session.flush()
        await session.refresh(new_prefs)
        await self._set_cache(new_prefs)
        return new_prefs

    # ── Cache helpers ──────────────────────────────────────────────

    async def invalidate_cache(self, user_id: uuid.UUID) -> None:
        """Remove the cached preferences for a user.

        Args:
            user_id: The user's UUID.
        """
        try:
            rd = await get_redis()
            await rd.delete(_cache_key(user_id))
        except Exception:
            logger.warning("Redis delete failed for prefs:%s", user_id, exc_info=True)

    async def _set_cache(self, prefs: UserPreferences) -> None:
        """Write a ``UserPreferences`` instance to Redis.

        Args:
            prefs: The ORM instance to cache.
        """
        try:
            rd = await get_redis()
            payload = {
                "id": str(prefs.id),
                "user_id": str(prefs.user_id),
                "preferences": prefs.preferences,
                "created_at": prefs.created_at.isoformat() if prefs.created_at else None,
                "updated_at": prefs.updated_at.isoformat() if prefs.updated_at else None,
            }
            await rd.setex(
                _cache_key(prefs.user_id),
                _CACHE_TTL_SECONDS,
                json.dumps(payload),
            )
        except Exception:
            logger.warning("Redis write failed for prefs:%s", prefs.user_id, exc_info=True)

    @staticmethod
    def _dict_to_model(data: dict[str, Any]) -> UserPreferences:
        """Rehydrate a ``UserPreferences`` instance from a cached dict.

        Note: the returned object is *detached* — it is not bound to any
        SQLAlchemy session.

        Args:
            data: The dictionary previously serialised to Redis.

        Returns:
            A transient ``UserPreferences`` ORM instance.
        """
        return UserPreferences(
            id=uuid.UUID(data["id"]),
            user_id=uuid.UUID(data["user_id"]),
            preferences=data["preferences"],
            created_at=(
                datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None
            ),
        )
