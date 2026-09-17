import math
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy import select, func, desc, asc
from sqlalchemy.orm import Session, joinedload
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.schemas.extraction import ExtractedEntityMention
from backend.app.utils.logger import setup_logger

logger = setup_logger("service.entity")


def get_entity(db: Session, entity_id: UUID) -> Optional[Entity]:
    """Retrieve an entity by primary key UUID."""
    return db.get(Entity, entity_id)


def get_or_create_entity(db: Session, mention: ExtractedEntityMention) -> Entity:
    """Retrieve existing canonical entity by (entity_type, normalized_name) or create a new one."""
    stmt = select(Entity).where(
        Entity.entity_type == mention.entity_type,
        Entity.normalized_name == mention.normalized_name,
    )
    existing = db.scalars(stmt).first()
    if existing:
        return existing

    # Create canonical entity record
    new_entity = Entity(
        entity_type=mention.entity_type,
        canonical_name=mention.canonical_name,
        normalized_name=mention.normalized_name,
        description=mention.description,
        country_code=mention.country_code,
        metadata_=mention.metadata,
    )
    db.add(new_entity)
    db.flush()  # Populate new_entity.id without full commit
    return new_entity


def list_entities(
    db: Session,
    entity_type: Optional[str] = None,
    country_code: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Entity], int, int]:
    """Retrieve paginated, filtered canonical entities."""
    stmt = select(Entity)
    count_stmt = select(func.count(Entity.id))

    if entity_type:
        stmt = stmt.where(Entity.entity_type == entity_type.upper())
        count_stmt = count_stmt.where(Entity.entity_type == entity_type.upper())

    if country_code:
        stmt = stmt.where(Entity.country_code == country_code.upper())
        count_stmt = count_stmt.where(Entity.country_code == country_code.upper())

    if search:
        search_pattern = f"%{search.lower().strip()}%"
        stmt = stmt.where(
            func.lower(Entity.canonical_name).like(search_pattern)
            | Entity.normalized_name.like(search_pattern)
        )
        count_stmt = count_stmt.where(
            func.lower(Entity.canonical_name).like(search_pattern)
            | Entity.normalized_name.like(search_pattern)
        )

    stmt = stmt.order_by(asc(Entity.canonical_name))

    total = db.scalar(count_stmt) or 0
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    offset = (page - 1) * page_size
    items = list(db.scalars(stmt.offset(offset).limit(page_size)).all())

    return items, total, total_pages


def get_document_entities(db: Session, document_id: UUID) -> List[DocumentEntity]:
    """Retrieve all entity mentions for a specific document with eager-loaded entity details."""
    stmt = (
        select(DocumentEntity)
        .options(joinedload(DocumentEntity.entity))
        .where(DocumentEntity.document_id == document_id)
        .order_by(desc(DocumentEntity.confidence))
    )
    return list(db.scalars(stmt).all())
