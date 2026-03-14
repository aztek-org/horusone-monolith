"""Configuration management for Horus ATC API."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Server
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000

    # Ollama Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3:latest"
    ollama_embedding_model: str = "nomic-embed-text"

    # Whisper Configuration
    whisper_model: str = "base"
    whisper_language: str = "en"  # en, es, or "auto" for auto-detection

    # TTS Configuration
    tts_language: str = "en"  # en or es

    # Audio Processing
    sample_rate: int = 16000
    chunk_size: int = 1024
    audio_format: str = "wav"

    # Radio Effects
    enable_radio_effects: bool = True
    noise_level: float = 0.02
    static_level: float = 0.01

    # CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Database
    database_url: str = "postgresql+asyncpg://horus:horus@localhost:5432/horus_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Keycloak / Authentication
    keycloak_issuer_url: str = "http://localhost:8080/realms/horus"
    keycloak_jwks_url: str = ""
    keycloak_client_id: str = "horus-api"
    keycloak_admin_url: str = "http://localhost:8080/admin/realms/horus"
    auth_enabled: bool = True

    # Logging
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def resolved_jwks_url(self) -> str:
        """Get JWKS URL, deriving from issuer if not explicitly set."""
        if self.keycloak_jwks_url:
            return self.keycloak_jwks_url
        return f"{self.keycloak_issuer_url}/protocol/openid-connect/certs"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
