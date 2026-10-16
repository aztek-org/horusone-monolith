"""Unit tests for the platform admin routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1 import admin
from app.db.session import get_db_session
from app.main import app
from app.middleware.auth import TokenUser, get_current_user
from app.models.seat import Seat
from app.schemas.admin import (
    AdminUserUpdate,
    OrganizationFeaturesUpdate,
    SeatCreateRequest,
    SeatRoleUpdate,
)
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _org(**overrides: object) -> SimpleNamespace:
    base = {
        "id": uuid.uuid4(),
        "name": "Sky Academy",
        "slug": "sky-academy",
        "logo_url": None,
        "is_active": True,
        "max_seats": 50,
        "billing_plan": "starter",
        "billing_status": "trial",
        "billing_cycle": "monthly",
        "created_at": _now(),
        "enabled_features": ["hangar", "squawk", "tower"],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _user_row(**overrides: object) -> SimpleNamespace:
    base = {
        "id": uuid.uuid4(),
        "email": "pilot@test.com",
        "display_name": "Pilot",
        "avatar_url": None,
        "is_active": True,
        "created_at": _now(),
        "seats": [],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _token(roles: list[str], org_id: uuid.UUID | None = None) -> TokenUser:
    return TokenUser(
        keycloak_id="kc-admin",
        email="admin@test.com",
        display_name="Admin",
        roles=roles,
        organization_id=str(org_id) if org_id else None,
    )


class _ScalarsResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> _ScalarsResult:
        return self

    def all(self) -> list[object]:
        return self._rows


class _AllResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _ScalarResult:
    def __init__(self, row: object | None) -> None:
        self._row = row

    def scalar_one_or_none(self) -> object | None:
        return self._row


# ── Organization endpoints ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_organizations_maps_aggregates() -> None:
    org = _org()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_AllResult([(org, 12, 3, 7)]))

    result = await admin.list_organizations(
        user=_token(["platform-admin"]), limit=50, offset=0, session=session
    )

    assert result[0].seat_count == 12
    assert result[0].active_sessions == 3
    assert result[0].scenario_count == 7


@pytest.mark.asyncio
async def test_create_organization_conflict_on_slug() -> None:
    session = AsyncMock()
    with patch.object(admin.org_repo, "get_by_slug", new=AsyncMock(return_value=_org())):
        with pytest.raises(HTTPException) as excinfo:
            await admin.create_organization(
                data=OrganizationCreate(name="Sky", slug="sky-academy"),
                user=_token(["platform-admin"]),
                session=session,
            )

    assert excinfo.value.status_code == 409


@pytest.mark.asyncio
async def test_create_organization_persists() -> None:
    org = _org()
    session = AsyncMock()
    with (
        patch.object(admin.org_repo, "get_by_slug", new=AsyncMock(return_value=None)),
        patch.object(admin.org_repo, "create", new=AsyncMock(return_value=org)),
    ):
        result = await admin.create_organization(
            data=OrganizationCreate(name="Sky", slug="sky-academy"),
            user=_token(["platform-admin"]),
            session=session,
        )

    assert result.slug == "sky-academy"


@pytest.mark.asyncio
async def test_get_organization_missing_returns_404() -> None:
    session = AsyncMock()
    with patch.object(admin.org_repo, "get_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as excinfo:
            await admin.get_organization(
                org_id=uuid.uuid4(),
                user=_token(["platform-admin"]),
                session=session,
            )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_get_organization_returns_live_stats() -> None:
    org = _org()
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[10, 2, 5])

    with patch.object(admin.org_repo, "get_by_id", new=AsyncMock(return_value=org)):
        result = await admin.get_organization(
            org_id=org.id, user=_token(["platform-admin"]), session=session
        )

    assert result.seat_count == 10
    assert result.active_sessions == 2
    assert result.scenario_count == 5


@pytest.mark.asyncio
async def test_get_organization_forbids_cross_org_admin() -> None:
    session = AsyncMock()
    with pytest.raises(HTTPException) as excinfo:
        await admin.get_organization(
            org_id=uuid.uuid4(),
            user=_token(["org-admin"], uuid.uuid4()),
            session=session,
        )

    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_update_organization_applies_fields() -> None:
    org = _org()
    session = AsyncMock()

    with patch.object(admin.org_repo, "get_by_id", new=AsyncMock(return_value=org)):
        result = await admin.update_organization(
            org_id=org.id,
            data=OrganizationUpdate(name="Renamed"),
            user=_token(["platform-admin"]),
            session=session,
        )

    assert result.name == "Renamed"
    assert org.name == "Renamed"


@pytest.mark.asyncio
async def test_deactivate_organization_sets_inactive() -> None:
    org = _org()
    session = AsyncMock()

    with patch.object(admin.org_repo, "get_by_id", new=AsyncMock(return_value=org)):
        result = await admin.deactivate_organization(
            org_id=org.id, user=_token(["platform-admin"]), session=session
        )

    assert org.is_active is False
    assert "deactivated" in result["detail"]


# ── Seat endpoints ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_seats_maps_user_details() -> None:
    org_id = uuid.uuid4()
    seat = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        organization_id=org_id,
        role="student",
        is_active=True,
        joined_at=_now(),
        user=SimpleNamespace(email="s@test.com", display_name="Student"),
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarsResult([seat]))

    result = await admin.list_seats(org_id=org_id, user=_token(["platform-admin"]), session=session)

    assert result[0].user_email == "s@test.com"


@pytest.mark.asyncio
async def test_create_seat_missing_user_returns_404() -> None:
    org = _org()
    session = AsyncMock()

    with (
        patch.object(admin.org_repo, "get_by_id", new=AsyncMock(return_value=org)),
        patch.object(admin.user_repo, "get_by_email", new=AsyncMock(return_value=None)),
    ):
        with pytest.raises(HTTPException) as excinfo:
            await admin.create_seat(
                org_id=org.id,
                data=SeatCreateRequest(email="missing@test.com", role="student"),
                user=_token(["platform-admin"]),
                session=session,
            )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_create_seat_conflict_when_member_exists() -> None:
    org = _org()
    target = _user_row()
    session = AsyncMock()

    with (
        patch.object(admin.org_repo, "get_by_id", new=AsyncMock(return_value=org)),
        patch.object(admin.user_repo, "get_by_email", new=AsyncMock(return_value=target)),
        patch.object(
            admin.seat_repo,
            "get_user_org_seat",
            new=AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
        ),
    ):
        with pytest.raises(HTTPException) as excinfo:
            await admin.create_seat(
                org_id=org.id,
                data=SeatCreateRequest(email=target.email, role="student"),
                user=_token(["platform-admin"]),
                session=session,
            )

    assert excinfo.value.status_code == 409


@pytest.mark.asyncio
async def test_create_seat_enforces_seat_limit() -> None:
    org = _org(max_seats=1)
    target = _user_row()
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=1)

    with (
        patch.object(admin.org_repo, "get_by_id", new=AsyncMock(return_value=org)),
        patch.object(admin.user_repo, "get_by_email", new=AsyncMock(return_value=target)),
        patch.object(admin.seat_repo, "get_user_org_seat", new=AsyncMock(return_value=None)),
    ):
        with pytest.raises(HTTPException) as excinfo:
            await admin.create_seat(
                org_id=org.id,
                data=SeatCreateRequest(email=target.email, role="student"),
                user=_token(["platform-admin"]),
                session=session,
            )

    assert excinfo.value.status_code == 409
    assert "seat limit" in excinfo.value.detail


@pytest.mark.asyncio
async def test_create_seat_persists_and_returns_member() -> None:
    org = _org(max_seats=10)
    target = _user_row()
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=0)
    session.add = Mock()

    async def _refresh(instance: object) -> None:
        if isinstance(instance, Seat):
            instance.id = uuid.uuid4()
            instance.is_active = True
            instance.joined_at = _now()

    session.refresh = AsyncMock(side_effect=_refresh)

    with (
        patch.object(admin.org_repo, "get_by_id", new=AsyncMock(return_value=org)),
        patch.object(admin.user_repo, "get_by_email", new=AsyncMock(return_value=target)),
        patch.object(admin.seat_repo, "get_user_org_seat", new=AsyncMock(return_value=None)),
    ):
        result = await admin.create_seat(
            org_id=org.id,
            data=SeatCreateRequest(email=target.email, role="student"),
            user=_token(["platform-admin"]),
            session=session,
        )

    assert result.user_email == target.email
    assert result.role == "student"


@pytest.mark.asyncio
async def test_update_seat_missing_returns_404() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarResult(None))

    with pytest.raises(HTTPException) as excinfo:
        await admin.update_seat(
            org_id=uuid.uuid4(),
            seat_id=uuid.uuid4(),
            data=SeatRoleUpdate(role="instructor"),
            user=_token(["platform-admin"]),
            session=session,
        )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_update_seat_changes_role() -> None:
    org_id = uuid.uuid4()
    seat = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        organization_id=org_id,
        role="student",
        is_active=True,
        joined_at=_now(),
        user=SimpleNamespace(email="s@test.com", display_name="Student"),
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarResult(seat))

    result = await admin.update_seat(
        org_id=org_id,
        seat_id=seat.id,
        data=SeatRoleUpdate(role="instructor"),
        user=_token(["platform-admin"]),
        session=session,
    )

    assert seat.role == "instructor"
    assert result.role == "instructor"


@pytest.mark.asyncio
async def test_deactivate_seat_sets_inactive() -> None:
    org_id = uuid.uuid4()
    seat = SimpleNamespace(id=uuid.uuid4(), is_active=True)
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarResult(seat))

    result = await admin.deactivate_seat(
        org_id=org_id,
        seat_id=seat.id,
        user=_token(["platform-admin"]),
        session=session,
    )

    assert seat.is_active is False
    assert "deactivated" in result["detail"]


# ── User endpoints ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_users_maps_rows() -> None:
    row = _user_row()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarsResult([row]))

    result = await admin.list_users(
        user=_token(["platform-admin"]),
        search=None,
        limit=50,
        offset=0,
        session=session,
    )

    assert result[0].email == "pilot@test.com"


@pytest.mark.asyncio
async def test_get_user_missing_returns_404() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarResult(None))

    with pytest.raises(HTTPException) as excinfo:
        await admin.get_user(
            user_id=uuid.uuid4(),
            user=_token(["platform-admin"]),
            session=session,
        )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_get_user_forbids_org_admin_outside_org() -> None:
    target = _user_row()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarResult(target))

    with patch.object(admin.seat_repo, "get_user_org_seat", new=AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as excinfo:
            await admin.get_user(
                user_id=target.id,
                user=_token(["org-admin"], uuid.uuid4()),
                session=session,
            )

    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_get_user_platform_admin_bypasses_org_check() -> None:
    target = _user_row()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarResult(target))

    result = await admin.get_user(
        user_id=target.id, user=_token(["platform-admin"]), session=session
    )

    assert result.email == "pilot@test.com"


@pytest.mark.asyncio
async def test_update_user_missing_returns_404() -> None:
    session = AsyncMock()
    with patch.object(admin.user_repo, "get_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as excinfo:
            await admin.update_user(
                user_id=uuid.uuid4(),
                data=AdminUserUpdate(display_name="New"),
                user=_token(["platform-admin"]),
                session=session,
            )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_update_user_applies_fields() -> None:
    target = _user_row()
    session = AsyncMock()

    with patch.object(admin.user_repo, "get_by_id", new=AsyncMock(return_value=target)):
        result = await admin.update_user(
            user_id=target.id,
            data=AdminUserUpdate(display_name="Renamed"),
            user=_token(["platform-admin"]),
            session=session,
        )

    assert result.display_name == "Renamed"


# ── Platform statistics & feature flags ────────────────────────────


@pytest.mark.asyncio
async def test_platform_stats_aggregates_counts() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[5, 100, 42, 9, 3])

    result = await admin.get_platform_stats(user=_token(["platform-admin"]), session=session)

    assert result.total_orgs == 5
    assert result.total_users == 100
    assert result.active_sessions == 3


@pytest.mark.asyncio
async def test_get_features_missing_returns_404() -> None:
    session = AsyncMock()
    with patch.object(admin.org_repo, "get_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as excinfo:
            await admin.get_organization_features(
                org_id=uuid.uuid4(),
                user=_token(["platform-admin"]),
                session=session,
            )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_get_features_forbids_cross_org_admin() -> None:
    """An org-admin cannot read another tenant's feature flags (issue #78)."""
    session = AsyncMock()
    with pytest.raises(HTTPException) as excinfo:
        await admin.get_organization_features(
            org_id=uuid.uuid4(),
            user=_token(["org-admin"], uuid.uuid4()),
            session=session,
        )

    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_get_features_allows_own_org_admin() -> None:
    """An org-admin can read their own organization's feature flags."""
    org = _org()
    session = AsyncMock()

    with patch.object(admin.org_repo, "get_by_id", new=AsyncMock(return_value=org)):
        result = await admin.get_organization_features(
            org_id=org.id,
            user=_token(["org-admin"], org.id),
            session=session,
        )

    assert result.org_id == org.id
    assert result.enabled_features == ["hangar", "squawk", "tower"]


@pytest.mark.asyncio
async def test_update_features_rejects_unknown_flags() -> None:
    org = _org()
    session = AsyncMock()

    with patch.object(admin.org_repo, "get_by_id", new=AsyncMock(return_value=org)):
        with pytest.raises(HTTPException) as excinfo:
            await admin.update_organization_features(
                org_id=org.id,
                data=OrganizationFeaturesUpdate(enabled_features=["unknown"]),
                _user=_token(["platform-admin"]),
                session=session,
            )

    assert excinfo.value.status_code == 400


@pytest.mark.asyncio
async def test_update_features_sanitizes_and_persists() -> None:
    org = _org()
    session = AsyncMock()
    session.add = Mock()

    with patch.object(admin.org_repo, "get_by_id", new=AsyncMock(return_value=org)):
        result = await admin.update_organization_features(
            org_id=org.id,
            data=OrganizationFeaturesUpdate(enabled_features=["hangar", "bogus"]),
            _user=_token(["platform-admin"]),
            session=session,
        )

    assert result.enabled_features == ["hangar"]
    assert org.enabled_features == ["hangar"]


# ── HTTP-level role gating ─────────────────────────────────────────


def test_admin_stats_requires_platform_admin(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _token(["instructor"])
    app.dependency_overrides[get_db_session] = lambda: object()

    response = client.get("/api/v1/admin/stats")

    assert response.status_code == 403


def test_admin_stats_allows_platform_admin(client: TestClient) -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[1, 2, 3, 4, 0])
    app.dependency_overrides[get_current_user] = lambda: _token(["platform-admin"])
    app.dependency_overrides[get_db_session] = lambda: session

    response = client.get("/api/v1/admin/stats")

    assert response.status_code == 200, response.text
    assert response.json()["total_users"] == 2
