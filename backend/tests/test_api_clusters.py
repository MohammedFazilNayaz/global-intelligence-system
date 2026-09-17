import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.models.document import Document
from backend.app.models.event import ExtractedEvent
from backend.app.processors.hasher import compute_content_hash
from backend.app.services.clustering_service import cluster_extracted_event


def test_api_list_event_clusters(client: TestClient, db_session, sample_source):
    """Test GET /api/v1/event-clusters pagination and filters."""
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)

    cluster = EventCluster(
        canonical_title="OPEC Approves Extension of Crude Oil Production Cuts",
        canonical_summary="Delegates agreed to prolong supply restrictions.",
        event_type="commodity_event",
        event_time_start=now,
        event_time_end=now,
        confidence=0.95,
        status="ACTIVE",
        metadata_={"document_count": 1, "unique_source_count": 1},
    )
    db_session.add(cluster)
    db_session.commit()

    # List all
    res = client.get("/api/v1/event-clusters")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    item = data["items"][0]
    assert item["canonical_title"] == cluster.canonical_title
    assert item["event_type"] == "commodity_event"

    # Filter by event_type
    res_filtered = client.get("/api/v1/event-clusters?event_type=commodity_event")
    assert res_filtered.status_code == 200
    assert len(res_filtered.json()["items"]) >= 1

    # Filter with non-matching type
    res_empty = client.get("/api/v1/event-clusters?event_type=non_existent_type")
    assert res_empty.status_code == 200
    assert len(res_empty.json()["items"]) == 0


def test_api_get_event_cluster_detail(client: TestClient, db_session, sample_source):
    """Test GET /api/v1/event-clusters/{id} returns full detail with members."""
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    doc = Document(
        source_id=sample_source.id,
        title="OPEC Extends Output Cuts",
        url="https://example.com/opec/1",
        published_at=now,
        content_hash=compute_content_hash("OPEC cuts", "url1"),
        processing_status="NORMALIZED",
    )
    db_session.add(doc)
    db_session.flush()

    ev = ExtractedEvent(
        document_id=doc.id,
        event_type="commodity_event",
        event_title="OPEC Extends Output Cuts",
        event_time=now,
        confidence=0.94,
        importance=0.88,
    )
    db_session.add(ev)
    db_session.commit()

    mem = cluster_extracted_event(db_session, ev.id)

    res = client.get(f"/api/v1/event-clusters/{mem.event_cluster_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(mem.event_cluster_id)
    assert len(data["members"]) == 1
    assert data["members"][0]["extracted_event_id"] == str(ev.id)


def test_api_get_cluster_for_event(client: TestClient, db_session, sample_source):
    """Test GET /api/v1/events/{id}/cluster returns membership and score explanation."""
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    doc = Document(
        source_id=sample_source.id,
        title="Sanctions Imposed on Shipping Network",
        url="https://example.com/sanctions/1",
        published_at=now,
        content_hash=compute_content_hash("Shipping sanctions", "url1"),
        processing_status="NORMALIZED",
    )
    db_session.add(doc)
    db_session.flush()

    ev = ExtractedEvent(
        document_id=doc.id,
        event_type="trade_action",
        event_title="Sanctions Imposed on Shipping Network",
        event_time=now,
        confidence=0.92,
        importance=0.85,
    )
    db_session.add(ev)
    db_session.commit()

    mem = cluster_extracted_event(db_session, ev.id)

    res = client.get(f"/api/v1/events/{ev.id}/cluster")
    assert res.status_code == 200
    data = res.json()
    assert data["event_cluster_id"] == str(mem.event_cluster_id)
    assert "metadata" in data
    assert data["membership_score"] == 1.0


def test_api_get_cluster_events(client: TestClient, db_session, sample_source):
    """Test GET /api/v1/event-clusters/{id}/events returns list of member events."""
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    doc = Document(
        source_id=sample_source.id,
        title="Tech Giant Announces AI Chip",
        url="https://example.com/chip/1",
        published_at=now,
        content_hash=compute_content_hash("AI Chip", "url1"),
        processing_status="NORMALIZED",
    )
    db_session.add(doc)
    db_session.flush()

    ev = ExtractedEvent(
        document_id=doc.id,
        event_type="corporate_action",
        event_title="Tech Giant Announces AI Chip",
        event_time=now,
        confidence=0.91,
        importance=0.75,
    )
    db_session.add(ev)
    db_session.commit()

    mem = cluster_extracted_event(db_session, ev.id)

    res = client.get(f"/api/v1/event-clusters/{mem.event_cluster_id}/events")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["extracted_event_id"] == str(ev.id)


def test_api_cluster_document_manual_trigger(client: TestClient, db_session, sample_source):
    """Test POST /api/v1/documents/{id}/cluster triggers clustering for document events."""
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    doc = Document(
        source_id=sample_source.id,
        title="Central Bank Policy Shift",
        url="https://example.com/policy/1",
        published_at=now,
        content_hash=compute_content_hash("Policy Shift", "url1"),
        processing_status="EXTRACTED",
    )
    db_session.add(doc)
    db_session.flush()

    ev = ExtractedEvent(
        document_id=doc.id,
        event_type="central_bank_decision",
        event_title="Central Bank Policy Shift",
        event_time=now,
        confidence=0.93,
        importance=0.88,
    )
    db_session.add(ev)
    db_session.commit()

    res = client.post(f"/api/v1/documents/{doc.id}/cluster")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["extracted_event_id"] == str(ev.id)
