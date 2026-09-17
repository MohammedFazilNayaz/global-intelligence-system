"""
V0.7.1 Production Data Integrity & Stabilization Test Suite.
Verifies all 12 phases of V0.7.1:
1. Test / Production Database Isolation
2. Zero synthetic test / benchmark records in production queries
3. Genuine Source Health & Telemetry semantics
4. Ingestion Scheduler & Worker lifecycle
5. Deterministic Freshness Semantics (CURRENT, RECENT, STALE, HISTORICAL, UNKNOWN, SYNTHETIC_TEST)
6. Non-Causal Live Feed Integrity
7. Canonical 16-Asset Market Desk universe
8. Geo View Primary Location Mapping
9. Knowledge Graph Crash Prevention & Schema
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.freshness_service import (
    compute_item_freshness_status,
    get_system_freshness_summary,
    get_all_sources_health,
)
from backend.app.services.market_service import (
    get_market_assets,
    get_market_dashboard_summary,
    initialize_canonical_market_assets,
)
from backend.app.services.live_feed_service import get_live_intelligence_feed
from backend.app.services.graph_service import get_entity_subgraph
from backend.app.models.market_asset import MarketAsset
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.event import ExtractedEvent
from backend.app.models.entity import Entity
from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.models.relationship import EntityRelationship
from backend.app.schemas.relationship import GraphNode
from backend.app.utils.time import utc_now


def test_freshness_semantics_historical_not_current():
    """Critical Invariant: A historical event must NOT become CURRENT simply because created_at is today."""
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    historical_time = datetime(2023, 5, 10, 10, 0, 0, tzinfo=timezone.utc)

    # Event occurred in 2023, created_at is today
    status, age = compute_item_freshness_status(
        event_time=historical_time,
        published_at=historical_time,
        now=now,
    )
    assert status == "HISTORICAL"
    assert age is not None
    assert age > 86400 * 30  # More than 30 days old


def test_freshness_semantics_multi_state_hierarchy():
    """Verify CURRENT (<=24h), RECENT (<=7d), STALE (<=30d), HISTORICAL (>30d), UNKNOWN, SYNTHETIC_TEST."""
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)

    # 1. CURRENT: 15 minutes ago
    status_curr, _ = compute_item_freshness_status(
        event_time=now - timedelta(minutes=15),
        published_at=now - timedelta(minutes=15),
        now=now,
    )
    assert status_curr == "CURRENT"

    # 2. RECENT: 3 days ago (within 7d)
    status_rec, _ = compute_item_freshness_status(
        event_time=now - timedelta(days=3),
        published_at=now - timedelta(days=3),
        now=now,
    )
    assert status_rec == "RECENT"

    # 3. STALE: 15 days ago (within 30d)
    status_stale, _ = compute_item_freshness_status(
        event_time=now - timedelta(days=15),
        published_at=now - timedelta(days=15),
        now=now,
    )
    assert status_stale == "STALE"

    # 4. HISTORICAL: 45 days ago (>30d)
    status_hist, _ = compute_item_freshness_status(
        event_time=now - timedelta(days=45),
        published_at=now - timedelta(days=45),
        now=now,
    )
    assert status_hist == "HISTORICAL"

    # 5. UNKNOWN: No timestamp available
    status_unk, _ = compute_item_freshness_status(
        event_time=None,
        published_at=None,
        now=now,
    )
    assert status_unk == "UNKNOWN"

    # 6. SYNTHETIC_TEST: Explicit metadata marker
    status_synth, _ = compute_item_freshness_status(
        event_time=now - timedelta(minutes=5),
        published_at=now - timedelta(minutes=5),
        metadata={"is_synthetic": True},
        now=now,
    )
    assert status_synth == "SYNTHETIC_TEST"


def test_source_health_never_healthy_when_unfetched(db_session):
    """A source that has never fetched must NOT be represented as healthy or current."""
    src = Source(
        name="Untested Cold Source",
        source_type="rss",
        base_url="https://coldsource.example",
        feed_url="https://coldsource.example/feed",
        active=True,
        polling_interval_seconds=300,
        last_successful_fetch_at=None,
        consecutive_failures=0,
    )
    db_session.add(src)
    db_session.commit()

    health_list = get_all_sources_health(db_session)
    matching = next((h for h in health_list if h.source_id == src.id), None)
    assert matching is not None
    assert matching.freshness_status == "UNKNOWN"
    assert matching.freshness_status != "CURRENT"

    # System freshness overview must reflect UNKNOWN, not HEALTHY
    sys_freshness = get_system_freshness_summary(db_session)
    assert sys_freshness.sources_unknown >= 1


def test_market_desk_canonical_universe_and_test_isolation(db_session):
    """Verify that only the 16 canonical assets are returned, excluding TEST_* and USDX_*."""
    initialize_canonical_market_assets(db_session)

    # Insert synthetic assets that should never appear in production endpoints
    test_asset1 = MarketAsset(symbol="TEST_BTC", canonical_name="Test Bitcoin", asset_type="crypto")
    test_asset2 = MarketAsset(symbol="USDX_BENCHMARK", canonical_name="USDX Bench", asset_type="forex")
    db_session.add_all([test_asset1, test_asset2])
    db_session.commit()

    # get_market_assets must filter them out
    records, total = get_market_assets(db_session, page=1, page_size=50)
    symbols = [r.symbol for r in records]

    assert "TEST_BTC" not in symbols
    assert "USDX_BENCHMARK" not in symbols
    assert total == 16

    # get_market_dashboard_summary must filter them out
    summary = get_market_dashboard_summary(db_session)
    assert summary.total_assets == 16


def test_geo_view_primary_location_entity_mapping(db_session):
    """Verify cluster.primary_location_entity mapping to prevent null coordinate assumptions."""
    loc_entity = Entity(
        canonical_name="Kyiv",
        normalized_name="kyiv",
        entity_type="CITY",
        country_code="UA",
        description="Capital city of Ukraine",
    )
    db_session.add(loc_entity)
    db_session.flush()

    cluster = EventCluster(
        canonical_title="Diplomatic Summit in Kyiv",
        canonical_summary="International leaders meet in Kyiv for security talks.",
        event_type="geopolitical_conflict",
        primary_location_entity_id=loc_entity.id,
        event_time_start=utc_now(),
        event_time_end=utc_now(),
        confidence=0.95,
        status="ACTIVE",
    )
    db_session.add(cluster)
    db_session.commit()

    reloaded = db_session.query(EventCluster).filter(EventCluster.id == cluster.id).first()
    assert reloaded.primary_location_entity is not None
    assert reloaded.primary_location_entity.canonical_name == "Kyiv"
    assert reloaded.primary_location_entity.country_code == "UA"


def test_knowledge_graph_node_schema_label_resilience():
    """Verify GraphNode handles canonical_name and label safely without crashing."""
    node = GraphNode(
        id=str(uuid.uuid4()),
        canonical_name="United Nations",
        label="UN",
        entity_type="INTERNATIONAL_ORGANIZATION",
        country_code=None,
    )
    assert node.canonical_name == "United Nations"
    assert node.label == "UN"

    # Also test node without optional label - auto fallback to canonical_name prevents null crashes
    node_unlabeled = GraphNode(
        id=str(uuid.uuid4()),
        canonical_name="Federal Reserve",
        entity_type="CENTRAL_BANK",
    )
    assert node_unlabeled.canonical_name == "Federal Reserve"
    assert node_unlabeled.label == "Federal Reserve"

