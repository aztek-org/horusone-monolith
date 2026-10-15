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
            else:
                # A constructed group (e.g. ``LLMSettings(...)``) has no branch
                # that can merge into it, so the legacy value would be dropped
                # here and the caller would silently receive the dataclass
                # defaults.  Refuse instead: a loud failure at construction is
                # cheaper than a deployment quietly talking to the wrong
                # endpoint.  Passing the group as a dict is the accepted shape.
                legacy_names = sorted(
                    name
                    for name, (group, _field) in _LEGACY_GROUP_FIELDS.items()
                    if group == group_name and name in data
                )
                raise ValueError(
                    f"Settings({group_name}=<{type(existing).__name__}>, "
                    f"{', '.join(legacy_names)}=...) cannot be combined: the "
                    f"{group_name!r} group is already a {type(existing).__name__}, "
                    f"which cannot take the legacy {', '.join(legacy_names)} "
                    f"value. Pass the group as a dict "
                    f"(Settings({group_name}={{...}})), or drop the legacy keyword "
                    f"and set the field on the {type(existing).__name__}."
                )

        super().__init__(**normalized)

    # -- Flat compatibility aliases ----------------------------------
    # The grouped fields above are the source of truth.  These properties keep
    # the pre-grouping attribute names working for out-of-tree callers, so each
    # one names its remaining in-repo readers: an alias with no reader is a
    # candidate for removal, not one with a reader that a reader cannot find.
    #
    # These properties are read-only.  The *inbound* direction is a separate
    # surface with its own precedence: ``_LEGACY_GROUP_FIELDS`` below lets a
    # pre-grouping keyword (``ollama_base_url=...``) stand in for a grouped one,
    # and the settings loader does the same for the matching environment names.
    # Both merge the legacy value *over* the grouped one, so when both are given
    # the legacy name wins.  That is deliberate -- an operator upgrading with
    # ``OLLAMA_BASE_URL`` still set keeps the value they had rather than
    # inheriting a new default -- and it is documented in
    # ``docs/development.md`` ("Environment Variable Reference").

    @property
    def ollama_base_url(self) -> str:
        """Flat alias for ``llm.base_url``, retained for backward compatibility.

        Nothing in ``backend/app/`` reads this any more.  The last in-repo
        reader was ``app/api/v1/flight_plans.py``, which passed it to
        ``FlightPlanParser``; the parser ignores it and now takes no such
        argument, so the reader is gone.  ``OLLAMA_BASE_URL`` is still accepted
        as an environment/keyword alias by ``Settings`` and the settings loader
        — that is a separate compatibility surface and is unaffected, though it
        does **override** ``LLM_BASE_URL`` when both are set.  Read the
        grouped field instead: ``settings.llm.base_url``.
        """
        return self.llm.base_url

    @property
    def ollama_llm_model(self) -> str:
        """Flat alias for ``llm.model``, retained for backward compatibility.

        Nothing in ``backend/app/`` reads this any more.  The last in-repo
        reader was ``app/api/v1/flight_plans.py``, which passed it to
        ``FlightPlanParser``; the parser ignores it and now takes no such
        argument, so the reader is gone.  ``OLLAMA_LLM_MODEL`` is still accepted
        as an environment/keyword alias by ``Settings`` and the settings loader
        — that is a separate compatibility surface and is unaffected.  Read the
        grouped field instead: ``settings.llm.model``.
        """
        return self.llm.model

    @property
    def ollama_embedding_model(self) -> str:
        """Flat alias for ``llm.embedding_model``; no application reader left.

        Read ``settings.llm.embedding_model``.
        """
        return self.llm.embedding_model

    @property
    def sample_rate(self) -> int:
        """Flat alias for ``audio.sample_rate``; no application reader left.

        Read ``settings.audio.sample_rate``.
        """
        return self.audio.sample_rate

    @property
    def chunk_size(self) -> int:
        """Flat alias for ``audio.chunk_size``; no application reader left.

        Read ``settings.audio.chunk_size``.  Note the name collision: this is
        the **audio** chunk size, while the knowledge chunk window is
        ``settings.knowledge.chunk_size`` — which is what ``KnowledgeIngestor``
        reads, since it is handed a ``KnowledgeSettings`` (ADR-008).  Reach for
        the wrong one and the wrong 1000 lands in ``ingest_events.chunk_size``.
        """
        return self.audio.chunk_size

    @property
    def audio_format(self) -> str:
        """Flat alias for ``audio.audio_format``; no application reader left.

        Read ``settings.audio.audio_format``.
        """
        return self.audio.audio_format

    @property
    def enable_radio_effects(self) -> bool:
        """Flat alias for ``audio.enable_radio_effects``.

        Read by ``app/services/audio_effects/filters.py``.  Read the grouped
        field instead: ``settings.audio.enable_radio_effects``.
        """
        return self.audio.enable_radio_effects

    @property
    def noise_level(self) -> float:
        """Flat alias for ``audio.noise_level``.

        Read by ``app/services/audio_effects/filters.py``.  Read the grouped
        field instead: ``settings.audio.noise_level``.
        """
        return self.audio.noise_level

    @property
    def static_level(self) -> float:
        """Flat alias for ``audio.static_level``.

        Read by ``app/services/audio_effects/filters.py``.  Read the grouped
        field instead: ``settings.audio.static_level``.
        """
        return self.audio.static_level

    @property
    def log_level(self) -> str:
        """Flat alias for ``trace.log_level``.

        Read by ``app/main.py`` when configuring logging.  Read the grouped field
        instead: ``settings.trace.log_level``.
        """
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
        issuers = {self.keycloak_issuer_url.rstrip("/")} if self.keycloak_issuer_url else set()
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
            raise MissingSettingError(f"Missing production settings: {', '.join(missing)}")
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
