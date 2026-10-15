"""Unit tests for InstructorRepository.

All database I/O is mocked via AsyncSession — no real DB connection needed.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories.instructor_repository import InstructorRepository
from app.models.instructor import InstructorProfile


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


# ── InstructorRepository ───────────────────────────────────────────────


class TestInstructorRepository:
    """Tests for instructor profile lookup and search."""

    @pytest.mark.asyncio
    async def test_get_profile_found(self) -> None:
        profile = MagicMock()
        session = _mock_session(scalar_result=profile)
        repo = InstructorRepository()

        assert await repo.get_profile(session, uuid.uuid4()) is profile

    @pytest.mark.asyncio
    async def test_get_profile_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = InstructorRepository()

        assert await repo.get_profile(session, uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_create_profile_when_absent(self) -> None:
        session = _mock_session(scalar_result=None)
        session.add = MagicMock()
        repo = InstructorRepository()
        user_id = uuid.uuid4()

        result = await repo.create_or_update_profile(
            session, user_id, {"bio": "CFI", "specializations": ["ifr"]}
        )

        assert isinstance(result, InstructorProfile)
        assert result.user_id == user_id
        assert result.bio == "CFI"
        session.add.assert_called_once_with(result)
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(result)

    @pytest.mark.asyncio
    async def test_update_profile_when_present(self) -> None:
        existing = MagicMock()
        existing.bio = "old"
        session = _mock_session(scalar_result=existing)
        session.add = MagicMock()
        repo = InstructorRepository()

        result = await repo.create_or_update_profile(session, uuid.uuid4(), {"bio": "new"})

        assert result is existing
        assert existing.bio == "new"
        session.add.assert_not_called()
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_instructors_returns_rows(self) -> None:
        rows = [MagicMock(), MagicMock()]
        session = _mock_session_scalars(rows)
        repo = InstructorRepository()

        assert await repo.search_instructors(session) == rows

    @pytest.mark.asyncio
    async def test_search_instructors_org_filter_joins_seats(self) -> None:
        session = _mock_session_scalars([])
        repo = InstructorRepository()

        await repo.search_instructors(session, org_id=uuid.uuid4())

        query = str(session.execute.await_args.args[0])
        assert "JOIN seats" in query
        assert "seats.organization_id" in query
        assert "seats.is_active IS true" in query

    @pytest.mark.asyncio
    async def test_search_instructors_specialization_filter(self) -> None:
        session = _mock_session_scalars([])
        repo = InstructorRepository()

        await repo.search_instructors(session, specialization="ifr")

        query = str(session.execute.await_args.args[0])
        assert "instructor_profiles.specializations @>" in query
