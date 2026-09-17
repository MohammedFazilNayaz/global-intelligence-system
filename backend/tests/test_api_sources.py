import uuid
import pytest


def test_list_sources_empty(client):
    """GET /api/v1/sources returns empty list when no sources configured."""
    response = client.get("/api/v1/sources")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_create_and_get_source(client):
    """POST /api/v1/sources registers a new source and GET /{id} retrieves it."""
    payload = {
        "name": "Global Maritime Daily",
        "source_type": "rss",
        "base_url": "https://maritime.example.com",
        "feed_url": "https://maritime.example.com/rss",
        "reliability_score": 0.88,
        "active": True,
        "polling_interval_seconds": 300,
        "config_metadata": {"topic": "shipping"},
    }
    create_resp = client.post("/api/v1/sources", json=payload)
    assert create_resp.status_code == 201
    source_data = create_resp.json()
    assert source_data["name"] == "Global Maritime Daily"
    source_id = source_data["id"]

    # Retrieve by ID
    get_resp = client.get(f"/api/v1/sources/{source_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == source_id


def test_create_source_conflict(client):
    """Duplicate source name must return 409 Conflict."""
    payload = {
        "name": "Duplicate Wire",
        "source_type": "rss",
        "base_url": "https://example.com",
        "feed_url": "https://example.com/rss",
    }
    r1 = client.post("/api/v1/sources", json=payload)
    assert r1.status_code == 201

    r2 = client.post("/api/v1/sources", json=payload)
    assert r2.status_code == 409


def test_get_nonexistent_source(client):
    """Unknown source ID returns 404."""
    random_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/sources/{random_id}")
    assert response.status_code == 404


def test_trigger_source_ingestion_api(client, sample_source, monkeypatch):
    """POST /api/v1/sources/{id}/ingest triggers ingestion and returns stats."""
    from backend.app.schemas.document import NormalizedDocument
    from backend.app.utils.time import utc_now

    mock_doc = NormalizedDocument(
        source_name=sample_source.name,
        title="Breaking API Headline",
        url="https://example.com/api-item",
        published_at=utc_now(),
        content_hash="abc" * 21 + "a",
    )

    class MockCollector:
        def __init__(self, *args, **kwargs):
            pass

        def collect(self):
            return [mock_doc]

    monkeypatch.setattr(
        "backend.app.collectors.registry.COLLECTOR_REGISTRY",
        {"rss": MockCollector},
    )

    resp = client.post(f"/api/v1/sources/{sample_source.id}/ingest")
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["source_name"] == sample_source.name
    assert stats["total_fetched"] == 1
    assert stats["new_ingested"] == 1

