import uuid
from datetime import datetime
from typing import Optional, Dict, Any
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


class EntityRelationship(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Database model representing a verified, evidence-backed relationship between entities."""
    __tablename__ = "entity_relationships"

    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("entities.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("entities.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    source_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("extracted_events.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    extraction_method: Mapped[str] = mapped_column(String(64), default="rule_based_v0.7", nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(32), default="v0.7.0", nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    source_entity: Mapped["Entity"] = relationship(
        "Entity",
        foreign_keys=[source_entity_id],
        back_populates="outbound_relationships",
    )
    target_entity: Mapped["Entity"] = relationship(
        "Entity",
        foreign_keys=[target_entity_id],
        back_populates="inbound_relationships",
    )
    source_document: Mapped[Optional["Document"]] = relationship("Document")
    source_event: Mapped[Optional["ExtractedEvent"]] = relationship("ExtractedEvent")

    __table_args__ = (
        UniqueConstraint(
            "source_entity_id",
            "target_entity_id",
            "relationship_type",
            name="uq_entity_relationship_source_target_type",
        ),
        Index("ix_entity_relationships_source_type", "source_entity_id", "relationship_type"),
        Index("ix_entity_relationships_target_type", "target_entity_id", "relationship_type"),
    )

    def __repr__(self) -> str:
        return f"<EntityRelationship {self.source_entity_id} -[{self.relationship_type}]-> {self.target_entity_id}>"
