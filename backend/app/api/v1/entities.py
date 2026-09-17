from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.schemas.entity import EntityRead, PaginatedEntities
from backend.app.schemas.event import ExtractedEventRead
from backend.app.schemas.economic import CountryEconomicProfileResponse
from backend.app.services import entity_service

router = APIRouter(prefix="/entities", tags=["Entities"])


@router.get("", response_model=PaginatedEntities)
def list_entities(
    entity_type: Optional[str] = Query(None, description="Filter by entity type (e.g. COUNTRY, CENTRAL_BANK)"),
    country_code: Optional[str] = Query(None, max_length=8, description="Filter by country code (e.g. US, GB)"),
    search: Optional[str] = Query(None, description="Search canonical or normalized name"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> PaginatedEntities:
    """Retrieve canonical intelligence entities with pagination and filtering."""
    items, total, total_pages = entity_service.list_entities(
        db,
        entity_type=entity_type,
        country_code=country_code,
        search=search,
        page=page,
        page_size=page_size,
    )
    return PaginatedEntities(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
    )


@router.get("/{entity_id}", response_model=EntityRead)
def get_entity(
    entity_id: UUID,
    db: Session = Depends(get_db),
) -> EntityRead:
    """Retrieve details for a single canonical entity by UUID."""
    entity = entity_service.get_entity(db, entity_id=entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity with ID '{entity_id}' not found.",
        )
    return entity


@router.get("/{entity_id}/events", response_model=List[ExtractedEventRead])
def get_entity_events(
    entity_id: UUID,
    db: Session = Depends(get_db),
) -> List[ExtractedEventRead]:
    """Retrieve all extracted events linked to an entity by location or document mention."""
    entity = entity_service.get_entity(db, entity_id=entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity with ID '{entity_id}' not found.",
        )

    from backend.app.models.event import ExtractedEvent
    from backend.app.models.entity import DocumentEntity
    from sqlalchemy.orm import joinedload
    from sqlalchemy import select, desc

    # Events where this entity is direct location or in document mentions
    stmt = (
        select(ExtractedEvent)
        .options(joinedload(ExtractedEvent.location_entity))
        .outerjoin(DocumentEntity, DocumentEntity.document_id == ExtractedEvent.document_id)
        .where(
            (ExtractedEvent.location_entity_id == entity_id) |
            (DocumentEntity.entity_id == entity_id)
        )
        .order_by(desc(ExtractedEvent.event_time).nulls_last(), desc(ExtractedEvent.created_at))
        .limit(100)
    )
    events = list(db.scalars(stmt).unique().all())[:50]
    return events


@router.get("/{entity_id}/economic-profile", response_model=CountryEconomicProfileResponse)
def get_entity_economic_profile(
    entity_id: UUID,
    db: Session = Depends(get_db),
):
    """Retrieve structured country or regional economic intelligence profile."""
    from backend.app.services.economic_service import get_country_economic_profile
    from backend.app.schemas.economic import CountryEconomicProfileResponse

    profile = get_country_economic_profile(db=db, country_entity_id=entity_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Economic profile for entity '{entity_id}' not found.",
        )
    return profile


@router.get("/{entity_id}/relationships")
def get_entity_relationships(
    entity_id: UUID,
    db: Session = Depends(get_db),
):
    """Retrieve direct outbound and inbound relationships for an entity."""
    from backend.app.services import graph_service
    from backend.app.schemas.relationship import EntityRelationshipWithEntities

    entity = entity_service.get_entity(db, entity_id=entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity with ID '{entity_id}' not found.",
        )

    outbound, inbound = graph_service.get_entity_relationships(db, entity_id)
    return {
        "entity_id": str(entity_id),
        "canonical_name": entity.canonical_name,
        "outbound": [EntityRelationshipWithEntities.model_validate(r) for r in outbound],
        "inbound": [EntityRelationshipWithEntities.model_validate(r) for r in inbound],
        "total_outbound": len(outbound),
        "total_inbound": len(inbound),
    }


@router.get("/{entity_id}/graph")
def get_entity_graph(
    entity_id: UUID,
    depth: int = Query(1, ge=1, le=3, description="Graph traversal depth (strictly bounded to max 3)"),
    limit: int = Query(50, ge=1, le=100, description="Max nodes to return"),
    db: Session = Depends(get_db),
):
    """Retrieve bounded knowledge subgraph centered on an entity."""
    from backend.app.services import graph_service

    entity = entity_service.get_entity(db, entity_id=entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity with ID '{entity_id}' not found.",
        )

    return graph_service.get_entity_subgraph(
        db,
        entity_id=entity_id,
        depth=depth,
        max_depth=3,
        limit=limit,
    )

