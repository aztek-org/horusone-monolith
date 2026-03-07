"""Shared test fixtures for Horus ATC API."""
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


@pytest.fixture
def test_settings() -> Settings:
    """Override settings for testing."""
    return Settings(
        environment="testing",
        ollama_base_url="http://localhost:11434",
        ollama_llm_model="test-model",
        whisper_model="base",
        cors_origins="http://localhost:3000",
        enable_radio_effects=False,
    )


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    """Provide a test HTTP client with settings overridden."""
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
