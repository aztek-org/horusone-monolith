"""Integration tests for health endpoints."""
import pytest
from fastapi.testclient import TestClient


def test_root_endpoint_status_code(client: TestClient) -> None:
    """Root endpoint should return HTTP 200."""
    response = client.get("/")
    assert response.status_code == 200


def test_root_endpoint_name(client: TestClient) -> None:
    """Root endpoint should identify the API by name."""
    response = client.get("/")
    data = response.json()
    assert data["name"] == "Horus ATC Voice Communication API"


def test_root_endpoint_status_field(client: TestClient) -> None:
    """Root endpoint should report operational status."""
    response = client.get("/")
    data = response.json()
    assert data["status"] == "operational"


def test_root_endpoint_exposes_endpoints(client: TestClient) -> None:
    """Root endpoint should list key API endpoints."""
    response = client.get("/")
    data = response.json()
    assert "endpoints" in data
    endpoints = data["endpoints"]
    assert "health" in endpoints
    assert "voice_websocket" in endpoints
    assert "docs" in endpoints


def test_health_check_returns_200(client: TestClient) -> None:
    """GET /health should return HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_check_status_is_healthy(client: TestClient) -> None:
    """GET /health should report a healthy status."""
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "healthy"


def test_health_check_includes_service_name(client: TestClient) -> None:
    """GET /health should include the service identifier."""
    response = client.get("/health")
    data = response.json()
    assert data["service"] == "horus-atc-api"


def test_health_check_includes_version(client: TestClient) -> None:
    """GET /health should include an API version string."""
    response = client.get("/health")
    data = response.json()
    assert "version" in data
    assert data["version"] != ""


def test_readiness_endpoint_reachable(client: TestClient) -> None:
    """GET /health/ready should be reachable (200 or 503, never 404)."""
    response = client.get("/health/ready")
    assert response.status_code in (200, 503)


def test_readiness_endpoint_includes_ready_field(client: TestClient) -> None:
    """GET /health/ready should include a 'ready' field in the response."""
    response = client.get("/health/ready")
    data = response.json()
    assert "ready" in data


def test_readiness_endpoint_includes_services(client: TestClient) -> None:
    """GET /health/ready should report individual service statuses."""
    response = client.get("/health/ready")
    data = response.json()
    assert "services" in data


def test_docs_endpoint_accessible(client: TestClient) -> None:
    """OpenAPI docs endpoint should be accessible."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_unknown_route_returns_404(client: TestClient) -> None:
    """Requests to undefined routes should return 404."""
    response = client.get("/nonexistent-route")
    assert response.status_code == 404
