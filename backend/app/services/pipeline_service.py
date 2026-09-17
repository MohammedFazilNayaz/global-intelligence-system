import re
import time
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.document import Document
from backend.app.models.event import ExtractedEvent
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.relationship import EntityRelationship
from backend.app.services.extraction_service import extract_from_document
from backend.app.services.clustering_service import cluster_document_events
from backend.app.services import graph_service
from backend.app.services import correlation_service
from backend.app.services import alert_service
from backend.app.extractors.relationship import DeterministicRelationshipExtractor
from backend.app.schemas.relationship import EntityRelationshipCreate
from backend.app.schemas.extraction import ProcessingStatus
from backend.app.utils.logger import get_logger
from backend.app.utils.time import utc_now

logger = get_logger("service.pipeline")

_SENTENCE_SPLIT_REGEX = re.compile(r"(?<=[.!?])\s+")


def process_document_end_to_end(
    db: Session,
    document_id: uuid.UUID,
    reprocess: bool = False,
) -> Dict[str, Any]:
    """Execute continuous multi-stage intelligence pipeline for a document.
    
    Stages:
    1. Entity, Event & Economic Extraction (extract_from_document)
    2. Event Clustering (cluster_document_events)
    3. Deterministic Relationship Extraction & Graph Persistence
    4. Event-Market Correlation
    5. Deterministic Alert Evaluation
    """
    start_time = time.perf_counter()
    doc = db.get(Document, document_id)
    if not doc:
        raise ValueError(f"Document '{document_id}' not found.")

    pipeline_summary = {
        "document_id": str(document_id),
        "entities_extracted": 0,
        "events_extracted": 0,
        "clusters_assigned": 0,
        "relationships_created": 0,
        "correlations_computed": 0,
        "alerts_generated": 0,
        "duration_seconds": 0.0,
        "status": "SUCCESS",
    }

    # Idempotency guard: do not reprocess already extracted document unless explicitly requested
    if doc.processing_status == ProcessingStatus.EXTRACTED.value and not reprocess:
        logger.debug(f"Document '{document_id}' is already EXTRACTED. Skipping redundant processing.")
        pipeline_summary["status"] = "SKIPPED_ALREADY_EXTRACTED"
        return pipeline_summary

    # Transition to EXTRACTION_PENDING
    doc.processing_status = ProcessingStatus.EXTRACTION_PENDING.value
    db.flush()

    try:
        # 1. Extraction (Entity, Event, Economic) & Auto-clustering
        extraction_res = extract_from_document(db, document_id=document_id, reprocess=reprocess, auto_cluster=True)
        pipeline_summary["entities_extracted"] = extraction_res.entities_count
        pipeline_summary["events_extracted"] = extraction_res.events_count

        # 2. Relationship Extraction from Document Content
        rel_extractor = DeterministicRelationshipExtractor()
        created_rels: List[EntityRelationship] = []

        # Retrieve entities mentioned in this document
        doc_entities = list(
            db.scalars(
                select(Entity)
                .join(DocumentEntity, DocumentEntity.entity_id == Entity.id)
                .where(DocumentEntity.document_id == document_id)
            ).all()
        )

        if len(doc_entities) >= 2 and doc.content:
            entity_dicts = [
                {
                    "id": e.id,
                    "canonical_name": e.canonical_name,
                    "entity_type": e.entity_type,
                    "country_code": e.country_code,
                }
                for e in doc_entities
            ]

            full_text = f"{doc.title}. {doc.description or ''}. {doc.content or ''}"
            raw_sentences = [s.strip() for s in _SENTENCE_SPLIT_REGEX.split(full_text) if len(s.strip()) >= 10]

            # 1. Single sentence extraction
            for sentence in raw_sentences:
                extracted_rels = rel_extractor.extract_relationships_from_sentence(
                    sentence=sentence,
                    entities=entity_dicts,
                    document_id=doc.id,
                )
                for rel_create in extracted_rels:
                    try:
                        saved_rel = graph_service.create_relationship(db, rel_create)
                        created_rels.append(saved_rel)
                    except Exception as rel_err:
                        logger.debug(f"Relationship creation skipped: {rel_err}")

            # 2. Adjacent 2-sentence sliding window
            for i in range(len(raw_sentences) - 1):
                two_sent = f"{raw_sentences[i]} {raw_sentences[i+1]}"
                if len(two_sent) > 250:
                    continue
                extracted_rels = rel_extractor.extract_relationships_from_sentence(
                    sentence=two_sent,
                    entities=entity_dicts,
                    document_id=doc.id,
                )
                for rel_create in extracted_rels:
                    try:
                        saved_rel = graph_service.create_relationship(db, rel_create)
                        created_rels.append(saved_rel)
                    except Exception as rel_err:
                        logger.debug(f"Relationship creation skipped: {rel_err}")

        pipeline_summary["relationships_created"] = len(created_rels)

        # 3. Event-Market Correlation & Alert Generation
        events = list(db.scalars(select(ExtractedEvent).where(ExtractedEvent.document_id == document_id)).all())
        total_correlations = 0
        total_alerts = 0

        for event in events:
            # Correlation
            try:
                corrs = correlation_service.compute_event_market_correlations(db, event_id=event.id)
                total_correlations += len(corrs)
            except Exception as corr_err:
                logger.debug(f"Event market correlation skipped for event {event.id}: {corr_err}")

            # Alert Evaluation
            try:
                alerts = alert_service.evaluate_event_alerts(db, event_id=event.id)
                total_alerts += len(alerts)
            except Exception as alert_err:
                logger.warning(f"Alert evaluation error for event {event.id}: {alert_err}")

        pipeline_summary["correlations_computed"] = total_correlations
        pipeline_summary["alerts_generated"] = total_alerts

        # Finalize document state to EXTRACTED
        doc.processing_status = ProcessingStatus.EXTRACTED.value
        doc.updated_at = utc_now()
        db.commit()
        pipeline_summary["duration_seconds"] = round(time.perf_counter() - start_time, 3)
        return pipeline_summary

    except Exception as exc:
        db.rollback()
        logger.error(f"Continuous processing pipeline failed for document '{document_id}': {exc}", exc_info=True)
        pipeline_summary["status"] = "FAILED"
        pipeline_summary["error"] = str(exc)
        pipeline_summary["duration_seconds"] = round(time.perf_counter() - start_time, 3)

        # Record failure status on document
        try:
            failed_doc = db.get(Document, document_id)
            if failed_doc:
                failed_doc.processing_status = ProcessingStatus.FAILED.value
                failed_doc.updated_at = utc_now()
                db.commit()
        except Exception as update_err:
            logger.error(f"Failed to record FAILED status on document '{document_id}': {update_err}")

        return pipeline_summary


def process_backlog(db: Session, limit: int = 50) -> Dict[str, Any]:
    """Process pending documents in backlog sequentially."""
    stmt = (
        select(Document.id)
        .where(Document.processing_status.in_([ProcessingStatus.NORMALIZED.value, ProcessingStatus.EXTRACTION_PENDING.value]))
        .order_by(Document.ingested_at)
        .limit(limit)
    )
    pending_ids = list(db.scalars(stmt).all())
    processed_count = 0
    failed_count = 0

    for doc_id in pending_ids:
        result = process_document_end_to_end(db, document_id=doc_id)
        if result.get("status") == "SUCCESS":
            processed_count += 1
        else:
            failed_count += 1

    return {
        "pending_found": len(pending_ids),
        "processed_count": processed_count,
        "failed_count": failed_count,
    }


def get_backlog_metrics(db: Session) -> Dict[str, Any]:
    """Retrieve operational queue depth and status breakdown for documents in pipeline."""
    from sqlalchemy import func
    statuses = ["RAW", "NORMALIZED", "EXTRACTION_PENDING", "EXTRACTED", "FAILED"]
    breakdown = {}
    for st in statuses:
        cnt = db.scalar(select(func.count(Document.id)).where(Document.processing_status == st)) or 0
        breakdown[st] = cnt

    pending_count = sum(breakdown.get(st, 0) for st in ["RAW", "NORMALIZED", "EXTRACTION_PENDING"])
    return {
        "pending_count": pending_count,
        "breakdown_by_status": breakdown,
    }

