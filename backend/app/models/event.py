import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    String,
    Text,
    Float,
    ForeignKey,
    JSON,
    Uuid,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, UTCDateTime


class ExtractedEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Database model representing an extracted event metadata record from a document."""
    __tablename__ = "extracted_events"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    event_title: Mapped[str] = mapped_column(String(512), nullable=False)
    event_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_time: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    location_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("entities.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    importance: Mapped[float] = mapped_column(Float, index=True, nullable=False)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="extracted_events")
    location_entity: Mapped[Optional["Entity"]] = relationship("Entity")
    cluster_membership: Mapped[Optional["EventClusterMember"]] = relationship(
        "EventClusterMember",
        back_populates="extracted_event",
        uselist=False,
        cascade="all, delete-orphan",
    )
    economic_observations: Mapped[List["EconomicObservation"]] = relationship(
        "EconomicObservation",
        back_populates="extracted_event",
        cascade="all, delete-orphan",
    )
    market_correlations: Mapped[List["EventMarketCorrelation"]] = relationship(
        "EventMarketCorrelation",
        back_populates="extracted_event",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_extracted_events_doc_type", "document_id", "event_type"),
    )

    def __repr__(self) -> str:
        return f"<ExtractedEvent id={self.id} type='{self.event_type}' title='{self.event_title[:30]}...'>"
