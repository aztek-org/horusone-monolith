"""Unit tests for the authentication helper routes."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1 import auth
from app.core.org_ids import org_id_for_slug
from app.middleware.auth import TokenUser


class _ScalarsResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> _ScalarsResult:
        return self

    def all(self) -> list[object]:
        return self._rows


def _token(roles: list[str] | None = None) -> TokenUser:
    return TokenUser(
        keycloak_id="kc-user",
        email="user@test.com",
        display_name="User",
        roles=roles or ["student"],
    )


@pytest.mark.asyncio
async def test_logout_clears_redis_session() -> None:
    redis = AsyncMock()
    redis.delete = AsyncMock()

    with patch.object(auth, "get_redis", new=AsyncMock(return_value=redis)):
        result = await auth.logout(body=auth.LogoutRequest(), user=_token())

    assert result.message == "Logged out successfully"
    assert redis.delete.await_args.args == ("session:kc-user",)


@pytest.mark.asyncio
async def test_logout_survives_redis_failure() -> None:
    with patch.object(auth, "get_redis", new=AsyncMock(side_effect=RuntimeError("redis down"))):
        result = await auth.logout(body=auth.LogoutRequest(), user=_token())

    assert result.message == "Logged out successfully"


@pytest.mark.asyncio
async def test_create_session_caches_hashed_token() -> None:
    redis = AsyncMock()
    redis.setex = AsyncMock()
    request = SimpleNamespace(headers={"user-agent": "pytest/1.0"})

    with patch.object(auth, "get_redis", new=AsyncMock(return_value=redis)):
        result = await auth.create_session(
            body=auth.SessionCreateRequest(access_token="secret-token"),
            user=_token(),
            request=request,
        )

    assert result.session_key == "session:kc-user"
    redis.setex.assert_awaited()


@pytest.mark.asyncio
async def test_get_current_user_profile_reports_active_seat() -> None:
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    seat = SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=org_id,
        organization=SimpleNamespace(name="Sky"),
        role="instructor",
        is_active=True,
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarsResult([seat]))
    local_user = SimpleNamespace(
        id=user_id,
        keycloak_id="kc-user",
        email="user@test.com",
        display_name="User",
        seats=[],
    )

    result = await auth.get_current_user_profile(
        user=_token(["instructor"]),
        local_user=local_user,
        session=session,
    )

    assert result.has_active_seat is True
    assert result.seats[0].organization_name == "Sky"
    assert result.seats[0].role == "instructor"
    assert result.enabled_features == ["hangar", "squawk", "tower"]


@pytest.mark.asyncio
async def test_get_current_user_profile_platform_admin_has_active_seat() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarsResult([]))
    local_user = SimpleNamespace(
        id=uuid.uuid4(),
        keycloak_id="kc-admin",
        email="admin@test.com",
        display_name="Admin",
        seats=[],
    )

    result = await auth.get_current_user_profile(
        user=_token(["platform-admin"]),
        local_user=local_user,
        session=session,
    )

    assert result.has_active_seat is True
    assert result.seats == []


@pytest.mark.asyncio
async def test_get_current_user_profile_resolves_slug_org_claim() -> None:
    """A legacy slug org claim must not 500 — it resolves to the org UUID (#18)."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarsResult([]))
    local_user = SimpleNamespace(
        id=uuid.uuid4(),
        keycloak_id="kc-user",
        email="user@test.com",
        display_name="User",
        seats=[],
    )
    token = TokenUser(
        keycloak_id="kc-user",
        email="user@test.com",
        display_name="User",
        roles=["instructor"],
        organization_id="skybridge",
    )

    result = await auth.get_current_user_profile(
        user=token,
        local_user=local_user,
        session=session,
    )

    assert result.organization_id == org_id_for_slug("skybridge")
