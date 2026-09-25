"""API tests for versioned Scene discovery."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.auth import TokenUser, get_current_user
from app.services.llm.scenes.default_scene import DEFAULT_SCENE


@pytest.fixture
def authenticated_client(client: TestClient) -> TestClient:
    """Use the same auth dependency override as other API integration tests."""
    app.dependency_overrides[get_current_user] = lambda: TokenUser(
        keycloak_id="scene-reader",
        email="scene-reader@test.com",
        display_name="Scene Reader",
        roles=["student"],
    )
    yield client
    app.dependency_overrides.pop(get_current_user, None)


EXPECTED_DEFAULT_SCENE = {
    "version": "default-v1",
    "name": "Cessna 172 Cross-country",
    "aircraft": {
        "type": "C172",
        "callsign": "Cessna 172 November 1234 Alpha",
    },
    "airports": {"departure": "KLAX", "arrival": "KSFO"},
    "objectives": [
        "Maintain standard ICAO phraseology",
        "Request and respond to clearances",
        "Demonstrate emergency readback",
    ],
    "difficulty": 1,
    "knowledge_refs": [],
}


def test_list_scenes_includes_default(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/api/v1/scenes/")

    assert response.status_code == 200
    assert response.json()[0] == EXPECTED_DEFAULT_SCENE


def test_get_scene_returns_default_training_context(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.get(f"/api/v1/scenes/{DEFAULT_SCENE.version}")

    assert response.status_code == 200
    assert response.json() == EXPECTED_DEFAULT_SCENE


def test_get_unknown_scene_returns_404(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/api/v1/scenes/does-not-exist-v9")

    assert response.status_code == 404
