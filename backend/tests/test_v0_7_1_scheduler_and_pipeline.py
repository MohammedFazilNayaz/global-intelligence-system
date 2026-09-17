"""
V0.7.1 Test Suite for Ingestion Scheduler, Pipeline Service, and Ingestion API.
Tests scheduler lifecycle, worker failure isolation, timeout handling, backlog recovery,
end-to-end pipeline processing, and REST endpoints.
"""
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.ingestion_run import IngestionRun
from backend.app.models.event import ExtractedEvent
from backend.app.models.cluster import EventCluster
from backend.app.services.scheduler_service import IngestionScheduler
from backend.app.services import pipeline_service
from backend.app.services.ingestion import IngestionStats
from backend.app.utils.time import utc_now


@pytest.mark.asyncio
async def test_scheduler_start_stop_lifecycle():
    """Verify IngestionScheduler starts, handles redundant start, and cleanly shuts down."""
    scheduler = IngestionScheduler(check_interval_seconds=1, per_source_timeout=2)
    assert not scheduler.is_running

    # Start
    scheduler.start()
    assert scheduler.is_running

    # Redundant start should be a safe no-op
    scheduler.start()
    assert scheduler.is_running

    # Stop
    await scheduler.stop()
    assert not scheduler.is_running

    # Redundant stop should be a safe no-op
    await scheduler.stop()
    assert not scheduler.is_running


@pytest.mark.asyncio
async def test_scheduler_tick_due_sources_and_backoff(db_session):
    """Verify _tick calculates due sources with exponential backoff on consecutive failures."""
    now = utc_now()

    # Source 1: Fresh, never fetched -> due
    s1 = Source(
        name="Source 1 Due",
        source_type="rss",
        base_url="https://s1.example",
        feed_url="https://s1.example/rss",
        active=True,
        polling_interval_seconds=60,
        last_attempted_fetch_at=None,
        consecutive_failures=0,
    )
    # Source 2: Fetched 30s ago, interval 60s -> NOT due
    s2 = Source(
        name="Source 2 Not Due",
        source_type="rss",
        base_url="https://s2.example",
        feed_url="https://s2.example/rss",
        active=True,
        polling_interval_seconds=60,
        last_attempted_fetch_at=now - timedelta(seconds=30),
        consecutive_failures=0,
    )
    # Source 3: Fetched 70s ago, interval 60s, but 2 consecutive failures -> backoff interval is 60 * 1.5^2 = 135s -> NOT due
    s3 = Source(
        name="Source 3 Backoff",
        source_type="rss",
        base_url="https://s3.example",
        feed_url="https://s3.example/rss",
        active=True,
        polling_interval_seconds=60,
        last_attempted_fetch_at=now - timedelta(seconds=70),
        consecutive_failures=2,
    )
    # Source 4: Inactive -> NOT due
    s4 = Source(
        name="Source 4 Inactive",
        source_type="rss",
        base_url="https://s4.example",
        feed_url="https://s4.example/rss",
        active=False,
        polling_interval_seconds=60,
        last_attempted_fetch_at=None,
        consecutive_failures=0,
    )
    db_session.add_all([s1, s2, s3, s4])
    db_session.commit()

    scheduler = IngestionScheduler(check_interval_seconds=1, per_source_timeout=2)
    scheduler._running = True

    with patch("backend.app.services.scheduler_service.SessionLocal", return_value=db_session), \
         patch.object(scheduler, "_sync_ingest_source", return_value=IngestionStats(source_id=s1.id, source_name="Source 1 Due")) as mock_sync:
        await scheduler._tick()
        assert mock_sync.call_count == 1
        assert scheduler._total_completed == 1


@pytest.mark.asyncio
async def test_scheduler_timeout_and_error_handling(db_session):
    """Verify scheduler worker isolates timeout and logs failure on source."""
    s1 = Source(
        name="Slow Source",
        source_type="rss",
        base_url="https://slow.example",
        feed_url="https://slow.example/rss",
        active=True,
        polling_interval_seconds=10,
        last_attempted_fetch_at=None,
        consecutive_failures=2,
    )
    db_session.add(s1)
    db_session.commit()

    scheduler = IngestionScheduler(check_interval_seconds=1, per_source_timeout=0.01)
    scheduler._running = True

    def slow_ingest(source_id):
        import time
        time.sleep(0.05)
        return IngestionStats(source_id=source_id, source_name="Slow")

    with patch("backend.app.services.scheduler_service.SessionLocal", return_value=db_session), \
         patch.object(scheduler, "_sync_ingest_source", side_effect=slow_ingest):
        await scheduler._tick()
        assert scheduler._total_failed >= 1

    # Verify timeout was recorded
    s1_reloaded = db_session.get(Source, s1.id)
    assert s1_reloaded.consecutive_failures >= 3
    assert "timed out" in s1_reloaded.last_error_message.lower()
    assert s1_reloaded.freshness_status == "FAILED"


def test_scheduler_sync_ingest_inactive_or_missing(db_session):
    """Verify _sync_ingest_source safely handles inactive or missing source ID."""
    scheduler = IngestionScheduler()
    with patch("backend.app.services.scheduler_service.SessionLocal", return_value=db_session):
        stats = scheduler._sync_ingest_source(uuid.uuid4())
        assert stats.source_name == "unknown"

        s_inactive = Source(
            name="Off",
            source_type="rss",
            base_url="https://off.example",
            feed_url="https://off.example/rss",
            active=False,
        )
        db_session.add(s_inactive)
        db_session.commit()
        stats2 = scheduler._sync_ingest_source(s_inactive.id)
        assert stats2.source_name == "unknown"


def test_scheduler_get_status_telemetry(db_session):
    """Verify get_status returns accurate counts, backlog, and runtime metrics."""
    s = Source(name="S1", source_type="rss", base_url="https://s1.example", feed_url="https://s1.example/rss", active=True)
    db_session.add(s)
    db_session.flush()

    d = Document(
        source_id=s.id,
        title="Pending Doc",
        content="Testing",
        url="https://s1.example/doc1",
        published_at=utc_now(),
        processing_status="RAW",
        content_hash="h1",
    )
    db_session.add(d)
    db_session.commit()

    scheduler = IngestionScheduler()
    status_stopped = scheduler.get_status(db_session)
    assert status_stopped.status == "STOPPED"
    assert status_stopped.configured_sources_count == 1
    assert status_stopped.active_sources_count == 1
    assert status_stopped.pending_backlog_count == 1


def test_pipeline_service_end_to_end_and_backlog(db_session):
    """Verify continuous pipeline service end-to-end execution and backlog processor."""
    s = Source(name="Pipeline Source", source_type="rss", base_url="https://pl.example", feed_url="https://pl.example/rss", active=True)
    db_session.add(s)
    db_session.flush()

    doc = Document(
        source_id=s.id,
        title="Federal Reserve Holds Benchmark Rates in Washington",
        description="The Federal Reserve maintained rates steady in the United States.",
        content="The Federal Reserve kept interest rates unchanged in Washington today.",
        url="https://pl.example/fed1",
        published_at=utc_now(),
        processing_status="RAW",
        content_hash="fed_hash_1",
    )
    db_session.add(doc)
    db_session.commit()

    # Process document
    res = pipeline_service.process_document_end_to_end(db_session, doc.id)
    assert res["status"] == "SUCCESS"
    assert res["entities_extracted"] > 0

    # Backlog recovery
    doc2 = Document(
        source_id=s.id,
        title="European Central Bank Raises Interest Rates",
        content="The European Central Bank increased rates in Frankfurt.",
        url="https://pl.example/ecb1",
        published_at=utc_now(),
        processing_status="EXTRACTION_PENDING",
        content_hash="ecb_hash_2",
    )
    db_session.add(doc2)
    db_session.commit()

    backlog_res = pipeline_service.process_backlog(db_session, limit=10)
    assert backlog_res["pending_found"] >= 1
    assert backlog_res["processed_count"] >= 1


def test_pipeline_service_nonexistent_document(db_session):
    """Verify process_document_end_to_end raises ValueError on non-existent document ID."""
    with pytest.raises(ValueError, match="not found"):
        pipeline_service.process_document_end_to_end(db_session, uuid.uuid4())


def test_api_ingestion_endpoints(client, db_session):
    """Verify Ingestion REST endpoints."""
    s = Source(name="API Source", source_type="rss", base_url="https://api.example", feed_url="https://api.example/rss", active=True)
    db_session.add(s)
    db_session.commit()

    # 1. GET /api/v1/ingestion/runs
    resp_runs = client.get("/api/v1/ingestion/runs")
    assert resp_runs.status_code == 200
    data_runs = resp_runs.json()
    assert "items" in data_runs
    assert "total" in data_runs

    # 2. GET /api/v1/ingestion/status
    resp_stat = client.get("/api/v1/ingestion/status")
    assert resp_stat.status_code == 200
    data_stat = resp_stat.json()
    assert "status" in data_stat
    assert data_stat["configured_sources_count"] == 1

    # 3. GET /api/v1/ingestion/runs/{run_id} (404 test)
    resp_run_404 = client.get(f"/api/v1/ingestion/runs/{uuid.uuid4()}")
    assert resp_run_404.status_code == 404

    # 4. POST /api/v1/ingestion/trigger with specific source
    with patch("backend.app.api.v1.ingestion.ingest_from_source", return_value=IngestionStats(source_id=s.id, source_name="API Source")):
        resp_trig = client.post("/api/v1/ingestion/trigger", json={"source_id": str(s.id)})
        assert resp_trig.status_code == 200
        assert resp_trig.json()["triggered_count"] == 1

    # 5. POST /api/v1/ingestion/trigger with all active sources
    with patch("backend.app.api.v1.ingestion.ingest_all_active_sources", return_value=[IngestionStats(source_id=s.id, source_name="API Source")]):
        resp_trig_all = client.post("/api/v1/ingestion/trigger")
        assert resp_trig_all.status_code == 200
