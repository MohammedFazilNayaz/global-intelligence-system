from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.economic import (
    EconomicIndicatorRead,
    EconomicIndicatorListResponse,
    EconomicObservationListResponse,
    EconomicObservationRead,
)
from backend.app.services.economic_service import (
    get_economic_indicators,
    get_economic_indicator_by_id,
    get_economic_observations,
)

router = APIRouter(prefix="/economic-indicators", tags=["economic-indicators"])


@router.get("", response_model=EconomicIndicatorListResponse)
def list_indicators_endpoint(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    domain: Optional[str] = Query(None, description="Filter by economic domain"),
    country_id: Optional[UUID] = Query(None, description="Filter by country entity UUID"),
    indicator_type: Optional[str] = Query(None, description="Filter by indicator type taxonomy"),
    search: Optional[str] = Query(None, description="Search indicator names"),
    db: Session = Depends(get_db),
):
    """List canonical economic indicators with server-side filtering and pagination."""
    items, total = get_economic_indicators(
        db=db,
        page=page,
        page_size=page_size,
        domain=domain,
        country_id=country_id,
        indicator_type=indicator_type,
        search=search,
    )
    return EconomicIndicatorListResponse(
        items=[EconomicIndicatorRead.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{id}", response_model=EconomicIndicatorRead)
def get_indicator_endpoint(
    id: UUID,
    db: Session = Depends(get_db),
):
    """Retrieve detailed economic indicator by UUID."""
    indicator = get_economic_indicator_by_id(db=db, indicator_id=id)
    if not indicator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Economic indicator '{id}' not found.",
        )
    return EconomicIndicatorRead.model_validate(indicator)


@router.get("/{id}/observations", response_model=EconomicObservationListResponse)
def get_indicator_observations_endpoint(
    id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    direction: Optional[str] = Query(None),
    min_relevance: Optional[float] = Query(None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    """Retrieve paginated time series observations for a given indicator."""
    indicator = get_economic_indicator_by_id(db=db, indicator_id=id)
    if not indicator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Economic indicator '{id}' not found.",
        )
    obs_items, total = get_economic_observations(
        db=db,
        page=page,
        page_size=page_size,
        indicator_id=id,
        direction=direction,
        min_relevance=min_relevance,
    )
    return EconomicObservationListResponse(
        items=[EconomicObservationRead.model_validate(o) for o in obs_items],
        total=total,
        page=page,
        page_size=page_size,
    )
