"""Unit tests for the generic BaseRepository.

Exercises the generic CRUD helpers through a concrete ``Scenario`` model.
All database I/O is mocked via AsyncSession — no real DB connection needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories.base import BaseRepository
from app.models.scenario import Scenario


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


class _StubCreate:
    """Minimal stand-in for a Pydantic create schema."""

    def __init__(self, payload: dict | None = None) -> None:
        self._payload = payload or {}

    def model_dump(self) -> dict:
        return dict(self._payload)


# ── BaseRepository ─────────────────────────────────────────────────────


class TestBaseRepository:
    """Tests for generic get/create/delete helpers."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self) -> None:
        fake = MagicMock()
        session = _mock_session(scalar_result=fake)
        repo = BaseRepository(Scenario)

        assert await repo.get_by_id(session, 1) is fake

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = BaseRepository(Scenario)

        assert await repo.get_by_id(session, 1) is None

    @pytest.mark.asyncio
    async def test_get_all_returns_rows(self) -> None:
        rows = [MagicMock(), MagicMock()]
        session = _mock_session_scalars(rows)
        repo = BaseRepository(Scenario)

        assert await repo.get_all(session, limit=10, offset=5) == rows

    @pytest.mark.asyncio
    async def test_create_persists_and_returns_model(self) -> None:
        session = AsyncMock()
        session.add = MagicMock()
        repo = BaseRepository(Scenario)
        stub = _StubCreate(
            {"name": "Circuit", "airport_icao": "KJFK", "runway": "04L"}
        )

        result = await repo.create(session, stub)

        assert isinstance(result, Scenario)
        assert result.name == "Circuit"
        session.add.assert_called_once_with(result)
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(result)

    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(self) -> None:
        fake = MagicMock()
        session = _mock_session(scalar_result=fake)
        repo = BaseRepository(Scenario)

        assert await repo.delete(session, 1) is True
        session.delete.assert_awaited_once_with(fake)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = BaseRepository(Scenario)

        assert await repo.delete(session, 1) is False
        session.delete.assert_not_awaited()
