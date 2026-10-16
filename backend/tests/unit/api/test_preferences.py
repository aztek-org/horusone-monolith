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


def _prefs_document(data: dict | None = None) -> SimpleNamespace:
    now = datetime.now(tz=timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        preferences=data if data is not None else preferences._default_preferences(),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def http(client: TestClient) -> TestClient:
    """Client with the database dependency replaced by an inert object."""
    app.dependency_overrides[get_db_session] = lambda: object()
    return client


def _authenticate(*, keycloak_id: str) -> None:
    app.dependency_overrides[get_current_user] = lambda: TokenUser(
        keycloak_id=keycloak_id,
        email="user@test.com",
        display_name="User",
        roles=["student"],
    )


def test_get_preferences_returns_defaults_for_dev_token(http: TestClient) -> None:
    _authenticate(keycloak_id="dev-user")

    response = http.get("/api/v1/users/me/preferences/")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"id", "user_id", "preferences", "created_at", "updated_at"}
    assert set(body["preferences"]) == {"keyboard_shortcuts", "voice", "display"}
    assert body["preferences"]["display"]["theme"] == "dark"


def test_get_preferences_returns_defaults_when_no_row_exists(http: TestClient) -> None:
    user_id = uuid.uuid4()
    _authenticate(keycloak_id=str(user_id))

    with patch.object(
        preferences.repo, "get_by_user_id", new=AsyncMock(return_value=None)
    ):
        response = http.get("/api/v1/users/me/preferences/")

    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == str(user_id)
    assert response.json()["preferences"]["voice"]["ptt_mode"] == "hold"


def test_get_preferences_returns_stored_document(http: TestClient) -> None:
    user_id = uuid.uuid4()
    stored = {"voice": {"radio_effects": False, "language": "es", "ptt_mode": "toggle"}}
    _authenticate(keycloak_id=str(user_id))

    with patch.object(
        preferences.repo,
        "get_by_user_id",
        new=AsyncMock(return_value=_prefs_document(stored)),
    ):
        response = http.get("/api/v1/users/me/preferences/")

    assert response.status_code == 200, response.text
    assert response.json()["preferences"] == stored


def test_patch_preferences_rejects_unknown_section(http: TestClient) -> None:
    _authenticate(keycloak_id=str(uuid.uuid4()))

    response = http.patch(
        "/api/v1/users/me/preferences/bogus",
        json={"data": {"theme": "light"}},
    )

    assert response.status_code == 400
    assert "Invalid section" in response.json()["detail"]


def test_patch_preferences_rejects_non_uuid_user(http: TestClient) -> None:
    _authenticate(keycloak_id="dev-user")

    response = http.patch(
        "/api/v1/users/me/preferences/voice",
        json={"data": {"language": "es"}},
    )

    assert response.status_code == 400
    assert "Invalid user ID format" in response.json()["detail"]


def test_patch_preferences_deep_merges_into_existing_section(http: TestClient) -> None:
    user_id = uuid.uuid4()
    _authenticate(keycloak_id=str(user_id))
    existing = _prefs_document({"voice": {"radio_effects": True}})
    upsert = AsyncMock(return_value=_prefs_document())

    with (
        patch.object(
            preferences.repo, "get_by_user_id", new=AsyncMock(return_value=existing)
        ),
        patch.object(preferences.repo, "upsert", new=upsert),
    ):
        response = http.patch(
            "/api/v1/users/me/preferences/voice",
            json={"data": {"language": "es"}},
        )

    assert response.status_code == 200, response.text
    assert upsert.await_args.args[2] == {
        "voice": {"radio_effects": True, "language": "es"}
    }


def test_put_preferences_persists_payload(http: TestClient) -> None:
    user_id = uuid.uuid4()
    _authenticate(keycloak_id=str(user_id))
    upsert = AsyncMock(return_value=_prefs_document())

    with patch.object(preferences.repo, "upsert", new=upsert):
        response = http.put(
            "/api/v1/users/me/preferences/",
            json={"preferences": {"display": {"theme": "light"}}},
        )

    assert response.status_code == 200, response.text
    assert upsert.await_args.args[2] == {"display": {"theme": "light"}}


def test_put_preferences_rejects_non_uuid_user(http: TestClient) -> None:
    _authenticate(keycloak_id="dev-user")

    response = http.put(
        "/api/v1/users/me/preferences/",
        json={"preferences": {"display": {"theme": "light"}}},
    )

    assert response.status_code == 400
