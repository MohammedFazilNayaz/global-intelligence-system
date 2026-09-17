import time
import uuid
from typing import Optional, Dict
from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.app.models.document import Document
from backend.app.models.entity import DocumentEntity
from backend.app.models.event import ExtractedEvent
from backend.app.extractors.base import BaseIntelligenceExtractor
from backend.app.extractors.factory import get_extractor
from backend.app.services.entity_service import get_or_create_entity
from backend.app.schemas.extraction import (
    ExtractionTriggerResponse,
    ExtractionProvenance,
    ProcessingStatus,
)
from backend.app.utils.logger import setup_logger
from backend.app.utils.time import utc_now

logger = setup_logger("service.extraction")


def extract_from_document(
    db: Session,
    document_id: UUID,
    extractor: Optional[BaseIntelligenceExtractor] = None,
    reprocess: bool = False,
    auto_cluster: bool = True,
) -> ExtractionTriggerResponse:
    """Execute intelligence extraction for a single document with full provenance and rollback safety.
    
    If reprocess=True, cleanly removes prior document mentions and extracted events,
    archives previous run provenance in document metadata, and performs extraction anew.
    """
    start_time = time.perf_counter()
    doc = db.get(Document, document_id)
    if not doc:
        raise ValueError(f"Document with ID '{document_id}' does not exist.")

    if extractor is None:
        extractor = get_extractor()

    # If already extracted and reprocess is False, return current status without re-running
    if doc.processing_status == ProcessingStatus.EXTRACTED.value and not reprocess:
        entities_count = db.scalar(
            select(DocumentEntity.id).where(DocumentEntity.document_id == doc.id)
        ) or 0
        events_count = db.scalar(
            select(ExtractedEvent.id).where(ExtractedEvent.document_id == doc.id)
        ) or 0
        prov_dict = doc.raw_metadata.get("extraction_provenance", {})
        prov = ExtractionProvenance(
            extractor_name=prov_dict.get("extractor_name", extractor.name),
            extractor_version=prov_dict.get("extractor_version", extractor.version),
            processed_at=doc.updated_at,
        )
        return ExtractionTriggerResponse(
            document_id=doc.id,
            processing_status=doc.processing_status,
            entities_count=len(doc.entity_mentions) if doc.entity_mentions else 0,
            events_count=len(doc.extracted_events) if doc.extracted_events else 0,
            duration_seconds=0.0,
            extractor=prov,
            message="Document already extracted. Set reprocess=True to re-extract.",
        )

    try:
        # Reprocessing audit trail & cleanup of previous intelligence
        if reprocess or doc.processing_status in (ProcessingStatus.EXTRACTED.value, ProcessingStatus.EXTRACTION_PENDING.value):
            meta = dict(doc.raw_metadata or {})
            history = list(meta.get("extraction_history", []))
            history.append({
                "reprocessed_at": utc_now().isoformat(),
                "previous_provenance": meta.get("extraction_provenance"),
            })
            meta["extraction_history"] = history
            doc.raw_metadata = meta
            flag_modified(doc, "raw_metadata")

            # Collect affected cluster IDs prior to deleting events
            from backend.app.models.cluster import EventClusterMember
            affected_cluster_ids = list(
                db.scalars(
                    select(EventClusterMember.event_cluster_id)
                    .join(ExtractedEvent, ExtractedEvent.id == EventClusterMember.extracted_event_id)
                    .where(ExtractedEvent.document_id == doc.id)
                ).all()
            )

            # Remove prior document entities, events, and economic observations
            from backend.app.models.observation import EconomicObservation
            db.execute(delete(DocumentEntity).where(DocumentEntity.document_id == doc.id))
            db.execute(delete(ExtractedEvent).where(ExtractedEvent.document_id == doc.id))
            db.execute(delete(EconomicObservation).where(EconomicObservation.document_id == doc.id))
            db.flush()

            # Refresh aggregate state or archive vacated clusters
            from backend.app.services.clustering_service import update_cluster_aggregate_state
            for cid in affected_cluster_ids:
                update_cluster_aggregate_state(db, cid)

        # 1. Transition state to EXTRACTION_PENDING
        doc.processing_status = ProcessingStatus.EXTRACTION_PENDING.value
        db.flush()

        # 2. Execute extractor
        result = extractor.extract(
            document_id=doc.id,
            title=doc.title,
            description=doc.description,
            content=doc.content,
            published_at=doc.published_at,
        )

        # 3. Persist Canonical Entities & DocumentEntity Associations
        resolved_entities_by_name: Dict[str, UUID] = {}
        seen_mentions = set()
        for entity_mention in result.entities:
            canonical_entity = get_or_create_entity(db, entity_mention)
            resolved_entities_by_name[entity_mention.canonical_name] = canonical_entity.id
            resolved_entities_by_name[entity_mention.normalized_name] = canonical_entity.id

            mention_key = (doc.id, canonical_entity.id, entity_mention.role, entity_mention.mention_text)
            if mention_key in seen_mentions:
                continue
            seen_mentions.add(mention_key)

            doc_entity = DocumentEntity(
                document_id=doc.id,
                entity_id=canonical_entity.id,
                mention_text=entity_mention.mention_text,
                entity_role=entity_mention.role,
                confidence=entity_mention.confidence,
                metadata_=entity_mention.metadata,
                created_at=utc_now(),
            )
            db.add(doc_entity)

        # 4. Persist Extracted Events
        doc_meta = doc.raw_metadata or {}
        created_events: List[ExtractedEvent] = []
        for event_item in result.events:
            location_id: Optional[UUID] = None
            if event_item.location_entity_name:
                location_id = resolved_entities_by_name.get(event_item.location_entity_name)

            event_meta = dict(event_item.metadata or {})
            if "latitude" in doc_meta and "longitude" in doc_meta:
                event_meta["latitude"] = doc_meta["latitude"]
                event_meta["longitude"] = doc_meta["longitude"]
                if "depth_km" in doc_meta:
                    event_meta["depth_km"] = doc_meta["depth_km"]
                if "magnitude" in doc_meta:
                    event_meta["magnitude"] = doc_meta["magnitude"]

            extracted_event = ExtractedEvent(
                document_id=doc.id,
                event_type=event_item.event_type,
                event_title=event_item.title,
                event_summary=event_item.summary,
                event_time=event_item.event_time,
                location_entity_id=location_id,
                confidence=event_item.confidence,
                importance=event_item.importance,
                metadata_=event_meta,
            )
            db.add(extracted_event)
            created_events.append(extracted_event)

        # Direct sensor hazard ingestion fallback (USGS GeoJSON, GDACS)
        if not created_events and doc_meta.get("event_type") == "disaster":
            mag = doc_meta.get("magnitude", 5.0)
            lat = doc_meta.get("latitude")
            lon = doc_meta.get("longitude")
            sensor_meta = {
                "latitude": lat,
                "longitude": lon,
                "depth_km": doc_meta.get("depth_km"),
                "magnitude": mag,
                "place": doc_meta.get("place"),
                "provenance": "USGS GeoJSON Instrumental Sensor",
            }
            sensor_event = ExtractedEvent(
                document_id=doc.id,
                event_type="disaster",
                event_title=doc.title,
                event_summary=doc.description or doc.title,
                event_time=doc.published_at or utc_now(),
                location_entity_id=None,
                confidence=0.99,
                importance=min(1.0, 0.5 + (float(mag or 4.5) - 4.5) * 0.15),
                metadata_=sensor_meta,
            )
            db.add(sensor_event)
            created_events.append(sensor_event)

        db.flush()

        # 5. Persist Economic Indicators and Observations (V0.5)
        if hasattr(result, "economic_observations") and result.economic_observations:
            from backend.app.services.economic_service import get_or_create_economic_indicator
            from backend.app.models.observation import EconomicObservation

            # Find primary event for linking
            primary_event_id = None
            for ev in created_events:
                if ev.event_type in ("economic_release", "central_bank_decision", "market_event"):
                    primary_event_id = ev.id
                    break

            for obs_item in result.economic_observations:
                country_entity_id = None
                if obs_item.country_name:
                    country_entity_id = resolved_entities_by_name.get(obs_item.country_name)

                indicator = get_or_create_economic_indicator(
                    db=db,
                    indicator_type=obs_item.indicator_type,
                    country_entity_id=country_entity_id,
                    canonical_name=obs_item.indicator_canonical_name,
                    economic_domain=obs_item.economic_domain,
                    default_unit=obs_item.reported_unit,
                )

                obs_meta = dict(obs_item.metadata or {})
                if obs_item.central_bank_decision:
                    obs_meta["central_bank_decision"] = obs_item.central_bank_decision

                obs_record = EconomicObservation(
                    id=uuid.uuid4(),
                    indicator_id=indicator.id,
                    event_id=primary_event_id,
                    document_id=doc.id,
                    observation_period=obs_item.observation_period,
                    observation_date=obs_item.observation_date,
                    reported_value=obs_item.reported_value,
                    reported_unit=obs_item.reported_unit,
                    previous_value=obs_item.previous_value,
                    expected_value=obs_item.expected_value,
                    revised_value=obs_item.revised_value,
                    direction=obs_item.direction,
                    change_value=obs_item.change_value,
                    change_percent=obs_item.change_percent,
                    calculation_method=obs_item.calculation_method,
                    economic_relevance=obs_item.economic_relevance,
                    metadata_=obs_meta,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                db.add(obs_record)

        # 6. Update processing status and provenance
        doc.processing_status = ProcessingStatus.EXTRACTED.value
        doc.raw_metadata["extraction_provenance"] = result.metadata.model_dump(mode="json")
        doc.raw_metadata.pop("extraction_error", None)
        flag_modified(doc, "raw_metadata")

        db.commit()
        db.refresh(doc)

        # 6. Auto-cluster extracted events into EventClusters
        if auto_cluster and result.events:
            from backend.app.services.clustering_service import cluster_document_events
            try:
                cluster_document_events(db, doc.id)
            except Exception as cluster_exc:
                logger.warning(f"Auto-clustering non-fatal failure for doc '{doc.id}': {cluster_exc}")

        duration = time.perf_counter() - start_time

        logger.info(
            f"Extraction successful for document '{doc.id}': "
            f"{len(result.entities)} entities, {len(result.events)} events in {duration:.3f}s"
        )

        return ExtractionTriggerResponse(
            document_id=doc.id,
            processing_status=doc.processing_status,
            entities_count=len(result.entities),
            events_count=len(result.events),
            duration_seconds=round(duration, 3),
            extractor=result.metadata,
            message="Intelligence extraction completed successfully.",
        )

    except Exception as exc:
        db.rollback()
        logger.error(f"Intelligence extraction failed for document '{document_id}': {exc}", exc_info=True)

        # Record failure state without destroying document
        try:
            doc_fail = db.get(Document, document_id)
            if doc_fail:
                doc_fail.processing_status = ProcessingStatus.EXTRACTION_FAILED.value
                doc_fail.raw_metadata["extraction_error"] = str(exc)
                flag_modified(doc_fail, "raw_metadata")
                db.commit()
        except Exception as inner_exc:
            logger.error(f"Failed to record extraction failure status: {inner_exc}")
            db.rollback()

        raise
