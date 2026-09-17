import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.geo import (
    GeoFeatureCollection,
    EventGeographicContext,
    LocationState,
)
from backend.app.schemas.event import PaginatedEvents, ExtractedEventRead
from backend.app.services import geo_service
from backend.app.services import event_service

router = APIRouter(prefix="/geo", tags=["Geographic Intelligence"])


@router.get("/features", response_model=GeoFeatureCollection)
def get_geographic_features(
    min_lon: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Minimum longitude (west boundary)"),
    min_lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Minimum latitude (south boundary)"),
    max_lon: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Maximum longitude (east boundary)"),
    max_lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Maximum latitude (north boundary)"),
    location_state: Optional[str] = Query(None, description="Filter by location state (RESOLVED, APPROXIMATE, REGIONAL, UNRESOLVED)"),
    event_type: Optional[str] = Query(None, description="Filter by event category"),
    country_code: Optional[str] = Query(None, max_length=8, description="ISO-2 Country code filter"),
    min_importance: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum event importance threshold"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum extraction confidence threshold"),
    from_time: Optional[datetime] = Query(None, description="Filter events on or after UTC datetime"),
    to_time: Optional[datetime] = Query(None, description="Filter events on or before UTC datetime"),
    freshness: Optional[str] = Query(None, description="Filter by freshness state (CURRENT, RECENT, STALE, HISTORICAL)"),
    include_unresolved: bool = Query(False, description="Whether to include features without coordinates in collection"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    db: Session = Depends(get_db),
) -> GeoFeatureCollection:
    """
    Retrieve paginated RFC 7946 GeoJSON FeatureCollection of intelligence events.
    Strictly read-only consumer: does not trigger ingestion, mutate events, or fabricate coordinates.
    """
    return geo_service.get_geo_feature_collection(
        db=db,
        min_lon=min_lon,
        min_lat=min_lat,
        max_lon=max_lon,
        max_lat=max_lat,
        location_state=location_state,
        event_type=event_type,
        country_code=country_code,
        min_importance=min_importance,
        min_confidence=min_confidence,
        from_time=from_time,
        to_time=to_time,
        freshness=freshness,
        include_unresolved=include_unresolved,
        page=page,
        page_size=page_size,
    )


@router.get("/events/{event_id}", response_model=EventGeographicContext)
def get_event_geographic_context(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EventGeographicContext:
    """
    Retrieve complete geographic provenance and location contract for an event.
    Exposes location state, primary location, additional locations, and audit provenance.
    """
    event = event_service.get_event(db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extracted event with ID '{event_id}' not found.",
        )
    return geo_service.normalize_event_geography(event, db=db, include_additional_locations=True)


@router.get("/unresolved", response_model=PaginatedEvents)
def get_unresolved_geographic_events(
    event_type: Optional[str] = Query(None, description="Filter by event category"),
    min_importance: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum event importance"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> PaginatedEvents:
    """
    Retrieve paginated extracted events that normalize into the UNRESOLVED location state.
    Provides reliable backend query for the Spatially Unresolved Intelligence Tray.
    """
    items, total, total_pages = geo_service.get_unresolved_events(
        db=db,
        event_type=event_type,
        min_importance=min_importance,
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
