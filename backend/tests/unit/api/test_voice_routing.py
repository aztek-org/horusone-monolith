"""Regression coverage for the /ws/voice protocol and Session fallback branches.

These tests pin the behaviour the Task 7 rewiring had to preserve: authentication,
the active-seat gate, both payload limits, and the reset / language_change / ping
messages — plus the two new branches where the persisted Session is absent or
fails, which must never look like a successful recorded exchange.
"""

from __future__ import annotations

import json
import os
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from psycopg import connect
from sqlalchemy.engine import make_url
from starlette.websockets import WebSocketDisconnect

from app.api.routes import voice as voice_module
from app.main import app
from tests.conftest import (
    FakeSessionModule,
    collect_frames,
    fake_audio_services,
    fake_ws_user,
    no_database,
)

DATABASE_URL = os.getenv("DATABASE_URL")
_SYNC_DSN = (
    make_url(DATABASE_URL).set(drivername="postgresql").render_as_string(
        hide_password=False
    )
    if DATABASE_URL
    else ""
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL is required for the voice WebSocket",
)


def _sync_db():
    """Open a loop-independent connection so assertions never touch the app pool."""
    return connect(_SYNC_DSN, autocommit=True)


def _install_session_module(module: FakeSessionModule) -> FakeSessionModule:
    """Replace the composed module for the duration of the TestClient lifespan."""
    app.state.session_module = module
    return module


def _closed_code(message: dict) -> int:
    """Read the close code from a Starlette TestClient close/disconnect frame."""
    assert message["type"] in {"websocket.close", "websocket.disconnect"}
    return message.get("code") or 4009


def _session_row(client_id: str):
    with _sync_db() as db:
        return db.execute(
            "SELECT id FROM training_sessions WHERE client_id = %s", (client_id,)
        ).fetchone()


def _delete_client_sessions(client_id: str) -> None:
    with _sync_db() as db:
        db.execute("DELETE FROM training_sessions WHERE client_id = %s", (client_id,))


def _create_organization() -> str:
    org_id = str(uuid.uuid4())
    with _sync_db() as db:
        db.execute(
            "INSERT INTO organizations (id, name, slug) VALUES (%s, %s, %s)",
            (org_id, "Voice routing test", f"voice-{org_id}"),
        )
    return org_id


def _delete_organization(org_id: str) -> None:
    with _sync_db() as db:
        db.execute("DELETE FROM organizations WHERE id = %s", (org_id,))


def _session_events(session_id: int) -> list[tuple]:
    with _sync_db() as db:
        return db.execute(
            "SELECT event_type, user_id, org_id, event_payload "
            "FROM training_session_events WHERE session_id = %s ORDER BY created_at, id",
            (session_id,),
        ).fetchall()


# ── Fallback: no persisted Session means the pipeline answers ──────────


def test_pipeline_fallback_is_used_when_no_session_can_be_persisted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a database-backed session the pipeline must serve the exchange.

    The Session module is replaced by a recorder so the test can prove the
    fallback path never reaches it.
    """
    no_database(monkeypatch)
    session_module = _install_session_module(FakeSessionModule())
    fake_ws_user(monkeypatch)
    fake_audio_services(monkeypatch)

    with client.websocket_connect("/ws/voice") as websocket:
        client_id = websocket.receive_json()["client_id"]
        websocket.send_bytes(b"RIFF-not-real-audio")
        websocket.send_json({"type": "audio_end"})
        payloads, audio_frames = collect_frames(websocket)

    assert "response_complete" in [payload["type"] for payload in payloads]
    assert audio_frames == 1
    assert session_module.sent == []
    assert _session_row(client_id) is None


def test_session_module_failure_is_not_converted_into_a_pipeline_answer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing Session must surface as a generic error, never as an answer.

    Silently falling back here would hand a student an unreviewed AI response
    while the system believed the exchange had been recorded, and echoing the
    raw exception would disclose provider, graph or database detail.
    """
    session_module = _install_session_module(
        FakeSessionModule(
            send_error=RuntimeError(
                "postgresql+asyncpg://horus:hunter2@db/horus_db: relation missing"
            )
        )
    )
    fake_ws_user(monkeypatch)
    fake_audio_services(monkeypatch)

    client_id = None
    try:
        with client.websocket_connect("/ws/voice") as websocket:
            client_id = websocket.receive_json()["client_id"]
            websocket.send_bytes(b"RIFF-not-real-audio")
            websocket.send_json({"type": "audio_end"})
            payloads, audio_frames = collect_frames(websocket)

        error = payloads[-1]
        assert error["type"] == "error"
        assert error["code"] == "SESSION_ERROR"
        assert error["message"] == "Training session unavailable. Please try again."
        assert "response_complete" not in [payload["type"] for payload in payloads]
        assert audio_frames == 0
        assert len(session_module.sent) == 1

        for secret in ("hunter2", "postgresql", "relation missing", "RuntimeError"):
            assert secret not in json.dumps(payloads)
    finally:
        if client_id:
            _delete_client_sessions(client_id)


def test_successful_voice_session_records_its_created_audit_event(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A voice-created session must persist with the audit event that explains it.

    The payload must match the HTTP create path so both routes produce the same
    audit record, and the event's tenant must match the row's.
    """
    org_id = _create_organization()
    _install_session_module(FakeSessionModule())
    fake_ws_user(monkeypatch, organization_id=org_id)
    fake_audio_services(monkeypatch)

    client_id = None
    try:
        with client.websocket_connect("/ws/voice") as websocket:
            client_id = websocket.receive_json()["client_id"]
            websocket.send_bytes(b"RIFF-not-real-audio")
            websocket.send_json({"type": "audio_end"})
            payloads, audio_frames = collect_frames(websocket)

        assert "response_complete" in [payload["type"] for payload in payloads]

        with _sync_db() as db:
            row = db.execute(
                "SELECT id, org_id, user_id, scenario_id, language, status, scene_version "
                "FROM training_sessions WHERE client_id = %s",
                (client_id,),
            ).fetchone()
        assert row is not None
        session_id, row_org_id, row_user_id, scenario_id, language, status, scene_version = row
        assert str(row_org_id) == org_id

        created = [event for event in _session_events(session_id) if event[0] == "created"]
        assert len(created) == 1
        _, event_user_id, event_org_id, payload = created[0]
        assert str(event_org_id) == org_id == str(row_org_id)
        assert event_user_id == row_user_id
        assert payload == {
            "scenario_id": scenario_id,
            "language": language,
            "status": status,
            "scene_version": scene_version,
        }
    finally:
        if client_id:
            _delete_client_sessions(client_id)
        _delete_organization(org_id)


def test_failed_session_start_leaves_no_orphan_session_row(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A row that could not be started must be removed, not left behind."""
    session_module = _install_session_module(
        FakeSessionModule(start_error=RuntimeError("validation graph unavailable"))
    )
    fake_ws_user(monkeypatch)
    fake_audio_services(monkeypatch)

    with client.websocket_connect("/ws/voice") as websocket:
        client_id = websocket.receive_json()["client_id"]
        websocket.send_bytes(b"RIFF-not-real-audio")
        websocket.send_json({"type": "audio_end"})
        payloads, audio_frames = collect_frames(websocket)

    assert _session_row(client_id) is None
    assert session_module.started != []
    # With no session the pipeline still answers; nothing was silently swallowed.
    assert "response_complete" in [payload["type"] for payload in payloads]
    assert audio_frames == 1


def test_pending_instructor_reports_a_hold_instead_of_a_generation_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A held exchange must not be reported as 'LLM did not generate a response'."""
    _install_session_module(FakeSessionModule(pending_instructor=True))
    fake_ws_user(monkeypatch)
    fake_audio_services(monkeypatch)

    client_id = None
    try:
        with client.websocket_connect("/ws/voice") as websocket:
            client_id = websocket.receive_json()["client_id"]
            websocket.send_bytes(b"RIFF-not-real-audio")
            websocket.send_json({"type": "audio_end"})
            payloads, audio_frames = collect_frames(websocket)

        assert payloads[-1]["type"] == "awaiting_instructor"
        assert "instructor review" in payloads[-1]["message"]
        assert audio_frames == 0
    finally:
        if client_id:
            _delete_client_sessions(client_id)


# ── Preserved WebSocket behaviour ─────────────────────────────────────


def test_unauthenticated_connection_is_rejected(client: TestClient) -> None:
    """No token means the socket is closed before any frame is sent."""
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws/voice") as websocket:
            websocket.receive_json()
    assert excinfo.value.code == 4001


def test_user_without_an_active_seat_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A student with no active seat gets NO_ACTIVE_SEAT and close code 4003."""
    fake_ws_user(monkeypatch, roles=["student"], organization_id=None)
    fake_audio_services(monkeypatch)

    async def _sync_user(_db: object, _token_user: object) -> object:
        return SimpleNamespace(id="local-user")

    async def _no_seats(*_args: object) -> list[object]:
        return []

    monkeypatch.setattr(voice_module, "sync_user_from_token", _sync_user)
    monkeypatch.setattr(
        voice_module, "_seat_repo", SimpleNamespace(get_user_seats=_no_seats)
    )

    with client.websocket_connect("/ws/voice") as websocket:
        payload = websocket.receive_json()
        assert payload["type"] == "error"
        assert payload["code"] == "NO_ACTIVE_SEAT"
        closed = websocket.receive()
    assert _closed_code(closed) == 4003


def test_oversized_audio_chunk_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A single chunk above the limit closes the socket with 4009."""
    no_database(monkeypatch)
    fake_ws_user(monkeypatch)
    fake_audio_services(monkeypatch)

    with client.websocket_connect("/ws/voice") as websocket:
        websocket.receive_json()
        websocket.send_bytes(b"\x00" * (voice_module.MAX_AUDIO_CHUNK_BYTES + 1))
        payload = websocket.receive_json()
        assert payload["code"] == "AUDIO_CHUNK_TOO_LARGE"
        closed = websocket.receive()
    assert _closed_code(closed) == 4009


def test_oversized_audio_payload_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Individually legal chunks above the total limit close the socket with 4009."""
    no_database(monkeypatch)
    monkeypatch.setattr(voice_module, "MAX_AUDIO_CHUNK_BYTES", 16)
    monkeypatch.setattr(voice_module, "MAX_AUDIO_MESSAGE_BYTES", 40)
    fake_ws_user(monkeypatch)
    fake_audio_services(monkeypatch)

    with client.websocket_connect("/ws/voice") as websocket:
        websocket.receive_json()
        for _ in range(3):
            websocket.send_bytes(b"\x00" * 16)
        payload = websocket.receive_json()
        assert payload["code"] == "AUDIO_PAYLOAD_TOO_LARGE"
        closed = websocket.receive()
    assert _closed_code(closed) == 4009


def test_control_messages_are_handled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ping, language_change, reset and unknown types all answer with their own frame."""
    no_database(monkeypatch)
    fake_ws_user(monkeypatch)
    fake_audio_services(monkeypatch)

    with client.websocket_connect("/ws/voice") as websocket:
        websocket.receive_json()

        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}

        websocket.send_json({"type": "language_change", "language": "es"})
        payload = websocket.receive_json()
        assert payload["type"] == "language_changed"
        assert payload["language"] == "es"

        websocket.send_json({"type": "reset"})
        assert websocket.receive_json()["type"] == "reset_complete"

        websocket.send_json({"type": "nonsense"})
        assert websocket.receive_json()["code"] == "UNSUPPORTED_MESSAGE_TYPE"
