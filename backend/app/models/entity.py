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


class Entity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Database model representing a global canonical intelligence entity."""
    __tablename__ = "entities"

    entity_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(8), index=True, nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    document_associations: Mapped[List["DocumentEntity"]] = relationship(
        "DocumentEntity",
        back_populates="entity",
        cascade="all, delete-orphan",
    )
    economic_indicators: Mapped[List["EconomicIndicator"]] = relationship(
        "EconomicIndicator",
        back_populates="country_entity",
    )
    market_assets: Mapped[List["MarketAsset"]] = relationship(
        "MarketAsset",
        back_populates="entity",
    )
    outbound_relationships: Mapped[List["EntityRelationship"]] = relationship(
        "EntityRelationship",
        foreign_keys="[EntityRelationship.source_entity_id]",
        back_populates="source_entity",
        cascade="all, delete-orphan",
    )
    inbound_relationships: Mapped[List["EntityRelationship"]] = relationship(
        "EntityRelationship",
        foreign_keys="[EntityRelationship.target_entity_id]",
        back_populates="target_entity",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("entity_type", "normalized_name", name="uq_entities_type_normalized"),
    )

    def __repr__(self) -> str:
        return f"<Entity id={self.id} type='{self.entity_type}' canonical='{self.canonical_name}'>"


class DocumentEntity(Base, UUIDPrimaryKeyMixin):
    """Association model linking documents to entities with extraction provenance and role context."""
    __tablename__ = "document_entities"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("entities.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    mention_text: Mapped[str] = mapped_column(String(256), nullable=False)
    entity_role: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="entity_mentions")
    entity: Mapped["Entity"] = relationship("Entity", back_populates="document_associations")

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "entity_id",
            "entity_role",
            "mention_text",
            name="uq_document_entity_mention",
        ),
        Index("ix_document_entities_doc_entity", "document_id", "entity_id"),
        Index("ix_document_entities_entity_doc", "entity_id", "document_id"),
    )

    def __repr__(self) -> str:
        return f"<DocumentEntity doc={self.document_id} entity={self.entity_id} role='{self.entity_role}'>"
