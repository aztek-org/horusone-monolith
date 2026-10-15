"""Unit tests for pure permission/RBAC helpers in app.core.permissions."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.core.permissions import (
    can_access_org,
    get_user_org_id,
    has_role,
    is_platform_admin,
    verify_org_access,
)
from app.middleware.auth import TokenUser


def _user(
    *,
    roles: list[str] | None = None,
    organization_id: str | None = None,
) -> TokenUser:
    return TokenUser(
        keycloak_id="kc-1",
        email="pilot@example.com",
        display_name="Test Pilot",
        roles=roles if roles is not None else ["student"],
        organization_id=organization_id,
    )


class TestIsPlatformAdmin:
    def test_true_when_role_present(self) -> None:
        assert is_platform_admin(_user(roles=["platform-admin"])) is True

    def test_false_when_role_absent(self) -> None:
        assert is_platform_admin(_user(roles=["instructor"])) is False

    def test_false_for_empty_roles(self) -> None:
        assert is_platform_admin(_user(roles=[])) is False


class TestHasRole:
    def test_true_for_any_matching_role(self) -> None:
        user = _user(roles=["instructor"])
        assert has_role(user, "admin", "instructor") is True

    def test_false_when_no_role_matches(self) -> None:
        user = _user(roles=["student"])
        assert has_role(user, "admin", "instructor") is False

    def test_false_when_no_roles_requested(self) -> None:
        assert has_role(_user(roles=["admin"])) is False


class TestGetUserOrgId:
    def test_parses_uuid_string(self) -> None:
        org = uuid.uuid4()
        assert get_user_org_id(_user(organization_id=str(org))) == org

    def test_returns_none_when_absent(self) -> None:
        assert get_user_org_id(_user(organization_id=None)) is None

    def test_raises_on_malformed_uuid(self) -> None:
        with pytest.raises(ValueError):
            get_user_org_id(_user(organization_id="not-a-uuid"))


class TestCanAccessOrg:
    def test_platform_admin_can_access_any_org(self) -> None:
        assert can_access_org(_user(roles=["platform-admin"]), uuid.uuid4()) is True

    def test_user_can_access_own_org(self) -> None:
        org = uuid.uuid4()
        assert can_access_org(_user(organization_id=str(org)), org) is True

    def test_user_cannot_access_other_org(self) -> None:
        user = _user(organization_id=str(uuid.uuid4()))
        assert can_access_org(user, uuid.uuid4()) is False

    def test_user_without_org_cannot_access(self) -> None:
        assert can_access_org(_user(organization_id=None), uuid.uuid4()) is False


class TestVerifyOrgAccess:
    def test_no_error_when_authorized(self) -> None:
        org = uuid.uuid4()
        verify_org_access(_user(organization_id=str(org)), org)

    def test_raises_403_when_unauthorized(self) -> None:
        user = _user(organization_id=str(uuid.uuid4()))

        with pytest.raises(HTTPException) as excinfo:
            verify_org_access(user, uuid.uuid4())

        assert excinfo.value.status_code == 403
        assert "access" in excinfo.value.detail.lower()
