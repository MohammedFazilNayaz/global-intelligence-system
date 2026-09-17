import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    String,
    Float,
    Boolean,
    Integer,
    ForeignKey,
    JSON,
    Uuid,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, UTCDateTime


class EconomicObservation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Database model representing a structured, evidence-backed economic observation."""
    __tablename__ = "economic_observations"

    indicator_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("economic_indicators.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("extracted_events.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    observation_period: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    observation_date: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    period_start: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    period_end: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    release_timestamp: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    is_revision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reported_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reported_unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    previous_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    revised_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    direction: Mapped[Optional[str]] = mapped_column(String(32), index=True, nullable=True)
    change_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    change_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calculation_method: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    economic_relevance: Mapped[float] = mapped_column(Float, index=True, default=0.5, nullable=False)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    indicator: Mapped["EconomicIndicator"] = relationship("EconomicIndicator", back_populates="observations")
    extracted_event: Mapped[Optional["ExtractedEvent"]] = relationship(
        "ExtractedEvent",
        back_populates="economic_observations",
    )
    document: Mapped[Optional["Document"]] = relationship("Document", back_populates="economic_observations")

    __table_args__ = (
        Index("ix_economic_obs_indicator_period", "indicator_id", "observation_period"),
        Index("ix_economic_obs_doc_indicator", "document_id", "indicator_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<EconomicObservation id={self.id} indicator={self.indicator_id} "
            f"reported={self.reported_value} {self.reported_unit}>"
        )
