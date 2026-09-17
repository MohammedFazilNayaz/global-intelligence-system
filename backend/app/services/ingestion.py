import time
import uuid
from datetime import timedelta
from typing import List, Optional, Set
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.ingestion_run import IngestionRun
from backend.app.collectors.base import BaseSourceCollector
from backend.app.collectors.registry import get_collector_class
from backend.app.services import pipeline_service
from backend.app.services import alert_service
from backend.app.services.freshness_service import compute_source_freshness_status
from backend.app.services.pipeline_worker import pipeline_worker_pool
from backend.app.utils.logger import setup_logger
from backend.app.utils.time import utc_now

logger = setup_logger("service.ingestion")


class IngestionStats(BaseModel):
    source_id: UUID
    source_name: str
    run_id: Optional[UUID] = None
    total_fetched: int = 0
    new_ingested: int = 0
    duplicates_skipped: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    inserted_doc_ids: List[UUID] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


def ingest_from_source(
    db: Session,
    source: Source,
    collector: Optional[BaseSourceCollector] = None,
    trigger_pipeline: bool = True,
) -> IngestionStats:
    """Execute ingestion pipeline for a single source with deduplication, run tracking, and continuous processing."""
    start_time = time.perf_counter()
    stats = IngestionStats(source_id=source.id, source_name=source.name)

    if not source.active:
        logger.info(f"Source '{source.name}' is inactive. Skipping ingestion.")
        return stats

    now = utc_now()
    source.last_attempted_fetch_at = now

    # 1. Initialize and persist IngestionRun record
    run = IngestionRun(
        id=uuid.uuid4(),
        source_id=source.id,
        status="RUNNING",
        started_at=now,
        documents_discovered=0,
        documents_inserted=0,
        duplicates_skipped=0,
        failures_count=0,
        processing_stats={},
    )
    db.add(run)
    db.commit()
    stats.run_id = run.id

    # 2. Instantiate collector adapter if not injected
    if collector is None:
        collector_cls = get_collector_class(source.source_type)
        collector = collector_cls(
            name=source.name,
            feed_url=source.feed_url,
            base_url=source.base_url,
            config_metadata=source.config_metadata,
        )

    # 3. Acquire & normalize documents
    fetch_start = time.perf_counter()
    fetch_duration_ms = 0.0
    try:
        normalized_docs = collector.collect()
        fetch_duration_ms = round((time.perf_counter() - fetch_start) * 1000, 2)
        stats.total_fetched = len(normalized_docs)
        run.documents_discovered = stats.total_fetched
    except Exception as exc:
        stats.errors += 1
        stats.duration_seconds = time.perf_counter() - start_time
        logger.error(f"Ingestion failed during data collection for '{source.name}': {exc}")

        # Update run failure state
        http_code = getattr(exc, "status_code", 500) if hasattr(exc, "status_code") else 500
        run.status = "FAILED"
        run.error_message = str(exc)
        run.failures_count = 1
        run.completed_at = utc_now()
        run.processing_stats = {
            "scheduled_at": now.isoformat(),
            "started_at": now.isoformat(),
            "completed_at": run.completed_at.isoformat(),
            "request_duration_ms": fetch_duration_ms,
            "http_status": http_code,
            "items_received": 0,
            "new_items": 0,
            "duplicate_items": 0,
            "parse_failures": 1 if any(k in str(exc).lower() for k in ("parse", "xml", "json", "expecting value")) else 0,
            "processing_failures": 1,
            "last_published_at": source.latest_published_at_observed.isoformat() if source.latest_published_at_observed else None,
            "last_new_document_at": source.last_successful_ingestion_at.isoformat() if source.last_successful_ingestion_at else None,
            "consecutive_failures": source.consecutive_failures + 1,
            "next_scheduled_at": (now + timedelta(seconds=source.polling_interval_seconds)).isoformat(),
        }

        # Update source failure telemetry
        source.consecutive_failures += 1
        source.total_failures_count += 1
        source.last_error_message = str(exc)
        if source.consecutive_failures >= 3:
            source.freshness_status = "FAILED"

        db.commit()

        # Evaluate potential source health alerts
        try:
            alert_service.evaluate_source_alerts(db, source_id=source.id)
            db.commit()
        except Exception:
            db.rollback()

        raise

    # Determine latest publication timestamp observed in the incoming batch
    latest_pub = max([d.published_at for d in normalized_docs if d.published_at], default=None)

    # 4. Deduplication against database and current batch
    candidate_hashes = {d.content_hash for d in normalized_docs}
    stmt = select(Document.content_hash).where(
        Document.source_id == source.id,
        Document.content_hash.in_(candidate_hashes),
    )
    existing_hashes: Set[str] = set(db.scalars(stmt).all())

    seen_in_batch: Set[str] = set()
    documents_to_insert: List[Document] = []

    for doc in normalized_docs:
        if doc.content_hash in existing_hashes or doc.content_hash in seen_in_batch:
            stats.duplicates_skipped += 1
            continue

        seen_in_batch.add(doc.content_hash)
        db_doc = Document(
            source_id=source.id,
            external_id=doc.external_id,
            title=doc.title,
            description=doc.description,
            content=doc.content,
            content_format=doc.content_format,
            url=doc.url,
            author=doc.author,
            published_at=doc.published_at,
            ingested_at=utc_now(),
            content_hash=doc.content_hash,
            language=doc.language,
            raw_metadata=doc.raw_metadata,
            processing_status="NORMALIZED",
        )
        documents_to_insert.append(db_doc)

    # 5. Atomic persistence of new documents
    inserted_doc_ids: List[UUID] = []
    try:
        if documents_to_insert:
            db.add_all(documents_to_insert)
            db.flush()
            inserted_doc_ids = [d.id for d in documents_to_insert]
            stats.new_ingested = len(documents_to_insert)
            stats.inserted_doc_ids = inserted_doc_ids
        db.commit()
    except Exception as exc:
        db.rollback()
        stats.errors += 1
        run.status = "FAILED"
        run.error_message = f"Database insert failed: {exc}"
        run.completed_at = utc_now()
        source.consecutive_failures += 1
        source.total_failures_count += 1
        source.last_error_message = str(exc)
        db.commit()
        logger.error(f"Database commit failed during ingestion for '{source.name}': {exc}")
        raise

    # 6. Execute multi-stage pipeline: synchronous if trigger_pipeline=True, else enqueue to async worker pool
    pipeline_results: List[Dict[str, Any]] = []
    if inserted_doc_ids:
        if trigger_pipeline:
            logger.info(f"Triggering synchronous pipeline for {len(inserted_doc_ids)} new documents from '{source.name}'")
            for doc_id in inserted_doc_ids:
                try:
                    res = pipeline_service.process_document_end_to_end(db, document_id=doc_id)
                    pipeline_results.append(res)
                except Exception as pipe_err:
                    logger.error(f"Non-fatal pipeline error for document '{doc_id}': {pipe_err}")
        elif pipeline_worker_pool.is_running:
            logger.info(f"Enqueueing {len(inserted_doc_ids)} new documents from '{source.name}' to async PipelineWorkerPool")
            for doc_id in inserted_doc_ids:
                pipeline_worker_pool.enqueue_document(doc_id)

    # 7. Finalize IngestionRun and Source Telemetry
    finish_time = utc_now()
    run.documents_inserted = stats.new_ingested
    run.duplicates_skipped = stats.duplicates_skipped
    run.completed_at = finish_time
    run.status = "SUCCESS"
    run.processing_stats = {
        "scheduled_at": now.isoformat(),
        "started_at": now.isoformat(),
        "completed_at": finish_time.isoformat(),
        "request_duration_ms": fetch_duration_ms,
        "http_status": 200,
        "items_received": stats.total_fetched,
        "new_items": stats.new_ingested,
        "duplicate_items": stats.duplicates_skipped,
        "parse_failures": 0,
        "processing_failures": max(0, len(inserted_doc_ids) - len(pipeline_results)) if trigger_pipeline else 0,
        "last_published_at": latest_pub.isoformat() if latest_pub else None,
        "last_new_document_at": finish_time.isoformat() if stats.new_ingested > 0 else (source.last_successful_ingestion_at.isoformat() if source.last_successful_ingestion_at else None),
        "consecutive_failures": 0,
        "next_scheduled_at": (finish_time + timedelta(seconds=source.polling_interval_seconds)).isoformat(),
        "inserted_document_ids": [str(d) for d in inserted_doc_ids],
    }

    source.last_successful_fetch_at = finish_time
    source.last_fetch_duration_ms = fetch_duration_ms
    if latest_pub:
        source.latest_published_at_observed = latest_pub
    if stats.new_ingested > 0:
        source.last_successful_ingestion_at = finish_time
        source.latest_document_ingested_at = finish_time
    source.consecutive_failures = 0
    source.last_error_message = None
    source.freshness_status = compute_source_freshness_status(source, finish_time)

    db.commit()

    # Evaluate potential source health alerts on success/staleness
    try:
        alert_service.evaluate_source_alerts(db, source_id=source.id)
        db.commit()
    except Exception as alert_err:
        logger.warning(f"Error evaluating source alerts for '{source.name}': {alert_err}")

    stats.duration_seconds = time.perf_counter() - start_time

    logger.info(
        f"Ingestion summary for '{source.name}' [Run {run.id}]: "
        f"fetched={stats.total_fetched}, new={stats.new_ingested}, duplicates={stats.duplicates_skipped}, duration={fetch_duration_ms}ms"
    )
    return stats


def ingest_all_active_sources(db: Session, trigger_pipeline: bool = True) -> List[IngestionStats]:
    """Iterate through all active sources and execute the ingestion pipeline."""
    stmt = select(Source).where(Source.active.is_(True))
    active_sources = list(db.scalars(stmt).all())
    results: List[IngestionStats] = []

    logger.info(f"Starting batch ingestion for {len(active_sources)} active sources.")
    for source in active_sources:
        try:
            stats = ingest_from_source(db, source, trigger_pipeline=trigger_pipeline)
            results.append(stats)
        except Exception as exc:
            logger.error(f"Error processing source '{source.name}': {exc}")
            results.append(
                IngestionStats(
                    source_id=source.id,
                    source_name=source.name,
                    errors=1,
                )
            )

    return results

