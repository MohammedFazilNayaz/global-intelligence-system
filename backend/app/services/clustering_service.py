import math
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple, Dict, Set, Any
from uuid import UUID

from sqlalchemy import select, func, desc, asc, delete
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import flag_modified

from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.models.event import ExtractedEvent
from backend.app.models.document import Document
from backend.app.models.entity import DocumentEntity, Entity
from backend.app.clustering.scorer import (
    calculate_cluster_match,
    ClusterMatchScore,
    DEFAULT_CLUSTER_THRESHOLD,
)
from backend.app.utils.logger import setup_logger
from backend.app.utils.time import utc_now

logger = setup_logger("service.clustering")


def get_effective_event_time(event: ExtractedEvent, doc: Document) -> Tuple[Optional[datetime], str]:
    """Determine effective event time, falling back to document published_at if absent."""
    if event.event_time is not None:
        return event.event_time, "event_extracted_time"
    return doc.published_at, "document_published_at"


def get_document_entity_ids(db: Session, document_id: UUID) -> Tuple[Set[UUID], Set[UUID]]:
    """Retrieve actor entity IDs and all entity IDs for a document."""
    doc_entities = list(
        db.scalars(
            select(DocumentEntity).where(DocumentEntity.document_id == document_id)
        ).all()
    )
    actor_ids = {de.entity_id for de in doc_entities if de.entity_role.lower() == "actor"}
    all_ids = {de.entity_id for de in doc_entities}
    return actor_ids, all_ids


def get_cluster_entity_ids(db: Session, cluster_id: UUID) -> Tuple[Set[UUID], Set[UUID]]:
    """Retrieve combined actor IDs and all entity IDs across all documents in a cluster."""
    stmt = (
        select(DocumentEntity)
        .join(ExtractedEvent, ExtractedEvent.document_id == DocumentEntity.document_id)
        .join(EventClusterMember, EventClusterMember.extracted_event_id == ExtractedEvent.id)
        .where(EventClusterMember.event_cluster_id == cluster_id)
    )
    cluster_doc_entities = list(db.scalars(stmt).all())
    actor_ids = {de.entity_id for de in cluster_doc_entities if de.entity_role.lower() == "actor"}
    all_ids = {de.entity_id for de in cluster_doc_entities}
    return actor_ids, all_ids


def cluster_extracted_event(
    db: Session,
    event_id: UUID,
    threshold: float = DEFAULT_CLUSTER_THRESHOLD,
) -> EventClusterMember:
    """Cluster an extracted event into an existing or newly created EventCluster."""
    event = db.scalar(
        select(ExtractedEvent)
        .options(
            joinedload(ExtractedEvent.document),
            joinedload(ExtractedEvent.location_entity),
            joinedload(ExtractedEvent.cluster_membership),
        )
        .where(ExtractedEvent.id == event_id)
    )
    if not event:
        raise ValueError(f"ExtractedEvent with ID '{event_id}' does not exist.")

    # If already clustered, return existing membership
    if event.cluster_membership is not None:
        return event.cluster_membership

    doc = event.document
    effective_time, time_source = get_effective_event_time(event, doc)

    # 1. Candidate Generation / Blocking
    temporal_window = timedelta(hours=48)
    cand_stmt = (
        select(EventCluster)
        .options(joinedload(EventCluster.primary_location_entity))
        .where(
            EventCluster.status == "ACTIVE",
            EventCluster.event_type == event.event_type.lower(),
        )
    )
    if effective_time:
        cand_stmt = cand_stmt.where(
            EventCluster.event_time_start <= effective_time + temporal_window,
            EventCluster.event_time_end >= effective_time - temporal_window,
        )

    candidates = list(db.scalars(cand_stmt).all())
    event_actor_ids, event_all_entity_ids = get_document_entity_ids(db, doc.id)

    event_text = f"{event.event_title} {event.event_summary or ''}".strip()
    event_country = event.location_entity.country_code if event.location_entity else None

    best_candidate: Optional[EventCluster] = None
    best_score: Optional[ClusterMatchScore] = None

    for cand in candidates:
        cand_actor_ids, cand_all_entity_ids = get_cluster_entity_ids(db, cand.id)
        cand_text = f"{cand.canonical_title} {cand.canonical_summary or ''}".strip()
        cand_country = (
            cand.primary_location_entity.country_code
            if cand.primary_location_entity
            else None
        )

        match_score = calculate_cluster_match(
            event_type_a=event.event_type,
            event_type_b=cand.event_type,
            time_a=effective_time,
            time_b=cand.event_time_start,
            loc_a_id=event.location_entity_id,
            loc_b_id=cand.primary_location_entity_id,
            country_a=event_country,
            country_b=cand_country,
            actor_ids_a=event_actor_ids,
            actor_ids_b=cand_actor_ids,
            all_entity_ids_a=event_all_entity_ids,
            all_entity_ids_b=cand_all_entity_ids,
            text_a=event_text,
            text_b=cand_text,
            threshold=threshold,
            candidate_cluster_id=cand.id,
        )

        if match_score.is_match and not match_score.is_vetoed:
            if best_score is None or match_score.final_score > best_score.final_score:
                best_score = match_score
                best_candidate = cand

    # 2. Attach to best candidate or create new cluster
    if best_candidate and best_score:
        score_metadata = best_score.to_metadata_dict()
        score_metadata["temporal_source"] = time_source

        member = EventClusterMember(
            event_cluster_id=best_candidate.id,
            extracted_event_id=event.id,
            membership_score=best_score.final_score,
            membership_method="deterministic_v0.3",
            metadata_=score_metadata,
            created_at=utc_now(),
        )
        db.add(member)
        db.flush()

        # Update cluster state
        update_cluster_aggregate_state(db, best_candidate.id)
        db.commit()
        db.refresh(member)
        return member

    # 3. Create new EventCluster
    new_cluster = EventCluster(
        canonical_title=event.event_title,
        canonical_summary=event.event_summary,
        event_type=event.event_type.lower(),
        event_time_start=effective_time,
        event_time_end=effective_time,
        primary_location_entity_id=event.location_entity_id,
        confidence=event.confidence,
        status="ACTIVE",
        metadata_={
            "document_count": 1,
            "unique_source_count": 1,
            "source_ids": [str(doc.source_id)],
            "canonical_event_id": str(event.id),
            "temporal_source": time_source,
            "importance": round(event.importance, 2) if event.importance is not None else 0.8,
        },
    )
    db.add(new_cluster)
    db.flush()

    initial_score_meta = {
        "method": "cluster_creation",
        "version": "0.3.0",
        "founding_member": True,
        "final_score": 1.0,
        "temporal_source": time_source,
    }
    member = EventClusterMember(
        event_cluster_id=new_cluster.id,
        extracted_event_id=event.id,
        membership_score=1.0,
        membership_method="deterministic_v0.3",
        metadata_=initial_score_meta,
        created_at=utc_now(),
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def update_cluster_aggregate_state(db: Session, cluster_id: UUID) -> Optional[EventCluster]:
    """Recompute canonical title, summary, confidence, time bounds, and source counts for a cluster."""
    cluster = db.get(EventCluster, cluster_id)
    if not cluster:
        return None

    members = list(
        db.scalars(
            select(EventClusterMember)
            .options(
                joinedload(EventClusterMember.extracted_event).joinedload(ExtractedEvent.document),
                joinedload(EventClusterMember.extracted_event).joinedload(ExtractedEvent.location_entity),
            )
            .where(EventClusterMember.event_cluster_id == cluster.id)
        ).all()
    )

    if not members:
        cluster.status = "ARCHIVED"
        flag_modified(cluster, "status")
        db.commit()
        return cluster

    events = [m.extracted_event for m in members if m.extracted_event is not None]
    if not events:
        return cluster

    # Earliest & latest times
    times: List[datetime] = []
    for ev in events:
        eff_time, _ = get_effective_event_time(ev, ev.document)
        if eff_time:
            times.append(eff_time)

    if times:
        cluster.event_time_start = min(times)
        cluster.event_time_end = max(times)

    # Select canonical event: highest confidence (earliest published_at as tie-breaker)
    best_event = sorted(
        events,
        key=lambda e: (e.confidence, -(e.document.published_at.timestamp() if e.document and e.document.published_at else 0)),
        reverse=True,
    )[0]

    cluster.canonical_title = best_event.event_title
    cluster.canonical_summary = best_event.event_summary

    # Majority location entity
    location_ids = [e.location_entity_id for e in events if e.location_entity_id is not None]
    if location_ids:
        most_common_loc = max(set(location_ids), key=location_ids.count)
        cluster.primary_location_entity_id = most_common_loc
    else:
        cluster.primary_location_entity_id = None

    # Multi-source confidence calculation
    source_ids = {str(e.document.source_id) for e in events if e.document is not None}
    doc_ids = {str(e.document_id) for e in events}
    unique_sources_count = len(source_ids)
    corroboration_bonus = 0.02 * min(4, max(0, unique_sources_count - 1))
    base_conf = max(e.confidence for e in events)
    cluster.confidence = min(0.99, round(base_conf + corroboration_bonus, 4))

    meta = dict(cluster.metadata_ or {})
    max_imp = max((e.importance for e in events if e.importance is not None), default=0.8)
    meta.update({
        "document_count": len(doc_ids),
        "unique_source_count": unique_sources_count,
        "source_ids": list(source_ids),
        "canonical_event_id": str(best_event.id),
        "importance": round(max_imp, 2),
    })
    cluster.metadata_ = meta
    flag_modified(cluster, "metadata_")

    db.commit()
    db.refresh(cluster)
    return cluster


def cluster_document_events(db: Session, document_id: UUID) -> List[EventClusterMember]:
    """Execute event clustering for all extracted events in a document."""
    events = list(
        db.scalars(
            select(ExtractedEvent).where(ExtractedEvent.document_id == document_id)
        ).all()
    )
    members: List[EventClusterMember] = []
    for ev in events:
        mem = cluster_extracted_event(db, ev.id)
        members.append(mem)
    return members


def list_event_clusters(
    db: Session,
    event_type: Optional[str] = None,
    status: Optional[str] = "ACTIVE",
    min_confidence: Optional[float] = None,
    min_importance: Optional[float] = None,
    location_entity_id: Optional[UUID] = None,
    entity_id: Optional[UUID] = None,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    search: Optional[str] = None,
    order_by: str = "newest",
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[EventCluster], int, int]:
    """Retrieve paginated, filtered event clusters with search and sorting options."""
    stmt = (
        select(EventCluster)
        .options(
            joinedload(EventCluster.primary_location_entity),
            joinedload(EventCluster.members).joinedload(EventClusterMember.extracted_event),
        )
    )
    count_stmt = select(func.count(EventCluster.id))

    if status:
        stmt = stmt.where(EventCluster.status == status.upper())
        count_stmt = count_stmt.where(EventCluster.status == status.upper())

    if event_type:
        stmt = stmt.where(EventCluster.event_type == event_type.lower())
        count_stmt = count_stmt.where(EventCluster.event_type == event_type.lower())

    if min_confidence is not None:
        stmt = stmt.where(EventCluster.confidence >= min_confidence)
        count_stmt = count_stmt.where(EventCluster.confidence >= min_confidence)

    from sqlalchemy import cast, Float
    sub_imp = (
        select(func.max(ExtractedEvent.importance))
        .join(EventClusterMember, EventClusterMember.extracted_event_id == ExtractedEvent.id)
        .where(EventClusterMember.event_cluster_id == EventCluster.id)
        .scalar_subquery()
    )
    raw_imp = cast(EventCluster.metadata_['importance'].as_string(), Float)
    imp_expr = func.coalesce(raw_imp, sub_imp, 0.0)

    if min_importance is not None:
        stmt = stmt.where(imp_expr >= min_importance)
        count_stmt = count_stmt.where(imp_expr >= min_importance)

    if location_entity_id:
        stmt = stmt.where(EventCluster.primary_location_entity_id == location_entity_id)
        count_stmt = count_stmt.where(EventCluster.primary_location_entity_id == location_entity_id)

    if entity_id:
        from backend.app.models.entity import DocumentEntity
        subquery = (
            select(EventClusterMember.event_cluster_id)
            .join(ExtractedEvent, ExtractedEvent.id == EventClusterMember.extracted_event_id)
            .outerjoin(DocumentEntity, DocumentEntity.document_id == ExtractedEvent.document_id)
            .where(
                (ExtractedEvent.location_entity_id == entity_id) |
                (DocumentEntity.entity_id == entity_id)
            )
        )
        stmt = stmt.where(
            (EventCluster.primary_location_entity_id == entity_id) |
            (EventCluster.id.in_(subquery))
        )
        count_stmt = count_stmt.where(
            (EventCluster.primary_location_entity_id == entity_id) |
            (EventCluster.id.in_(subquery))
        )

    if from_time:
        stmt = stmt.where(EventCluster.event_time_start >= from_time)
        count_stmt = count_stmt.where(EventCluster.event_time_start >= from_time)

    if to_time:
        stmt = stmt.where(EventCluster.event_time_end <= to_time)
        count_stmt = count_stmt.where(EventCluster.event_time_end <= to_time)

    if search:
        search_pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            EventCluster.canonical_title.ilike(search_pattern) |
            EventCluster.canonical_summary.ilike(search_pattern)
        )
        count_stmt = count_stmt.where(
            EventCluster.canonical_title.ilike(search_pattern) |
            EventCluster.canonical_summary.ilike(search_pattern)
        )

    # Ordering
    if order_by == "highest_confidence":
        stmt = stmt.order_by(desc(EventCluster.confidence), desc(EventCluster.event_time_start).nulls_last())
    elif order_by == "highest_importance":
        stmt = stmt.order_by(desc(imp_expr), desc(EventCluster.confidence), desc(EventCluster.event_time_start).nulls_last())
    elif order_by == "oldest":
        stmt = stmt.order_by(asc(EventCluster.event_time_start).nulls_last(), asc(EventCluster.created_at))
    elif order_by == "newest":
        stmt = stmt.order_by(desc(EventCluster.event_time_start).nulls_last(), desc(EventCluster.updated_at))
    else:
        stmt = stmt.order_by(desc(EventCluster.updated_at))

    total = db.scalar(count_stmt) or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size

    items = list(db.scalars(stmt.offset(offset).limit(page_size)).unique().all())

    return items, total, total_pages


def get_event_cluster(db: Session, cluster_id: UUID) -> Optional[EventCluster]:
    """Retrieve single event cluster by ID with members, documents, sources, and primary location."""
    stmt = (
        select(EventCluster)
        .options(
            joinedload(EventCluster.primary_location_entity),
            joinedload(EventCluster.members)
            .joinedload(EventClusterMember.extracted_event)
            .joinedload(ExtractedEvent.document)
            .joinedload(Document.source),
        )
        .where(EventCluster.id == cluster_id)
    )
    return db.scalars(stmt).unique().first()


def get_cluster_for_event(db: Session, event_id: UUID) -> Optional[EventClusterMember]:
    """Retrieve cluster membership record for an extracted event."""
    stmt = (
        select(EventClusterMember)
        .options(
            joinedload(EventClusterMember.cluster).joinedload(EventCluster.primary_location_entity),
            joinedload(EventClusterMember.extracted_event),
        )
        .where(EventClusterMember.extracted_event_id == event_id)
    )
    return db.scalars(stmt).first()


def get_cluster_members(db: Session, cluster_id: UUID) -> List[EventClusterMember]:
    """Retrieve all membership records for an event cluster."""
    stmt = (
        select(EventClusterMember)
        .options(
            joinedload(EventClusterMember.extracted_event).joinedload(ExtractedEvent.location_entity)
        )
        .where(EventClusterMember.event_cluster_id == cluster_id)
        .order_by(desc(EventClusterMember.membership_score))
    )
    return list(db.scalars(stmt).all())
