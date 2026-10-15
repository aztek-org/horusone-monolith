"""Unit tests for VoiceLogRepository.

All database I/O is mocked via AsyncSession — no real DB connection needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories.voice_log_repo import VoiceLogRepository


# ── Mock helpers ───────────────────────────────────────────────────────


def _mock_session(scalar_result: object = None) -> AsyncMock:
    """Return an AsyncSession mock whose execute() returns a scalar proxy."""
    session = AsyncMock()
    result_proxy = MagicMock()
    result_proxy.scalar_one_or_none.return_value = scalar_result
    session.execute.return_value = result_proxy
    return session


def _mock_session_scalars(rows: list) -> AsyncMock:
    """Return an AsyncSession mock for queries using ``result.scalars().all()``."""
    session = AsyncMock()
    result_proxy = MagicMock()
    scalars_proxy = MagicMock()
    scalars_proxy.all.return_value = rows
    result_proxy.scalars.return_value = scalars_proxy
    session.execute.return_value = result_proxy
    return session


# ── VoiceLogRepository ─────────────────────────────────────────────────


class TestVoiceLogRepository:
    """Tests for session voice-log queries and inherited CRUD."""

    @pytest.mark.asyncio
    async def test_get_by_session_returns_chronological_rows(self) -> None:
        rows = [MagicMock(), MagicMock()]
        session = _mock_session_scalars(rows)
        repo = VoiceLogRepository()

        result = await repo.get_by_session(session, 7)

        assert result == rows
        query = str(session.execute.await_args.args[0])
        assert "voice_logs.session_id" in query
        assert "ORDER BY" in query.upper()

    @pytest.mark.asyncio
    async def test_get_by_session_empty(self) -> None:
        session = _mock_session_scalars([])
        repo = VoiceLogRepository()

        assert await repo.get_by_session(session, 7) == []

    @pytest.mark.asyncio
    async def test_get_by_id_found(self) -> None:
        fake = MagicMock()
        session = _mock_session(scalar_result=fake)
        repo = VoiceLogRepository()

        assert await repo.get_by_id(session, 1) is fake

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = VoiceLogRepository()

        assert await repo.get_by_id(session, 1) is None

    @pytest.mark.asyncio
    async def test_get_all_returns_rows(self) -> None:
        rows = [MagicMock()]
        session = _mock_session_scalars(rows)
        repo = VoiceLogRepository()

        assert await repo.get_all(session) == rows

    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(self) -> None:
        fake = MagicMock()
        session = _mock_session(scalar_result=fake)
        repo = VoiceLogRepository()

        assert await repo.delete(session, 1) is True
        session.delete.assert_awaited_once_with(fake)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = VoiceLogRepository()

        assert await repo.delete(session, 1) is False
