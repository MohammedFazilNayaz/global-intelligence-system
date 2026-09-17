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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, UTCDateTime


class EconomicIndicator(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Database model representing a global canonical economic indicator."""
    __tablename__ = "economic_indicators"

    symbol: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    canonical_name: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    indicator_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    economic_domain: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    country_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("entities.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    default_unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    country_entity: Mapped[Optional["Entity"]] = relationship(
        "Entity",
        back_populates="economic_indicators",
    )
    observations: Mapped[List["EconomicObservation"]] = relationship(
        "EconomicObservation",
        back_populates="indicator",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_economic_indicators_domain_type", "economic_domain", "indicator_type"),
        UniqueConstraint("indicator_type", "country_entity_id", name="uq_indicator_type_country"),
    )

    def __repr__(self) -> str:
        return f"<EconomicIndicator id={self.id} type='{self.indicator_type}' name='{self.canonical_name}'>"
