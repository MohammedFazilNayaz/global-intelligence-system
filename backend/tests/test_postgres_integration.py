import os
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import psycopg

from backend.app.db.base import Base
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.event import ExtractedEvent
from backend.app.services.ingestion import ingest_from_source
from backend.app.services.extraction_service import extract_from_document
from backend.app.processors.normalizer import build_normalized_document
from backend.app.processors.hasher import compute_content_hash

PG_TEST_URL = os.environ.get(
    "PG_TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:@127.0.0.1:5432/global_intelligence_test",
)


def is_postgres_available() -> bool:
    try:
        with psycopg.connect("postgresql://postgres:@127.0.0.1:5432/global_intelligence_test", connect_timeout=2) as conn:
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not is_postgres_available(),
    reason="PostgreSQL 16 is not reachable on 127.0.0.1:5432",
)


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(PG_TEST_URL, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine):
    Session = sessionmaker(bind=pg_engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_postgresql_connection_and_engine_version(pg_session):
    """Verify integration connects to an actual PostgreSQL engine."""
    result = pg_session.execute(text("SELECT version();")).scalar()
    assert "PostgreSQL" in result


def test_postgresql_uuid_and_utc_timestamps(pg_session):
    """Verify PostgreSQL stores and returns native UUIDs and timezone-aware UTC datetimes."""
    source = Source(
        name=f"PG Test Source {uuid.uuid4().hex[:6]}",
        source_type="rss",
        base_url="https://example.com",
        feed_url="https://example.com/rss",
        reliability_score=0.9,
    )
    pg_session.add(source)
    pg_session.commit()
    pg_session.refresh(source)

    assert isinstance(source.id, uuid.UUID)
    assert source.created_at.tzinfo == timezone.utc
    assert source.updated_at.tzinfo == timezone.utc


def test_postgresql_foreign_key_enforcement(pg_session):
    """Verify PostgreSQL enforces Foreign Key integrity when inserting documents."""
    orphan_doc = Document(
        source_id=uuid.uuid4(),  # Non-existent source
        title="Orphan Document",
        url="https://example.com/orphan",
        published_at=datetime.now(timezone.utc),
        content_hash=compute_content_hash("Orphan", "https://example.com/orphan"),
    )
    pg_session.add(orphan_doc)
    with pytest.raises(IntegrityError) as exc_info:
        pg_session.commit()
    assert "violates foreign key constraint" in str(exc_info.value).lower()
    pg_session.rollback()


def test_postgresql_unique_constraint_enforcement(pg_session):
    """Verify PostgreSQL enforces unique (source_id, content_hash) constraint."""
    source = Source(
        name=f"PG Unique Test {uuid.uuid4().hex[:6]}",
        source_type="rss",
        base_url="https://example.com",
        feed_url="https://example.com/rss",
    )
    pg_session.add(source)
    pg_session.commit()

    now = datetime.now(timezone.utc)
    chash = compute_content_hash("Unique Headline", "https://example.com/unique")

    d1 = Document(
        source_id=source.id,
        title="Unique Headline",
        url="https://example.com/unique",
        published_at=now,
        content_hash=chash,
    )
    d2 = Document(
        source_id=source.id,
        title="Unique Headline",
        url="https://example.com/unique",
        published_at=now,
        content_hash=chash,
    )

    pg_session.add(d1)
    pg_session.commit()

    pg_session.add(d2)
    with pytest.raises(IntegrityError) as exc_info:
        pg_session.commit()
    assert "uq_documents_source_content_hash" in str(exc_info.value)
    pg_session.rollback()


def test_postgresql_json_metadata_storage(pg_session):
    """Verify PostgreSQL stores and queries structured JSON data."""
    source = Source(
        name=f"PG JSON Source {uuid.uuid4().hex[:6]}",
        source_type="rss",
        base_url="https://example.com",
        feed_url="https://example.com/rss",
        config_metadata={"nested": {"keys": [1, 2, 3]}, "verified": True},
    )
    pg_session.add(source)
    pg_session.commit()
    pg_session.refresh(source)

    assert source.config_metadata["verified"] is True
    assert source.config_metadata["nested"]["keys"] == [1, 2, 3]


def test_postgresql_v0_2_entity_and_unique_constraint(pg_session):
    """Verify Entity model and (entity_type, normalized_name) unique constraint on PostgreSQL 16."""
    norm_name = f"test entity {uuid.uuid4().hex[:6]}"
    e1 = Entity(
        entity_type="COMPANY",
        canonical_name="Test Enterprise Corp",
        normalized_name=norm_name,
        country_code="US",
        metadata_={"industry": "defense", "verified": True},
    )
    pg_session.add(e1)
    pg_session.commit()
    pg_session.refresh(e1)

    assert isinstance(e1.id, uuid.UUID)
    assert e1.created_at.tzinfo == timezone.utc
    assert e1.metadata_["industry"] == "defense"

    # Duplicate constraint
    e2 = Entity(
        entity_type="COMPANY",
        canonical_name="Test Enterprise Corp",
        normalized_name=norm_name,
    )
    pg_session.add(e2)
    with pytest.raises(IntegrityError) as exc_info:
        pg_session.commit()
    assert "uq_entities_type_normalized" in str(exc_info.value)
    pg_session.rollback()


def test_postgresql_v0_2_document_entity_cascade(pg_session):
    """Verify DocumentEntity foreign keys and ON DELETE CASCADE on PostgreSQL 16."""
    source = Source(
        name=f"PG Doc Cascade Source {uuid.uuid4().hex[:6]}",
        source_type="rss",
        base_url="https://example.com",
        feed_url="https://example.com/rss",
    )
    pg_session.add(source)
    pg_session.commit()

    now = datetime.now(timezone.utc)
    doc = Document(
        source_id=source.id,
        title="Cascade Test Headline",
        url=f"https://example.com/cascade/{uuid.uuid4().hex[:6]}",
        published_at=now,
        content_hash=compute_content_hash("Cascade", f"https://example.com/{uuid.uuid4()}"),
    )
    entity = Entity(
        entity_type="LOCATION",
        canonical_name=f"Strait of Test {uuid.uuid4().hex[:4]}",
        normalized_name=f"strait of test {uuid.uuid4().hex[:4]}",
    )
    pg_session.add_all([doc, entity])
    pg_session.commit()

    de = DocumentEntity(
        document_id=doc.id,
        entity_id=entity.id,
        mention_text="Strait of Test",
        entity_role="location",
        confidence=0.91,
    )
    pg_session.add(de)
    pg_session.commit()

    de_id = de.id
    # Delete document -> document_entity should cascade delete in PostgreSQL
    pg_session.delete(doc)
    pg_session.commit()

    assert pg_session.get(DocumentEntity, de_id) is None
    # Entity itself must be preserved
    assert pg_session.get(Entity, entity.id) is not None


def test_postgresql_v0_2_extracted_events_and_set_null(pg_session):
    """Verify ExtractedEvent location_entity_id ON DELETE SET NULL behavior on PostgreSQL 16."""
    source = Source(
        name=f"PG Event Source {uuid.uuid4().hex[:6]}",
        source_type="rss",
        base_url="https://example.com",
        feed_url="https://example.com/rss",
    )
    pg_session.add(source)
    pg_session.commit()

    now = datetime.now(timezone.utc)
    doc = Document(
        source_id=source.id,
        title="PG Event Test Doc",
        url=f"https://example.com/ev/{uuid.uuid4().hex[:6]}",
        published_at=now,
        content_hash=compute_content_hash("Event Test", f"https://example.com/{uuid.uuid4()}"),
    )
    loc = Entity(
        entity_type="CITY",
        canonical_name=f"Geneva Test {uuid.uuid4().hex[:4]}",
        normalized_name=f"geneva test {uuid.uuid4().hex[:4]}",
    )
    pg_session.add_all([doc, loc])
    pg_session.commit()

    event = ExtractedEvent(
        document_id=doc.id,
        event_type="international_agreement",
        event_title="Peace Accord Signed in Geneva",
        location_entity_id=loc.id,
        confidence=0.95,
        importance=0.88,
        metadata_={"verified": True},
    )
    pg_session.add(event)
    pg_session.commit()
    pg_session.refresh(event)

    assert event.location_entity_id == loc.id

    # Delete loc -> location_entity_id should become NULL in PostgreSQL
    pg_session.delete(loc)
    pg_session.commit()
    pg_session.refresh(event)

    assert event.location_entity_id is None

