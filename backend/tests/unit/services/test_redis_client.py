"""Unit tests for the async Redis client singleton.

``redis.from_url`` and the settings loader are patched so no Redis server
or network connection is required.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.core.redis as redis_module
from app.core.redis import close_redis, get_redis


@pytest.fixture(autouse=True)
def _reset_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure each test starts with no cached client."""
    monkeypatch.setattr(redis_module, "_redis_client", None)


def _patch_settings(monkeypatch: pytest.MonkeyPatch, url: str = "redis://cache:6379/0") -> None:
    monkeypatch.setattr(
        redis_module, "get_settings", lambda: SimpleNamespace(redis_url=url)
    )


class TestGetRedis:
    @pytest.mark.asyncio
    async def test_creates_client_with_configured_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = MagicMock()
        from_url = MagicMock(return_value=client)
        monkeypatch.setattr(redis_module.redis, "from_url", from_url)
        _patch_settings(monkeypatch, "redis://cache:6379/2")

        result = await get_redis()

        assert result is client
        from_url.assert_called_once_with("redis://cache:6379/2", decode_responses=True)

    @pytest.mark.asyncio
    async def test_reuses_the_singleton(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = MagicMock()
        from_url = MagicMock(return_value=client)
        monkeypatch.setattr(redis_module.redis, "from_url", from_url)
        _patch_settings(monkeypatch)

        first = await get_redis()
        second = await get_redis()

        assert first is second
        assert from_url.call_count == 1


class TestCloseRedis:
    @pytest.mark.asyncio
    async def test_closes_and_resets_the_singleton(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = MagicMock()
        client.aclose = AsyncMock()
        monkeypatch.setattr(redis_module, "_redis_client", client)

        await close_redis()

        client.aclose.assert_awaited_once()
        assert redis_module._redis_client is None

    @pytest.mark.asyncio
    async def test_is_a_noop_when_no_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(redis_module, "_redis_client", None)

        await close_redis()

        assert redis_module._redis_client is None
