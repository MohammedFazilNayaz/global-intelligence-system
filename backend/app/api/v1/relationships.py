import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.relationship import (
    EntityRelationshipCreate,
    EntityRelationshipRead,
    EntityRelationshipWithEntities,
    PaginatedRelationships,
    RelationshipType,
)
from backend.app.services import graph_service

router = APIRouter(prefix="/relationships", tags=["Relationships"])


@router.get("", response_model=PaginatedRelationships)
def list_relationships(
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    source_entity_id: Optional[uuid.UUID] = Query(None, description="Filter by source entity ID"),
    target_entity_id: Optional[uuid.UUID] = Query(None, description="Filter by target entity ID"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> PaginatedRelationships:
    """List entity relationships with server-side pagination and filtering."""
    items, total, total_pages = graph_service.list_relationships(
        db,
        relationship_type=relationship_type,
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        min_confidence=min_confidence,
        page=page,
        page_size=page_size,
    )
    return PaginatedRelationships(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
    )


@router.post("", response_model=EntityRelationshipRead, status_code=status.HTTP_201_CREATED)
def create_relationship(
    rel_in: EntityRelationshipCreate,
    db: Session = Depends(get_db),
) -> EntityRelationshipRead:
    """Create a new entity relationship with mandatory evidence, provenance, and orphan checks."""
    try:
        rel = graph_service.create_relationship(db, rel_in)
        return rel
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )


@router.get("/{relationship_id}", response_model=EntityRelationshipWithEntities)
def get_relationship(
    relationship_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EntityRelationshipWithEntities:
    """Retrieve details of a single entity relationship by UUID."""
    rel = graph_service.get_relationship(db, relationship_id)
    if not rel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Relationship with ID '{relationship_id}' not found.",
        )
    return rel
