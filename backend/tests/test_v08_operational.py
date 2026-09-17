"""
V0.8 Operational Layer Unit and Integration Tests.
Tests operational metrics, latency percentiles, processing backlog telemetry,
deterministic alert evaluation, source health metadata, and pipeline idempotency.
"""
from datetime import datetime, timezone, timedelta
import uuid
import pytest
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.event import ExtractedEvent
from backend.app.models.cluster import EventCluster
from backend.app.models.ingestion_run import IngestionRun
from backend.app.models.alert import Alert
from backend.app.services.freshness_service import get_operational_metrics, get_all_sources_health
from backend.app.services.alert_service import evaluate_system_alerts, evaluate_cluster_alerts
from backend.app.services.pipeline_service import process_document_end_to_end, get_backlog_metrics
from backend.app.processors.hasher import compute_content_hash


def test_source_model_operational_properties():
    """Verify source model typed properties backed by config_metadata."""
    src = Source(
        name="Telemetry Test Source",
        source_type="rss",
        base_url="https://telemetry.test",
        feed_url="https://telemetry.test/rss",
        active=True,
        polling_interval_seconds=300,
        config_metadata={},
    )
    
    # Default state
    assert src.health_status == "UNKNOWN"
    assert src.last_successful_ingestion_at is None
    assert src.latest_published_at_observed is None
    assert src.latest_document_ingested_at is None
    assert src.last_fetch_duration_ms is None
    assert src.total_failures_count == 0

    # Mutate properties
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    src.last_successful_ingestion_at = now
    src.latest_published_at_observed = now - timedelta(minutes=15)
    src.latest_document_ingested_at = now
    src.last_fetch_duration_ms = 350
    src.total_failures_count = 5

    assert src.last_successful_ingestion_at == now
    assert src.latest_published_at_observed == now - timedelta(minutes=15)
    assert src.latest_document_ingested_at == now
    assert src.last_fetch_duration_ms == 350
    assert src.total_failures_count == 5

    # Invalid ISO handling
    src.config_metadata["last_successful_ingestion_at"] = "not-a-date"
    assert src.last_successful_ingestion_at is None
    src.config_metadata["latest_published_at_observed"] = "invalid"
    assert src.latest_published_at_observed is None
    src.config_metadata["latest_document_ingested_at"] = "invalid"
    assert src.latest_document_ingested_at is None

    # Health evaluation states
    src.active = False
    assert src.health_status in ("INACTIVE", "DISABLED")
    src.active = True

    src.consecutive_failures = 3
    assert src.health_status in ("FAILING", "FAILED")

    src.consecutive_failures = 1
    assert src.health_status == "DEGRADED"

    src.consecutive_failures = 0
    src.freshness_status = "CURRENT"
    assert src.health_status == "HEALTHY"


def test_operational_metrics_empty_database(db_session):
    """Verify get_operational_metrics returns zeroed percentiles on empty database."""
    metrics = get_operational_metrics(db_session)
    assert metrics.pipeline_health == "OPERATIONAL"
    assert metrics.active_sources_count == 0
    assert metrics.pending_backlog_count == 0
    assert metrics.fetch_latency.sample_size == 0
    assert metrics.processing_latency.sample_size == 0
    assert metrics.e2e_latency.sample_size == 0


def test_operational_metrics_with_telemetry_data(db_session, sample_source):
    """Verify latency percentiles calculation with real Document and Event records."""
    now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    
    # Add an ingestion run with duration
    run = IngestionRun(
        source_id=sample_source.id,
        status="SUCCESS",
        started_at=now - timedelta(minutes=10),
        completed_at=now - timedelta(minutes=9, seconds=58),
        documents_discovered=5,
        documents_inserted=5,
        duplicates_skipped=0,
        failures_count=0,
        processing_stats={"duration_ms": 2000},
    )
    db_session.add(run)

    # Add documents with known durations
    doc1 = Document(
        source_id=sample_source.id,
        title="Telemetry Doc 1",
        url="https://example.com/doc1",
        content="Content for telemetry document 1.",
        content_hash=compute_content_hash("Telemetry Doc 1", "Content 1"),
        published_at=now - timedelta(minutes=30),
        ingested_at=now - timedelta(minutes=20),
        processing_status="EXTRACTED",
        raw_metadata={"pipeline_duration_seconds": 1.5},
    )
    doc2 = Document(
        source_id=sample_source.id,
        title="Telemetry Doc 2",
        url="https://example.com/doc2",
        content="Content for telemetry document 2.",
        content_hash=compute_content_hash("Telemetry Doc 2", "Content 2"),
        published_at=now - timedelta(minutes=15),
        ingested_at=now - timedelta(minutes=5),
        processing_status="EXTRACTED",
        raw_metadata={"pipeline_duration_seconds": 3.5},
    )
    db_session.add_all([doc1, doc2])
    db_session.commit()

    # Explicitly set updated_at
    doc1.updated_at = doc1.ingested_at + timedelta(seconds=2)
    doc2.updated_at = doc2.ingested_at + timedelta(seconds=4)

    # Add ExtractedEvent for doc1
    evt1 = ExtractedEvent(
        document_id=doc1.id,
        event_title="Telemetry Event 1",
        event_type="DIPLOMATIC",
        event_time=now - timedelta(minutes=30),
        importance=0.8,
        confidence=0.9,
        created_at=now - timedelta(minutes=19, seconds=58),
    )
    db_session.add(evt1)
    db_session.commit()

    metrics = get_operational_metrics(db_session)
    assert metrics.active_sources_count == 1
    assert metrics.fetch_latency.sample_size == 2
    assert metrics.fetch_latency.median_seconds == 600.0
    assert metrics.processing_latency.sample_size == 2
    assert metrics.processing_latency.median_seconds == 4.0
    assert metrics.e2e_latency.sample_size == 2


def test_api_operational_metrics_endpoint(client, db_session, sample_source):
    """Verify GET /api/v1/intelligence/metrics returns 200 and schema compliant JSON."""
    resp = client.get("/api/v1/intelligence/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "fetch_latency" in data
    assert "processing_latency" in data
    assert "e2e_latency" in data
    assert "pipeline_health" in data
    assert "calculated_at" in data


def test_api_ingestion_backlog_endpoint(client, db_session, sample_source):
    """Verify GET /api/v1/ingestion/backlog returns accurate pending breakdown."""
    now = datetime.now(timezone.utc)
    # Add one RAW doc and one EXTRACTED doc
    raw_doc = Document(
        source_id=sample_source.id,
        title="Pending Doc",
        url="https://example.com/pending",
        content="Raw pending content",
        content_hash=compute_content_hash("Pending Doc", "Content"),
        published_at=now,
        ingested_at=now,
        processing_status="RAW",
    )
    ext_doc = Document(
        source_id=sample_source.id,
        title="Extracted Doc",
        url="https://example.com/extracted",
        content="Extracted content",
        content_hash=compute_content_hash("Extracted Doc", "Content"),
        published_at=now,
        ingested_at=now,
        processing_status="EXTRACTED",
    )
    db_session.add_all([raw_doc, ext_doc])
    db_session.commit()

    resp = client.get("/api/v1/ingestion/backlog?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_count"] == 1
    assert data["breakdown_by_status"]["RAW"] == 1
    assert len(data["sample_pending"]) == 1
    assert data["sample_pending"][0]["title"] == "Pending Doc"


def test_system_alert_evaluation_rules(db_session, sample_source):
    """Verify evaluate_system_alerts creates deterministic alerts for backlog and failure rates."""
    now = datetime.now(timezone.utc)
    
    # 1. Backlog alert evaluation
    for i in range(55):
        doc = Document(
            source_id=sample_source.id,
            title=f"Backlog Doc {i}",
            url=f"https://example.com/backlog/{i}",
            content="Content",
            content_hash=compute_content_hash(f"Backlog {i}", "Content"),
            published_at=now,
            ingested_at=now,
            processing_status="RAW",
        )
        db_session.add(doc)
    db_session.commit()

    alerts = evaluate_system_alerts(db_session)
    backlog_alerts = [a for a in alerts if a.trigger_type == "PROCESSING_BACKLOG_EXCEEDED"]
    assert len(backlog_alerts) == 1
    assert "exceed" in backlog_alerts[0].explanation.lower()

    # Deduplication test: running evaluate_system_alerts again should not duplicate active alert
    alerts2 = evaluate_system_alerts(db_session)
    active_backlog = (
        db_session.query(Alert)
        .filter(Alert.trigger_type == "PROCESSING_BACKLOG_EXCEEDED", Alert.status == "ACTIVE")
        .all()
    )
    assert len(active_backlog) == 1

    # 2. High failure rate alert evaluation: Add 4 failed runs
    for i in range(4):
        failed_run = IngestionRun(
            source_id=sample_source.id,
            status="FAILED",
            started_at=now - timedelta(minutes=i * 5),
            completed_at=now - timedelta(minutes=i * 5, seconds=-1),
            documents_discovered=0,
            documents_inserted=0,
            duplicates_skipped=0,
            failures_count=1,
            error_message="Simulated connection failure",
        )
        db_session.add(failed_run)
    db_session.commit()

    alerts3 = evaluate_system_alerts(db_session)
    failure_alerts = [a for a in alerts3 if a.trigger_type == "HIGH_INGESTION_FAILURE_RATE"]
    assert len(failure_alerts) >= 1


def test_cluster_alert_evaluation_rules(db_session, sample_document):
    """Verify evaluate_cluster_alerts creates alerts for significant clusters without causal claims."""
    from backend.app.models.cluster import EventClusterMember
    now = datetime.now(timezone.utc)
    cluster = EventCluster(
        canonical_title="Major Geopolitical Treaty Signed",
        canonical_summary="Two nations reached diplomatic accord.",
        event_type="DIPLOMATIC",
        confidence=0.9,
        status="ACTIVE",
        metadata_={"importance": 0.85},
    )
    db_session.add(cluster)
    db_session.commit()

    # Add 3 events and member associations
    for i in range(3):
        evt = ExtractedEvent(
            document_id=sample_document.id,
            event_title=f"Treaty Sub-event {i}",
            event_type="DIPLOMATIC",
            event_time=now,
            importance=0.85,
            confidence=0.9,
            created_at=now,
        )
        db_session.add(evt)
        db_session.commit()
        member = EventClusterMember(
            event_cluster_id=cluster.id,
            extracted_event_id=evt.id,
            membership_score=0.95,
        )
        db_session.add(member)
    db_session.commit()

    alerts = evaluate_cluster_alerts(db_session, cluster.id)
    assert len(alerts) >= 1
    assert alerts[0].trigger_type == "SIGNIFICANT_CLUSTER_UPDATE"
    assert alerts[0].confidence == 0.9
    assert "predict" not in alerts[0].explanation.lower()

    # Deduplication test
    alerts2 = evaluate_cluster_alerts(db_session, cluster.id)
    assert len(alerts2) == 0 or alerts2[0].id == alerts[0].id


def test_pipeline_processing_idempotency(db_session, sample_source):
    """Verify process_document_lifecycle is strictly idempotent and skips already extracted documents."""
    now = datetime.now(timezone.utc)
    doc = Document(
        source_id=sample_source.id,
        title="Germany and France Announce Joint Clean Energy Accord",
        url="https://example.com/energy-accord",
        content="President of France and Chancellor of Germany signed the pact in Berlin on Tuesday.",
        content_hash=compute_content_hash("Energy Accord", "Berlin Pact"),
        published_at=now,
        ingested_at=now,
        processing_status="RAW",
    )
    db_session.add(doc)
    db_session.commit()

    # First pass: moves RAW -> NORMALIZED -> EXTRACTION_PENDING -> EXTRACTED
    res1 = process_document_end_to_end(db_session, doc.id)
    assert res1["status"] in ("EXTRACTED", "SUCCESS")
    assert doc.processing_status == "EXTRACTED"
    
    events_count_1 = db_session.query(ExtractedEvent).filter(ExtractedEvent.document_id == doc.id).count()

    # Second pass: reprocess=False must return SKIPPED_ALREADY_EXTRACTED
    res2 = process_document_end_to_end(db_session, doc.id, reprocess=False)
    assert res2["status"] == "SKIPPED_ALREADY_EXTRACTED"

    events_count_2 = db_session.query(ExtractedEvent).filter(ExtractedEvent.document_id == doc.id).count()
    assert events_count_1 == events_count_2, "Idempotency violation: duplicate events created!"
