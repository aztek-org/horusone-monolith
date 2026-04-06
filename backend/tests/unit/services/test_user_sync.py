"""Unit tests for user synchronization service."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.middleware.auth import TokenUser


# ── Helpers ────────────────────────────────────────────────────────────


def _make_token_user(
    *,
    keycloak_id: str = "kc-abc",
    email: str = "pilot@example.com",
    display_name: str = "Test Pilot",
) -> TokenUser:
    return TokenUser(
        keycloak_id=keycloak_id,
        email=email,
        display_name=display_name,
    )


def _make_fake_user(
    *,
    keycloak_id: str = "kc-abc",
    email: str = "pilot@example.com",
    display_name: str = "Test Pilot",
) -> MagicMock:
    """Create a MagicMock that mimics a User ORM model."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.keycloak_id = keycloak_id
    user.email = email
    user.display_name = display_name
    return user


# ── sync_user_from_token ──────────────────────────────────────────────


class TestSyncUserFromToken:
    """Tests for sync_user_from_token()."""

    @pytest.mark.asyncio
    @patch("app.services.user_sync.user_repo")
    async def test_creates_new_user_when_not_found(
        self, mock_repo: MagicMock
    ) -> None:
        from app.services.user_sync import sync_user_from_token

        session = AsyncMock()
        token_user = _make_token_user()

        mock_repo.get_by_keycloak_id = AsyncMock(return_value=None)
        mock_repo.get_by_email = AsyncMock(return_value=None)
        new_user = _make_fake_user()
        mock_repo.create = AsyncMock(return_value=new_user)

        result = await sync_user_from_token(session, token_user)

        assert result is new_user
        mock_repo.get_by_keycloak_id.assert_awaited_once_with(session, "kc-abc")
        mock_repo.create.assert_awaited_once()
        # Verify the create was called with a UserCreate schema
        create_arg = mock_repo.create.call_args[0][1]
        assert create_arg.email == "pilot@example.com"
        assert create_arg.display_name == "Test Pilot"
        assert create_arg.keycloak_id == "kc-abc"

    @pytest.mark.asyncio
    @patch("app.services.user_sync.user_repo")
    async def test_returns_existing_user_no_changes(
        self, mock_repo: MagicMock
    ) -> None:
        from app.services.user_sync import sync_user_from_token

        session = AsyncMock()
        token_user = _make_token_user(
            email="same@test.com",
            display_name="Same Name",
        )
        existing = _make_fake_user(
            email="same@test.com",
            display_name="Same Name",
        )
        mock_repo.get_by_keycloak_id = AsyncMock(return_value=existing)

        result = await sync_user_from_token(session, token_user)

        assert result is existing
        session.flush.assert_not_awaited()
        mock_repo.create.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.user_sync.user_repo")
    async def test_updates_email_when_changed(
        self, mock_repo: MagicMock
    ) -> None:
        from app.services.user_sync import sync_user_from_token

        session = AsyncMock()
        token_user = _make_token_user(email="new@test.com")
        existing = _make_fake_user(email="old@test.com")
        mock_repo.get_by_keycloak_id = AsyncMock(return_value=existing)

        result = await sync_user_from_token(session, token_user)

        assert result is existing
        assert existing.email == "new@test.com"
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.services.user_sync.user_repo")
    async def test_updates_display_name_when_changed(
        self, mock_repo: MagicMock
    ) -> None:
        from app.services.user_sync import sync_user_from_token

        session = AsyncMock()
        token_user = _make_token_user(display_name="New Name")
        existing = _make_fake_user(display_name="Old Name")
        mock_repo.get_by_keycloak_id = AsyncMock(return_value=existing)

        result = await sync_user_from_token(session, token_user)

        assert result is existing
        assert existing.display_name == "New Name"
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.services.user_sync.user_repo")
    async def test_updates_both_email_and_display_name(
        self, mock_repo: MagicMock
    ) -> None:
        from app.services.user_sync import sync_user_from_token

        session = AsyncMock()
        token_user = _make_token_user(
            email="new@test.com",
            display_name="New Display",
        )
        existing = _make_fake_user(
            email="old@test.com",
            display_name="Old Display",
        )
        mock_repo.get_by_keycloak_id = AsyncMock(return_value=existing)

        result = await sync_user_from_token(session, token_user)

        assert existing.email == "new@test.com"
        assert existing.display_name == "New Display"
        session.flush.assert_awaited_once()
