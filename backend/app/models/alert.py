import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import String, Float, Text, JSON, Uuid, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, UTCDateTime
from backend.app.utils.time import utc_now


class Alert(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Deterministic intelligence alert surfaced for high-importance events, economic shocks, or data quality events."""
    __tablename__ = "alerts"

    trigger_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    alert_title: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=utc_now,
        nullable=False,
        index=True,
    )
    importance: Mapped[float] = mapped_column(
        Float,
        default=0.5,
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.8,
        nullable=False,
    )
    affected_entity_ids: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    affected_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("extracted_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    affected_source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    evidence: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="ACTIVE",
        nullable=False,
        index=True,
    )
    metadata_: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    event: Mapped[Optional["ExtractedEvent"]] = relationship("ExtractedEvent")
    source: Mapped[Optional["Source"]] = relationship("Source")

    __table_args__ = (
        Index("ix_alerts_trigger_status", "trigger_type", "status"),
        Index("ix_alerts_event_trigger", "affected_event_id", "trigger_type"),
    )

    def __repr__(self) -> str:
        return f"<Alert id={self.id} trigger='{self.trigger_type}' title='{self.alert_title[:30]}' status='{self.status}'>"
