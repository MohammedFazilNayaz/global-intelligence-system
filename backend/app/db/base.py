import uuid
from datetime import datetime
from sqlalchemy import DateTime, Uuid, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from backend.app.utils.time import utc_now, ensure_utc


class UTCDateTime(TypeDecorator):
    """DateTime type that guarantees timezone-aware UTC datetimes across all DB engines."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return ensure_utc(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return ensure_utc(value)
        return value


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy models."""
    pass


class TimestampMixin:
    """Reusable mixin providing timezone-aware created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    """Reusable mixin providing a UUID primary key."""
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        sort_order=-1,
    )
