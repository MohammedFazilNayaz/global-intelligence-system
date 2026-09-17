from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from backend.app.db.session import get_db
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.event import ExtractedEvent
from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.schemas.cluster import EventClusterRead

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


from backend.app.services.economic_service import get_economic_dashboard_summary
from backend.app.services.market_service import get_market_dashboard_summary


class DashboardSummary(BaseModel):
    active_clusters_count: int
    total_events_count: int
    total_documents_count: int
    active_sources_count: int
    high_importance_events_count: int
    event_types_breakdown: Dict[str, int]
    recent_clusters: List[EventClusterRead]
    economic_summary: Optional[Dict[str, Any]] = None
    market_summary: Optional[Dict[str, Any]] = None


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    """Retrieve operational and intelligence summary metrics for the analyst dashboard."""
    active_clusters_count = db.scalar(
        select(func.count(EventCluster.id)).where(EventCluster.status == "ACTIVE")
    ) or 0

    total_events_count = db.scalar(
        select(func.count(ExtractedEvent.id))
    ) or 0

    total_documents_count = db.scalar(
        select(func.count(Document.id))
    ) or 0

    active_sources_count = db.scalar(
        select(func.count(Source.id)).where(Source.active.is_(True))
    ) or 0

    high_importance_events_count = db.scalar(
        select(func.count(ExtractedEvent.id)).where(ExtractedEvent.importance >= 0.80)
    ) or 0

    # Event types breakdown across active clusters
    types_rows = db.execute(
        select(EventCluster.event_type, func.count(EventCluster.id))
        .where(EventCluster.status == "ACTIVE")
        .group_by(EventCluster.event_type)
    ).all()
    event_types_breakdown = {row[0]: row[1] for row in types_rows}

    # Top 5 most recent active clusters
    recent_clusters_entities = list(
        db.scalars(
            select(EventCluster)
            .options(
                joinedload(EventCluster.primary_location_entity),
                joinedload(EventCluster.members).joinedload(EventClusterMember.extracted_event),
            )
            .where(EventCluster.status == "ACTIVE")
            .order_by(EventCluster.event_time_start.desc().nulls_last(), EventCluster.updated_at.desc())
            .limit(5)
        ).unique().all()
    )

    recent_clusters_reads: List[EventClusterRead] = []
    for c in recent_clusters_entities:
        importance_val = (c.metadata_ or {}).get("importance")
        if importance_val is None and c.members:
            importance_val = max(
                (m.extracted_event.importance for m in c.members if m.extracted_event and m.extracted_event.importance is not None),
                default=0.8,
            )

        source_count = (c.metadata_ or {}).get("unique_source_count", 1)
        doc_count = (c.metadata_ or {}).get("document_count", len(c.members))

        recent_clusters_reads.append(
            EventClusterRead(
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
        )

    econ_summary = get_economic_dashboard_summary(db=db)
    mkt_summary = get_market_dashboard_summary(db=db)

    return DashboardSummary(
        active_clusters_count=active_clusters_count,
        total_events_count=total_events_count,
        total_documents_count=total_documents_count,
        active_sources_count=active_sources_count,
        high_importance_events_count=high_importance_events_count,
        event_types_breakdown=event_types_breakdown,
        recent_clusters=recent_clusters_reads,
        economic_summary=econ_summary.model_dump(mode="json"),
        market_summary=mkt_summary.model_dump(mode="json"),
    )
