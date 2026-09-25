"""Tests for fail-fast environment settings resolution."""
from pathlib import Path

import pytest

from app.config import get_settings, reset_settings_cache
from app.settings_loader import MissingSettingError, load_settings


def write_env(tmp_path: Path, values: dict[str, str]) -> Path:
    """Write environment values to the loader's env file path."""
    env_file = tmp_path / ".env"
    env_file.write_text("\n".join(f"{key}={value}" for key, value in values.items()))
    return env_file


def test_production_requires_explicit_database_url(tmp_path: Path) -> None:
    with pytest.raises(MissingSettingError, match="DATABASE_URL"):
        load_settings(env_file=write_env(tmp_path, {"ENVIRONMENT": "production"}))


def test_production_rejects_external_fallback_true(tmp_path: Path) -> None:
    env = {
        "ENVIRONMENT": "production",
        "DATABASE_URL": "postgresql+asyncpg://x/y",
        "REDIS_URL": "redis://x",
        "CORS_ORIGINS": "https://app.example",
        "KEYCLOAK_ISSUER_URL": "https://auth.example/realms/horus",
        "LLM_PROVIDER": "ollama",
        "LLM_BASE_URL": "http://ollama:11434",
        "LLM_MODEL": "llama3.2:3b",
        "LLM_EMBEDDING_MODEL": "nomic-embed-text",
        "LLM_ALLOW_EXTERNAL_FALLBACK": "true",
        "LLM_FALLBACK_PROVIDER": "groq",
    }
    with pytest.raises(MissingSettingError, match="external fallback"):
        load_settings(env_file=write_env(tmp_path, env))


def test_production_reports_all_missing_keys(tmp_path: Path) -> None:
    with pytest.raises(MissingSettingError) as exc_info:
        load_settings(env_file=write_env(tmp_path, {"ENVIRONMENT": "production"}))

    message = str(exc_info.value)
    assert "DATABASE_URL" in message
    assert "REDIS_URL" in message
    assert "CORS_ORIGINS" in message
    assert "KEYCLOAK_ISSUER_URL" in message
    assert "LLM_PROVIDER" in message
    assert "LLM_BASE_URL" in message
    assert "LLM_MODEL" in message
    assert "LLM_EMBEDDING_MODEL" in message


def test_load_settings_installs_canonical_cached_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "testing")
    env_file = write_env(
        tmp_path,
        {
            "LLM_PROVIDER": "ollama",
            "LLM_BASE_URL": "https://llm.example/v1",
            "LLM_MODEL": "loaded-model",
        },
    )
    reset_settings_cache()

    try:
        loaded = load_settings(env_file)
        cached = get_settings()
        assert cached is loaded
        assert cached.llm.model == "loaded-model"
    finally:
        reset_settings_cache()
