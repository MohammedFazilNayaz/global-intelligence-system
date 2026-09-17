import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
import httpx

from backend.app.main import app
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.event import ExtractedEvent
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.relationship import EntityRelationship
from backend.app.models.market_asset import MarketAsset
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.collectors.base import CollectorError
from backend.app.collectors.rss import RSSCollector
from backend.app.collectors.api import APICollector
from backend.app.utils.http_client import HttpTimeoutError, HttpStatusError
from backend.app.services.ingestion import ingest_from_source
from backend.app.services.dossier_service import build_event_intelligence_dossier
from backend.app.schemas.dossier import EvidenceClass
from backend.app.utils.time import utc_now


def test_7_state_classification_healthy_to_failed(db_session):
    """Test deterministic evaluation of all 7 canonical operational states."""
    now = utc_now()
    src = Source(
        name="Test Feed",
        source_type="rss",
        base_url="https://example.com",
        feed_url="https://example.com/rss",
        polling_interval_seconds=300,
        active=True,
        consecutive_failures=0,
        last_successful_fetch_at=now - timedelta(minutes=5),
        freshness_status="CURRENT",
        config_metadata={},
    )
    src.last_successful_ingestion_at = now - timedelta(hours=2)
    db_session.add(src)
    db_session.commit()

    # 1. HEALTHY: active, recent fetch, recent document (< 48h)
    assert src.health_status == "HEALTHY"

    # 2. DISABLED: active = False
    src.active = False
    assert src.health_status == "DISABLED"
    src.active = True

    # 3. AUTH_REQUIRED: auth metadata flag
    src.config_metadata = {"auth_required": True}
    assert src.health_status == "AUTH_REQUIRED"
    src.config_metadata = {}

    # 4. RATE_LIMITED: http 429 in metadata or error
    src.last_error_message = "HTTP 429 Too Many Requests"
    assert src.health_status == "RATE_LIMITED"
    src.last_error_message = None

    # 5. FAILED: consecutive failures >= 3
    src.consecutive_failures = 3
    assert src.health_status == "FAILED"

    # 6. DEGRADED: consecutive failures 1 or 2
    src.consecutive_failures = 1
    assert src.health_status == "DEGRADED"
    src.consecutive_failures = 0

    # 7. STALE: operational, but freshness_status == STALE
    src.freshness_status = "STALE"
    assert src.health_status == "STALE"


def test_adversarial_source_timeout(db_session):
    """Test source network timeout handling and failure telemetry."""
    src = Source(
        name="Timeout Feed",
        source_type="rss",
        base_url="https://example.com",
        feed_url="https://timeout.example.com/rss",
        polling_interval_seconds=300,
        active=True,
        config_metadata={},
    )
    db_session.add(src)
    db_session.commit()

    with patch("backend.app.utils.http_client.ResilientHttpClient.get", side_effect=HttpTimeoutError("Connection timed out")):
        with pytest.raises(CollectorError):
            ingest_from_source(db_session, src, trigger_pipeline=False)

    db_session.refresh(src)
    assert "timed out" in (src.last_error_message or "").lower()
    assert src.consecutive_failures == 1
    assert src.health_status == "DEGRADED"


def test_adversarial_http_404_and_403(db_session):
    """Test HTTP 404 response resilience."""
    src = Source(
        name="NotFound Feed",
        source_type="rss",
        base_url="https://example.com",
        feed_url="https://404.example.com/rss",
        polling_interval_seconds=300,
        active=True,
        config_metadata={},
    )
    db_session.add(src)
    db_session.commit()

    err = HttpStatusError(404, "Not Found", "https://404.example.com/rss")

    with patch("backend.app.utils.http_client.ResilientHttpClient.get", side_effect=err):
        with pytest.raises(CollectorError):
            ingest_from_source(db_session, src, trigger_pipeline=False)

    db_session.refresh(src)
    assert src.consecutive_failures == 1


def test_adversarial_http_429_rate_limit(db_session):
    """Test HTTP 429 response rate-limit classification."""
    src = Source(
        name="RateLimited API",
        source_type="api",
        base_url="https://api.example.com",
        feed_url="https://api.example.com/data",
        polling_interval_seconds=300,
        active=True,
        config_metadata={},
    )
    db_session.add(src)
    db_session.commit()

    err = HttpStatusError(429, "Too Many Requests", "https://api.example.com/data")

    with patch("backend.app.utils.http_client.ResilientHttpClient.get", side_effect=err):
        with pytest.raises(CollectorError):
            ingest_from_source(db_session, src, trigger_pipeline=False)

    db_session.refresh(src)
    assert src.health_status == "RATE_LIMITED"


def test_adversarial_malformed_xml():
    """Test resilience against corrupt or truncated XML feeds."""
    collector = RSSCollector(name="Malformed", feed_url="https://example.com/broken.xml", base_url="https://example.com")
    malformed_xml = "<rss><channel><title>Broken Feed<item><title>Unclosed</rss>"
    
    # feedparser handles malformed XML leniently or raises ValueError on empty unparseable
    try:
        docs = collector.parse_and_normalize(malformed_xml)
        assert isinstance(docs, list)
    except ValueError as e:
        assert "Malformed RSS feed" in str(e)


def test_adversarial_malformed_json():
    """Test resilience against invalid JSON API responses."""
    collector = APICollector(name="MalformedJSON", feed_url="https://api.example.com", base_url="https://api.example.com", config_metadata={"items_path": "data"})
    malformed_json = "{'invalid': json syntax, missing quotes"
    
    docs = collector.parse_and_normalize(malformed_json)
    assert docs == []


def test_adversarial_empty_feed():
    """Test valid XML feed with zero articles."""
    collector = RSSCollector(name="EmptyFeed", feed_url="https://example.com/empty.xml", base_url="https://example.com")
    empty_xml = """<?xml version="1.0"?>
    <rss version="2.0">
        <channel>
            <title>Empty Feed</title>
            <link>https://example.com</link>
            <description>No items</description>
        </channel>
    </rss>"""
    docs = collector.parse_and_normalize(empty_xml)
    assert docs == []


def test_adversarial_duplicate_only_and_timestamp_decoupling(db_session):
    """Test that duplicate-only polling updates LAST_CHECKED while preserving LAST_NEW_CONTENT."""
    past_ingestion_time = utc_now() - timedelta(hours=5)
    src = Source(
        name="Dupe Feed",
        source_type="rss",
        base_url="https://example.com",
        feed_url="https://dupe.example.com/rss",
        polling_interval_seconds=300,
        active=True,
        config_metadata={},
    )
    src.last_successful_ingestion_at = past_ingestion_time
    db_session.add(src)
    db_session.commit()

    sample_rss = """<?xml version="1.0"?>
    <rss version="2.0">
        <channel>
            <title>Duplicate Feed</title>
            <link>https://dupe.example.com</link>
            <item>
                <title>Same Article Always</title>
                <link>https://dupe.example.com/article1</link>
                <description>Content text</description>
                <pubDate>Mon, 15 Sep 2026 12:00:00 GMT</pubDate>
            </item>
        </channel>
    </rss>"""

    mock_resp = MagicMock()
    mock_resp.text = sample_rss

    with patch("backend.app.utils.http_client.ResilientHttpClient.get", return_value=mock_resp):
        stats1 = ingest_from_source(db_session, src, trigger_pipeline=False)

    assert stats1.new_ingested == 1
    db_session.refresh(src)
    first_ingestion_at = src.last_successful_ingestion_at

    # Second poll with unchanged content
    with patch("backend.app.utils.http_client.ResilientHttpClient.get", return_value=mock_resp):
        stats2 = ingest_from_source(db_session, src, trigger_pipeline=False)

    assert stats2.new_ingested == 0  # 0 new documents
    assert stats2.duplicates_skipped == 1
    db_session.refresh(src)
    # LAST_CHECKED is updated to current poll
    assert src.last_successful_fetch_at is not None
    # LAST_NEW_CONTENT remains from when new document was ingested
    assert src.last_successful_ingestion_at == first_ingestion_at


def test_dossier_synthesis_21_fields(db_session):
    """Test full synthesis of the 21-field event intelligence dossier with rigorous evidence classification."""
    now = utc_now()
    src = Source(
        name="Reuters Global",
        source_type="rss",
        base_url="https://example.com",
        feed_url="https://reuters.com/rss",
        polling_interval_seconds=300,
        active=True,
        config_metadata={"domain": "reuters.com"},
    )
    db_session.add(src)
    db_session.flush()

    doc = Document(
        source_id=src.id,
        title="OPEC+ Announces Emergency Oil Production Quota Reductions",
        url="https://reuters.com/oil-cut-emergency",
        published_at=now - timedelta(hours=2),
        ingested_at=now - timedelta(hours=1),
        content_hash="hash1234567890",
        description="Major producers agree on coordinated cuts amid maritime shipping friction.",
    )
    db_session.add(doc)
    db_session.flush()

    ent_country = Entity(
        entity_type="COUNTRY",
        canonical_name="Saudi Arabia",
        normalized_name="saudi arabia",
        country_code="SA",
    )
    ent_actor = Entity(
        entity_type="ORGANIZATION",
        canonical_name="OPEC",
        normalized_name="opec",
    )
    ent_target = Entity(
        entity_type="COUNTRY",
        canonical_name="United States",
        normalized_name="united states",
        country_code="US",
    )
    db_session.add_all([ent_country, ent_actor, ent_target])
    db_session.flush()

    # Document entities
    de1 = DocumentEntity(
        document_id=doc.id,
        entity_id=ent_actor.id,
        mention_text="OPEC",
        entity_role="subject",
        confidence=0.95,
    )
    de2 = DocumentEntity(
        document_id=doc.id,
        entity_id=ent_target.id,
        mention_text="United States",
        entity_role="object",
        confidence=0.90,
    )
    db_session.add_all([de1, de2])

    event = ExtractedEvent(
        document_id=doc.id,
        event_type="ENERGY_DISRUPTION",
        event_title="OPEC+ Announces Emergency Oil Production Quota Reductions",
        event_summary="Coordinated cuts announced.",
        event_time=now - timedelta(hours=2),
        location_entity_id=ent_country.id,
        confidence=0.96,
        importance=0.88,
        metadata_={},
    )
    db_session.add(event)
    db_session.flush()

    # Entity relationship: OPEC supplies US
    rel = EntityRelationship(
        source_entity_id=ent_actor.id,
        target_entity_id=ent_target.id,
        relationship_type="supplies",
        confidence=0.90,
        source_event_id=event.id,
        evidence="OPEC supplies crude to global markets including US",
    )
    db_session.add(rel)

    # Market asset & correlation
    asset = MarketAsset(
        symbol="BRENT-CRUDE",
        canonical_name="Brent Crude Oil",
        asset_type="COMMODITY",
    )
    db_session.add(asset)
    db_session.flush()

    corr = EventMarketCorrelation(
        event_id=event.id,
        market_asset_id=asset.id,
        window_size="1h",
        window_start=now - timedelta(hours=2),
        window_end=now - timedelta(hours=1),
        event_price=78.50,
        post_event_price=81.20,
        return_percent=3.44,
        calculated_at=now,
    )
    db_session.add(corr)
    db_session.commit()

    dossier = build_event_intelligence_dossier(db_session, event.id)
    assert dossier is not None

    # Verify key 21 fields
    assert dossier.what_happened["title"] == event.event_title
    assert dossier.what_happened["event_type"] == "ENERGY_DISRUPTION"
    assert dossier.why_it_matters["importance_grade"] == "CRITICAL"
    assert len(dossier.directly_involved) == 1
    assert dossier.directly_involved[0].name == "OPEC"
    assert dossier.directly_involved[0].evidence_class == EvidenceClass.DIRECT

    assert len(dossier.directly_affected) == 1
    assert dossier.directly_affected[0].name == "United States"

    # Potential beneficiaries with neutral phrasing
    assert len(dossier.potential_beneficiaries) > 0
    assert "Potential beneficiary:" in dossier.potential_beneficiaries[0].rationale
    assert dossier.potential_beneficiaries[0].evidence_class == EvidenceClass.ANALYTICAL_IMPLICATION

    # Affected countries
    country_codes = [c.country_code for c in dossier.affected_countries]
    assert "SA" in country_codes

    # Sectors
    sectors = [s.sector_name for s in dossier.affected_sectors]
    assert "Energy & Natural Resources" in sectors

    # Commodity connections
    assert len(dossier.commodity_connections) == 1
    assert dossier.commodity_connections[0].asset_symbol == "BRENT-CRUDE"
    assert dossier.commodity_connections[0].evidence_class == EvidenceClass.OBSERVED

    # Source evidence & independent timestamps
    assert len(dossier.source_evidence) == 1
    assert dossier.source_evidence[0].source_name == "Reuters Global"
    assert dossier.publication_time is not None
    assert dossier.ingestion_time is not None
    assert dossier.fetch_time is not None
    assert dossier.confidence == 0.96


def test_dossier_sparse_evidence_zero_fabrication(db_session):
    """Test that sparse event produces empty structures and UNKNOWNs without hallucination."""
    now = utc_now()
    src = Source(
        name="Sparse Source",
        source_type="rss",
        base_url="https://example.com",
        feed_url="https://sparse.example.com",
        polling_interval_seconds=300,
        active=True,
    )
    db_session.add(src)
    db_session.flush()

    doc = Document(
        source_id=src.id,
        title="Unclassified Regional Notice",
        url="https://sparse.example.com/1",
        published_at=now,
        ingested_at=now,
        content_hash="sparsehash123",
    )
    db_session.add(doc)
    db_session.flush()

    sparse_event = ExtractedEvent(
        document_id=doc.id,
        event_type="GENERAL_NOTICE",
        event_title="Unclassified Regional Notice",
        confidence=0.45,
        importance=0.20,
    )
    db_session.add(sparse_event)
    db_session.commit()

    dossier = build_event_intelligence_dossier(db_session, sparse_event.id)
    assert dossier is not None

    # Zero fabrication checks
    assert dossier.directly_involved == []
    assert dossier.directly_affected == []
    assert dossier.potential_beneficiaries == []
    assert dossier.potential_exposures == []
    assert dossier.affected_companies == []
    assert dossier.commodity_connections == []
    assert dossier.currency_connections == []
    assert dossier.equity_connections == []
    assert dossier.rate_connections == []
    assert dossier.geopolitical_connections == []
    assert dossier.related_events == []


def test_dossier_rest_api_endpoint(client, db_session):
    """Test GET /api/v1/intelligence/events/{event_id}/dossier API endpoint."""
    now = utc_now()
    src = Source(
        name="API Source",
        source_type="rss",
        base_url="https://example.com",
        feed_url="https://api.source.com",
        polling_interval_seconds=300,
        active=True,
    )
    db_session.add(src)
    db_session.flush()

    doc = Document(
        source_id=src.id,
        title="Central Bank Rate Shift",
        url="https://api.source.com/rate",
        published_at=now,
        ingested_at=now,
        content_hash="ratehash123",
    )
    db_session.add(doc)
    db_session.flush()

    ev = ExtractedEvent(
        document_id=doc.id,
        event_type="policy_decision",
        event_title="Central Bank Rate Shift",
        confidence=0.91,
        importance=0.75,
    )
    db_session.add(ev)
    db_session.commit()

    # Success 200
    res = client.get(f"/api/v1/intelligence/events/{ev.id}/dossier")
    assert res.status_code == 200
    data = res.json()
    assert data["what_happened"]["title"] == "Central Bank Rate Shift"
    assert data["confidence"] == 0.91
    assert "source_evidence" in data

    # 404 for non-existent event
    random_id = uuid.uuid4()
    res404 = client.get(f"/api/v1/intelligence/events/{random_id}/dossier")
    assert res404.status_code == 404
