"""Composition-root wiring and voice-path coverage for the training Session module."""

from __future__ import annotations

import os
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from psycopg import Connection, connect
from sqlalchemy.engine import make_url

from app.api.v1 import sessions
from app.config import Settings, get_settings
from app.llm.adapters.fake_adapter import FakeAdapter
from app.main import _build_scene_registry, app
from app.middleware.auth import TokenUser
from app.schemas.training_session import TrainingSessionCreate
from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from app.services.llm.scenes.registry import SceneRegistry
from app.services.training_sessions.session_module import TrainingSessionModule
from app.services.training_sessions.session_store import InMemorySessionStore
from app.services.training_sessions.trace import InMemoryTraceRecorder
from app.services.training_sessions.types import StartSessionCommand
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


class _NoDb:
    """Session factory stand-in; the Scene lookup happens before any SQL."""

    def __init__(self) -> None:
        self.commits = 0

    async def __aenter__(self) -> _NoDb:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, _statement: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


class _RecordingUnitOfWork:
    """AsyncSession stand-in that records the route's own database work."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute(self, *_args: object, **_kwargs: object) -> None:
        self.calls.append("execute")

    def add(self, _instance: object) -> None:
        self.calls.append("add")

    async def flush(self) -> None:
        self.calls.append("flush")

    async def refresh(self, _instance: object) -> None:
        self.calls.append("refresh")

    async def commit(self) -> None:
        self.calls.append("commit")


def _module(registry: SceneRegistry) -> TrainingSessionModule:
    """A Session module over in-memory collaborators, so no database is needed."""
    return TrainingSessionModule(
        InMemorySessionStore(),
        InMemoryTraceRecorder(),
        registry,
        FakeAdapter(),
        db_session_factory=_NoDb,
        require_org=False,
    )


def _clear_process_pipeline() -> None:
    """Drop the process-wide AudioPipeline so the next connection rebuilds it."""
    try:
        del app.state.audio_pipeline
    except (AttributeError, KeyError):
        pass


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


def test_scenes_path_without_the_packaged_default_registers_it(
    test_settings: Settings, tmp_path
) -> None:
    """A configured ``SCENES_PATH`` must not unregister the packaged default.

    ``SceneRegistry.default()`` falls back to the *packaged* Scene when the
    version is absent, and the voice route then hands that version to
    ``TrainingSessionModule.start``, which resolves it by version against the
    same registry.  An unregistered fallback is therefore a ``KeyError`` waiting
    to happen, so the default is registered even when the operator's YAML omits
    it.  This is an API response change: ``GET /api/v1/scenes`` now lists
    ``default-v1`` for such a deployment.
    """
    scenes_file = tmp_path / "scenes.yaml"
    _write_scenes_file(scenes_file)
    app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(
        update={"scenes_path": str(scenes_file)}
    )
    try:
        with TestClient(app) as client:
            registry = client.app.state.scene_registry

            # Appended after the operator's own Scenes, so the YAML keeps its order.
            assert [scene.version for scene in registry.list_all()] == [
                "storm-v3",
                DEFAULT_SCENE.version,
            ]
            assert registry.get(DEFAULT_SCENE.version) is DEFAULT_SCENE
            assert registry.default() is DEFAULT_SCENE
    finally:
        app.dependency_overrides.clear()


def test_scenes_path_naming_the_default_keeps_the_operators_own(
    test_settings: Settings, tmp_path
) -> None:
    """A YAML that defines ``default-v1`` keeps its definition; nothing is doubled."""
    scenes_file = tmp_path / "scenes.yaml"
    scenes_file.write_text(
        "scenes:\n"
        "  - version: default-v1\n"
        "    name: Operator default\n"
        "    prompt_template: |-\n"
        "      {callsign} at {altitude} ft, {heading} degrees, {speed} knots\n"
        "      near {position}, {phase}, heading {destination}, {weather},\n"
        "      aircraft {aircraft_type}. Pilot: {pilot_message}\n",
        encoding="utf-8",
    )
    registry = _build_scene_registry(
        test_settings.model_copy(update={"scenes_path": str(scenes_file)})
    )

    assert [scene.version for scene in registry.list_all()] == [DEFAULT_SCENE.version]
    assert registry.default().name == "Operator default"


@pytest.mark.asyncio
async def test_start_accepts_the_registrys_default_when_the_yaml_omits_it(
    test_settings: Settings, tmp_path
) -> None:
    """The Scene the registry hands out as its default is one it can start.

    This is the failure the fallback caused: ``default()`` returned a Scene whose
    version was never registered, so the voice route's ``start()`` raised
    ``KeyError`` and the socket died with no error frame, or the session degraded
    to unrecorded.  Resolving the default and starting it is the whole contract.
    """
    scenes_file = tmp_path / "scenes.yaml"
    _write_scenes_file(scenes_file)
    registry = _build_scene_registry(
        test_settings.model_copy(update={"scenes_path": str(scenes_file)})
    )

    snapshot = await _module(registry).start(
        StartSessionCommand(
            uuid.uuid4(),
            uuid.uuid4(),
            1,
            registry.default().version,
            "en",
            {"departure_icao": "KLAX", "arrival_icao": "KSFO"},
        )
    )

    assert snapshot.state["scene_version"] == DEFAULT_SCENE.version


@pytest.mark.asyncio
async def test_unknown_scene_version_is_refused_with_a_configured_scenes_path(
    test_settings: Settings, tmp_path
) -> None:
    """Registering the default must not make the registry lenient.

    If the lookup fell back instead of raising, a typo in ``scene_version``
    would silently train against the packaged default and be recorded as such.
    The 404 must survive the registry fix, and nothing may be written first.
    """
    scenes_file = tmp_path / "scenes.yaml"
    _write_scenes_file(scenes_file)
    registry = _build_scene_registry(
        test_settings.model_copy(update={"scenes_path": str(scenes_file)})
    )
    unit_of_work = _RecordingUnitOfWork()

    with pytest.raises(HTTPException) as excinfo:
        await sessions.create_session(
            data=TrainingSessionCreate(language="en", scene_version="ghost-v9"),
            request=SimpleNamespace(
                app=SimpleNamespace(
                    state=SimpleNamespace(
                        session_module=_module(registry),
                        scene_registry=registry,
                        settings=SimpleNamespace(environment="testing"),
                    )
                )
            ),
            user=TokenUser(
                keycloak_id="kc-student",
                email="student@test.com",
                display_name="Student",
                roles=["student"],
                organization_id=str(uuid.uuid4()),
            ),
            _seat=object(),
            org_id=uuid.uuid4(),
            local_user=SimpleNamespace(id=uuid.uuid4()),
            session=unit_of_work,
        )

    assert excinfo.value.status_code == 404
    assert "ghost-v9" in excinfo.value.detail
    assert unit_of_work.calls == []


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


@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is required for the voice WebSocket")
def test_voice_survives_a_scenes_path_without_the_packaged_default(
    test_settings: Settings, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A SCENES_PATH with no ``default-v1`` must not kill the voice socket.

    The registry used to hold only the YAML's own Scenes, so the voice route's
    ``default()`` returned a packaged Scene whose version was never registered:
    ``start()`` raised ``KeyError`` *after* ``manager.connect`` had already
    accepted and connected the socket, so the pilot held a live connection whose
    session was never recorded — a silent unrecorded session, not a refused one.
    The packaged default is now registered alongside the operator's Scenes, so
    the session is recorded against a Scene the module can start.
    """
    scenes_file = tmp_path / "scenes.yaml"
    _write_scenes_file(scenes_file)
    _clear_process_pipeline()
    app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(
        update={"scenes_path": str(scenes_file)}
    )
    try:
        with TestClient(app) as client:
            registered = [scene.version for scene in client.app.state.scene_registry.list_all()]
            assert registered == ["storm-v3", DEFAULT_SCENE.version]
            assert client.app.state.scene_registry.default().version == DEFAULT_SCENE.version

            fake_ws_user(monkeypatch)
            fake_audio_services(monkeypatch)

            with client.websocket_connect("/ws/voice") as websocket:
                connected = websocket.receive_json()

            assert connected["type"] == "connected"
    finally:
        _clear_process_pipeline()
        app.dependency_overrides.clear()
