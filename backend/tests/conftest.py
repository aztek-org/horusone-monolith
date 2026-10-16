"""Shared test fixtures for Horus ATC API."""
import io
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.routes import voice as voice_module
from app.config import Settings, get_settings
from app.db.session import reset_engine
from app.main import app
from app.middleware.auth import TokenUser
from app.services.training_sessions.types import Debrief

_SETTINGS_ENV_VARS = (
    "ENVIRONMENT",
    "ENV_FILE",
    "DATABASE_URL",
    "REDIS_URL",
    "CORS_ORIGINS",
    "KEYCLOAK_ISSUER_URL",
    "KEYCLOAK_JWKS_URL",
    "KEYCLOAK_CLIENT_ID",
    "KEYCLOAK_ISSUER_ALIASES",
    "KEYCLOAK_ADMIN_URL",
    "AUTH_ENABLED",
    "HOST",
    "PORT",
    "LOG_LEVEL",
    "WHISPER_MODEL",
    "WHISPER_LANGUAGE",
    "TTS_LANGUAGE",
    "SAMPLE_RATE",
    "CHUNK_SIZE",
    "AUDIO_FORMAT",
    "ENABLE_RADIO_EFFECTS",
    "NOISE_LEVEL",
    "STATIC_LEVEL",
    "LLM_PROVIDER",
    "LLM_FALLBACK_PROVIDER",
    "LLM_API_KEY",
    "LLM_FALLBACK_API_KEY",
    "GROQ_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_EMBEDDING_MODEL",
    "LLM_TEMPERATURE",
    "LLM_MAX_OUTPUT_TOKENS",
    "LLM_TIMEOUT_SECONDS",
    "LLM_ALLOW_EXTERNAL_FALLBACK",
    "KNOWLEDGE_CHUNK_SIZE",
    "KNOWLEDGE_CHUNK_OVERLAP",
    "KNOWLEDGE_EMBEDDING_DIMENSIONS",
    "KNOWLEDGE_TOP_K",
    "KNOWLEDGE_DEFAULT_CHUNK_QUOTA",
    "TRACE_RETENTION_DAYS",
    "TRACE_LOG_LEVEL",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OLLAMA_BASE_URL",
    "OLLAMA_LLM_MODEL",
    "OLLAMA_EMBEDDING_MODEL",
    "SCENES_PATH",
)


@pytest.fixture(autouse=True)
def isolate_database_engine():
    """Give every test its own SQLAlchemy engine.

    The process-global engine caches asyncpg connections, which are bound to the
    event loop that opened them. Each ``TestClient`` runs a fresh loop, so a
    cached pool would be unusable in the next test.
    """
    reset_engine()
    yield
    reset_engine()


@pytest.fixture(autouse=True)
def isolate_settings_environment(request, monkeypatch):
    """Keep settings unit tests independent of the caller's shell environment."""
    if request.path.name not in {"test_config.py", "test_settings_loader.py"}:
        return

    for name in _SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def test_settings() -> Settings:
    """Override settings for testing."""
    return Settings(
        environment="testing",
        llm={
            "provider": "fake",
            "base_url": "http://unused",
            "model": "fake",
            "embedding_model": "nomic-embed-text",
            "temperature": 0.3,
            "max_output_tokens": 150,
        },
        audio={"enable_radio_effects": False},
        whisper_model="base",
        cors_origins="http://localhost:3000",
    )


class FakeSessionModule:
    """Recording stand-in for the composed training Session module."""

    def __init__(
        self,
        debrief: Debrief | None = None,
        *,
        start_error: Exception | None = None,
        send_error: Exception | None = None,
        end_error: Exception | None = None,
        atc_response: str = "N123AB, taxi via alpha.",
        pending_instructor: bool = False,
    ) -> None:
        self.started: list[object] = []
        self.ended: list[object] = []
        self.sent: list[object] = []
        self.awaited: list[SimpleNamespace] = []
        self.debrief = debrief or Debrief(scoring={}, badges_earned=[], report="")
        self.start_error = start_error
        self.send_error = send_error
        self.end_error = end_error
        self.atc_response = atc_response
        self.pending_instructor = pending_instructor

    async def start(self, command: object) -> SimpleNamespace:
        self.started.append(command)
        if self.start_error is not None:
            raise self.start_error
        return SimpleNamespace(session_id=0, phase="ingestion", exchange_count=0, state={})

    async def end(self, command: object) -> Debrief:
        self.ended.append(command)
        if self.end_error is not None:
            raise self.end_error
        return self.debrief

    async def send(self, command: object) -> SimpleNamespace:
        self.sent.append(command)
        if self.send_error is not None:
            raise self.send_error
        return SimpleNamespace(
            atc_response="" if self.pending_instructor else self.atc_response,
            is_emergency=False,
            exchange_count=len(self.sent),
            pending_instructor=self.pending_instructor,
            citations=[],
        )

    async def await_instructor(
        self,
        org_id: object,
        session_id: int,
        instructor_response: str | None = None,
    ) -> SimpleNamespace | None:
        self.awaited.append(
            SimpleNamespace(
                org_id=org_id,
                session_id=session_id,
                instructor_response=instructor_response,
            )
        )
        if not self.pending_instructor:
            return None
        return SimpleNamespace(
            atc_response=(
                instructor_response if instructor_response is not None else self.atc_response
            ),
            is_emergency=False,
            exchange_count=len(self.sent),
            pending_instructor=False,
            citations=[],
        )


def no_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every database access fail, so the voice route takes its fallback path."""
    def _unavailable() -> None:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(voice_module, "get_session_factory", _unavailable)


def fake_audio_services(
    monkeypatch: pytest.MonkeyPatch,
    transcript: str = "N123AB tower, taxi via alpha",
) -> None:
    """Replace the STT and TTS boundaries with deterministic in-process fakes.

    Also stubs the Whisper model load so the 145 MB checkpoint is not read.
    """
    import numpy as np
    import soundfile as sf

    from app.services.stt import whisper_service
    from app.services.tts import tts_service

    async def _transcribe(_self: object, _audio: bytes, language: str | None = None):
        return transcript, "en"

    async def _synthesize(_self: object, _text: str, language: str | None = None) -> bytes:
        buffer = io.BytesIO()
        sf.write(buffer, np.zeros(800, dtype="float32"), 16000, format="WAV")
        return buffer.getvalue()

    monkeypatch.setattr(whisper_service.whisper, "load_model", lambda *_a, **_k: object())
    monkeypatch.setattr(whisper_service.WhisperSTTService, "transcribe", _transcribe)
    monkeypatch.setattr(tts_service.TTSService, "synthesize", _synthesize)


def fake_ws_user(
    monkeypatch: pytest.MonkeyPatch,
    *,
    roles: list[str] | None = None,
    organization_id: str | None = None,
) -> TokenUser:
    """Authenticate WebSocket connections with a fixed platform-admin token user."""
    token_user = TokenUser(
        keycloak_id="kc-voice",
        email="voice@test.com",
        display_name="Voice Pilot",
        roles=roles if roles is not None else ["platform-admin"],
        organization_id=organization_id,
    )

    async def _authenticated(_websocket: object) -> TokenUser:
        return token_user

    monkeypatch.setattr(voice_module, "get_current_user_ws", _authenticated)
    return token_user


def collect_frames(websocket, limit: int = 10) -> tuple[list[dict], int]:
    """Drain frames until a terminal payload arrives; return payloads and audio count."""
    payloads: list[dict] = []
    audio_frames = 0
    for _ in range(limit):
        message = websocket.receive()
        if message.get("type") == "websocket.disconnect":
            break
        if message.get("bytes"):
            audio_frames += 1
        if message.get("text"):
            payloads.append(json.loads(message["text"]))
            if payloads[-1].get("type") in {"response_complete", "error", "awaiting_instructor"}:
                break
    return payloads, audio_frames


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    """Provide a test HTTP client with settings overridden."""
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
