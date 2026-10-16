"""Postgres integration coverage for the /users/me/preferences routes.

Exercises the full request path (auth dependency -> local User sync -> repo ->
real JSONB row), proving the row owner is the local ``User.id`` and not the
Keycloak subject (issue #17).
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.middleware.auth import TokenUser, get_current_user
from app.models.user import User
from app.models.user_preferences import UserPreferences

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL is required for preferences route integration tests",
)


async def _delete_user(keycloak_id: str) -> None:
    engine = create_async_engine(DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            user = await db.scalar(select(User).where(User.keycloak_id == keycloak_id))
            if user is not None:
                await db.execute(delete(UserPreferences).where(UserPreferences.user_id == user.id))
                await db.execute(delete(User).where(User.id == user.id))
                await db.commit()
    finally:
        await engine.dispose()


def test_preferences_round_trip_for_non_uuid_subject(client: TestClient) -> None:
    # Regression for #17: a non-UUID Keycloak subject must not 400/500, and the
    # persisted row must key off the local User.id.
    keycloak_id = f"kc-{uuid.uuid4()}"
    app.dependency_overrides[get_current_user] = lambda: TokenUser(
        keycloak_id=keycloak_id,
        email=f"{uuid.uuid4()}@prefs-e2e.com",
        display_name="Prefs E2E",
        roles=["student"],
    )

    try:
        put = client.put(
            "/api/v1/users/me/preferences/",
            json={"preferences": {"display": {"theme": "solarized"}}},
        )
        assert put.status_code == 200, put.text

        got = client.get("/api/v1/users/me/preferences/")
        assert got.status_code == 200, got.text
        body = got.json()

        assert body["preferences"]["display"]["theme"] == "solarized"
        assert body["user_id"] != keycloak_id
        uuid.UUID(body["user_id"])  # owner is a real users.id UUID
    finally:
        asyncio.run(_delete_user(keycloak_id))
