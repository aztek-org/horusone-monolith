"""Postgres integration coverage for UserPreferencesRepository.

Unlike the unit suite (which mocks the session entirely), these tests exercise
the real ORM/JSONB persistence path against a live database, plus the Redis
serialization round-trip via an in-process fake.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.repositories import user_preferences_repo as prefs_module
from app.db.repositories.user_preferences_repo import (
    UserPreferencesRepository,
    _cache_key,
)
from app.models.user import User
from app.models.user_preferences import UserPreferences

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL is required for preferences integration tests",
)


class _FakeRedis:
    """Minimal async Redis stand-in backed by a dict."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


@pytest.fixture
async def session_factory():
    engine = create_async_engine(DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    fake = _FakeRedis()

    async def _get_redis() -> _FakeRedis:
        return fake

    monkeypatch.setattr(prefs_module, "get_redis", _get_redis)
    return fake


@pytest.fixture
async def user_id(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    uid = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            User(
                id=uid,
                keycloak_id=f"kc-{uid}",
                email=f"{uid}@prefs.test",
                display_name="Prefs Tester",
            )
        )
        await db.commit()
    try:
        yield uid
    finally:
        async with session_factory() as db:
            await db.execute(delete(UserPreferences).where(UserPreferences.user_id == uid))
            await db.execute(delete(User).where(User.id == uid))
            await db.commit()


@pytest.mark.asyncio
async def test_cache_hit_serves_prefs_after_row_removed(
    session_factory: async_sessionmaker[AsyncSession],
    fake_redis: _FakeRedis,
    user_id: uuid.UUID,
) -> None:
    # Regression for #76: a warm cache must be served without touching the DB.
    # Deleting the row after warming the cache makes any DB fall-back return None.
    repo = UserPreferencesRepository()
    async with session_factory() as db:
        await repo.upsert(db, user_id, {"theme": "dark", "voice": {"volume": 5}})
        await db.commit()

    assert _cache_key(user_id) in fake_redis.store

    async with session_factory() as db:
        await db.execute(delete(UserPreferences).where(UserPreferences.user_id == user_id))
        await db.commit()

    async with session_factory() as db:
        result = await repo.get_by_user_id(db, user_id)

    assert result is not None
    assert result.user_id == user_id
    assert result.preferences == {"theme": "dark", "voice": {"volume": 5}}


@pytest.mark.asyncio
async def test_upsert_deep_merges_and_persists(
    session_factory: async_sessionmaker[AsyncSession],
    fake_redis: _FakeRedis,
    user_id: uuid.UUID,
) -> None:
    repo = UserPreferencesRepository()
    async with session_factory() as db:
        await repo.upsert(db, user_id, {"voice": {"volume": 5}, "theme": "dark"})
        await db.commit()
    async with session_factory() as db:
        await repo.upsert(db, user_id, {"voice": {"rate": 2}})
        await db.commit()

    await repo.invalidate_cache(user_id)
    async with session_factory() as db:
        result = await repo.get_by_user_id(db, user_id)

    assert result is not None
    assert result.preferences == {"voice": {"volume": 5, "rate": 2}, "theme": "dark"}


@pytest.mark.asyncio
async def test_invalidate_then_read_repopulates_cache(
    session_factory: async_sessionmaker[AsyncSession],
    fake_redis: _FakeRedis,
    user_id: uuid.UUID,
) -> None:
    repo = UserPreferencesRepository()
    async with session_factory() as db:
        await repo.upsert(db, user_id, {"theme": "light"})
        await db.commit()

    await repo.invalidate_cache(user_id)
    assert _cache_key(user_id) not in fake_redis.store

    async with session_factory() as db:
        result = await repo.get_by_user_id(db, user_id)

    assert result is not None
    assert result.preferences == {"theme": "light"}
    assert _cache_key(user_id) in fake_redis.store
