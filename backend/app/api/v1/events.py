from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.schemas.event import ExtractedEventRead, PaginatedEvents
from backend.app.services import event_service

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("", response_model=PaginatedEvents)
def list_events(
    event_type: Optional[str] = Query(None, description="Filter by event type (e.g. central_bank_decision, conflict)"),
    document_id: Optional[UUID] = Query(None, description="Filter by parent document ID"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum extraction confidence"),
    min_importance: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum event importance"),
    order_by: str = Query(
        "importance_desc",
        pattern="^(importance_desc|created_at_desc|confidence_desc|event_time_desc)$",
        description="Sort ordering",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> PaginatedEvents:
    """Retrieve extracted intelligence events with filtering, confidence/importance thresholds, and pagination."""
    items, total, total_pages = event_service.list_events(
        db,
        document_id=document_id,
        event_type=event_type,
        min_confidence=min_confidence,
        min_importance=min_importance,
        order_by=order_by,
        page=page,
        page_size=page_size,
    )
    return PaginatedEvents(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
    )


@router.get("/{event_id}", response_model=ExtractedEventRead)
def get_event(
    event_id: UUID,
    db: Session = Depends(get_db),
) -> ExtractedEventRead:
    """Retrieve single extracted event metadata by UUID."""
    event = event_service.get_event(db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extracted event with ID '{event_id}' not found.",
        )
    return event


@router.get("/{event_id}/relationships")
def get_event_relationships(
    event_id: UUID,
    db: Session = Depends(get_db),
):
    """Retrieve cross-domain connections (entities, indicators, market assets) for an event."""
    from backend.app.services import graph_service

    res = graph_service.get_event_relationships(db, event_id=event_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extracted event with ID '{event_id}' not found.",
        )
    return res


@router.get("/{event_id}/impact")
def get_event_impact(
    event_id: UUID,
    db: Session = Depends(get_db),
):
    """Retrieve explainable, observational impact assessment for an event."""
    from backend.app.services import graph_service

    res = graph_service.get_event_impact_assessment(db, event_id=event_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extracted event with ID '{event_id}' not found.",
        )
    return res
