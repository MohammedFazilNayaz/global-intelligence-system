import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    String,
    Float,
    ForeignKey,
    JSON,
    Uuid,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, UTCDateTime


class EventMarketCorrelation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Database model representing deterministic temporal correlation between an event and market movement."""
    __tablename__ = "event_market_correlations"

    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("extracted_events.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    cluster_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("event_clusters.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    market_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("market_assets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    window_size: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    window_start: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    pre_event_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    event_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    post_event_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    return_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    absolute_change: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volatility: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_change: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_excursion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_excursion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    methodology: Mapped[str] = mapped_column(String(64), default="window_close_return", nullable=False)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    extracted_event: Mapped["ExtractedEvent"] = relationship(
        "ExtractedEvent",
        back_populates="market_correlations",
    )
    event_cluster: Mapped[Optional["EventCluster"]] = relationship(
        "EventCluster",
        back_populates="market_correlations",
    )
    market_asset: Mapped["MarketAsset"] = relationship(
        "MarketAsset",
        back_populates="correlations",
    )

    __table_args__ = (
        UniqueConstraint("event_id", "market_asset_id", "window_size", name="uq_event_asset_window"),
        Index("ix_corr_event_asset", "event_id", "market_asset_id"),
        Index("ix_corr_asset_window", "market_asset_id", "window_size"),
    )

    def __repr__(self) -> str:
        return (
            f"<EventMarketCorrelation id={self.id} event={self.event_id} asset={self.market_asset_id} "
            f"window={self.window_size} return={self.return_percent}%>"
        )
