import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.models.document import Document
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.event import ExtractedEvent
from backend.app.processors.hasher import compute_content_hash
from backend.app.services.clustering_service import cluster_extracted_event


def test_dashboard_summary_endpoint(client: TestClient, db_session, sample_source):
    """Verify GET /api/v1/dashboard/summary calculates and returns aggregate metrics."""
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)

    # Ingest test document & event
    doc = Document(
        source_id=sample_source.id,
        title="OPEC Approves Extension of Production Cuts",
        url="https://example.com/opec-sum",
        published_at=now,
        content_hash=compute_content_hash("OPEC sum", "url1"),
        processing_status="EXTRACTED",
    )
    db_session.add(doc)
    db_session.flush()

    ev = ExtractedEvent(
        document_id=doc.id,
        event_type="commodity_event",
        event_title="OPEC Approves Extension of Production Cuts",
        event_time=now,
        confidence=0.96,
        importance=0.88,
    )
    db_session.add(ev)
    db_session.commit()

    cluster_extracted_event(db_session, ev.id)

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["active_clusters_count"] >= 1
    assert data["total_events_count"] >= 1
    assert data["total_documents_count"] >= 1
    assert data["active_sources_count"] >= 1
    assert data["high_importance_events_count"] >= 1
    assert "commodity_event" in data["event_types_breakdown"]
    assert len(data["recent_clusters"]) >= 1


def test_global_search_endpoint(client: TestClient, db_session, sample_source):
    """Verify GET /api/v1/search finds clusters and entities matching keyword."""
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)

    entity = Entity(
        entity_type="CENTRAL_BANK",
        canonical_name="Bank of Japan",
        normalized_name="bank of japan",
        country_code="JP",
        metadata_={},
    )
    db_session.add(entity)

    cluster = EventCluster(
        canonical_title="Bank of Japan Holds Policy Rates Constant",
        event_type="central_bank_decision",
        event_time_start=now,
        event_time_end=now,
        confidence=0.92,
        status="ACTIVE",
        metadata_={"importance": 0.85},
    )
    db_session.add(cluster)
    db_session.commit()

    res = client.get("/api/v1/search?q=Japan")
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "Japan"
    assert len(data["clusters"]) >= 1
    assert len(data["entities"]) >= 1
    assert any(c["canonical_title"] == cluster.canonical_title for c in data["clusters"])
    assert any(e["canonical_name"] == entity.canonical_name for e in data["entities"])


def test_entity_events_endpoint(client: TestClient, db_session, sample_source):
    """Verify GET /api/v1/entities/{id}/events returns linked events."""
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)

    entity = Entity(
        entity_type="COUNTRY",
        canonical_name="Ukraine",
        normalized_name="ukraine",
        country_code="UA",
        metadata_={},
    )
    db_session.add(entity)
    db_session.flush()

    doc = Document(
        source_id=sample_source.id,
        title="Drone Strike Reported in Kyiv",
        url="https://example.com/strike-ua",
        published_at=now,
        content_hash=compute_content_hash("UA strike", "url2"),
        processing_status="EXTRACTED",
    )
    db_session.add(doc)
    db_session.flush()

    ev = ExtractedEvent(
        document_id=doc.id,
        event_type="conflict",
        event_title="Drone Strike Reported in Kyiv",
        event_time=now,
        location_entity_id=entity.id,
        confidence=0.95,
        importance=0.92,
    )
    db_session.add(ev)
    db_session.commit()

    res = client.get(f"/api/v1/entities/{entity.id}/events")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["id"] == str(ev.id)
    assert data[0]["location_entity_id"] == str(entity.id)


def test_cluster_filters_search_and_sorting(client: TestClient, db_session, sample_source):
    """Verify list_event_clusters with search, order_by, and min_importance."""
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)

    c1 = EventCluster(
        canonical_title="High Importance Crisis Summit",
        event_type="international_agreement",
        event_time_start=now,
        event_time_end=now,
        confidence=0.98,
        status="ACTIVE",
        metadata_={"importance": 0.95},
    )
    c2 = EventCluster(
        canonical_title="Low Significance Administrative Notice",
        event_type="government_decision",
        event_time_start=now - timedelta(days=2),
        event_time_end=now - timedelta(days=2),
        confidence=0.70,
        status="ACTIVE",
        metadata_={"importance": 0.30},
    )
    db_session.add_all([c1, c2])
    db_session.commit()

    # Search filter
    r_search = client.get("/api/v1/event-clusters?search=Crisis")
    assert r_search.status_code == 200
    items_search = r_search.json()["items"]
    assert len(items_search) == 1
    assert items_search[0]["id"] == str(c1.id)

    # Min importance filter
    r_imp = client.get("/api/v1/event-clusters?min_importance=0.80")
    assert r_imp.status_code == 200
    items_imp = r_imp.json()["items"]
    assert any(c["id"] == str(c1.id) for c in items_imp)
    assert not any(c["id"] == str(c2.id) for c in items_imp)

    # Order by
    r_ord = client.get("/api/v1/event-clusters?order_by=highest_confidence")
    assert r_ord.status_code == 200
    assert r_ord.json()["total"] >= 2
