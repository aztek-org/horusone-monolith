"""Unit tests for the admin API schemas."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.admin import (
    AdminStats,
    AdminUserUpdate,
    OrganizationFeaturesResponse,
    OrganizationFeaturesUpdate,
    OrganizationWithStats,
    SeatCreateRequest,
    SeatRoleUpdate,
    SeatWithUser,
    UserWithSeats,
)


class TestSeatCreateRequest:
    def test_default_role_is_student(self) -> None:
        request = SeatCreateRequest(email="pilot@example.com")
        assert request.role == "student"

    @pytest.mark.parametrize("role", ["admin", "instructor", "student"])
    def test_accepts_supported_roles(self, role: str) -> None:
        assert SeatCreateRequest(email="a@b.com", role=role).role == role

    def test_rejects_invalid_role(self) -> None:
        with pytest.raises(ValidationError, match="role"):
            SeatCreateRequest(email="a@b.com", role="superuser")

    def test_rejects_invalid_email(self) -> None:
        with pytest.raises(ValidationError, match="email"):
            SeatCreateRequest(email="not-an-email")


class TestSeatRoleUpdate:
    def test_role_required(self) -> None:
        with pytest.raises(ValidationError, match="role"):
            SeatRoleUpdate()

    def test_rejects_invalid_role(self) -> None:
        with pytest.raises(ValidationError, match="role"):
            SeatRoleUpdate(role="owner")


class TestOrganizationFeaturesUpdate:
    def test_requires_at_least_one_feature(self) -> None:
        with pytest.raises(ValidationError, match="enabled_features"):
            OrganizationFeaturesUpdate(enabled_features=[])

    def test_rejects_too_many_features(self) -> None:
        with pytest.raises(ValidationError, match="enabled_features"):
            OrganizationFeaturesUpdate(enabled_features=[f"f{i}" for i in range(21)])

    def test_accepts_feature_list(self) -> None:
        update = OrganizationFeaturesUpdate(enabled_features=["voice", "replay"])
        assert update.enabled_features == ["voice", "replay"]


class TestAdminUserUpdate:
    def test_all_optional(self) -> None:
        update = AdminUserUpdate()
        assert update.display_name is None
        assert update.is_active is None

    def test_display_name_must_not_be_empty_when_supplied(self) -> None:
        with pytest.raises(ValidationError, match="display_name"):
            AdminUserUpdate(display_name="")


class TestReadModels:
    def test_user_with_seats_defaults(self) -> None:
        user = UserWithSeats(
            id=uuid.uuid4(),
            email="a@b.com",
            display_name="A",
            is_active=True,
            created_at="2024-01-01T00:00:00",
        )
        assert user.seats == []
        assert user.avatar_url is None

    def test_stats_requires_counters(self) -> None:
        with pytest.raises(ValidationError):
            AdminStats(total_orgs=1)

    def test_organization_with_stats_defaults(self) -> None:
        org = OrganizationWithStats(
            id=uuid.uuid4(),
            name="Sky",
            slug="sky",
            is_active=True,
            max_seats=10,
            billing_plan="starter",
            billing_status="trial",
            billing_cycle="monthly",
            created_at="2024-01-01T00:00:00",
        )
        assert org.seat_count == 0
        assert org.active_sessions == 0
        assert org.scenario_count == 0

    def test_feature_response(self) -> None:
        response = OrganizationFeaturesResponse(
            org_id=uuid.uuid4(), enabled_features=["voice"]
        )
        assert response.enabled_features == ["voice"]

    def test_seat_with_user_requires_user_fields(self) -> None:
        seat = SeatWithUser(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            role="student",
            is_active=True,
            joined_at="2024-01-01T00:00:00",
            user_email="a@b.com",
            user_display_name="A",
        )
        assert seat.user_display_name == "A"
