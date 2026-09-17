import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, Integer, Text, JSON, Uuid, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, UTCDateTime
from backend.app.utils.time import utc_now


class IngestionRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks discrete execution runs of source ingestion with audit stats and provenance."""
    __tablename__ = "ingestion_runs"

    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="RUNNING",
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=utc_now,
        nullable=False,
        index=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime,
        nullable=True,
    )
    documents_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    documents_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicates_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failures_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_stats: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="ingestion_runs")

    __table_args__ = (
        Index("ix_ingestion_runs_source_started", "source_id", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<IngestionRun id={self.id} source_id={self.source_id} status='{self.status}' inserted={self.documents_inserted}>"
