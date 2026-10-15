"""Unit tests for UserPreferencesRepository.

All database I/O is mocked via AsyncSession and Redis is replaced with an
in-process fake — no real DB or network connection needed.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories import user_preferences_repo as prefs_module
from app.db.repositories.user_preferences_repo import (
    UserPreferencesRepository,
    _cache_key,
    _deep_merge,
)
from app.models.user_preferences import UserPreferences

# ── Fakes and mock helpers ─────────────────────────────────────────────


class _FakeRedis:
    """Minimal async Redis stand-in backed by a dict."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.deleted: list[str] = []

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.store.pop(key, None)


def _mock_session(scalar_result: object = None) -> AsyncMock:
    """Return an AsyncSession mock whose execute() returns a scalar proxy."""
    session = AsyncMock()
    result_proxy = MagicMock()
    result_proxy.scalar_one_or_none.return_value = scalar_result
    session.execute.return_value = result_proxy
    return session


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    """Patch ``get_redis`` in the repository module with an in-process fake."""
    fake = _FakeRedis()

    async def _get_redis() -> _FakeRedis:
        return fake

    monkeypatch.setattr(prefs_module, "get_redis", _get_redis)
    return fake


# ── Pure helpers ───────────────────────────────────────────────────────


class TestPreferenceHelpers:
    """Tests for the module-level cache helpers."""

    def test_cache_key_format(self) -> None:
        user_id = uuid.uuid4()
        assert _cache_key(user_id) == f"prefs:{user_id}"

    def test_deep_merge_nested_dicts(self) -> None:
        base = {"voice": {"volume": 5, "rate": 1}, "theme": "dark"}
        override = {"voice": {"volume": 9}}
        merged = _deep_merge(base, override)

        assert merged == {"voice": {"volume": 9, "rate": 1}, "theme": "dark"}
        assert base == {"voice": {"volume": 5, "rate": 1}, "theme": "dark"}

    def test_deep_merge_replaces_scalar(self) -> None:
        assert _deep_merge({"theme": "dark"}, {"theme": "light"}) == {"theme": "light"}


# ── UserPreferencesRepository ──────────────────────────────────────────


class TestUserPreferencesRepository:
    """Tests for cached reads and upsert behaviour."""

    def test_dict_to_model_rehydrates_all_fields(self) -> None:
        # Regression for #76: rehydrating a cached payload must produce a
        # usable transient ORM instance, not raise AttributeError.
        prefs_id = uuid.uuid4()
        user_id = uuid.uuid4()
        data = {
            "id": str(prefs_id),
            "user_id": str(user_id),
            "preferences": {"voice": {"volume": 5}},
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-02-02T00:00:00+00:00",
        }

        prefs = UserPreferencesRepository._dict_to_model(data)

        assert isinstance(prefs, UserPreferences)
        assert prefs.id == prefs_id
        assert prefs.user_id == user_id
        assert prefs.preferences == {"voice": {"volume": 5}}
        assert prefs.created_at == datetime.fromisoformat(data["created_at"])
        assert prefs.updated_at == datetime.fromisoformat(data["updated_at"])

    @pytest.mark.asyncio
    async def test_get_by_user_id_cache_hit_returns_rehydrated_model(
        self, fake_redis: _FakeRedis
    ) -> None:
        # A cached payload must be served from Redis without touching the
        # database (regression for #76).
        user_id = uuid.uuid4()
        prefs_id = uuid.uuid4()
        payload = {
            "id": str(prefs_id),
            "user_id": str(user_id),
            "preferences": {"theme": "dark"},
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": None,
        }
        fake_redis.store[_cache_key(user_id)] = json.dumps(payload)
        session = _mock_session(scalar_result=None)
        repo = UserPreferencesRepository()

        result = await repo.get_by_user_id(session, user_id)

        assert result is not None
        assert result.id == prefs_id
        assert result.user_id == user_id
        assert result.preferences == {"theme": "dark"}
        session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_by_user_id_db_hit_warms_cache(self, fake_redis: _FakeRedis) -> None:
        user_id = uuid.uuid4()
        prefs = UserPreferences(user_id=user_id, preferences={"theme": "dark"})
        prefs.id = uuid.uuid4()
        prefs.created_at = None
        prefs.updated_at = None
        session = _mock_session(scalar_result=prefs)
        repo = UserPreferencesRepository()

        result = await repo.get_by_user_id(session, user_id)

        assert result is prefs
        session.execute.assert_awaited_once()
        assert _cache_key(user_id) in fake_redis.store

    @pytest.mark.asyncio
    async def test_get_by_user_id_db_miss_returns_none(self, fake_redis: _FakeRedis) -> None:
        user_id = uuid.uuid4()
        session = _mock_session(scalar_result=None)
        repo = UserPreferencesRepository()

        assert await repo.get_by_user_id(session, user_id) is None
        assert _cache_key(user_id) not in fake_redis.store

    @pytest.mark.asyncio
    async def test_get_by_user_id_redis_failure_falls_back_to_db(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _boom() -> object:
            raise RuntimeError("redis down")

        monkeypatch.setattr(prefs_module, "get_redis", _boom)
        prefs = UserPreferences(user_id=uuid.uuid4(), preferences={"a": 1})
        prefs.id = uuid.uuid4()
        prefs.created_at = None
        prefs.updated_at = None
        session = _mock_session(scalar_result=prefs)
        repo = UserPreferencesRepository()

        result = await repo.get_by_user_id(session, prefs.user_id)

        assert result is prefs

    @pytest.mark.asyncio
    async def test_upsert_existing_deep_merges(self, fake_redis: _FakeRedis) -> None:
        user_id = uuid.uuid4()
        existing = UserPreferences(user_id=user_id, preferences={"voice": {"volume": 5}})
        existing.id = uuid.uuid4()
        existing.created_at = None
        existing.updated_at = None
        session = _mock_session(scalar_result=existing)
        repo = UserPreferencesRepository()

        result = await repo.upsert(session, user_id, {"voice": {"rate": 2}})

        assert result is existing
        assert result.preferences == {"voice": {"volume": 5, "rate": 2}}
        session.flush.assert_awaited_once()
        assert _cache_key(user_id) in fake_redis.store

    @pytest.mark.asyncio
    async def test_upsert_new_creates_row(self, fake_redis: _FakeRedis) -> None:
        user_id = uuid.uuid4()
        session = _mock_session(scalar_result=None)
        session.add = MagicMock()
        repo = UserPreferencesRepository()

        result = await repo.upsert(session, user_id, {"theme": "light"})

        assert isinstance(result, UserPreferences)
        assert result.user_id == user_id
        assert result.preferences == {"theme": "light"}
        session.add.assert_called_once_with(result)
        session.flush.assert_awaited_once()
        assert _cache_key(user_id) in fake_redis.store

    @pytest.mark.asyncio
    async def test_invalidate_cache_deletes_key(self, fake_redis: _FakeRedis) -> None:
        user_id = uuid.uuid4()
        fake_redis.store[_cache_key(user_id)] = "{}"
        repo = UserPreferencesRepository()

        await repo.invalidate_cache(user_id)

        assert _cache_key(user_id) in fake_redis.deleted
        assert _cache_key(user_id) not in fake_redis.store
