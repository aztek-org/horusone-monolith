"""Shared test fixtures for Horus ATC API."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db.session import reset_engine
from app.main import app
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

    def __init__(self, debrief: Debrief | None = None) -> None:
        self.started: list[object] = []
        self.ended: list[object] = []
        self.sent: list[object] = []
        self.debrief = debrief or Debrief(scoring={}, badges_earned=[], report="")

    async def start(self, command: object) -> SimpleNamespace:
        self.started.append(command)
        return SimpleNamespace(session_id=0, phase="ingestion", exchange_count=0, state={})

    async def end(self, command: object) -> Debrief:
        self.ended.append(command)
        return self.debrief

    async def send(self, command: object) -> SimpleNamespace:
        self.sent.append(command)
        return SimpleNamespace(
            atc_response="",
            is_emergency=False,
            exchange_count=len(self.sent),
            pending_instructor=False,
            citations=[],
        )


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    """Provide a test HTTP client with settings overridden."""
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
