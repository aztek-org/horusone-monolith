"""Composition-root wiring and voice-path coverage for the training Session module."""

from __future__ import annotations

import io
import json
import os

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient
from psycopg import Connection, connect
from sqlalchemy.engine import make_url

from app.api.routes import voice as voice_module
from app.middleware.auth import TokenUser
from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from app.services.stt import whisper_service
from app.services.tts import tts_service

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


def test_composition_root_builds_session_module(client: TestClient) -> None:
    """The lifespan must build every collaborator once and publish it on app.state."""
    state = client.app.state

    assert state.session_module is not None
    assert state.llm.provider == "fake"
    assert state.scene_registry.get(DEFAULT_SCENE.version).version == DEFAULT_SCENE.version
    assert state.session_store is not None
    assert state.trace_recorder is not None
    assert state.retriever is None
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
    token_user = TokenUser(
        keycloak_id="kc-voice",
        email="voice@test.com",
        display_name="Voice Pilot",
        roles=["platform-admin"],
        organization_id=None,
    )

    async def _authenticated(_websocket: object) -> TokenUser:
        return token_user

    async def _transcribe(_self: object, _audio: bytes, language: str | None = None):
        return "N123AB tower, taxi via alpha", "en"

    async def _synthesize(_self: object, _text: str, language: str | None = None) -> bytes:
        buffer = io.BytesIO()
        sf.write(buffer, np.zeros(800, dtype="float32"), 16000, format="WAV")
        return buffer.getvalue()

    monkeypatch.setattr(voice_module, "get_current_user_ws", _authenticated)
    monkeypatch.setattr(whisper_service.whisper, "load_model", lambda *_a, **_k: object())
    monkeypatch.setattr(whisper_service.WhisperSTTService, "transcribe", _transcribe)
    monkeypatch.setattr(tts_service.TTSService, "synthesize", _synthesize)

    client_id = None
    payloads: list[dict] = []
    audio_frames = 0
    with client.websocket_connect("/ws/voice") as websocket:
        connected = websocket.receive_json()
        assert connected["type"] == "connected"
        client_id = connected["client_id"]

        websocket.send_bytes(b"RIFF-not-real-audio")
        websocket.send_json({"type": "audio_end"})

        for _ in range(10):
            message = websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("bytes"):
                audio_frames += 1
            if message.get("text"):
                payloads.append(json.loads(message["text"]))
                if payloads[-1].get("type") == "response_complete":
                    break

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
                "session_started",
                "exchange_completed",
            ]
        finally:
            db.execute("DELETE FROM training_sessions WHERE client_id = %s", (client_id,))
