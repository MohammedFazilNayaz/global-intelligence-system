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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, UTCDateTime
from backend.app.utils.time import utc_now


class EventCluster(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Database model representing a real-world event synthesized from one or more reports."""
    __tablename__ = "event_clusters"

    canonical_title: Mapped[str] = mapped_column(String(512), nullable=False)
    canonical_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    event_time_start: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, index=True, nullable=True)
    event_time_end: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, index=True, nullable=True)
    primary_location_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("entities.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True, nullable=False)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    members: Mapped[List["EventClusterMember"]] = relationship(
        "EventClusterMember",
        back_populates="cluster",
        cascade="all, delete-orphan",
        order_by="desc(EventClusterMember.membership_score)",
    )
    primary_location_entity: Mapped[Optional["Entity"]] = relationship("Entity")
    market_correlations: Mapped[List["EventMarketCorrelation"]] = relationship(
        "EventMarketCorrelation",
        back_populates="event_cluster",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_event_clusters_type_time", "event_type", "event_time_start"),
        Index("ix_event_clusters_status_type", "status", "event_type"),
    )

    def __repr__(self) -> str:
        return f"<EventCluster id={self.id} type='{self.event_type}' title='{self.canonical_title[:30]}...'>"


class EventClusterMember(Base, UUIDPrimaryKeyMixin):
    """Association model linking an atomic ExtractedEvent to an EventCluster with match explanation."""
    __tablename__ = "event_cluster_members"

    event_cluster_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("event_clusters.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    extracted_event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("extracted_events.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    membership_score: Mapped[float] = mapped_column(Float, nullable=False)
    membership_method: Mapped[str] = mapped_column(String(64), default="deterministic_v0.3", nullable=False)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)

    # Relationships
    cluster: Mapped["EventCluster"] = relationship("EventCluster", back_populates="members")
    extracted_event: Mapped["ExtractedEvent"] = relationship(
        "ExtractedEvent",
        back_populates="cluster_membership",
    )

    __table_args__ = (
        UniqueConstraint("extracted_event_id", name="uq_cluster_member_event"),
        Index("ix_cluster_members_cluster_event", "event_cluster_id", "extracted_event_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<EventClusterMember cluster={self.event_cluster_id} "
            f"event={self.extracted_event_id} score={self.membership_score}>"
        )
