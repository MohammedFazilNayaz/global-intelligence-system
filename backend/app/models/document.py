import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Uuid,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, UTCDateTime
from backend.app.utils.time import utc_now


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Database model representing an ingested, normalized intelligence document."""
    __tablename__ = "documents"

    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sources.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(256), index=True, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_format: Mapped[str] = mapped_column(String(32), default="text/plain", nullable=False)
    url: Mapped[str] = mapped_column(Text, index=True, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    published_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="en", index=True, nullable=False)
    raw_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), default="NORMALIZED", index=True, nullable=False)

    # Relationship back to source
    source: Mapped["Source"] = relationship("Source", back_populates="documents")

    # V0.2 Intelligence Relationships
    entity_mentions: Mapped[List["DocumentEntity"]] = relationship(
        "DocumentEntity",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    extracted_events: Mapped[List["ExtractedEvent"]] = relationship(
        "ExtractedEvent",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    economic_observations: Mapped[List["EconomicObservation"]] = relationship(
        "EconomicObservation",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # Prevent exact duplicate content from the same source
        UniqueConstraint("source_id", "content_hash", name="uq_documents_source_content_hash"),
        # Optimized index for per-source chronological intelligence feeds
        Index("ix_documents_source_published", "source_id", "published_at"),
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} source_id={self.source_id} title='{self.title[:30]}...'>"
