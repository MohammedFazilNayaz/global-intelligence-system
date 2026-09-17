import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.exc import IntegrityError
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.processors.hasher import compute_content_hash


def test_source_model_creation(db_session):
    """Verify source model attributes, UUID, and timestamps."""
    source = Source(
        name="Global News Network",
        source_type="rss",
        base_url="https://gnn.example.com",
        feed_url="https://gnn.example.com/rss",
        reliability_score=0.9,
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    assert isinstance(source.id, uuid.UUID)
    assert source.active is True
    assert source.polling_interval_seconds == 300
    assert source.created_at.tzinfo is not None
    assert source.updated_at.tzinfo is not None


def test_source_unique_name_constraint(db_session):
    """Sources must enforce unique names."""
    s1 = Source(
        name="Unique Wire",
        source_type="rss",
        base_url="https://example1.com",
        feed_url="https://example1.com/rss",
    )
    s2 = Source(
        name="Unique Wire",
        source_type="rss",
        base_url="https://example2.com",
        feed_url="https://example2.com/rss",
    )
    db_session.add(s1)
    db_session.commit()

    db_session.add(s2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_document_model_creation_and_relationship(db_session, sample_source):
    """Verify document links to source and relationship populates."""
    now = datetime.now(timezone.utc)
    doc = Document(
        source_id=sample_source.id,
        title="Breaking Financial Report",
        url="https://example.com/item-99",
        published_at=now,
        content_hash=compute_content_hash("Breaking Financial Report", "https://example.com/item-99"),
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(sample_source)

    assert len(sample_source.documents) == 1
    assert sample_source.documents[0].title == "Breaking Financial Report"
    assert doc.source.name == sample_source.name


def test_document_duplicate_hash_constraint(db_session, sample_source):
    """Enforce unique constraint on (source_id, content_hash)."""
    now = datetime.now(timezone.utc)
    chash = compute_content_hash("Headline", "https://example.com/same-url")

    d1 = Document(
        source_id=sample_source.id,
        title="Headline",
        url="https://example.com/same-url",
        published_at=now,
        content_hash=chash,
    )
    d2 = Document(
        source_id=sample_source.id,
        title="Headline",
        url="https://example.com/same-url",
        published_at=now,
        content_hash=chash,
    )

    db_session.add(d1)
    db_session.commit()

    db_session.add(d2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_document_different_source_same_hash_allowed(db_session, sample_source):
    """V0.1 allows identical content hashes from different sources (cross-source deduplication is V0.3)."""
    now = datetime.now(timezone.utc)
    chash = compute_content_hash("Shared Wire Story", "https://example.com/wire-1")

    # Create second source
    source2 = Source(
        name="Secondary Wire",
        source_type="rss",
        base_url="https://secwire.example.com",
        feed_url="https://secwire.example.com/rss",
    )
    db_session.add(source2)
    db_session.commit()

    d1 = Document(
        source_id=sample_source.id,
        title="Shared Wire Story",
        url="https://example.com/wire-1",
        published_at=now,
        content_hash=chash,
    )
    d2 = Document(
        source_id=source2.id,
        title="Shared Wire Story",
        url="https://example.com/wire-1",
        published_at=now,
        content_hash=chash,
    )

    db_session.add(d1)
    db_session.add(d2)
    # Must commit cleanly without constraint violation
    db_session.commit()

    count = db_session.query(Document).filter(Document.content_hash == chash).count()
    assert count == 2


def test_document_same_source_different_hash_allowed(db_session, sample_source):
    """Same source with different hashes must be accepted."""
    now = datetime.now(timezone.utc)
    d1 = Document(
        source_id=sample_source.id,
        title="Story Alpha",
        url="https://example.com/alpha",
        published_at=now,
        content_hash=compute_content_hash("Story Alpha", "https://example.com/alpha"),
    )
    d2 = Document(
        source_id=sample_source.id,
        title="Story Beta",
        url="https://example.com/beta",
        published_at=now,
        content_hash=compute_content_hash("Story Beta", "https://example.com/beta"),
    )
    db_session.add(d1)
    db_session.add(d2)
    db_session.commit()

    assert d1.id != d2.id

