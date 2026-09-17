"""
V0.7.1 Comprehensive Services & Adapters Coverage Test Suite.
Tests freshness telemetry, live intelligence feed filtering & batch loaders,
deterministic alerts & non-causal linting, market data services, and collector edge cases.
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.event import ExtractedEvent
from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.models.indicator import EconomicIndicator
from backend.app.models.observation import EconomicObservation
from backend.app.models.market_asset import MarketAsset
from backend.app.models.market_observation import MarketObservation
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.models.alert import Alert
from backend.app.services.freshness_service import (
    get_system_freshness_summary,
    get_all_sources_health,
)
from backend.app.services.live_feed_service import get_live_intelligence_feed
from backend.app.services.alert_service import (
    evaluate_event_alerts,
    _assert_non_causal,
    list_alerts,
    get_alert_by_id,
    acknowledge_alert,
)
from backend.app.services.market_service import (
    get_asset_observations,
    store_market_observations,
    get_market_dashboard_summary,
    get_or_create_market_asset,
)
from backend.app.collectors.rss import RSSCollector
from backend.app.collectors.api import APICollector
from backend.app.market.providers import CryptoMarketProvider
from backend.app.utils.time import utc_now


# =====================================================================
# 1. Freshness Service Telemetry Tests
# =====================================================================
def test_freshness_service_all_status_branches(db_session):
    """Verify get_system_freshness_summary across UNKNOWN, HEALTHY, STALE, and DEGRADED states."""
    now = utc_now()

    # Empty DB -> UNKNOWN
    s_empty = get_system_freshness_summary(db_session)
    assert s_empty.system_status == "UNKNOWN"

    # 1 source with recent successful fetch -> HEALTHY
    src_healthy = Source(
        name="Healthy Src",
        source_type="rss",
        base_url="https://h.example",
        feed_url="https://h.example/rss",
        active=True,
        polling_interval_seconds=300,
        last_successful_fetch_at=now - timedelta(minutes=5),
        last_attempted_fetch_at=now - timedelta(minutes=5),
        consecutive_failures=0,
    )
    db_session.add(src_healthy)
    db_session.flush()

    s_healthy = get_system_freshness_summary(db_session)
    assert s_healthy.system_status == "HEALTHY"

    # Add 1 failing source -> DEGRADED
    src_failed = Source(
        name="Failed Src",
        source_type="rss",
        base_url="https://f.example",
        feed_url="https://f.example/rss",
        active=True,
        polling_interval_seconds=300,
        last_successful_fetch_at=None,
        last_attempted_fetch_at=now - timedelta(minutes=2),
        consecutive_failures=4,
    )
    db_session.add(src_failed)
    db_session.flush()

    s_degraded = get_system_freshness_summary(db_session)
    assert s_degraded.system_status == "DEGRADED"

    # Test backlog age and latencies
    doc_backlog = Document(
        source_id=src_healthy.id,
        title="Backlog item",
        url="https://h.example/b1",
        published_at=now - timedelta(hours=2),
        ingested_at=now - timedelta(hours=1),
        processing_status="RAW",
        content_hash="bh1",
    )
    doc_extracted = Document(
        source_id=src_healthy.id,
        title="Extracted item",
        url="https://h.example/e1",
        published_at=now - timedelta(minutes=30),
        ingested_at=now - timedelta(minutes=20),
        processing_status="EXTRACTED",
        content_hash="eh1",
    )
    db_session.add_all([doc_backlog, doc_extracted])
    db_session.commit()

    summary_with_docs = get_system_freshness_summary(db_session)
    assert summary_with_docs.pending_backlog_count >= 1
    assert summary_with_docs.oldest_backlog_document_age_seconds is not None
    assert summary_with_docs.median_ingestion_latency_seconds is not None


# =====================================================================
# 2. Live Intelligence Feed Filter & Batch Loader Tests
# =====================================================================
def test_live_feed_service_comprehensive(db_session):
    """Verify live intelligence feed with all filters and batch-loaded context."""
    now = utc_now()

    # Empty feed returns cleanly
    empty_items, total, counts = get_live_intelligence_feed(db_session)
    assert empty_items == []
    assert total == 0

    # Create full relational hierarchy
    src = Source(
        name="BBC World News",
        source_type="rss",
        base_url="https://bbc.example",
        feed_url="https://bbc.example/rss",
        active=True,
    )
    db_session.add(src)
    db_session.flush()

    doc = Document(
        source_id=src.id,
        title="Federal Reserve Announces Benchmark Rate",
        url="https://bbc.example/fed",
        published_at=now - timedelta(hours=2),
        ingested_at=now - timedelta(hours=1),
        processing_status="EXTRACTED",
        content_hash="fed_live_hash",
    )
    db_session.add(doc)
    db_session.flush()

    loc = Entity(
        canonical_name="Washington",
        normalized_name="washington",
        entity_type="CITY",
        country_code="US",
    )
    actor = Entity(
        canonical_name="Federal Reserve",
        normalized_name="federal reserve",
        entity_type="CENTRAL_BANK",
        country_code="US",
    )
    db_session.add_all([loc, actor])
    db_session.flush()

    doc_entity = DocumentEntity(
        document_id=doc.id,
        entity_id=actor.id,
        mention_text="Federal Reserve",
        entity_role="actor",
        confidence=0.95,
    )
    db_session.add(doc_entity)

    event = ExtractedEvent(
        document_id=doc.id,
        event_type="central_bank_decision",
        event_title="Fed Benchmark Rate Decision",
        event_summary="The Federal Reserve announced rates in Washington.",
        event_time=now - timedelta(hours=2),
        location_entity_id=loc.id,
        confidence=0.95,
        importance=0.90,
    )
    db_session.add(event)
    db_session.flush()

    cluster = EventCluster(
        canonical_title="Global Central Bank Rate Actions",
        canonical_summary="Central banks adjust monetary policy.",
        event_type="central_bank_decision",
        confidence=0.95,
        status="ACTIVE",
    )
    db_session.add(cluster)
    db_session.flush()

    member = EventClusterMember(event_cluster_id=cluster.id, extracted_event_id=event.id, membership_score=0.95)
    db_session.add(member)

    # Economic Observation
    ind = EconomicIndicator(
        canonical_name="Federal Funds Rate",
        normalized_name="federal funds rate",
        indicator_type="INTEREST_RATE",
        economic_domain="MONETARY_POLICY",
    )
    db_session.add(ind)
    db_session.flush()

    obs = EconomicObservation(
        indicator_id=ind.id,
        event_id=event.id,
        document_id=doc.id,
        reported_value=5.5,
        reported_unit="percent",
        direction="HOLD",
        economic_relevance=0.9,
    )
    db_session.add(obs)

    # Market Asset & Correlation
    asset = MarketAsset(symbol="US10Y", canonical_name="US 10-Year Yield", asset_type="rates")
    db_session.add(asset)
    db_session.flush()

    corr = EventMarketCorrelation(
        event_id=event.id,
        cluster_id=cluster.id,
        market_asset_id=asset.id,
        window_size="1h",
        window_start=now - timedelta(hours=3),
        window_end=now - timedelta(hours=1),
        calculated_at=utc_now(),
        return_percent=-0.05,
        volume_change=12.0,
        metadata_={"neutral_observation": "Yield observed following rate decision"},
    )
    db_session.add(corr)

    # Alert
    alert = Alert(
        trigger_type="HIGH_IMPORTANCE_EVENT",
        alert_title="High Importance Rate Decision",
        explanation="Observational alert on benchmark rate.",
        evidence="Verbatim announcement in Washington.",
        affected_event_id=event.id,
        status="ACTIVE",
    )
    db_session.add(alert)
    db_session.commit()

    # Query 1: Default
    items, total, stats = get_live_intelligence_feed(db_session)
    assert total == 1
    assert len(items) == 1
    assert items[0].event_title == "Fed Benchmark Rate Decision"
    assert items[0].source_name == "BBC World News"
    assert items[0].primary_location == "Washington"
    assert items[0].cluster_id == cluster.id
    assert len(items[0].entities) >= 1
    assert len(items[0].economic_context) >= 1
    assert len(items[0].market_context) >= 1
    assert len(items[0].active_alerts) >= 1

    # Query 2: Filter by event_type matching
    items_type, _, _ = get_live_intelligence_feed(db_session, event_type="central_bank")
    assert len(items_type) == 1

    # Query 3: Filter by event_type non-matching
    items_non_match, _, _ = get_live_intelligence_feed(db_session, event_type="conflict")
    assert len(items_non_match) == 0

    # Query 4: Filter by hours
    items_hours, _, _ = get_live_intelligence_feed(db_session, hours=24)
    assert len(items_hours) == 1

    # Query 5: Filter by min_importance
    items_imp, _, _ = get_live_intelligence_feed(db_session, min_importance=0.8)
    assert len(items_imp) == 1
    items_high_imp, _, _ = get_live_intelligence_feed(db_session, min_importance=0.99)
    assert len(items_high_imp) == 0


# =====================================================================
# 3. Alert Service & Non-Causal Linter Tests
# =====================================================================
def test_alert_service_and_non_causal_linter(db_session):
    """Verify deterministic alert generation, deduplication, non-causal linter, and management."""
    # Test linter
    with pytest.raises(ValueError, match="Prohibited causal claim"):
        _assert_non_causal("The conflict caused market panic.")

    with pytest.raises(ValueError, match="Prohibited causal claim"):
        _assert_non_causal("Rate hikes led to bond selloffs.")

    # Valid non-causal statement passes
    _assert_non_causal("Bond yields changed by 5 bps following the policy meeting.")

    # Non-existent event returns empty
    assert evaluate_event_alerts(db_session, uuid.uuid4()) == []

    # Create event eligible for HIGH_IMPORTANCE_EVENT and CENTRAL_BANK_DECISION
    s = Source(name="Wire", source_type="rss", base_url="https://w.example", feed_url="https://w.example/rss", active=True)
    db_session.add(s)
    db_session.flush()

    doc = Document(source_id=s.id, title="Doc 1", url="https://w.example/1", published_at=utc_now(), processing_status="RAW", content_hash="h_w1")
    db_session.add(doc)
    db_session.flush()

    event = ExtractedEvent(
        document_id=doc.id,
        event_type="central_bank_decision",
        event_title="Central Bank Policy Shift",
        event_summary="Benchmark rates adjusted in Zurich.",
        event_time=utc_now(),
        confidence=0.92,
        importance=0.88,
    )
    db_session.add(event)
    db_session.commit()

    alerts = evaluate_event_alerts(db_session, event.id)
    assert len(alerts) >= 1
    alert_id = alerts[0].id

    # Deduplication test: Running evaluation again should return 0 new alerts
    dupe_alerts = evaluate_event_alerts(db_session, event.id)
    assert len(dupe_alerts) == 0

    # Alert management functions
    alert_obj = get_alert_by_id(db_session, alert_id)
    assert alert_obj is not None

    ack = acknowledge_alert(db_session, alert_id, note="Reviewed by analyst")
    assert ack.status == "ACKNOWLEDGED"

    alert_list, count = list_alerts(db_session, status="ACKNOWLEDGED")
    assert count >= 1


def test_api_alerts_endpoints(client, db_session):
    """Verify FastAPI /api/v1/alerts endpoints."""
    alert = Alert(
        trigger_type="HIGH_IMPORTANCE_EVENT",
        alert_title="Test Alert",
        explanation="Non-causal test explanation.",
        evidence="Verbatim test alert evidence.",
        status="ACTIVE",
    )
    db_session.add(alert)
    db_session.commit()

    # List alerts
    resp_list = client.get("/api/v1/alerts")
    assert resp_list.status_code == 200
    assert resp_list.json()["total"] >= 1

    # Get single alert
    resp_get = client.get(f"/api/v1/alerts/{alert.id}")
    assert resp_get.status_code == 200

    # Acknowledge
    resp_ack = client.post(f"/api/v1/alerts/{alert.id}/acknowledge", json={"note": "Verified"})
    assert resp_ack.status_code == 200
    assert resp_ack.json()["status"] == "ACKNOWLEDGED"



# =====================================================================
# 4. Market Service & Providers Edge Case Tests
# =====================================================================
def test_market_service_edge_cases(db_session):
    """Verify tzinfo handling, empty observations, and top movers with prior candle."""
    now = datetime(2026, 9, 12, 12, 0, 0)  # naive datetime

    # get_or_create_market_asset
    asset = get_or_create_market_asset(
        db=db_session,
        symbol="ETH-USD",
        canonical_name="Ethereum",
        asset_type="crypto",
    )
    assert asset.symbol == "ETH-USD"

    # Query with naive from_time and to_time
    obs_list = get_asset_observations(
        db=db_session,
        asset_id=asset.id,
        from_time=now - timedelta(days=1),
        to_time=now,
    )
    assert obs_list == []

    # store_market_observations with empty list
    count, report = store_market_observations(db_session, [], asset_id=asset.id)
    assert count == 0
    assert report.duplicate_count == 0

    # Top movers calculation with latest and prev candle
    obs_prev = MarketObservation(
        market_asset_id=asset.id,
        timestamp=utc_now() - timedelta(hours=25),
        open=2500.0,
        high=2550.0,
        low=2480.0,
        close=2500.0,
        volume=100.0,
        interval="1h",
        source="test_provider",
    )
    obs_latest = MarketObservation(
        market_asset_id=asset.id,
        timestamp=utc_now(),
        open=2600.0,
        high=2650.0,
        low=2590.0,
        close=2625.0,
        volume=150.0,
        interval="1h",
        source="test_provider",
    )
    db_session.add_all([obs_prev, obs_latest])
    db_session.commit()

    summary = get_market_dashboard_summary(db_session)
    assert summary.total_observations >= 2
    eth_mover = next((m for m in summary.top_movers if m["symbol"] == "ETH-USD"), None)
    assert eth_mover is not None
    assert eth_mover["return_24h"] == 5.0  # (2625 / 2500 - 1) * 100 = 5.0%


def test_binance_provider_mocked():
    """Verify CryptoMarketProvider methods with mocked HTTP responses."""
    provider = CryptoMarketProvider()
    assert provider.provider_name in ("Binance", "BinancePublicAPI")
    assert "BTC-USD" in provider.supported_symbols()

    # Mock historical bars
    mock_kline = [
        [1700000000000, "65000.0", "65500.0", "64900.0", "65200.0", "125.0", 1700003600000, "8150000.0", 120, "60.0", "3900000.0", "0"]
    ]
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_kline
        mock_get.return_value = mock_resp

        bars = provider.fetch_historical_bars(symbol="BTC-USD", interval="1h", limit=1)
        assert len(bars) == 1
        assert bars[0].close == 65200.0

        latest = provider.fetch_latest_bar(symbol="BTC-USD")
        assert latest is not None
        assert latest.close == 65200.0


# =====================================================================
# 5. Collectors Parser & Error Edge Case Tests
# =====================================================================
def test_rss_collector_normalization_branches():
    """Verify RSSCollector entry variations and fallback behavior."""
    collector = RSSCollector(name="Test RSS", feed_url="https://rss.example/feed", base_url="https://rss.example")

    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <link>https://rss.example</link>
        <item>
          <title>Article One</title>
          <link>https://rss.example/1</link>
          <description>Summary text 1</description>
        </item>
        <item>
          <title>Article Two</title>
          <link>https://rss.example/2</link>
          <description>Summary text 2</description>
        </item>
      </channel>
    </rss>
    """
    docs = collector.parse_and_normalize(sample_xml)
    assert len(docs) == 2
    assert docs[0].title == "Article One"
    assert docs[1].title == "Article Two"

    # Malformed XML without entries should raise ValueError
    with pytest.raises(ValueError, match="Malformed RSS feed"):
        collector.parse_and_normalize("invalid xml content <<>>")


def test_api_collector_normalization_branches():
    """Verify APICollector path traversal, date fallbacks, and error branches."""
    collector = APICollector(
        name="Test API",
        feed_url="https://api.example/articles",
        base_url="https://api.example",
        config_metadata={"items_path": "data.articles"},
    )

    nested_data = {
        "data": {
            "articles": [
                {"title": "API Post 1", "url": "https://api.example/1", "published_at": "2026-09-11T12:00:00Z"},
                {"title": "API Post 2", "url": "https://api.example/2", "published_at": "invalid-date"},
                {"title": "", "url": ""},  # empty -> skipped
            ]
        }
    }
    docs = collector.parse_and_normalize(nested_data)
    assert len(docs) == 2
    assert docs[0].title == "API Post 1"
    assert docs[1].title == "API Post 2"

    assert len(docs) == 2
    assert docs[0].title == "API Post 1"
    assert docs[1].title == "API Post 2"
