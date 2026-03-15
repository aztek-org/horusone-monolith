"""Unit tests for User, Organization, and Seat repositories.

All database I/O is mocked via AsyncSession — no real DB connection needed.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories.organization_repo import OrganizationRepository
from app.db.repositories.seat_repo import SeatRepository
from app.db.repositories.user_repo import UserRepository


# ── Mock helpers ───────────────────────────────────────────────────────


def _mock_session(scalar_result: object = None) -> AsyncMock:
    """Return an AsyncSession mock whose execute() returns a result proxy.

    Args:
        scalar_result: Value returned by ``result.scalar_one_or_none()``.
    """
    session = AsyncMock()
    result_proxy = MagicMock()
    result_proxy.scalar_one_or_none.return_value = scalar_result
    session.execute.return_value = result_proxy
    return session


def _mock_session_scalars(rows: list) -> AsyncMock:
    """Return an AsyncSession mock for queries using ``result.scalars().all()``.

    Args:
        rows: List of ORM model instances to return.
    """
    session = AsyncMock()
    result_proxy = MagicMock()
    scalars_proxy = MagicMock()
    scalars_proxy.all.return_value = rows
    result_proxy.scalars.return_value = scalars_proxy
    session.execute.return_value = result_proxy
    return session


# ── UserRepository ─────────────────────────────────────────────────────


class TestUserRepository:
    """Tests for UserRepository custom queries."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self) -> None:
        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        session = _mock_session(scalar_result=fake_user)

        repo = UserRepository()
        result = await repo.get_by_id(session, fake_user.id)

        assert result is fake_user
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = UserRepository()
        result = await repo.get_by_id(session, uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_keycloak_id_found(self) -> None:
        fake_user = MagicMock()
        fake_user.keycloak_id = "kc-123"
        session = _mock_session(scalar_result=fake_user)

        repo = UserRepository()
        result = await repo.get_by_keycloak_id(session, "kc-123")

        assert result is fake_user
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_keycloak_id_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = UserRepository()
        result = await repo.get_by_keycloak_id(session, "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_email_found(self) -> None:
        fake_user = MagicMock()
        fake_user.email = "pilot@example.com"
        session = _mock_session(scalar_result=fake_user)

        repo = UserRepository()
        result = await repo.get_by_email(session, "pilot@example.com")

        assert result is fake_user

    @pytest.mark.asyncio
    async def test_get_by_email_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = UserRepository()
        result = await repo.get_by_email(session, "nobody@example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(self) -> None:
        fake_user = MagicMock()
        session = _mock_session(scalar_result=fake_user)

        repo = UserRepository()
        result = await repo.delete(session, uuid.uuid4())

        assert result is True
        session.delete.assert_awaited_once_with(fake_user)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = UserRepository()
        result = await repo.delete(session, uuid.uuid4())
        assert result is False


# ── OrganizationRepository ─────────────────────────────────────────────


class TestOrganizationRepository:
    """Tests for OrganizationRepository custom queries."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self) -> None:
        fake_org = MagicMock()
        fake_org.id = uuid.uuid4()
        session = _mock_session(scalar_result=fake_org)

        repo = OrganizationRepository()
        result = await repo.get_by_id(session, fake_org.id)

        assert result is fake_org

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = OrganizationRepository()
        result = await repo.get_by_id(session, uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_slug_found(self) -> None:
        fake_org = MagicMock()
        fake_org.slug = "acme-flight-school"
        session = _mock_session(scalar_result=fake_org)

        repo = OrganizationRepository()
        result = await repo.get_by_slug(session, "acme-flight-school")

        assert result is fake_org

    @pytest.mark.asyncio
    async def test_get_by_slug_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = OrganizationRepository()
        result = await repo.get_by_slug(session, "nonexistent-slug")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(self) -> None:
        fake_org = MagicMock()
        session = _mock_session(scalar_result=fake_org)

        repo = OrganizationRepository()
        result = await repo.delete(session, uuid.uuid4())

        assert result is True
        session.delete.assert_awaited_once_with(fake_org)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = OrganizationRepository()
        result = await repo.delete(session, uuid.uuid4())
        assert result is False


# ── SeatRepository ─────────────────────────────────────────────────────


class TestSeatRepository:
    """Tests for SeatRepository custom queries."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self) -> None:
        fake_seat = MagicMock()
        fake_seat.id = uuid.uuid4()
        session = _mock_session(scalar_result=fake_seat)

        repo = SeatRepository()
        result = await repo.get_by_id(session, fake_seat.id)

        assert result is fake_seat

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = SeatRepository()
        result = await repo.get_by_id(session, uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_seats_returns_list(self) -> None:
        seat_a = MagicMock()
        seat_b = MagicMock()
        session = _mock_session_scalars([seat_a, seat_b])

        repo = SeatRepository()
        result = await repo.get_user_seats(session, uuid.uuid4())

        assert result == [seat_a, seat_b]
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_user_seats_empty(self) -> None:
        session = _mock_session_scalars([])
        repo = SeatRepository()
        result = await repo.get_user_seats(session, uuid.uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_get_org_seats_returns_list(self) -> None:
        seat_a = MagicMock()
        session = _mock_session_scalars([seat_a])

        repo = SeatRepository()
        result = await repo.get_org_seats(session, uuid.uuid4())

        assert result == [seat_a]

    @pytest.mark.asyncio
    async def test_get_user_org_seat_found(self) -> None:
        fake_seat = MagicMock()
        session = _mock_session(scalar_result=fake_seat)

        repo = SeatRepository()
        result = await repo.get_user_org_seat(session, uuid.uuid4(), uuid.uuid4())

        assert result is fake_seat

    @pytest.mark.asyncio
    async def test_get_user_org_seat_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = SeatRepository()
        result = await repo.get_user_org_seat(session, uuid.uuid4(), uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_existing_returns_true(self) -> None:
        fake_seat = MagicMock()
        session = _mock_session(scalar_result=fake_seat)

        repo = SeatRepository()
        result = await repo.delete(session, uuid.uuid4())

        assert result is True
        session.delete.assert_awaited_once_with(fake_seat)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = SeatRepository()
        result = await repo.delete(session, uuid.uuid4())
        assert result is False
