"""Composition-root wiring and voice-path coverage for the training Session module."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from psycopg import Connection, connect
from sqlalchemy.engine import make_url

from app.config import Settings, get_settings
from app.main import app
from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from tests.conftest import collect_frames, fake_audio_services, fake_ws_user

DATABASE_URL = os.getenv("DATABASE_URL")
_SYNC_DSN = (
    make_url(DATABASE_URL).set(drivername="postgresql").render_as_string(
        hide_password=False
    )
    if DATABASE_URL
    else ""
)


def _sync_db() -> Connection:
    """Open a loop-independent connection so the sync test never touches the app pool."""
    return connect(_SYNC_DSN, autocommit=True)


def _write_scenes_file(path) -> None:
    path.write_text(
        "scenes:\n"
        "  - version: storm-v3\n"
        "    name: Storm\n"
        "    prompt_template: |-\n"
        "      {callsign} at {altitude} ft, {heading} degrees, {speed} knots\n"
        "      near {position}, {phase}, heading {destination}, {weather},\n"
        "      aircraft {aircraft_type}. Pilot: {pilot_message}\n",
        encoding="utf-8",
    )


def test_scene_registry_falls_back_to_the_packaged_default(client: TestClient) -> None:
    """With no configured scenes_path the packaged default Scene is registered."""
    registry = client.app.state.scene_registry

    assert registry.default().version == DEFAULT_SCENE.version
    assert registry.get(DEFAULT_SCENE.version) is DEFAULT_SCENE


def test_scene_registry_loads_the_configured_scenes_path(test_settings: Settings, tmp_path) -> None:
    """SCENES_PATH reaches the registry through Settings, not a direct env read."""
    scenes_file = tmp_path / "scenes.yaml"
    _write_scenes_file(scenes_file)
    app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(
        update={"scenes_path": str(scenes_file)}
    )
    try:
        with TestClient(app) as client:
            registry = client.app.state.scene_registry
            assert registry.get("storm-v3").version == "storm-v3"
            assert registry.default().version == DEFAULT_SCENE.version
    finally:
        app.dependency_overrides.clear()


def test_composition_root_builds_session_module(client: TestClient) -> None:
    """The lifespan must build every collaborator once and publish it on app.state."""
    state = client.app.state

    assert state.session_module is not None
    assert state.llm.provider == "fake"
    assert state.scene_registry.get(DEFAULT_SCENE.version).version == DEFAULT_SCENE.version
    assert state.session_store is not None
    assert state.trace_recorder is not None
    assert state.retriever is not None
    assert state.settings.environment == "testing"


@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is required for the voice WebSocket")
def test_voice_session_without_scene_records_default_scene(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Connecting to /ws/voice without a Scene must still serve an exchange.

    The training session the voice route creates is recorded with the packaged
    default Scene version, proving the voice path no longer needs a caller to
    choose a Scene first.
    """
    fake_ws_user(monkeypatch)
    fake_audio_services(monkeypatch)

    client_id = None
    payloads: list[dict] = []
    audio_frames = 0
    with client.websocket_connect("/ws/voice") as websocket:
        connected = websocket.receive_json()
        assert connected["type"] == "connected"
        client_id = connected["client_id"]

        websocket.send_bytes(b"RIFF-not-real-audio")
        websocket.send_json({"type": "audio_end"})
        payloads, audio_frames = collect_frames(websocket)

    frame_types = [payload["type"] for payload in payloads]
    assert "response_complete" in frame_types
    assert "error" not in frame_types
    assert audio_frames == 1

    with _sync_db() as db:
        try:
            row = db.execute(
                "SELECT id, scene_version, scene_snapshot FROM training_sessions "
                "WHERE client_id = %s",
                (client_id,),
            ).fetchone()
            assert row is not None
            session_id, scene_version, scene_snapshot = row
            assert scene_version == DEFAULT_SCENE.version
            assert scene_snapshot["version"] == DEFAULT_SCENE.version

            logs = db.execute(
                "SELECT role, transcript FROM voice_logs WHERE session_id = %s ORDER BY id",
                (session_id,),
            ).fetchall()
            assert [role for role, _ in logs] == ["pilot", "atc"]
            assert logs[0][1] == "N123AB tower, taxi via alpha"
            assert logs[1][1]

            events = db.execute(
                "SELECT event_type FROM training_session_events "
                "WHERE session_id = %s ORDER BY created_at",
                (session_id,),
            ).fetchall()
            assert [event_type for (event_type,) in events] == [
                "created",
                "session_started",
                "exchange_completed",
            ]
        finally:
            db.execute("DELETE FROM training_sessions WHERE client_id = %s", (client_id,))
