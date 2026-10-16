"""Unit tests for TrainingModuleRepository.

All database I/O is mocked via AsyncSession — no real DB connection needed.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories.training_module_repo import TrainingModuleRepository


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


# ── TrainingModuleRepository ───────────────────────────────────────────


class TestTrainingModuleRepository:
    """Tests for UUID-aware CRUD and scenario membership helpers."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self) -> None:
        fake = MagicMock()
        session = _mock_session(scalar_result=fake)
        repo = TrainingModuleRepository()

        assert await repo.get_by_id(session, uuid.uuid4()) is fake

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = TrainingModuleRepository()

        assert await repo.get_by_id(session, uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(self) -> None:
        fake = MagicMock()
        session = _mock_session(scalar_result=fake)
        repo = TrainingModuleRepository()

        assert await repo.delete(session, uuid.uuid4()) is True
        session.delete.assert_awaited_once_with(fake)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = TrainingModuleRepository()

        assert await repo.delete(session, uuid.uuid4()) is False
        session.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_by_org_none_returns_global_only(self) -> None:
        session = _mock_session_scalars([])
        repo = TrainingModuleRepository()

        await repo.get_by_org(session, None)

        query = str(session.execute.await_args.args[0])
        assert "training_modules.org_id IS NULL" in query

    @pytest.mark.asyncio
    async def test_get_by_org_with_global_includes_or_clause(self) -> None:
        session = _mock_session_scalars([])
        repo = TrainingModuleRepository()

        await repo.get_by_org(session, uuid.uuid4(), include_global=True)

        query = str(session.execute.await_args.args[0])
        assert "training_modules.org_id = " in query
        assert "training_modules.org_id IS NULL" in query

    @pytest.mark.asyncio
    async def test_get_by_org_without_global_excludes_null(self) -> None:
        session = _mock_session_scalars([])
        repo = TrainingModuleRepository()

        await repo.get_by_org(session, uuid.uuid4(), include_global=False)

        query = str(session.execute.await_args.args[0])
        assert "training_modules.org_id = " in query
        assert "training_modules.org_id IS NULL" not in query

    @pytest.mark.asyncio
    async def test_get_with_scenarios_found(self) -> None:
        module = MagicMock()
        session = _mock_session(scalar_result=module)
        repo = TrainingModuleRepository()

        assert await repo.get_with_scenarios(session, uuid.uuid4()) is module

    @pytest.mark.asyncio
    async def test_get_with_scenarios_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = TrainingModuleRepository()

        assert await repo.get_with_scenarios(session, uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_add_scenario_executes_insert(self) -> None:
        session = AsyncMock()
        repo = TrainingModuleRepository()

        await repo.add_scenario(session, uuid.uuid4(), scenario_id=3, sort_order=1)

        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_remove_scenario_returns_true_when_row_deleted(self) -> None:
        session = AsyncMock()
        session.execute.return_value = MagicMock(rowcount=1)
        repo = TrainingModuleRepository()

        assert await repo.remove_scenario(session, uuid.uuid4(), 3) is True

    @pytest.mark.asyncio
    async def test_remove_scenario_returns_false_when_missing(self) -> None:
        session = AsyncMock()
        session.execute.return_value = MagicMock(rowcount=0)
        repo = TrainingModuleRepository()

        assert await repo.remove_scenario(session, uuid.uuid4(), 3) is False

    @pytest.mark.asyncio
    async def test_reorder_scenarios_executes_once_per_id(self) -> None:
        session = AsyncMock()
        repo = TrainingModuleRepository()

        await repo.reorder_scenarios(session, uuid.uuid4(), [5, 2, 9])

        assert session.execute.await_count == 3
