from datetime import datetime
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.cluster import (
    EventClusterRead,
    EventClusterDetailRead,
    EventClusterMemberRead,
    MemberDocumentRead,
    PaginatedEventClusters,
)
from backend.app.services import clustering_service

router = APIRouter(tags=["Event Clusters"])


@router.get("/event-clusters", response_model=PaginatedEventClusters)
def list_event_clusters(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    status_filter: Optional[str] = Query("ACTIVE", alias="status", description="Filter by cluster status (ACTIVE, ARCHIVED, MERGED)"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum cluster confidence"),
    min_importance: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum event importance"),
    location_entity_id: Optional[UUID] = Query(None, description="Filter by primary location entity UUID"),
    entity_id: Optional[UUID] = Query(None, description="Filter by mentioned or related entity UUID"),
    from_time: Optional[datetime] = Query(None, description="Filter events on or after this timestamp"),
    to_time: Optional[datetime] = Query(None, description="Filter events on or before this timestamp"),
    search: Optional[str] = Query(None, description="Search canonical cluster title"),
    order_by: str = Query("newest", pattern="^(newest|highest_importance|highest_confidence|oldest)$", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> PaginatedEventClusters:
    """Retrieve paginated, filtered real-world event clusters."""
    items, total, total_pages = clustering_service.list_event_clusters(
        db=db,
        event_type=event_type,
        status=status_filter,
        min_confidence=min_confidence,
        min_importance=min_importance,
        location_entity_id=location_entity_id,
        entity_id=entity_id,
        from_time=from_time,
        to_time=to_time,
        search=search,
        order_by=order_by,
        page=page,
        page_size=page_size,
    )

    cluster_reads: List[EventClusterRead] = []
    for c in items:
        source_count = (c.metadata_ or {}).get("unique_source_count", 1)
        doc_count = (c.metadata_ or {}).get("document_count", len(c.members) if c.members else 1)
        importance_val = (c.metadata_ or {}).get("importance")
        if importance_val is None and c.members:
            importance_val = max(
                (m.extracted_event.importance for m in c.members if m.extracted_event and m.extracted_event.importance is not None),
                default=0.8,
            )

        cr = EventClusterRead(
            id=c.id,
            canonical_title=c.canonical_title,
            canonical_summary=c.canonical_summary,
            event_type=c.event_type,
            event_time_start=c.event_time_start,
            event_time_end=c.event_time_end,
            primary_location_entity_id=c.primary_location_entity_id,
            confidence=c.confidence,
            importance=importance_val or 0.8,
            status=c.status,
            metadata=c.metadata_ or {},
            created_at=c.created_at,
            updated_at=c.updated_at,
            primary_location_entity=c.primary_location_entity,
            members_count=len(c.members) if c.members else doc_count,
            unique_sources_count=source_count,
            member_count=len(c.members) if c.members else doc_count,
            unique_source_count=source_count,
        )
        cluster_reads.append(cr)

    return PaginatedEventClusters(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=cluster_reads,
    )


@router.get("/event-clusters/{cluster_id}", response_model=EventClusterDetailRead)
def get_event_cluster(
    cluster_id: UUID,
    db: Session = Depends(get_db),
) -> EventClusterDetailRead:
    """Retrieve details of a single event cluster, including its members and explainable provenance."""
    cluster = clustering_service.get_event_cluster(db=db, cluster_id=cluster_id)
    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event cluster with ID '{cluster_id}' not found.",
        )

    members_reads: List[EventClusterMemberRead] = []
    for m in cluster.members:
        doc_obj = None
        if m.extracted_event and m.extracted_event.document:
            d = m.extracted_event.document
            doc_obj = MemberDocumentRead(
                id=d.id,
                source_id=d.source_id,
                source_name=d.source.name if d.source else None,
                title=d.title,
                url=d.url,
                published_at=d.published_at,
            )

        members_reads.append(
            EventClusterMemberRead(
                id=m.id,
                event_cluster_id=m.event_cluster_id,
                extracted_event_id=m.extracted_event_id,
                membership_score=m.membership_score,
                membership_method=m.membership_method,
                metadata=m.metadata_ or {},
                created_at=m.created_at,
                extracted_event=m.extracted_event,
                document=doc_obj,
            )
        )

    unique_source_ids = set()
    for m in cluster.members:
        if m.extracted_event and m.extracted_event.document and m.extracted_event.document.source_id:
            unique_source_ids.add(m.extracted_event.document.source_id)

    source_count = (cluster.metadata_ or {}).get(
        "unique_source_count", len(unique_source_ids) if unique_source_ids else 1
    )
    doc_count = (cluster.metadata_ or {}).get("document_count", len(cluster.members))
    importance_val = (cluster.metadata_ or {}).get("importance")
    if importance_val is None and cluster.members:
        importance_val = max(
            (m.extracted_event.importance for m in cluster.members if m.extracted_event and m.extracted_event.importance is not None),
            default=0.8,
        )

    return EventClusterDetailRead(
        id=cluster.id,
        canonical_title=cluster.canonical_title,
        canonical_summary=cluster.canonical_summary,
        event_type=cluster.event_type,
        event_time_start=cluster.event_time_start,
        event_time_end=cluster.event_time_end,
        primary_location_entity_id=cluster.primary_location_entity_id,
        confidence=cluster.confidence,
        importance=importance_val or 0.8,
        status=cluster.status,
        metadata=cluster.metadata_ or {},
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
        primary_location_entity=cluster.primary_location_entity,
        members_count=len(cluster.members),
        unique_sources_count=source_count,
        member_count=len(cluster.members),
        unique_source_count=source_count,
        members=members_reads,
    )


@router.get("/events/{event_id}/cluster", response_model=EventClusterMemberRead)
def get_cluster_for_event(
    event_id: UUID,
    db: Session = Depends(get_db),
) -> EventClusterMemberRead:
    """Retrieve the cluster membership record and score breakdown for an extracted event."""
    member = clustering_service.get_cluster_for_event(db=db, event_id=event_id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extracted event with ID '{event_id}' has not been assigned to a cluster.",
        )

    return EventClusterMemberRead(
        id=member.id,
        event_cluster_id=member.event_cluster_id,
        extracted_event_id=member.extracted_event_id,
        membership_score=member.membership_score,
        membership_method=member.membership_method,
        metadata=member.metadata_ or {},
        created_at=member.created_at,
        extracted_event=member.extracted_event,
    )


@router.get("/event-clusters/{cluster_id}/events", response_model=List[EventClusterMemberRead])
def get_cluster_events(
    cluster_id: UUID,
    db: Session = Depends(get_db),
) -> List[EventClusterMemberRead]:
    """Retrieve all member extracted events belonging to a cluster."""
    cluster = clustering_service.get_event_cluster(db=db, cluster_id=cluster_id)
    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event cluster with ID '{cluster_id}' not found.",
        )

    members = clustering_service.get_cluster_members(db=db, cluster_id=cluster_id)
    result: List[EventClusterMemberRead] = []
    for m in members:
        result.append(
            EventClusterMemberRead(
                id=m.id,
                event_cluster_id=m.event_cluster_id,
                extracted_event_id=m.extracted_event_id,
                membership_score=m.membership_score,
                membership_method=m.membership_method,
                metadata=m.metadata_ or {},
                created_at=m.created_at,
                extracted_event=m.extracted_event,
            )
        )
    return result


@router.post("/documents/{document_id}/cluster", response_model=List[EventClusterMemberRead])
def cluster_document(
    document_id: UUID,
    db: Session = Depends(get_db),
) -> List[EventClusterMemberRead]:
    """Explicitly trigger event clustering for all extracted events in a document."""
    try:
        members = clustering_service.cluster_document_events(db=db, document_id=document_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    return [
        EventClusterMemberRead(
            id=m.id,
            event_cluster_id=m.event_cluster_id,
            extracted_event_id=m.extracted_event_id,
            membership_score=m.membership_score,
            membership_method=m.membership_method,
            metadata=m.metadata_ or {},
            created_at=m.created_at,
        )
        for m in members
    ]
