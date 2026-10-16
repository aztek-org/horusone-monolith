"""Unit tests for the scenario routes' RBAC scoping and validation."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1 import scenarios
from app.db.session import get_db_session
from app.main import app
from app.middleware.auth import TokenUser, get_current_user
from app.middleware.org_context import (
    get_authenticated_user,
    get_org_id,
    require_active_seat,
)
from app.schemas.scenario import ScenarioCreate


class _ScalarsResult:
    """SQLAlchemy result stub supporting ``scalars().all()``."""

    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> _ScalarsResult:
        return self

    def all(self) -> list[object]:
        return self._rows


class _ScalarResult:
    """SQLAlchemy result stub supporting ``scalar_one_or_none()``."""

    def __init__(self, row: object | None) -> None:
        self._row = row

    def scalar_one_or_none(self) -> object | None:
        return self._row


def _build_user(roles: list[str], org_id: uuid.UUID | None = None) -> TokenUser:
    return TokenUser(
        keycloak_id="kc-user",
        email="user@test.com",
        display_name="User",
        roles=roles,
        organization_id=str(org_id) if org_id else None,
    )


@pytest.mark.asyncio
async def test_list_scenarios_scopes_non_admin_to_org_and_global() -> None:
    org_id = uuid.uuid4()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarsResult([]))

    await scenarios.list_scenarios(
        user=_build_user(["student"], org_id),
        org_id=org_id,
        limit=10,
        offset=0,
        session=session,
    )

    query = session.execute.await_args.args[0]
    where_clause = str(query.whereclause)
    assert "scenarios.org_id" in where_clause
    assert query.whereclause is not None


@pytest.mark.asyncio
async def test_list_scenarios_platform_admin_is_unscoped() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarsResult([]))

    await scenarios.list_scenarios(
        user=_build_user(["platform-admin"]),
        org_id=None,
        limit=10,
        offset=0,
        session=session,
    )

    query = session.execute.await_args.args[0]
    assert query.whereclause is None


@pytest.mark.asyncio
async def test_list_scenarios_without_org_sees_only_global() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarsResult([]))

    await scenarios.list_scenarios(
        user=_build_user(["student"]),
        org_id=None,
        limit=10,
        offset=0,
        session=session,
    )

    where_clause = str(session.execute.await_args.args[0].whereclause)
    assert "scenarios.org_id IS NULL" in where_clause


@pytest.mark.asyncio
async def test_create_scenario_persists_org_and_author() -> None:
    org_id = uuid.uuid4()
    author_id = uuid.uuid4()
    session = AsyncMock()
    session.add = Mock()

    await scenarios.create_scenario(
        data=ScenarioCreate(name="Arrival", airport_icao="KLAX", runway="24L"),
        user=_build_user(["instructor"], org_id),
        _seat=object(),
        org_id=org_id,
        local_user=SimpleNamespace(id=author_id),
        session=session,
    )

    created = session.add.call_args.args[0]
    assert created.org_id == org_id
    assert created.created_by == author_id
    assert created.name == "Arrival"
    session.flush.assert_awaited()
    session.refresh.assert_awaited()


@pytest.mark.asyncio
async def test_get_scenario_missing_returns_404() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarResult(None))

    with pytest.raises(HTTPException) as excinfo:
        await scenarios.get_scenario(
            scenario_id=7, user=_build_user(["student"]), session=session
        )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_get_scenario_cross_org_is_forbidden() -> None:
    other_org = uuid.uuid4()
    scenario = SimpleNamespace(id=7, org_id=other_org)
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarResult(scenario))

    with pytest.raises(HTTPException) as excinfo:
        await scenarios.get_scenario(
            scenario_id=7,
            user=_build_user(["student"], uuid.uuid4()),
            session=session,
        )

    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_get_scenario_global_is_accessible() -> None:
    scenario = SimpleNamespace(id=7, org_id=None)
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarResult(scenario))

    result = await scenarios.get_scenario(
        scenario_id=7, user=_build_user(["student"]), session=session
    )

    assert result is scenario


def _override_for_role_check(roles: list[str]) -> None:
    app.dependency_overrides[get_current_user] = lambda: _build_user(roles)
    app.dependency_overrides[require_active_seat] = lambda: object()
    app.dependency_overrides[get_db_session] = lambda: object()
    app.dependency_overrides[get_org_id] = lambda: None
    app.dependency_overrides[get_authenticated_user] = lambda: SimpleNamespace(
        id=uuid.uuid4()
    )


def test_create_scenario_requires_instructor_role(client: TestClient) -> None:
    _override_for_role_check(["student"])

    response = client.post(
        "/api/v1/scenarios/",
        json={"name": "Arrival", "airport_icao": "KLAX", "runway": "24L"},
    )

    assert response.status_code == 403


def test_list_scenarios_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/scenarios/")

    assert response.status_code == 401
