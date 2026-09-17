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


class MarketObservation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Database model representing structured historical market bar/candle observations."""
    __tablename__ = "market_observations"

    market_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("market_assets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, index=True, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    interval: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    market_asset: Mapped["MarketAsset"] = relationship("MarketAsset", back_populates="observations")

    __table_args__ = (
        UniqueConstraint("market_asset_id", "interval", "timestamp", "source", name="uq_market_obs_asset_interval_ts_source"),
        Index("ix_market_obs_asset_interval_ts", "market_asset_id", "interval", "timestamp"),
        Index("ix_market_obs_asset_ts", "market_asset_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<MarketObservation id={self.id} asset={self.market_asset_id} "
            f"interval={self.interval} ts={self.timestamp} close={self.close}>"
        )
