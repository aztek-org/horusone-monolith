"""Unit tests for organization context middleware."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.middleware.auth import TokenUser
from app.middleware.org_context import get_org_id, require_org_id


# ── Helpers ────────────────────────────────────────────────────────────


def _make_token_user(
    *,
    roles: list[str] | None = None,
    organization_id: str | None = None,
) -> TokenUser:
    return TokenUser(
        keycloak_id="kc-test",
        email="test@example.com",
        display_name="Test User",
        roles=roles or [],
        organization_id=organization_id,
    )


def _make_seat(
    *, org_id: uuid.UUID | None = None, is_active: bool = True
) -> MagicMock:
    seat = MagicMock()
    seat.organization_id = org_id or uuid.uuid4()
    seat.is_active = is_active
    return seat


# ── get_org_id ─────────────────────────────────────────────────────────


class TestGetOrgId:
    """Tests for get_org_id() dependency."""

    @pytest.mark.asyncio
    async def test_platform_admin_with_jwt_org_id(self) -> None:
        """Platform admins can scope themselves to an org via JWT claim."""
        org_uuid = str(uuid.uuid4())
        token_user = _make_token_user(
            roles=["platform-admin"],
            organization_id=org_uuid,
        )
        session = AsyncMock()

        result = await get_org_id(token_user, session)

        assert result == uuid.UUID(org_uuid)

    @pytest.mark.asyncio
    async def test_platform_admin_without_org_returns_none(self) -> None:
        """Platform admins with no org claim get None (full access)."""
        token_user = _make_token_user(roles=["platform-admin"])
        session = AsyncMock()

        result = await get_org_id(token_user, session)

        assert result is None

    @pytest.mark.asyncio
    async def test_regular_user_with_jwt_org_id(self) -> None:
        """Non-admin users get org from JWT claim."""
        org_uuid = str(uuid.uuid4())
        token_user = _make_token_user(
            roles=["instructor"],
            organization_id=org_uuid,
        )
        session = AsyncMock()

        result = await get_org_id(token_user, session)

        assert result == uuid.UUID(org_uuid)

    @pytest.mark.asyncio
    @patch("app.middleware.org_context.seat_repo")
    @patch("app.middleware.org_context.sync_user_from_token")
    async def test_regular_user_falls_back_to_seat(
        self, mock_sync: AsyncMock, mock_seat_repo: MagicMock
    ) -> None:
        """Without JWT org claim, falls back to first active seat."""
        token_user = _make_token_user(roles=["student"])

        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        mock_sync.return_value = fake_user

        expected_org = uuid.uuid4()
        mock_seat_repo.get_user_seats = AsyncMock(
            return_value=[_make_seat(org_id=expected_org)]
        )
        session = AsyncMock()

        result = await get_org_id(token_user, session)

        assert result == expected_org
        mock_sync.assert_awaited_once_with(session, token_user)
        mock_seat_repo.get_user_seats.assert_awaited_once_with(session, fake_user.id)

    @pytest.mark.asyncio
    @patch("app.middleware.org_context.seat_repo")
    @patch("app.middleware.org_context.sync_user_from_token")
    async def test_user_no_jwt_no_active_seats_returns_none(
        self, mock_sync: AsyncMock, mock_seat_repo: MagicMock
    ) -> None:
        token_user = _make_token_user(roles=["student"])

        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        mock_sync.return_value = fake_user

        # Two seats but both inactive
        mock_seat_repo.get_user_seats = AsyncMock(
            return_value=[
                _make_seat(is_active=False),
                _make_seat(is_active=False),
            ]
        )
        session = AsyncMock()

        result = await get_org_id(token_user, session)

        assert result is None

    @pytest.mark.asyncio
    @patch("app.middleware.org_context.seat_repo")
    @patch("app.middleware.org_context.sync_user_from_token")
    async def test_user_no_jwt_empty_seats_returns_none(
        self, mock_sync: AsyncMock, mock_seat_repo: MagicMock
    ) -> None:
        token_user = _make_token_user(roles=["student"])

        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        mock_sync.return_value = fake_user

        mock_seat_repo.get_user_seats = AsyncMock(return_value=[])
        session = AsyncMock()

        result = await get_org_id(token_user, session)

        assert result is None

    @pytest.mark.asyncio
    @patch("app.middleware.org_context.seat_repo")
    @patch("app.middleware.org_context.sync_user_from_token")
    async def test_selects_first_active_seat(
        self, mock_sync: AsyncMock, mock_seat_repo: MagicMock
    ) -> None:
        """When multiple active seats exist, uses the first one."""
        token_user = _make_token_user(roles=["instructor"])

        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        mock_sync.return_value = fake_user

        first_org = uuid.uuid4()
        second_org = uuid.uuid4()
        mock_seat_repo.get_user_seats = AsyncMock(
            return_value=[
                _make_seat(org_id=first_org, is_active=True),
                _make_seat(org_id=second_org, is_active=True),
            ]
        )
        session = AsyncMock()

        result = await get_org_id(token_user, session)

        assert result == first_org


# ── require_org_id ─────────────────────────────────────────────────────


class TestRequireOrgId:
    """Tests for require_org_id() dependency."""

    @pytest.mark.asyncio
    async def test_with_org_id_returns_it(self) -> None:
        org = uuid.uuid4()
        result = await require_org_id(org)
        assert result == org

    @pytest.mark.asyncio
    async def test_none_raises_403(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await require_org_id(None)
        assert exc_info.value.status_code == 403
        assert "No organization" in exc_info.value.detail
