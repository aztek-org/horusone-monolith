"""Shared test fixtures for Horus ATC API."""
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


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
            "provider": "ollama",
            "base_url": "http://ollama:11434",
            "model": "test-model",
        },
        audio={"enable_radio_effects": False},
        whisper_model="base",
        cors_origins="http://localhost:3000",
    )


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    """Provide a test HTTP client with settings overridden."""
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
