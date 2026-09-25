"""Fail-fast environment resolution for non-Docker deployments."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import ValidationError

from app.config import Settings


class MissingSettingError(RuntimeError):
    """Raised when production settings are incomplete or unsafe."""


REQUIRED_IN_PRODUCTION = (
    "DATABASE_URL",
    "REDIS_URL",
    "CORS_ORIGINS",
    "KEYCLOAK_ISSUER_URL",
    "LLM_PROVIDER",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_EMBEDDING_MODEL",
)

_TOP_LEVEL_ENV = {
    "ENVIRONMENT": "environment",
    "HOST": "host",
    "PORT": "port",
    "DATABASE_URL": "database_url",
    "REDIS_URL": "redis_url",
    "CORS_ORIGINS": "cors_origins",
    "AUTH_ENABLED": "auth_enabled",
    "KEYCLOAK_ISSUER_URL": "keycloak_issuer_url",
    "KEYCLOAK_ISSUER_ALIASES": "keycloak_issuer_aliases",
    "KEYCLOAK_JWKS_URL": "keycloak_jwks_url",
    "KEYCLOAK_CLIENT_ID": "keycloak_client_id",
    "KEYCLOAK_ADMIN_URL": "keycloak_admin_url",
    "WHISPER_MODEL": "whisper_model",
    "WHISPER_LANGUAGE": "whisper_language",
    "TTS_LANGUAGE": "tts_language",
}

_GROUP_ENV = {
    "llm": {
        "LLM_PROVIDER": "provider",
        "LLM_FALLBACK_PROVIDER": "fallback_provider",
        "LLM_BASE_URL": "base_url",
        "LLM_MODEL": "model",
        "LLM_EMBEDDING_MODEL": "embedding_model",
        "LLM_API_KEY": "api_key",
        "LLM_FALLBACK_API_KEY": "api_key",
        "GROQ_API_KEY": "api_key",
        "LLM_TEMPERATURE": "temperature",
        "LLM_MAX_OUTPUT_TOKENS": "max_output_tokens",
        "LLM_TIMEOUT_SECONDS": "timeout_seconds",
        "LLM_ALLOW_EXTERNAL_FALLBACK": "allow_external_fallback",
    },
    "knowledge": {
        "KNOWLEDGE_CHUNK_SIZE": "chunk_size",
        "KNOWLEDGE_CHUNK_OVERLAP": "chunk_overlap",
        "KNOWLEDGE_EMBEDDING_DIMENSIONS": "embedding_dimensions",
        "KNOWLEDGE_TOP_K": "top_k",
        "KNOWLEDGE_DEFAULT_CHUNK_QUOTA": "default_chunk_quota",
    },
    "trace": {
        "TRACE_RETENTION_DAYS": "retention_days",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "otel_endpoint",
        "TRACE_LOG_LEVEL": "log_level",
        "LOG_LEVEL": "log_level",
    },
    "audio": {
        "SAMPLE_RATE": "sample_rate",
        "CHUNK_SIZE": "chunk_size",
        "AUDIO_FORMAT": "audio_format",
        "ENABLE_RADIO_EFFECTS": "enable_radio_effects",
        "NOISE_LEVEL": "noise_level",
        "STATIC_LEVEL": "static_level",
    },
}

_LEGACY_ENV = {
    "OLLAMA_BASE_URL": ("llm", "base_url"),
    "OLLAMA_LLM_MODEL": ("llm", "model"),
    "OLLAMA_EMBEDDING_MODEL": ("llm", "embedding_model"),
}


def _read_env_file(path: Path) -> dict[str, str]:
    """Read simple KEY=value entries from an environment file."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _settings_input(values: dict[str, str]) -> dict[str, object]:
    """Translate environment names into the grouped Settings constructor shape."""
    data: dict[str, object] = {}
    groups: dict[str, dict[str, object]] = {name: {} for name in _GROUP_ENV}

    for env_name, setting_name in _TOP_LEVEL_ENV.items():
        if env_name in values:
            data[setting_name] = values[env_name]

    for group_name, fields in _GROUP_ENV.items():
        for env_name, setting_name in fields.items():
            if env_name in values:
                groups[group_name][setting_name] = values[env_name]

    for env_name, (group_name, setting_name) in _LEGACY_ENV.items():
        if env_name in values:
            groups[group_name][setting_name] = values[env_name]

    for group_name, group_values in groups.items():
        if group_values:
            data[group_name] = group_values
    return data


def load_settings(env_file: str | Path) -> Settings:
    """Build Settings from env_file plus OS env; fail fast in production."""
    values = _read_env_file(Path(env_file))
    values.update({key: value for key, value in os.environ.items() if value})

    if values.get("ENVIRONMENT") == "production":
        missing = [key for key in REQUIRED_IN_PRODUCTION if not values.get(key)]
        if missing:
            raise MissingSettingError(
                f"Missing production settings: {', '.join(missing)}"
            )

    try:
        return Settings(**_settings_input(values))
    except ValidationError as exc:
        if values.get("ENVIRONMENT") == "production":
            raise MissingSettingError(str(exc)) from exc
        raise
