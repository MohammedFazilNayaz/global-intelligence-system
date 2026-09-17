import math
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy import select, func, desc, asc
from sqlalchemy.orm import Session, joinedload
from backend.app.models.event import ExtractedEvent
from backend.app.utils.logger import setup_logger

logger = setup_logger("service.event")


def get_event(db: Session, event_id: UUID) -> Optional[ExtractedEvent]:
    """Retrieve an extracted event by UUID with location entity loaded."""
    stmt = (
        select(ExtractedEvent)
        .options(joinedload(ExtractedEvent.location_entity))
        .where(ExtractedEvent.id == event_id)
    )
    return db.scalars(stmt).first()


def list_events(
    db: Session,
    document_id: Optional[UUID] = None,
    event_type: Optional[str] = None,
    min_confidence: Optional[float] = None,
    min_importance: Optional[float] = None,
    order_by: str = "importance_desc",
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[ExtractedEvent], int, int]:
    """Retrieve paginated, filtered extracted events."""
    stmt = select(ExtractedEvent).options(joinedload(ExtractedEvent.location_entity))
    count_stmt = select(func.count(ExtractedEvent.id))

    if document_id:
        stmt = stmt.where(ExtractedEvent.document_id == document_id)
        count_stmt = count_stmt.where(ExtractedEvent.document_id == document_id)

    if event_type:
        stmt = stmt.where(ExtractedEvent.event_type == event_type.lower())
        count_stmt = count_stmt.where(ExtractedEvent.event_type == event_type.lower())

    if min_confidence is not None:
        stmt = stmt.where(ExtractedEvent.confidence >= min_confidence)
        count_stmt = count_stmt.where(ExtractedEvent.confidence >= min_confidence)

    if min_importance is not None:
        stmt = stmt.where(ExtractedEvent.importance >= min_importance)
        count_stmt = count_stmt.where(ExtractedEvent.importance >= min_importance)

    # Ordering
    if order_by == "created_at_desc":
        stmt = stmt.order_by(desc(ExtractedEvent.created_at))
    elif order_by == "confidence_desc":
        stmt = stmt.order_by(desc(ExtractedEvent.confidence))
    elif order_by == "event_time_desc":
        stmt = stmt.order_by(desc(ExtractedEvent.event_time))
    else:  # default importance_desc
        stmt = stmt.order_by(desc(ExtractedEvent.importance))

    total = db.scalar(count_stmt) or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    offset = (page - 1) * page_size
    items = list(db.scalars(stmt.offset(offset).limit(page_size)).all())

    return items, total, total_pages


def get_document_events(db: Session, document_id: UUID) -> List[ExtractedEvent]:
    """Retrieve all events extracted from a specific document."""
    stmt = (
        select(ExtractedEvent)
        .options(joinedload(ExtractedEvent.location_entity))
        .where(ExtractedEvent.document_id == document_id)
        .order_by(desc(ExtractedEvent.importance))
    )
    return list(db.scalars(stmt).all())
