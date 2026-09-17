import pytest


def test_health_endpoint(client):
    """GET /health returns healthy status and connected database."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data


def test_api_v1_health_endpoint(client):
    """GET /api/v1/health is also accessible under API prefix."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_status_page(client):
    """GET / returns HTML landing status page."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Global Intelligence Platform" in response.text
