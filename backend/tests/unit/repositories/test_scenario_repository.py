"""Unit tests for ScenarioRepository.

All database I/O is mocked via AsyncSession — no real DB connection needed.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories.scenario_repo import ScenarioRepository


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


# ── ScenarioRepository ─────────────────────────────────────────────────


class TestScenarioRepository:
    """Tests for scenario queries and inherited CRUD."""

    @pytest.mark.asyncio
    async def test_get_by_airport_returns_rows(self) -> None:
        rows = [MagicMock(), MagicMock()]
        session = _mock_session_scalars(rows)
        repo = ScenarioRepository()

        result = await repo.get_by_airport(session, "KJFK")

        assert result == rows
        query = str(session.execute.await_args.args[0])
        assert "scenarios.airport_icao" in query

    @pytest.mark.asyncio
    async def test_get_by_airport_empty(self) -> None:
        session = _mock_session_scalars([])
        repo = ScenarioRepository()

        assert await repo.get_by_airport(session, "KZZZ") == []

    @pytest.mark.asyncio
    async def test_get_by_id_found(self) -> None:
        fake = MagicMock()
        session = _mock_session(scalar_result=fake)
        repo = ScenarioRepository()

        assert await repo.get_by_id(session, 42) is fake

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = ScenarioRepository()

        assert await repo.get_by_id(session, 42) is None

    @pytest.mark.asyncio
    async def test_get_all_returns_rows(self) -> None:
        rows = [MagicMock()]
        session = _mock_session_scalars(rows)
        repo = ScenarioRepository()

        assert await repo.get_all(session, limit=5, offset=2) == rows

    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(self) -> None:
        fake = MagicMock()
        session = _mock_session(scalar_result=fake)
        repo = ScenarioRepository()

        assert await repo.delete(session, 7) is True
        session.delete.assert_awaited_once_with(fake)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = ScenarioRepository()

        assert await repo.delete(session, 7) is False
