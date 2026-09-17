from datetime import datetime
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.schemas.document import DocumentRead, PaginatedDocuments
from backend.app.schemas.entity import DocumentEntityRead
from backend.app.schemas.event import ExtractedEventRead
from backend.app.schemas.extraction import ExtractionTriggerResponse
from backend.app.services import document_service, entity_service, event_service, extraction_service

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("", response_model=PaginatedDocuments)
def list_documents(
    source_id: Optional[UUID] = Query(None, description="Filter by source ID"),
    language: Optional[str] = Query(None, max_length=16, description="Filter by ISO language code"),
    processing_status: Optional[str] = Query(None, description="Filter by status (e.g. NORMALIZED)"),
    published_after: Optional[datetime] = Query(None, description="Filter documents published after UTC datetime"),
    published_before: Optional[datetime] = Query(None, description="Filter documents published before UTC datetime"),
    order_by: str = Query(
        "published_at_desc",
        pattern="^(published_at_desc|published_at_asc|ingested_at_desc|ingested_at_asc)$",
        description="Sort ordering",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> PaginatedDocuments:
    """Retrieve normalized intelligence documents with pagination, filtering, and ordering."""
    items, total, total_pages = document_service.list_documents(
        db,
        source_id=source_id,
        language=language,
        processing_status=processing_status,
        published_after=published_after,
        published_before=published_before,
        order_by=order_by,
        page=page,
        page_size=page_size,
    )

    return PaginatedDocuments(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
    )


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
) -> DocumentRead:
    """Retrieve a single document by UUID."""
    doc = document_service.get_document(db, doc_id=document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    return doc


@router.get("/{document_id}/entities", response_model=list[DocumentEntityRead])
def get_document_entities(
    document_id: UUID,
    db: Session = Depends(get_db),
) -> list[DocumentEntityRead]:
    """Retrieve all entity mentions extracted from a specific document."""
    doc = document_service.get_document(db, doc_id=document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    return entity_service.get_document_entities(db, document_id=document_id)


@router.get("/{document_id}/events", response_model=list[ExtractedEventRead])
def get_document_events(
    document_id: UUID,
    db: Session = Depends(get_db),
) -> list[ExtractedEventRead]:
    """Retrieve all events extracted from a specific document."""
    doc = document_service.get_document(db, doc_id=document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    return event_service.get_document_events(db, document_id=document_id)


@router.post("/{document_id}/extract", response_model=ExtractionTriggerResponse)
def trigger_document_extraction(
    document_id: UUID,
    reprocess: bool = Query(False, description="Force re-extraction and replacement of existing intelligence"),
    db: Session = Depends(get_db),
) -> ExtractionTriggerResponse:
    """Execute intelligence extraction on a document and persist structured entities and events."""
    doc = document_service.get_document(db, doc_id=document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    try:
        return extraction_service.extract_from_document(
            db=db,
            document_id=document_id,
            reprocess=reprocess,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Intelligence extraction failed: {exc}",
        )

