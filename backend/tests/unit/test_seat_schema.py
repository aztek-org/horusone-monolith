"""Unit tests for the Seat schemas."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.seat import SeatCreate, SeatRead, SeatUpdate


class TestSeatCreate:
    def test_default_role(self) -> None:
        seat = SeatCreate(user_id=uuid.uuid4(), organization_id=uuid.uuid4())
        assert seat.role == "student"

    @pytest.mark.parametrize("role", ["admin", "instructor", "student"])
    def test_accepts_supported_roles(self, role: str) -> None:
        seat = SeatCreate(
            user_id=uuid.uuid4(), organization_id=uuid.uuid4(), role=role
        )
        assert seat.role == role

    def test_rejects_unsupported_role(self) -> None:
        with pytest.raises(ValidationError, match="role"):
            SeatCreate(
                user_id=uuid.uuid4(), organization_id=uuid.uuid4(), role="viewer"
            )

    def test_requires_user_and_org(self) -> None:
        with pytest.raises(ValidationError, match="user_id"):
            SeatCreate(organization_id=uuid.uuid4())


class TestSeatUpdate:
    def test_all_optional(self) -> None:
        update = SeatUpdate()
        assert update.role is None
        assert update.is_active is None

    def test_rejects_invalid_role(self) -> None:
        with pytest.raises(ValidationError, match="role"):
            SeatUpdate(role="owner")

    def test_accepts_partial_update(self) -> None:
        assert SeatUpdate(is_active=False).is_active is False


class TestSeatRead:
    def test_accepts_full_row(self) -> None:
        seat = SeatRead(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            role="instructor",
            is_active=True,
            joined_at="2024-01-01T00:00:00",
        )
        assert seat.role == "instructor"
