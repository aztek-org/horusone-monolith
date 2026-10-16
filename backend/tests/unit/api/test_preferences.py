"""Unit tests for the user-preferences HTTP routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import preferences
from app.db.session import get_db_session
from app.main import app
from app.middleware.auth import TokenUser, get_current_user
from app.middleware.org_context import get_authenticated_user


def _prefs_document(
    data: dict | None = None, *, user_id: uuid.UUID | None = None
) -> SimpleNamespace:
    now = datetime.now(tz=timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        preferences=data if data is not None else preferences._default_preferences(),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def http(client: TestClient) -> TestClient:
    """Client with the database dependency replaced by an inert object."""
    app.dependency_overrides[get_db_session] = lambda: object()
    return client


def _authenticate(*, user_id: uuid.UUID, keycloak_id: str = "kc-dev-subject") -> None:
    """Authenticate as a local user whose Keycloak subject is not a UUID.

    Preferences must be keyed off the local ``User.id`` (a UUID), never off
    the Keycloak subject identifier (issue #17).
    """
    app.dependency_overrides[get_current_user] = lambda: TokenUser(
        keycloak_id=keycloak_id,
        email="user@test.com",
        display_name="User",
        roles=["student"],
    )
    app.dependency_overrides[get_authenticated_user] = lambda: SimpleNamespace(id=user_id)


def test_get_preferences_returns_defaults_when_no_row_exists(http: TestClient) -> None:
    user_id = uuid.uuid4()
    _authenticate(user_id=user_id)
    get_by_user_id = AsyncMock(return_value=None)

    with patch.object(preferences.repo, "get_by_user_id", new=get_by_user_id):
        response = http.get("/api/v1/users/me/preferences/")

    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == str(user_id)
    assert response.json()["preferences"]["voice"]["ptt_mode"] == "hold"
    assert get_by_user_id.await_args.args[1] == user_id


def test_get_preferences_returns_stored_document(http: TestClient) -> None:
    user_id = uuid.uuid4()
    stored = {"voice": {"radio_effects": False, "language": "es", "ptt_mode": "toggle"}}
    _authenticate(user_id=user_id)
    get_by_user_id = AsyncMock(return_value=_prefs_document(stored, user_id=user_id))

    with patch.object(preferences.repo, "get_by_user_id", new=get_by_user_id):
        response = http.get("/api/v1/users/me/preferences/")

    assert response.status_code == 200, response.text
    assert response.json()["preferences"] == stored
    assert get_by_user_id.await_args.args[1] == user_id


def test_put_preferences_persists_under_local_user_id(http: TestClient) -> None:
    # Regression for #17: a non-UUID Keycloak subject must not break the write,
    # and the row owner must be the local User.id.
    user_id = uuid.uuid4()
    _authenticate(user_id=user_id, keycloak_id="kc-abc-123")
    upsert = AsyncMock(return_value=_prefs_document(user_id=user_id))

    with patch.object(preferences.repo, "upsert", new=upsert):
        response = http.put(
            "/api/v1/users/me/preferences/",
            json={"preferences": {"display": {"theme": "light"}}},
        )

    assert response.status_code == 200, response.text
    assert upsert.await_args.args[1] == user_id
    assert upsert.await_args.args[2] == {"display": {"theme": "light"}}


def test_patch_preferences_rejects_unknown_section(http: TestClient) -> None:
    _authenticate(user_id=uuid.uuid4())

    response = http.patch(
        "/api/v1/users/me/preferences/bogus",
        json={"data": {"theme": "light"}},
    )

    assert response.status_code == 400
    assert "Invalid section" in response.json()["detail"]


def test_patch_preferences_deep_merges_into_existing_section(http: TestClient) -> None:
    user_id = uuid.uuid4()
    _authenticate(user_id=user_id, keycloak_id="kc-abc-123")
    existing = _prefs_document({"voice": {"radio_effects": True}}, user_id=user_id)
    upsert = AsyncMock(return_value=_prefs_document(user_id=user_id))

    with (
        patch.object(preferences.repo, "get_by_user_id", new=AsyncMock(return_value=existing)),
        patch.object(preferences.repo, "upsert", new=upsert),
    ):
        response = http.patch(
            "/api/v1/users/me/preferences/voice",
            json={"data": {"language": "es"}},
        )

    assert response.status_code == 200, response.text
    assert upsert.await_args.args[1] == user_id
    assert upsert.await_args.args[2] == {"voice": {"radio_effects": True, "language": "es"}}
