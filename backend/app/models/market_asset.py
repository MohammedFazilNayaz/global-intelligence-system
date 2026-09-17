import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    String,
    Text,
    ForeignKey,
    JSON,
    Uuid,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, UTCDateTime


class MarketAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Database model representing a canonical market asset (e.g. BTC-USD, SPX, EUR/USD)."""
    __tablename__ = "market_assets"

    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    exchange_venue: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    quote_currency: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    base_currency: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("entities.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    entity: Mapped[Optional["Entity"]] = relationship(
        "Entity",
        back_populates="market_assets",
    )
    observations: Mapped[List["MarketObservation"]] = relationship(
        "MarketObservation",
        back_populates="market_asset",
        cascade="all, delete-orphan",
    )
    correlations: Mapped[List["EventMarketCorrelation"]] = relationship(
        "EventMarketCorrelation",
        back_populates="market_asset",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_market_assets_type_symbol", "asset_type", "symbol"),
    )

    def __repr__(self) -> str:
        return f"<MarketAsset id={self.id} symbol='{self.symbol}' name='{self.canonical_name}' type='{self.asset_type}'>"
