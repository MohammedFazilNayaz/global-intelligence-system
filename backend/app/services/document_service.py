import math
from datetime import datetime
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy import select, func, desc, asc
from sqlalchemy.orm import Session
from backend.app.models.document import Document


def get_document(db: Session, doc_id: UUID) -> Optional[Document]:
    """Retrieve a single document by UUID."""
    return db.get(Document, doc_id)


def list_documents(
    db: Session,
    source_id: Optional[UUID] = None,
    language: Optional[str] = None,
    processing_status: Optional[str] = None,
    published_after: Optional[datetime] = None,
    published_before: Optional[datetime] = None,
    order_by: str = "published_at_desc",
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Document], int, int]:
    """Retrieve paginated, filtered, and ordered documents.
    
    Returns (items, total_count, total_pages).
    """
    stmt = select(Document)
    count_stmt = select(func.count(Document.id))

    # Filters
    if source_id:
        stmt = stmt.where(Document.source_id == source_id)
        count_stmt = count_stmt.where(Document.source_id == source_id)

    if language:
        stmt = stmt.where(Document.language == language.lower())
        count_stmt = count_stmt.where(Document.language == language.lower())

    if processing_status:
        stmt = stmt.where(Document.processing_status == processing_status)
        count_stmt = count_stmt.where(Document.processing_status == processing_status)

    if published_after:
        stmt = stmt.where(Document.published_at >= published_after)
        count_stmt = count_stmt.where(Document.published_at >= published_after)

    if published_before:
        stmt = stmt.where(Document.published_at <= published_before)
        count_stmt = count_stmt.where(Document.published_at <= published_before)

    # Ordering
    if order_by == "published_at_asc":
        stmt = stmt.order_by(asc(Document.published_at))
    elif order_by == "ingested_at_desc":
        stmt = stmt.order_by(desc(Document.ingested_at))
    elif order_by == "ingested_at_asc":
        stmt = stmt.order_by(asc(Document.ingested_at))
    else:  # default published_at_desc
        stmt = stmt.order_by(desc(Document.published_at))

    total = db.scalar(count_stmt) or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    offset = (page - 1) * page_size
    items = list(db.scalars(stmt.offset(offset).limit(page_size)).all())

    return items, total, total_pages
