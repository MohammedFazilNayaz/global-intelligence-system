import uuid
from datetime import datetime, timezone
import pytest
from backend.app.models.document import Document
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.event import ExtractedEvent
from backend.app.processors.hasher import compute_content_hash
from backend.app.schemas.extraction import EntityType, EventType


@pytest.fixture
def populated_v0_2_data(db_session, sample_source):
    """Seed test database with documents, canonical entities, document entities, and extracted events."""
    now = datetime(2026, 9, 7, 10, 0, 0, tzinfo=timezone.utc)
    doc = Document(
        source_id=sample_source.id,
        title="Bank of England Cuts Benchmark Interest Rates",
        description="London policymakers lowered rates to stimulate growth.",
        content="Governor confirmed the rate cut decision in a morning press briefing in London.",
        url="https://example.com/boe-rate-cut",
        published_at=now,
        content_hash=compute_content_hash("BoE Cut", "https://example.com/boe-rate-cut"),
        processing_status="EXTRACTED",
        raw_metadata={"extraction_provenance": {"extractor_name": "RuleBasedIntelligenceExtractor"}},
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    e1 = Entity(
        entity_type=EntityType.CENTRAL_BANK.value,
        canonical_name="Bank of England",
        normalized_name="bank of england",
        country_code="GB",
    )
    e2 = Entity(
        entity_type=EntityType.CITY.value,
        canonical_name="London",
        normalized_name="london",
        country_code="GB",
    )
    db_session.add_all([e1, e2])
    db_session.commit()

    de1 = DocumentEntity(
        document_id=doc.id,
        entity_id=e1.id,
        mention_text="Bank of England",
        entity_role="actor",
        confidence=0.95,
    )
    de2 = DocumentEntity(
        document_id=doc.id,
        entity_id=e2.id,
        mention_text="London",
        entity_role="location",
        confidence=0.88,
    )
    db_session.add_all([de1, de2])

    ev = ExtractedEvent(
        document_id=doc.id,
        event_type=EventType.CENTRAL_BANK_DECISION.value,
        event_title="Bank of England Cuts Benchmark Interest Rates",
        event_summary="London policymakers lowered rates to stimulate growth.",
        event_time=now,
        location_entity_id=e2.id,
        confidence=0.92,
        importance=0.88,
        metadata_={"trigger": "cuts rates"},
    )
    db_session.add(ev)
    db_session.commit()
    db_session.refresh(ev)

    return {"doc": doc, "e1": e1, "e2": e2, "event": ev}


def test_api_list_entities(client, populated_v0_2_data):
    """Verify GET /api/v1/entities with pagination and filters."""
    # List all
    resp = client.get("/api/v1/entities")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2

    # Filter by entity_type
    resp_type = client.get("/api/v1/entities?entity_type=CENTRAL_BANK")
    assert resp_type.status_code == 200
    assert resp_type.json()["total"] == 1
    assert resp_type.json()["items"][0]["canonical_name"] == "Bank of England"

    # Filter by country_code
    resp_cc = client.get("/api/v1/entities?country_code=GB")
    assert resp_cc.status_code == 200
    assert resp_cc.json()["total"] >= 2

    # Search filter
    resp_search = client.get("/api/v1/entities?search=london")
    assert resp_search.status_code == 200
    assert resp_search.json()["total"] == 1
    assert resp_search.json()["items"][0]["canonical_name"] == "London"


def test_api_get_entity_by_id(client, populated_v0_2_data):
    """Verify GET /api/v1/entities/{id} success and 404."""
    entity_id = populated_v0_2_data["e1"].id
    resp = client.get(f"/api/v1/entities/{entity_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(entity_id)
    assert resp.json()["canonical_name"] == "Bank of England"

    random_id = str(uuid.uuid4())
    resp_404 = client.get(f"/api/v1/entities/{random_id}")
    assert resp_404.status_code == 404


def test_api_get_document_entities(client, populated_v0_2_data):
    """Verify GET /api/v1/documents/{id}/entities returns associated mentions."""
    doc_id = populated_v0_2_data["doc"].id
    resp = client.get(f"/api/v1/documents/{doc_id}/entities")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    mention_names = {item["entity"]["canonical_name"] for item in items}
    assert "Bank of England" in mention_names
    assert "London" in mention_names


def test_api_get_document_events(client, populated_v0_2_data):
    """Verify GET /api/v1/documents/{id}/events returns extracted events."""
    doc_id = populated_v0_2_data["doc"].id
    resp = client.get(f"/api/v1/documents/{doc_id}/events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["event_type"] == "central_bank_decision"
    assert events[0]["importance"] == 0.88


def test_api_list_events(client, populated_v0_2_data):
    """Verify GET /api/v1/events with filtering by type, confidence, and importance."""
    resp = client.get("/api/v1/events?event_type=central_bank_decision&min_importance=0.8")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["items"][0]["event_type"] == "central_bank_decision"

    # Filter with higher importance threshold -> 0 results
    resp_empty = client.get("/api/v1/events?min_importance=0.99")
    assert resp_empty.status_code == 200
    assert resp_empty.json()["total"] == 0


def test_api_get_event_by_id(client, populated_v0_2_data):
    """Verify GET /api/v1/events/{id} success and 404."""
    event_id = populated_v0_2_data["event"].id
    resp = client.get(f"/api/v1/events/{event_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(event_id)
    assert resp.json()["event_title"] == "Bank of England Cuts Benchmark Interest Rates"

    random_id = str(uuid.uuid4())
    resp_404 = client.get(f"/api/v1/events/{random_id}")
    assert resp_404.status_code == 404


def test_api_trigger_document_extraction(client, db_session, sample_source):
    """Verify POST /api/v1/documents/{id}/extract executes pipeline via REST API."""
    now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
    doc = Document(
        source_id=sample_source.id,
        title="OPEC Agrees on Crude Oil Production Target Quotas in Vienna",
        description="Energy ministers from Saudi Arabia and UAE reached consensus on output limits.",
        url="https://example.com/opec-target",
        published_at=now,
        content_hash=compute_content_hash("OPEC Target", "https://example.com/opec-target"),
        processing_status="NORMALIZED",
    )
    db_session.add(doc)
    db_session.commit()

    resp = client.post(f"/api/v1/documents/{doc.id}/extract")
    assert resp.status_code == 200
    data = resp.json()
    assert data["document_id"] == str(doc.id)
    assert data["processing_status"] == "EXTRACTED"
    assert data["entities_count"] > 0
    assert data["events_count"] > 0

    # Test reprocessing flag via API
    resp_reproc = client.post(f"/api/v1/documents/{doc.id}/extract?reprocess=true")
    assert resp_reproc.status_code == 200
    assert resp_reproc.json()["processing_status"] == "EXTRACTED"
