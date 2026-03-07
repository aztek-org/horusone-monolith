"""Tests for configuration management."""
import pytest

from app.config import Settings


def test_settings_defaults() -> None:
    """Test that default settings are correctly set when no env overrides exist."""
    settings = Settings()
    assert settings.environment in ("development", "testing")
    assert settings.port == 8000
    assert settings.whisper_model == "base"
    assert settings.enable_radio_effects is True


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


def test_settings_custom_values() -> None:
    """Test that custom values can be passed and override defaults."""
    settings = Settings(
        environment="production",
        port=9000,
        ollama_llm_model="llama3:8b",
        enable_radio_effects=False,
        noise_level=0.05,
    )
    assert settings.environment == "production"
    assert settings.port == 9000
    assert settings.ollama_llm_model == "llama3:8b"
    assert settings.enable_radio_effects is False
    assert settings.noise_level == pytest.approx(0.05)


def test_ollama_defaults() -> None:
    """Test Ollama configuration has sensible defaults."""
    settings = Settings()
    assert settings.ollama_base_url.startswith("http://")
    assert settings.ollama_llm_model != ""


def test_audio_processing_defaults() -> None:
    """Test audio processing settings have sensible defaults."""
    settings = Settings()
    assert settings.sample_rate == 16000
    assert settings.chunk_size == 1024
    assert settings.audio_format == "wav"
