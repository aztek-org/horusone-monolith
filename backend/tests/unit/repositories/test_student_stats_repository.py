"""Unit tests for StudentStatsRepository query behavior."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories.student_stats_repository import StudentStatsRepository


def _mock_session_scalars(rows: list[object]) -> AsyncMock:
    """Return an AsyncSession mock for ``result.scalars().all()`` calls."""
    session = AsyncMock()
    result_proxy = MagicMock()
    scalars_proxy = MagicMock()
    scalars_proxy.all.return_value = rows
    result_proxy.scalars.return_value = scalars_proxy
    session.execute.return_value = result_proxy
    return session


class TestStudentStatsRepository:
    """Tests for student stats repository query helpers."""

    @pytest.mark.asyncio
    async def test_get_maneuver_logs_without_filter(self) -> None:
        row = MagicMock()
        session = _mock_session_scalars([row])
        repo = StudentStatsRepository()

        result = await repo.get_maneuver_logs(
            session,
            user_id=uuid.uuid4(),
            limit=10,
            offset=0,
        )

        assert result == [row]
        query = session.execute.await_args.args[0]
        assert "WHERE maneuver_logs.maneuver_type" not in str(query)

    @pytest.mark.asyncio
    async def test_get_maneuver_logs_with_type_filter(self) -> None:
        row = MagicMock()
        session = _mock_session_scalars([row])
        repo = StudentStatsRepository()

        result = await repo.get_maneuver_logs(
            session,
            user_id=uuid.uuid4(),
            limit=10,
            offset=0,
            maneuver_type="approach",
        )

        assert result == [row]
        query = session.execute.await_args.args[0]
        assert "maneuver_logs.maneuver_type = :maneuver_type_1" in str(query)
