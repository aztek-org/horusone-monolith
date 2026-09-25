"""Tests for configuration management."""
import pytest

from app.config import Settings, get_settings, reset_settings_cache
from app.settings_loader import MissingSettingError


def test_grouped_llm_settings() -> None:
    settings = Settings(
        environment="testing",
        llm={
            "provider": "ollama",
            "base_url": "http://ollama:11434",
            "model": "llama3.2:3b",
            "embedding_model": "nomic-embed-text",
            "temperature": 0.3,
            "max_output_tokens": 150,
        },
    )
    assert settings.llm.provider == "ollama"
    assert settings.llm.temperature == 0.3
    assert settings.knowledge.embedding_dimensions == 768


def test_all_url_defaults_are_empty() -> None:
    settings = Settings(_env_file=None, environment="testing")

    assert settings.llm.base_url == ""
    assert settings.database_url == ""
    assert settings.redis_url == ""
    assert settings.keycloak_issuer_url == ""
    assert settings.keycloak_jwks_url == ""
    assert settings.keycloak_admin_url == ""
    assert settings.trace.otel_endpoint is None
    assert settings.cors_origins == ""


def test_production_requires_explicit_values() -> None:
    with pytest.raises(MissingSettingError) as exc_info:
        Settings(_env_file=None, environment="production")

    message = str(exc_info.value)
    for key in (
        "DATABASE_URL",
        "REDIS_URL",
        "CORS_ORIGINS",
        "KEYCLOAK_ISSUER_URL",
        "LLM_PROVIDER",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LLM_EMBEDDING_MODEL",
    ):
        assert key in message


def test_settings_defaults() -> None:
    """Test that default settings are correctly set when no env overrides exist."""
    settings = Settings()
    assert settings.environment in ("development", "testing")
    assert settings.port == 8000
    assert settings.whisper_model == "base"
    assert settings.enable_radio_effects is True


def test_knowledge_chunking_defaults_are_stable() -> None:
    """Keep shipped knowledge chunking aligned with the ingest contract."""
    settings = Settings(_env_file=None, environment="testing")

    assert settings.knowledge.chunk_size == 1000
    assert settings.knowledge.chunk_overlap == 150


def test_cors_origins_list_multiple() -> None:
    """Test CORS origins are correctly parsed from a comma-separated string."""
    settings = Settings(cors_origins="http://localhost:3000,https://example.com")
    origins = settings.cors_origins_list
    assert len(origins) == 2
    assert "http://localhost:3000" in origins
    assert "https://example.com" in origins


def test_cors_origins_list_single() -> None:
    """Test CORS origins with a single entry produces a one-element list."""
    settings = Settings(cors_origins="http://localhost:3000")
    assert settings.cors_origins_list == ["http://localhost:3000"]


def test_cors_origins_list_trims_whitespace() -> None:
    """Test that whitespace around each origin is stripped."""
    settings = Settings(cors_origins=" http://localhost:3000 , https://example.com ")
    origins = settings.cors_origins_list
    assert origins == ["http://localhost:3000", "https://example.com"]


def test_cors_origins_wildcard_blocked_in_production() -> None:
    """Test wildcard CORS is blocked in production."""
    settings = Settings(
        environment="production",
        database_url="postgresql+asyncpg://x/y",
        redis_url="redis://x",
        cors_origins="*",
        keycloak_issuer_url="https://auth.example/realms/horus",
        llm={
            "provider": "ollama",
            "base_url": "http://llm:11434",
            "model": "llama3.2:3b",
            "embedding_model": "nomic-embed-text",
        },
    )
    with pytest.raises(ValueError, match="Wildcard CORS origin"):
        _ = settings.cors_origins_list


def test_settings_custom_values() -> None:
    """Test that custom values can be passed and override defaults."""
    settings = Settings(
        environment="testing",
        port=9000,
        ollama_llm_model="llama3:8b",
        enable_radio_effects=False,
        noise_level=0.05,
    )
    assert settings.environment == "testing"
    assert settings.port == 9000
    assert settings.ollama_llm_model == "llama3:8b"
    assert settings.enable_radio_effects is False
    assert settings.noise_level == pytest.approx(0.05)


def test_llm_host_values_require_configuration() -> None:
    """LLM host and model values must be explicitly configured."""
    settings = Settings(_env_file=None, environment="testing")
    assert settings.ollama_base_url == ""
    assert settings.ollama_llm_model == ""


def test_audio_processing_defaults() -> None:
    """Test audio processing settings have sensible defaults."""
    settings = Settings()
    assert settings.sample_rate == 16000
    assert settings.chunk_size == 1024
    assert settings.audio_format == "wav"


def test_issuer_aliases_are_accepted_only_outside_production() -> None:
    common = {
        "keycloak_issuer_url": "https://auth.example/realms/horus",
        "keycloak_issuer_aliases": "https://alias.example/realms/horus",
    }

    development = Settings(environment="development", **common)
    production = Settings(
        environment="production",
        database_url="postgresql+asyncpg://x/y",
        redis_url="redis://x",
        cors_origins="https://app.example",
        llm={
            "provider": "ollama",
            "base_url": "http://llm:11434",
            "model": "llama3.2:3b",
            "embedding_model": "nomic-embed-text",
        },
        **common,
    )

    assert "https://alias.example/realms/horus" in development.accepted_keycloak_issuers
    assert production.accepted_keycloak_issuers == {
        "https://auth.example/realms/horus"
    }


def test_get_settings_reads_grouped_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_EMBEDDING_MODEL", "test-embedding-model")
    monkeypatch.setenv("KNOWLEDGE_TOP_K", "9")
    reset_settings_cache()

    try:
        settings = get_settings()
        assert settings.llm.provider == "ollama"
        assert settings.llm.base_url == "https://llm.example/v1"
        assert settings.llm.model == "test-model"
        assert settings.llm.embedding_model == "test-embedding-model"
        assert settings.knowledge.top_k == 9
    finally:
        reset_settings_cache()
