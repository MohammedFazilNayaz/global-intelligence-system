import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.exc import IntegrityError
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.document import Document
from backend.app.schemas.extraction import EntityType, EntityRole


def test_entity_model_creation(db_session):
    """Verify Entity model persistence with UUID, UTC timestamps, and JSON metadata."""
    entity = Entity(
        entity_type=EntityType.COUNTRY.value,
        canonical_name="United States",
        normalized_name="united states",
        description="Federal republic in North America",
        country_code="US",
        metadata_={"aliases": ["USA", "U.S."]},
    )
    db_session.add(entity)
    db_session.commit()
    db_session.refresh(entity)

    assert isinstance(entity.id, uuid.UUID)
    assert entity.entity_type == "COUNTRY"
    assert entity.canonical_name == "United States"
    assert entity.normalized_name == "united states"
    assert entity.country_code == "US"
    assert entity.metadata_["aliases"] == ["USA", "U.S."]
    assert entity.created_at.tzinfo == timezone.utc
    assert entity.updated_at.tzinfo == timezone.utc


def test_entity_unique_type_normalized_constraint(db_session):
    """Verify unique constraint on (entity_type, normalized_name)."""
    e1 = Entity(
        entity_type=EntityType.COUNTRY.value,
        canonical_name="Japan",
        normalized_name="japan",
    )
    db_session.add(e1)
    db_session.commit()

    e2 = Entity(
        entity_type=EntityType.COUNTRY.value,
        canonical_name="Japan",
        normalized_name="japan",
    )
    db_session.add(e2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_entity_different_type_same_name_allowed(db_session):
    """Verify entities with same name but different types can coexist (e.g. City vs Country)."""
    e1 = Entity(
        entity_type=EntityType.COUNTRY.value,
        canonical_name="Singapore",
        normalized_name="singapore",
    )
    e2 = Entity(
        entity_type=EntityType.CITY.value,
        canonical_name="Singapore",
        normalized_name="singapore",
    )
    db_session.add_all([e1, e2])
    db_session.commit()
    assert e1.id != e2.id


def test_document_entity_relationship_and_cascade(db_session, sample_document):
    """Verify DocumentEntity association, bidirectional relationships, and cascade on document delete."""
    entity = Entity(
        entity_type=EntityType.CENTRAL_BANK.value,
        canonical_name="Federal Reserve",
        normalized_name="federal reserve",
        country_code="US",
    )
    db_session.add(entity)
    db_session.commit()

    doc_entity = DocumentEntity(
        document_id=sample_document.id,
        entity_id=entity.id,
        mention_text="the Fed",
        entity_role=EntityRole.ACTOR.value,
        confidence=0.95,
        metadata_={"matched_token": "the Fed"},
    )
    db_session.add(doc_entity)
    db_session.commit()

    # Test bidirectional relationship
    db_session.refresh(sample_document)
    db_session.refresh(entity)
    assert len(sample_document.entity_mentions) == 1
    assert sample_document.entity_mentions[0].mention_text == "the Fed"
    assert len(entity.document_associations) == 1
    assert entity.document_associations[0].document_id == sample_document.id

    # Cascade test: deleting document deletes document_entity association, but keeps canonical entity
    db_session.delete(sample_document)
    db_session.commit()

    assert db_session.get(DocumentEntity, doc_entity.id) is None
    assert db_session.get(Entity, entity.id) is not None


def test_document_entity_unique_mention_constraint(db_session, sample_document):
    """Verify duplicate document_entity mentions with identical role and text are prevented."""
    entity = Entity(
        entity_type=EntityType.COMMODITY.value,
        canonical_name="Crude Oil",
        normalized_name="crude oil",
    )
    db_session.add(entity)
    db_session.commit()

    de1 = DocumentEntity(
        document_id=sample_document.id,
        entity_id=entity.id,
        mention_text="Crude Oil",
        entity_role=EntityRole.COMMODITY.value,
        confidence=0.9,
    )
    de2 = DocumentEntity(
        document_id=sample_document.id,
        entity_id=entity.id,
        mention_text="Crude Oil",
        entity_role=EntityRole.COMMODITY.value,
        confidence=0.9,
    )
    db_session.add(de1)
    db_session.commit()

    db_session.add(de2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
