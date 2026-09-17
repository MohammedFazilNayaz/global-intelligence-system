from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from backend.app.models.source import Source
from backend.app.schemas.source import SourceCreate, SourceUpdate


def get_source(db: Session, source_id: UUID) -> Optional[Source]:
    """Retrieve a single source by UUID."""
    return db.get(Source, source_id)


def get_source_by_name(db: Session, name: str) -> Optional[Source]:
    """Retrieve a single source by exact name."""
    stmt = select(Source).where(Source.name == name)
    return db.scalars(stmt).first()


def list_sources(
    db: Session,
    active_only: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[Source], int]:
    """List sources with optional active filter and count."""
    stmt = select(Source)
    count_stmt = select(func.count(Source.id))

    if active_only:
        stmt = stmt.where(Source.active.is_(True))
        count_stmt = count_stmt.where(Source.active.is_(True))

    total = db.scalar(count_stmt) or 0
    items = list(db.scalars(stmt.order_by(Source.name).offset(skip).limit(limit)).all())
    return items, total


def create_source(db: Session, source_in: SourceCreate) -> Source:
    """Create and persist a new source."""
    config = dict(source_in.config_metadata or {})
    is_primary = getattr(source_in, "is_primary", False) or bool(config.get("is_primary", False))
    region = getattr(source_in, "region", None) or config.get("region", "Global")
    country = getattr(source_in, "country", None) or config.get("country", "XX")
    domain = getattr(source_in, "domain", None) or config.get("domain", "General")

    source = Source(
        name=source_in.name,
        source_type=source_in.source_type,
        base_url=source_in.base_url,
        feed_url=source_in.feed_url,
        reliability_score=source_in.reliability_score,
        active=source_in.active,
        polling_interval_seconds=source_in.polling_interval_seconds,
        config_metadata=config,
        is_primary=is_primary,
        region=region,
        country=country,
        domain=domain,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def update_source(db: Session, source_id: UUID, source_in: SourceUpdate) -> Optional[Source]:
    """Update an existing source."""
    source = get_source(db, source_id)
    if not source:
        return None

    update_data = source_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(source, field, value)

    db.commit()
    db.refresh(source)
    return source
