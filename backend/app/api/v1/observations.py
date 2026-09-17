from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.economic import (
    EconomicObservationRead,
    EconomicObservationDetailRead,
    EconomicObservationListResponse,
)
from backend.app.services.economic_service import (
    get_economic_observations,
    get_economic_observation_by_id,
)

router = APIRouter(prefix="/economic-observations", tags=["economic-observations"])


@router.get("", response_model=EconomicObservationListResponse)
def list_observations_endpoint(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    indicator_id: Optional[UUID] = Query(None, description="Filter by indicator UUID"),
    domain: Optional[str] = Query(None, description="Filter by economic domain"),
    country_id: Optional[UUID] = Query(None, description="Filter by country entity UUID"),
    direction: Optional[str] = Query(None, description="Filter by direction (increase, decrease, unchanged, hike, cut, hold)"),
    min_relevance: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum economic relevance"),
    from_time: Optional[datetime] = Query(None, description="Observation start date (ISO 8601)"),
    to_time: Optional[datetime] = Query(None, description="Observation end date (ISO 8601)"),
    db: Session = Depends(get_db),
):
    """List structured economic observations with server-side filtering, relevance ordering, and pagination."""
    items, total = get_economic_observations(
        db=db,
        page=page,
        page_size=page_size,
        indicator_id=indicator_id,
        domain=domain,
        country_id=country_id,
        direction=direction,
        min_relevance=min_relevance,
        from_time=from_time,
        to_time=to_time,
    )
    return EconomicObservationListResponse(
        items=[EconomicObservationRead.model_validate(o) for o in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{id}", response_model=EconomicObservationDetailRead)
def get_observation_endpoint(
    id: UUID,
    db: Session = Depends(get_db),
):
    """Retrieve detailed economic observation by UUID with full provenance trace."""
    obs = get_economic_observation_by_id(db=db, observation_id=id)
    if not obs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Economic observation '{id}' not found.",
        )

    # Resolve document and source details for complete provenance trace
    source_name = None
    doc_title = None
    doc_url = None
    if obs.document:
        doc_title = obs.document.title
        doc_url = obs.document.url
        if obs.document.source:
            source_name = obs.document.source.name

    evidence_snippet = (obs.metadata_ or {}).get("evidence_snippet")

    return EconomicObservationDetailRead(
        id=obs.id,
        indicator_id=obs.indicator_id,
        event_id=obs.event_id,
        document_id=obs.document_id,
        observation_period=obs.observation_period,
        observation_date=obs.observation_date,
        reported_value=obs.reported_value,
        reported_unit=obs.reported_unit,
        previous_value=obs.previous_value,
        expected_value=obs.expected_value,
        revised_value=obs.revised_value,
        direction=obs.direction,
        change_value=obs.change_value,
        change_percent=obs.change_percent,
        calculation_method=obs.calculation_method,
        economic_relevance=obs.economic_relevance,
        metadata_=obs.metadata_,
        created_at=obs.created_at,
        updated_at=obs.updated_at,
        indicator=obs.indicator,
        source_name=source_name,
        document_title=doc_title,
        document_url=doc_url,
        evidence_snippet=evidence_snippet,
    )
