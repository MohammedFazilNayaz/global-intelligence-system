import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.models.entity import Entity
from backend.app.models.relationship import EntityRelationship
from backend.app.models.event import ExtractedEvent
from backend.app.models.document import Document
from backend.app.models.source import Source
from backend.app.models.indicator import EconomicIndicator
from backend.app.models.observation import EconomicObservation
from backend.app.models.market_asset import MarketAsset
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.schemas.relationship import RelationshipType
from backend.app.processors.hasher import compute_content_hash
from backend.app.utils.time import utc_now


@pytest.fixture
def api_test_data(db_session):
    db = db_session
    try:
        now = utc_now()
        # 1. Entities
        e1 = Entity(
            canonical_name=f"Test Org {uuid.uuid4().hex[:6]}",
            normalized_name=f"test org {uuid.uuid4().hex[:6]}",
            entity_type="ORGANIZATION",
            country_code="US",
            description="Test organization",
        )
        e2 = Entity(
            canonical_name=f"Test Location {uuid.uuid4().hex[:6]}",
            normalized_name=f"test location {uuid.uuid4().hex[:6]}",
            entity_type="LOCATION",
            country_code="US",
            description="Test location",
        )
        db.add_all([e1, e2])
        db.flush()

        # 2. Relationship
        rel = EntityRelationship(
            source_entity_id=e1.id,
            target_entity_id=e2.id,
            relationship_type=RelationshipType.HEADQUARTERED_IN.value,
            confidence=0.95,
            evidence="Test Org is headquartered in Test Location.",
            extraction_method="api_test",
            extractor_version="v0.7.0",
            metadata_={},
        )
        db.add(rel)
        db.flush()

        # 3. Source & Document & Event
        src = Source(
            name=f"API Test Source {uuid.uuid4().hex[:6]}",
            base_url="https://apitest.local",
            feed_url="https://apitest.local/rss",
            source_type="rss",
            reliability_score=0.9,
        )
        db.add(src)
        db.flush()

        doc = Document(
            source_id=src.id,
            title="API Test Document",
            content="Full document text",
            url="https://apitest.local/doc1",
            content_hash=compute_content_hash("Full document text", "https://apitest.local/doc1"),
            published_at=now,
        )
        db.add(doc)
        db.flush()

        ev = ExtractedEvent(
            document_id=doc.id,
            event_type="regulatory_action",
            event_title="API Test Event",
            event_summary="Summary of API test event",
            event_time=now,
            location_entity_id=e2.id,
            confidence=0.92,
            importance=0.88,
            metadata_={},
        )
        db.add(ev)
        db.flush()

        # 4. Economic Observation
        ind = EconomicIndicator(
            canonical_name=f"Test Indicator {uuid.uuid4().hex[:6]}",
            normalized_name=f"test indicator {uuid.uuid4().hex[:6]}",
            indicator_type=f"ind_{uuid.uuid4().hex[:4]}",
            economic_domain="Policy",
            country_entity_id=e2.id,
        )
        db.add(ind)
        db.flush()

        obs = EconomicObservation(
            indicator_id=ind.id,
            event_id=ev.id,
            document_id=doc.id,
            reported_value=4.5,
            reported_unit="%",
            economic_relevance=0.85,
            metadata_={},
        )
        db.add(obs)
        db.flush()

        # 5. Market Correlation
        asset = MarketAsset(
            symbol=f"TEST_{uuid.uuid4().hex[:4]}",
            canonical_name="Test Asset",
            asset_type="equity",
            metadata_={},
        )
        db.add(asset)
        db.flush()

        corr = EventMarketCorrelation(
            event_id=ev.id,
            market_asset_id=asset.id,
            window_size="1h",
            window_start=now,
            window_end=now,
            pre_event_price=100.0,
            post_event_price=102.5,
            return_percent=2.5,
            volume_change=15.0,
            calculated_at=now,
            methodology="window_close_return",
            metadata_={},
        )
        db.add(corr)
        db.commit()

        yield {
            "entity1": e1,
            "entity2": e2,
            "relationship": rel,
            "event": ev,
            "indicator": ind,
            "asset": asset,
        }
    finally:
        pass


def test_list_and_filter_relationships(client, api_test_data):
    rel = api_test_data["relationship"]

    res = client.get("/api/v1/relationships?page=1&page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1

    # Filter by relationship_type
    res_type = client.get(f"/api/v1/relationships?relationship_type={rel.relationship_type}")
    assert res_type.status_code == 200
    assert any(item["id"] == str(rel.id) for item in res_type.json()["items"])

    # Filter by source_entity_id
    res_src = client.get(f"/api/v1/relationships?source_entity_id={rel.source_entity_id}")
    assert res_src.status_code == 200
    assert all(item["source_entity_id"] == str(rel.source_entity_id) for item in res_src.json()["items"])


def test_get_relationship_detail(client, api_test_data):
    rel = api_test_data["relationship"]

    res = client.get(f"/api/v1/relationships/{rel.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(rel.id)
    assert data["relationship_type"] == rel.relationship_type
    assert data["source_entity"]["canonical_name"] == api_test_data["entity1"].canonical_name
    assert data["target_entity"]["canonical_name"] == api_test_data["entity2"].canonical_name

    # 404 for random UUID
    res_404 = client.get(f"/api/v1/relationships/{uuid.uuid4()}")
    assert res_404.status_code == 404


def test_create_relationship_api(client, api_test_data):
    e1 = api_test_data["entity1"]
    e2 = api_test_data["entity2"]

    payload = {
        "source_entity_id": str(e1.id),
        "target_entity_id": str(e2.id),
        "relationship_type": "operates_in",
        "confidence": 0.91,
        "evidence": "Test Org operates in Test Location according to commercial records.",
        "extraction_method": "api_test",
        "extractor_version": "v0.7.0",
        "metadata": {"source": "manual_entry"},
    }
    res = client.post("/api/v1/relationships", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["relationship_type"] == "operates_in"
    assert data["confidence"] == 0.91

    # Missing evidence validation (HTTP 422)
    bad_payload = payload.copy()
    bad_payload["evidence"] = ""
    res_bad = client.post("/api/v1/relationships", json=bad_payload)
    assert res_bad.status_code == 422

    # Non-existent orphan entity validation (HTTP 422)
    orphan_payload = payload.copy()
    orphan_payload["source_entity_id"] = str(uuid.uuid4())
    res_orphan = client.post("/api/v1/relationships", json=orphan_payload)
    assert res_orphan.status_code == 422


def test_get_entity_relationships_and_graph(client, api_test_data):
    e1 = api_test_data["entity1"]
    e2 = api_test_data["entity2"]

    # 1. Entity relationships
    res_rels = client.get(f"/api/v1/entities/{e1.id}/relationships")
    assert res_rels.status_code == 200
    data_rels = res_rels.json()
    assert data_rels["entity_id"] == str(e1.id)
    assert len(data_rels["outbound"]) >= 1

    # 2. Entity graph
    res_graph = client.get(f"/api/v1/entities/{e1.id}/graph?depth=2")
    assert res_graph.status_code == 200
    data_graph = res_graph.json()
    assert data_graph["center_node_id"] == str(e1.id)
    assert data_graph["depth"] == 2
    assert len(data_graph["nodes"]) >= 2
    assert len(data_graph["edges"]) >= 1

    # 404 for non-existent entity
    res_404 = client.get(f"/api/v1/entities/{uuid.uuid4()}/graph")
    assert res_404.status_code == 404


def test_get_event_relationships_and_impact(client, api_test_data):
    ev = api_test_data["event"]

    # 1. Event relationships
    res_rels = client.get(f"/api/v1/events/{ev.id}/relationships")
    assert res_rels.status_code == 200
    data_rels = res_rels.json()
    assert data_rels["event_id"] == str(ev.id)
    assert data_rels["location_entity"] is not None
    assert len(data_rels["economic_indicators"]) >= 1
    assert len(data_rels["market_assets"]) >= 1
    assert len(data_rels["graph_edges"]) >= 2

    # 2. Event impact assessment
    res_impact = client.get(f"/api/v1/events/{ev.id}/impact")
    assert res_impact.status_code == 200
    data_impact = res_impact.json()
    assert data_impact["event_id"] == str(ev.id)
    assert data_impact["event_importance"] == 0.88
    assert len(data_impact["economic_context"]) >= 1
    assert len(data_impact["market_context"]) >= 1
    assert "disclaimer" in data_impact
    assert "retrospective, observational associations" in data_impact["disclaimer"]

    # Verify no causal words in response explanation
    causal_words = ["caused", "drove", "triggered", "because of", "will lead to"]
    for w in causal_words:
        assert w not in data_impact["explanation"].lower()


def test_search_graph_api(client, api_test_data):
    e1 = api_test_data["entity1"]

    query_str = e1.canonical_name
    res = client.get(f"/api/v1/search/graph?q={query_str}&depth=1")
    assert res.status_code == 200
    data = res.json()
    assert data["total_nodes"] >= 1
    assert any(n["id"] == str(e1.id) for n in data["nodes"])
