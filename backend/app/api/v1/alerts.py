import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.alert import (
    AlertRead,
    PaginatedAlerts,
    AlertAcknowledgeRequest,
)
from backend.app.services import alert_service

router = APIRouter(prefix="/alerts", tags=["Intelligence Alerts"])


@router.get("", response_model=PaginatedAlerts)
def list_alerts(
    status: Optional[str] = Query(None, description="Filter by status: ACTIVE, ACKNOWLEDGED, RESOLVED"),
    trigger_type: Optional[str] = Query(None, description="Filter by trigger type"),
    min_importance: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum importance threshold"),
    limit: int = Query(50, ge=1, le=100, description="Page size limit"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> PaginatedAlerts:
    """List intelligence alerts with filtering and pagination."""
    items, total = alert_service.list_alerts(
        db,
        status=status,
        trigger_type=trigger_type,
        min_importance=min_importance,
        limit=limit,
        offset=offset,
    )
    return PaginatedAlerts(total=total, items=items)


@router.get("/{alert_id}", response_model=AlertRead)
def get_alert(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> AlertRead:
    """Retrieve details for a specific intelligence alert."""
    alert = alert_service.get_alert_by_id(db, alert_id=alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found.",
        )
    return alert


@router.post("/{alert_id}/acknowledge", response_model=AlertRead)
def acknowledge_alert(
    alert_id: uuid.UUID,
    request: Optional[AlertAcknowledgeRequest] = None,
    db: Session = Depends(get_db),
) -> AlertRead:
    """Acknowledge an active intelligence alert."""
    note = request.note if request else None
    alert = alert_service.acknowledge_alert(db, alert_id=alert_id, note=note)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found.",
        )
    return alert
