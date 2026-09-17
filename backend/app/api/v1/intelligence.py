import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.intelligence_feed import (
    PaginatedLiveFeedResponse,
    OperationalMetricsResponse,
)
from backend.app.schemas.dossier import EventIntelligenceDossierResponse
from backend.app.services.live_feed_service import get_live_intelligence_feed
from backend.app.services.freshness_service import get_operational_metrics
from backend.app.services.dossier_service import build_event_intelligence_dossier

router = APIRouter(prefix="/intelligence", tags=["Real-Time Intelligence"])


@router.get("/metrics", response_model=OperationalMetricsResponse)
def get_operational_latency_metrics(
    db: Session = Depends(get_db),
) -> OperationalMetricsResponse:
    """Retrieve operational latency distributions (fetch, processing, and E2E percentiles)."""
    return get_operational_metrics(db)


@router.get("/live", response_model=PaginatedLiveFeedResponse)
def get_live_feed(
    since: Optional[datetime] = Query(None, description="Filter events on or after UTC datetime"),
    hours: Optional[int] = Query(None, ge=1, le=720, description="Relative time window in hours"),
    min_importance: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum calibrated importance"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum extraction confidence"),
    event_type: Optional[str] = Query(None, description="Filter by event category"),
    country_code: Optional[str] = Query(None, description="ISO-2 Country code filter"),
    entity_id: Optional[uuid.UUID] = Query(None, description="Entity filter"),
    source_id: Optional[uuid.UUID] = Query(None, description="Source filter"),
    limit: int = Query(20, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
) -> PaginatedLiveFeedResponse:
    """Retrieve chronologically ordered real-time global intelligence feed."""
    items, total, freshness_summary = get_live_intelligence_feed(
        db=db,
        since=since,
        hours=hours,
        min_importance=min_importance,
        min_confidence=min_confidence,
        event_type=event_type,
        country_code=country_code,
        entity_id=entity_id,
        source_id=source_id,
        limit=limit,
        offset=offset,
    )
    page = (offset // limit) + 1 if limit > 0 else 1
    return PaginatedLiveFeedResponse(
        total=total,
        items=items,
        page=page,
        page_size=limit,
        freshness_summary=freshness_summary,
    )


@router.get("/recent")
def get_recent_intelligence_summary(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """Retrieve summary statistics of recent global intelligence."""
    items, total, freshness_summary = get_live_intelligence_feed(
        db=db,
        hours=hours,
        limit=10,
        offset=0,
    )
    return {
        "window_hours": hours,
        "total_events_in_window": total,
        "freshness_summary": freshness_summary,
        "recent_highlights": [
            {
                "event_id": str(item.event_id),
                "title": item.event_title,
                "importance": item.importance,
                "confidence": item.confidence,
                "event_type": item.event_type,
                "location": item.primary_location,
                "cluster_title": item.cluster_title,
            }
            for item in items[:5]
        ],
    }


@router.get("/events/{event_id}/dossier", response_model=EventIntelligenceDossierResponse)
def get_event_dossier(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EventIntelligenceDossierResponse:
    """Retrieve compact but complete 21-field event intelligence dossier with rigorous evidence classification."""
    dossier = build_event_intelligence_dossier(db, event_id)
    if not dossier:
        raise HTTPException(status_code=404, detail=f"Intelligence event '{event_id}' not found")
    return dossier
