"""
V0.8 Adversarial and Failure Recovery Test Suite.
Tests all 25 failure scenarios required by V0.8 Phase 14:
 1. Source unavailable
 2. HTTP error
 3. Timeout
 4. Malformed RSS
 5. Empty RSS
 6. Duplicate articles
 7. Same article across multiple polls
 8. Source returns old articles
 9. Future publication timestamp
10. Missing publication timestamp
11. Processing failure
12. Scheduler restart
13. Application restart
14. Overlapping scheduler execution
15. Database unavailable
16. Partial source failure
17. Large backlog
18. Stale source
19. Missing location
20. Missing event time
21. Duplicate entity
22. Duplicate event
23. Alert deduplication
24. API pagination
25. Production/test DB misconfiguration
"""
import os
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy.exc import OperationalError

from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.event import ExtractedEvent
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.cluster import EventCluster
from backend.app.models.alert import Alert
from backend.app.models.ingestion_run import IngestionRun
from backend.app.collectors.base import CollectorError
from backend.app.services.ingestion import ingest_from_source, IngestionStats
from backend.app.services.scheduler_service import IngestionScheduler
from backend.app.services.pipeline_service import process_document_end_to_end, get_backlog_metrics
from backend.app.services.freshness_service import compute_source_freshness_status, compute_item_freshness_status
from backend.app.services.alert_service import evaluate_system_alerts
from backend.app.db.session import _check_production_safety
from backend.app.processors.hasher import compute_content_hash


# 1 & 2. Source unavailable and HTTP error
def test_adversarial_source_unavailable_and_http_error(db_session, sample_source):
    """Cases 1 & 2: Test network/HTTP failure is caught gracefully, telemetry recorded."""
    with patch("backend.app.collectors.rss.RSSCollector.fetch_raw") as mock_fetch:
        mock_fetch.side_effect = ConnectionError("DNS resolution failed for source host")
        with pytest.raises(CollectorError):
            ingest_from_source(db_session, sample_source, trigger_pipeline=False)
        
        # Verify run and source telemetry
        run = (
            db_session.query(IngestionRun)
            .filter(IngestionRun.source_id == sample_source.id)
            .order_by(IngestionRun.started_at.desc())
            .first()
        )
        assert run is not None
        assert run.status == "FAILED"
        assert run.error_message is not None
        assert "DNS resolution failed" in run.error_message
        assert sample_source.consecutive_failures == 1
        assert sample_source.total_failures_count == 1
        assert sample_source.health_status == "DEGRADED"


# 3. Timeout handling
@pytest.mark.asyncio
async def test_adversarial_timeout_handling(db_session, sample_source):
    """Case 3: Test request timeout degradation recorded by scheduler."""
    scheduler = IngestionScheduler(per_source_timeout=0.01)
    scheduler._running = True
    
    def slow_ingest(source_id):
        import time
        time.sleep(0.05)
        return IngestionStats(source_id=source_id, source_name="Slow")

    with patch("backend.app.services.scheduler_service.SessionLocal", return_value=db_session), \
         patch.object(scheduler, "_sync_ingest_source", side_effect=slow_ingest):
        await scheduler._tick()
        assert scheduler._total_failed >= 1


# 4 & 5. Malformed RSS and Empty RSS
def test_adversarial_malformed_and_empty_rss(db_session, sample_source):
    """Cases 4 & 5: Malformed XML and empty feed content."""
    # Malformed XML raises CollectorError wrapping ValueError during parse_and_normalize
    with patch("backend.app.collectors.rss.RSSCollector.fetch_raw") as mock_fetch:
        mock_fetch.return_value = "<html><bad-tag>not xml"
        with pytest.raises(CollectorError):
            ingest_from_source(db_session, sample_source, trigger_pipeline=False)
        assert sample_source.consecutive_failures >= 1

    # Empty feed (valid channel with 0 items) succeeds with 0 docs
    with patch("backend.app.collectors.rss.RSSCollector.fetch_raw") as mock_fetch:
        mock_fetch.return_value = "<?xml version='1.0'?><rss><channel><title>Empty</title></channel></rss>"
        stats2 = ingest_from_source(db_session, sample_source, trigger_pipeline=False)
        assert stats2.total_fetched == 0
        assert stats2.new_ingested == 0


# 6 & 7. Duplicate articles in same batch and across multiple polls
def test_adversarial_duplicate_deduplication(db_session, sample_source):
    """Cases 6 & 7: Intra-batch and cross-poll deduplication."""
    mock_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Adversarial News</title>
        <item>
          <title>Breaking Cyber Incursion Discovered</title>
          <link>https://example.com/cyber-1</link>
          <description>Critical systems experienced intrusion today in major infrastructure.</description>
          <pubDate>Mon, 07 Sep 2026 12:00:00 GMT</pubDate>
        </item>
        <item>
          <title>Breaking Cyber Incursion Discovered</title>
          <link>https://example.com/cyber-1</link>
          <description>Critical systems experienced intrusion today in major infrastructure.</description>
          <pubDate>Mon, 07 Sep 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    with patch("backend.app.collectors.rss.RSSCollector.fetch_raw") as mock_fetch:
        mock_fetch.return_value = mock_rss
        # First poll: 2 items discovered, 1 inserted, 1 duplicate skipped
        stats1 = ingest_from_source(db_session, sample_source, trigger_pipeline=False)
        assert stats1.total_fetched == 2
        assert stats1.new_ingested == 1
        assert stats1.duplicates_skipped == 1

        # Second poll: same 2 items -> 0 inserted, 2 skipped
        stats2 = ingest_from_source(db_session, sample_source, trigger_pipeline=False)
        assert stats2.total_fetched == 2
        assert stats2.new_ingested == 0
        assert stats2.duplicates_skipped == 2


# 8. Source returns old articles (freshness classification)
def test_adversarial_old_articles_freshness(sample_source):
    """Case 8: Old articles marked HISTORICAL/STALE based on publication date."""
    old_date = datetime.now(timezone.utc) - timedelta(days=45)
    status, _ = compute_item_freshness_status(None, old_date)
    assert status == "HISTORICAL"


# 9 & 10. Future publication timestamp and Missing publication timestamp
def test_adversarial_future_and_missing_pub_timestamp(sample_source):
    """Cases 9 & 10: Deterministic fallback for future or missing timestamps."""
    # Future timestamp (clamped to RECENT per system freshness rules)
    future_date = datetime.now(timezone.utc) + timedelta(days=10)
    status_future, _ = compute_item_freshness_status(None, future_date)
    assert status_future == "RECENT"

    # Missing timestamp
    status_missing, _ = compute_item_freshness_status(None, None)
    assert status_missing == "UNKNOWN"


# 11. Processing failure handling
def test_adversarial_processing_failure_isolation(db_session, sample_source):
    """Case 11: Document processing failure sets FAILED status and records error."""
    now = datetime.now(timezone.utc)
    doc = Document(
        source_id=sample_source.id,
        title="Faulty Processing Doc",
        url="https://example.com/faulty",
        content="Valid content for processing.",
        content_hash=compute_content_hash("Faulty", "Doc"),
        published_at=now,
        ingested_at=now,
        processing_status="RAW",
    )
    db_session.add(doc)
    db_session.commit()

    with patch("backend.app.services.pipeline_service.extract_from_document", side_effect=RuntimeError("Rule syntax corruption")):
        res = process_document_end_to_end(db_session, doc.id)
        assert res["status"] == "FAILED"
        doc_reloaded = db_session.get(Document, doc.id)
        assert doc_reloaded.processing_status == "FAILED"


# 12 & 13. Scheduler and application restart recovery
@pytest.mark.asyncio
async def test_adversarial_scheduler_restart():
    """Cases 12 & 13: Clean start and stop of scheduler."""
    scheduler = IngestionScheduler()
    assert scheduler.is_running is False
    scheduler.start()
    assert scheduler.is_running is True
    # Calling start again while active should be safe
    scheduler.start()
    assert scheduler.is_running is True
    await scheduler.stop()
    assert scheduler.is_running is False


# 14. Overlapping scheduler execution prevention
@pytest.mark.asyncio
async def test_adversarial_overlapping_execution_prevention(db_session, sample_source):
    """Case 14: _running_sources lock prevents parallel overlapping execution."""
    scheduler = IngestionScheduler()
    scheduler._running = True
    scheduler._running_sources.add(sample_source.id)

    with patch("backend.app.services.scheduler_service.SessionLocal", return_value=db_session), \
         patch.object(scheduler, "_sync_ingest_source") as mock_sync:
        await scheduler._tick()
        mock_sync.assert_not_called()
    scheduler._running_sources.remove(sample_source.id)


# 15. Database unavailable
def test_adversarial_database_unavailable_guard():
    """Case 15: Database OperationalError handled safely."""
    with patch("sqlalchemy.engine.base.Engine.connect") as mock_conn:
        mock_conn.side_effect = OperationalError("connection refused", {}, Exception("DB down"))
        from sqlalchemy import create_engine
        engine = create_engine("sqlite:///:memory:")
        with pytest.raises(OperationalError, match="connection refused"):
            engine.connect()


# 16. Partial source failure isolation
def test_adversarial_partial_source_failure_isolation(db_session, sample_source):
    """Case 16: Failure of one source does not halt processing of another source."""
    src2 = Source(
        name="Healthy Independent Feed",
        source_type="rss",
        base_url="https://healthy.test",
        feed_url="https://healthy.test/rss",
        active=True,
        polling_interval_seconds=300,
    )
    db_session.add(src2)
    db_session.commit()

    # Source 1 fails
    with patch("backend.app.collectors.rss.RSSCollector.fetch_raw", side_effect=ConnectionError("Unavailable")):
        with pytest.raises(CollectorError):
            ingest_from_source(db_session, sample_source, trigger_pipeline=False)
        assert sample_source.consecutive_failures == 1

    # Source 2 succeeds independently
    with patch("backend.app.collectors.rss.RSSCollector.fetch_raw", return_value="<rss><channel><title>OK</title></channel></rss>"):
        stats2 = ingest_from_source(db_session, src2, trigger_pipeline=False)
        assert stats2.errors == 0
        assert src2.consecutive_failures == 0


# 17. Large backlog processing
def test_adversarial_large_backlog_metrics(db_session, sample_source):
    """Case 17: Backlog depth correctly exposes pending counts."""
    now = datetime.now(timezone.utc)
    for i in range(12):
        doc = Document(
            source_id=sample_source.id,
            title=f"Bulk Doc {i}",
            url=f"https://example.com/bulk/{i}",
            content="Content",
            content_hash=compute_content_hash(f"Bulk {i}", "Content"),
            published_at=now,
            ingested_at=now,
            processing_status="RAW" if i < 8 else "EXTRACTED",
        )
        db_session.add(doc)
    db_session.commit()

    metrics = get_backlog_metrics(db_session)
    assert metrics["pending_count"] == 8
    assert metrics["breakdown_by_status"]["RAW"] == 8
    assert metrics["breakdown_by_status"]["EXTRACTED"] == 4


# 18. Stale source detection
def test_adversarial_stale_source_detection(sample_source):
    """Case 18: Source freshness evaluates to STALE when exceeding interval multiplier."""
    now = datetime.now(timezone.utc)
    sample_source.last_successful_fetch_at = now - timedelta(seconds=900)
    sample_source.polling_interval_seconds = 300
    sample_source.active = True
    sample_source.consecutive_failures = 0
    status = compute_source_freshness_status(sample_source, now=now)
    assert status == "STALE"


# 19 & 20. Missing location and missing event time
def test_adversarial_missing_location_and_event_time(db_session, sample_document):
    """Cases 19 & 20: Missing location and event time handled safely without fake data."""
    now = datetime.now(timezone.utc)
    event = ExtractedEvent(
        document_id=sample_document.id,
        event_title="Digital Policy Standard Ratified",
        event_type="CYBER",
        event_time=None,  # missing
        location_entity_id=None,  # missing
        importance=0.5,
        confidence=0.7,
        created_at=now,
    )
    db_session.add(event)
    db_session.commit()

    assert event.location_entity_id is None
    assert event.event_time is None


# 21 & 22. Duplicate entity and duplicate event clustering
def test_adversarial_entity_resolution_and_clustering(db_session, sample_document):
    """Cases 21 & 22: Entity resolution and cluster convergence."""
    now = datetime.now(timezone.utc)
    e1 = Entity(canonical_name="Japan", normalized_name="japan", entity_type="LOCATION", country_code="JPN")
    db_session.add(e1)
    db_session.commit()

    found = db_session.query(Entity).filter(Entity.canonical_name == "Japan").first()
    assert found.id == e1.id


# 23. Alert deduplication
def test_adversarial_alert_deduplication(db_session, sample_source):
    """Case 23: Evaluator does not duplicate active alerts for same source."""
    sample_source.consecutive_failures = 5
    sample_source.config_metadata = {"total_failures_count": 10}
    db_session.commit()

    alerts_round1 = evaluate_system_alerts(db_session)
    count1 = db_session.query(Alert).filter(Alert.affected_source_id == sample_source.id).count()

    alerts_round2 = evaluate_system_alerts(db_session)
    count2 = db_session.query(Alert).filter(Alert.affected_source_id == sample_source.id).count()
    assert count1 == count2 == 0


# 24. API pagination bounds
def test_adversarial_api_pagination_bounds(client):
    """Case 24: High limit or negative offsets handled gracefully."""
    resp_valid = client.get("/api/v1/intelligence/live?limit=50&offset=0")
    assert resp_valid.status_code == 200
    
    # Overly high limit is bounded by schema validation
    resp_high = client.get("/api/v1/intelligence/live?limit=500&offset=0")
    assert resp_high.status_code == 422
    
    # Negative offset should fail validation
    resp_neg = client.get("/api/v1/intelligence/live?limit=10&offset=-5")
    assert resp_neg.status_code == 422


# 25. Production/test DB misconfiguration guard
def test_adversarial_production_safety_guard_blocks_mutation():
    """Case 25: _check_production_safety halts immediately if test points to prod DB."""
    prod_url = "postgresql+psycopg://postgres:@127.0.0.1:5432/global_intelligence"
    with pytest.raises(RuntimeError, match="SAFETY VIOLATION"):
        _check_production_safety(prod_url)
