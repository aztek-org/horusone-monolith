"""Unit tests for the User schemas."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate, UserRead, UserUpdate


class TestUserCreate:
    def test_accepts_valid_payload(self) -> None:
        user = UserCreate(
            email="pilot@example.com",
            display_name="Test Pilot",
            keycloak_id="kc-123",
        )
        assert user.email == "pilot@example.com"

    def test_rejects_invalid_email(self) -> None:
        with pytest.raises(ValidationError, match="email"):
            UserCreate(email="nope", display_name="A", keycloak_id="kc")

    def test_rejects_empty_display_name(self) -> None:
        with pytest.raises(ValidationError, match="display_name"):
            UserCreate(email="a@b.com", display_name="", keycloak_id="kc")

    def test_rejects_empty_keycloak_id(self) -> None:
        with pytest.raises(ValidationError, match="keycloak_id"):
            UserCreate(email="a@b.com", display_name="A", keycloak_id="")


class TestUserUpdate:
    def test_all_optional(self) -> None:
        update = UserUpdate()
        assert update.display_name is None
        assert update.avatar_url is None

    def test_rejects_empty_display_name_when_supplied(self) -> None:
        with pytest.raises(ValidationError, match="display_name"):
            UserUpdate(display_name="")

    def test_rejects_overlong_avatar_url(self) -> None:
        with pytest.raises(ValidationError, match="avatar_url"):
            UserUpdate(avatar_url="x" * 2049)


class TestUserRead:
    def test_accepts_full_row(self) -> None:
        user = UserRead(
            id=uuid.uuid4(),
            email="a@b.com",
            display_name="A",
            is_active=True,
            created_at="2024-01-01T00:00:00",
        )
        assert user.avatar_url is None

    def test_requires_server_fields(self) -> None:
        with pytest.raises(ValidationError):
            UserRead(email="a@b.com")
