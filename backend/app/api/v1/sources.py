from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.schemas.source import (
    SourceRead,
    SourceCreate,
    SourceUpdate,
    PaginatedSources,
)
from backend.app.schemas.ingestion import SourceHealthSummary
from backend.app.services import source_service, freshness_service
from backend.app.services.ingestion import ingest_from_source, IngestionStats

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("/health", response_model=List[SourceHealthSummary])
def get_sources_health(
    db: Session = Depends(get_db),
) -> List[SourceHealthSummary]:
    """Retrieve operational telemetry and freshness matrix for all configured sources."""
    return freshness_service.get_all_sources_health(db)


@router.get("", response_model=PaginatedSources)
def list_sources(
    active_only: bool = Query(False, description="Filter for active sources only"),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Page size limit"),
    db: Session = Depends(get_db),
) -> PaginatedSources:
    """List configured intelligence sources."""
    items, total = source_service.list_sources(
        db, active_only=active_only, skip=skip, limit=limit
    )
    return PaginatedSources(total=total, items=items)


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(
    source_in: SourceCreate,
    db: Session = Depends(get_db),
) -> SourceRead:
    """Register a new intelligence source."""
    existing = source_service.get_source_by_name(db, name=source_in.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source with name '{source_in.name}' already exists.",
        )
    return source_service.create_source(db, source_in)


@router.get("/{source_id}", response_model=SourceRead)
def get_source(
    source_id: UUID,
    db: Session = Depends(get_db),
) -> SourceRead:
    """Retrieve details for a specific intelligence source."""
    source = source_service.get_source(db, source_id=source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with ID '{source_id}' not found.",
        )
    return source


@router.patch("/{source_id}", response_model=SourceRead)
def update_source(
    source_id: UUID,
    source_in: SourceUpdate,
    db: Session = Depends(get_db),
) -> SourceRead:
    """Update configuration, active state, or cadence for an intelligence source."""
    source = source_service.update_source(db, source_id=source_id, source_in=source_in)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with ID '{source_id}' not found.",
        )
    return source


@router.post("/{source_id}/ingest", response_model=IngestionStats)
def trigger_source_ingestion(
    source_id: UUID,
    db: Session = Depends(get_db),
) -> IngestionStats:
    """Trigger an immediate data ingestion run for a specific source."""
    source = source_service.get_source(db, source_id=source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with ID '{source_id}' not found.",
        )
    try:
        return ingest_from_source(db, source=source)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ingestion failed for source '{source.name}': {str(exc)}",
        )

