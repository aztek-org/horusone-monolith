"""Configuration management for Horus ATC API."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class MissingSettingError(RuntimeError):
    """Raised when required or production-safe settings are missing."""


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

_DEVELOPMENT_ISSUER_ALIASES = {
    "http://localhost:8080/realms/horus",
    "http://localhost:8180/realms/horus",
    "http://auth.localhost/realms/horus",
    "http://keycloak:8080/realms/horus",
}


@dataclass(frozen=True)
class LLMSettings:
    """Configuration for the primary and optional fallback language model."""

    provider: str = ""
    fallback_provider: str | None = None
    base_url: str = ""
    model: str = ""
    embedding_model: str = ""
    api_key: str | None = None
    temperature: float = 0.3
    max_output_tokens: int = 150
    timeout_seconds: float = 120.0
    allow_external_fallback: bool = False


@dataclass(frozen=True)
class KnowledgeSettings:
    """Configuration for knowledge retrieval and chunking."""

    chunk_size: int = 1000
    chunk_overlap: int = 150
    embedding_dimensions: int = 768
    top_k: int = 5
    default_chunk_quota: int = 10


@dataclass(frozen=True)
class TraceSettings:
    """Configuration for tracing, retention, and trace log level."""

    retention_days: int = 90
    otel_endpoint: str | None = None
    log_level: str = "INFO"


@dataclass(frozen=True)
class AudioSettings:
    """Configuration for audio capture and radio effects."""

    sample_rate: int = 16000
    chunk_size: int = 1024
    audio_format: str = "wav"
    enable_radio_effects: bool = True
    noise_level: float = 0.02
    static_level: float = 0.01


_LEGACY_GROUP_FIELDS = {
    "ollama_base_url": ("llm", "base_url"),
    "ollama_llm_model": ("llm", "model"),
    "ollama_embedding_model": ("llm", "embedding_model"),
    "sample_rate": ("audio", "sample_rate"),
    "chunk_size": ("audio", "chunk_size"),
    "audio_format": ("audio", "audio_format"),
    "enable_radio_effects": ("audio", "enable_radio_effects"),
    "noise_level": ("audio", "noise_level"),
    "static_level": ("audio", "static_level"),
    "log_level": ("trace", "log_level"),
}


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "testing", "production"] = "development"
    host: str = ""
    port: int = 8000

    database_url: str = ""
    redis_url: str = ""

    cors_origins: str = ""
    auth_enabled: bool = True
    keycloak_issuer_url: str = ""
    keycloak_issuer_aliases: str = ""
    keycloak_jwks_url: str = ""
    keycloak_client_id: str = "horus-api"
    keycloak_admin_url: str = ""

    llm: LLMSettings = LLMSettings()
    knowledge: KnowledgeSettings = KnowledgeSettings()
    trace: TraceSettings = TraceSettings()
    audio: AudioSettings = AudioSettings()

    scenes_path: str = ""

    whisper_model: str = "base"
    whisper_language: str = "en"
    tts_language: str = "en"

    def __init__(self, **data: Any) -> None:
        """Accept legacy flat settings while groups remain the source of truth."""
        normalized = dict(data)
        grouped: dict[str, dict[str, Any]] = {}
        for legacy_name, (group_name, group_field) in _LEGACY_GROUP_FIELDS.items():
            if legacy_name not in normalized:
                continue
            value = normalized.pop(legacy_name)
            grouped.setdefault(group_name, {})[group_field] = value

        for group_name, group_values in grouped.items():
            existing = normalized.get(group_name)
            if existing is None:
                normalized[group_name] = group_values
            elif isinstance(existing, dict):
                normalized[group_name] = {**existing, **group_values}

        super().__init__(**normalized)

    @property
    def ollama_base_url(self) -> str:
        """Temporary compatibility alias; remove when Tasks 2, 5, and 7 migrate consumers."""
        return self.llm.base_url

    @property
    def ollama_llm_model(self) -> str:
        """Temporary compatibility alias; remove when Tasks 2, 5, and 7 migrate consumers."""
        return self.llm.model

    @property
    def ollama_embedding_model(self) -> str:
        """Temporary compatibility alias; remove when Tasks 2, 5, and 7 migrate consumers."""
        return self.llm.embedding_model

    @property
    def sample_rate(self) -> int:
        """Temporary compatibility alias; remove when Tasks 2, 5, and 7 migrate consumers."""
        return self.audio.sample_rate

    @property
    def chunk_size(self) -> int:
        """Temporary compatibility alias; remove when Tasks 2, 5, and 7 migrate consumers."""
        return self.audio.chunk_size

    @property
    def audio_format(self) -> str:
        """Temporary compatibility alias; remove when Tasks 2, 5, and 7 migrate consumers."""
        return self.audio.audio_format

    @property
    def enable_radio_effects(self) -> bool:
        """Temporary compatibility alias; remove when Tasks 2, 5, and 7 migrate consumers."""
        return self.audio.enable_radio_effects

    @property
    def noise_level(self) -> float:
        """Temporary compatibility alias; remove when Tasks 2, 5, and 7 migrate consumers."""
        return self.audio.noise_level

    @property
    def static_level(self) -> float:
        """Temporary compatibility alias; remove when Tasks 2, 5, and 7 migrate consumers."""
        return self.audio.static_level

    @property
    def log_level(self) -> str:
        """Temporary compatibility alias; remove when Tasks 2, 5, and 7 migrate consumers."""
        return self.trace.log_level

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into a list."""
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        if self.environment == "production" and "*" in origins:
            raise ValueError("Wildcard CORS origin is not allowed in production")
        return origins

    @property
    def resolved_jwks_url(self) -> str:
        """Get JWKS URL, deriving from issuer if not explicitly set."""
        if self.keycloak_jwks_url:
            return self.keycloak_jwks_url
        return f"{self.keycloak_issuer_url}/protocol/openid-connect/certs"

    @property
    def accepted_keycloak_issuers(self) -> set[str]:
        """Get accepted issuer URLs for JWT validation."""
        issuers = (
            {self.keycloak_issuer_url.rstrip("/")}
            if self.keycloak_issuer_url
            else set()
        )
        if self.environment in {"development", "testing"}:
            issuers.update(_DEVELOPMENT_ISSUER_ALIASES)
            issuers.update(
                alias.strip().rstrip("/")
                for alias in self.keycloak_issuer_aliases.split(",")
                if alias.strip()
            )
        return issuers

    def model_post_init(self, __context: Any) -> None:
        """Require complete, production-safe configuration."""
        if self.environment != "production":
            return

        configured_values = {
            "DATABASE_URL": self.database_url,
            "REDIS_URL": self.redis_url,
            "CORS_ORIGINS": self.cors_origins,
            "KEYCLOAK_ISSUER_URL": self.keycloak_issuer_url,
            "LLM_PROVIDER": self.llm.provider,
            "LLM_BASE_URL": self.llm.base_url,
            "LLM_MODEL": self.llm.model,
            "LLM_EMBEDDING_MODEL": self.llm.embedding_model,
        }
        missing = [key for key, value in configured_values.items() if not value]
        if missing:
            raise MissingSettingError(
                f"Missing production settings: {', '.join(missing)}"
            )
        if self.llm.allow_external_fallback:
            raise MissingSettingError(
                "external fallback is not allowed in production; "
                "set LLM_ALLOW_EXTERNAL_FALLBACK=false"
            )


_cached_settings: Settings | None = None


@lru_cache
def get_settings() -> Settings:
    """Return the canonical settings instance for the process."""
    if _cached_settings is not None:
        return _cached_settings

    from app.settings_loader import load_settings_from_environment

    return load_settings_from_environment()


def _install_settings(settings: Settings) -> None:
    """Install an explicitly loaded settings instance as canonical."""
    global _cached_settings
    _cached_settings = settings
    get_settings.cache_clear()


def reset_settings_cache() -> None:
    """Clear the process settings cache, primarily for isolated tests."""
    global _cached_settings
    _cached_settings = None
    get_settings.cache_clear()
