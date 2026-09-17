from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from sqlalchemy import select, func
from backend.app.models.document import Document
from backend.app.services.ingestion import ingest_from_source
from backend.app.processors.normalizer import build_normalized_document


def test_ingest_from_source_new_and_deduplication(db_session, sample_source):
    """Test full ingestion flow: initial batch insert followed by duplicate detection."""
    now = datetime(2026, 9, 7, 10, 0, 0, tzinfo=timezone.utc)
    doc1 = build_normalized_document(
        source_name=sample_source.name,
        title="Diplomatic Communique Issued",
        url="https://example.com/item/1",
        published_at=now,
        description="Leaders conclude summit.",
    )
    doc2 = build_normalized_document(
        source_name=sample_source.name,
        title="Maritime Security Agreement Signed",
        url="https://example.com/item/2",
        published_at=now,
        description="Pact guarantees freedom of navigation.",
    )

    mock_collector = MagicMock()
    mock_collector.collect.return_value = [doc1, doc2]

    # First ingestion run
    stats1 = ingest_from_source(db_session, sample_source, collector=mock_collector)
    assert stats1.total_fetched == 2
    assert stats1.new_ingested == 2
    assert stats1.duplicates_skipped == 0

    count = db_session.scalar(select(func.count(Document.id)))
    assert count == 2

    # Second ingestion run with identical items
    stats2 = ingest_from_source(db_session, sample_source, collector=mock_collector)
    assert stats2.total_fetched == 2
    assert stats2.new_ingested == 0
    assert stats2.duplicates_skipped == 2

    count_after = db_session.scalar(select(func.count(Document.id)))
    assert count_after == 2


def test_ingest_inactive_source_skips(db_session, sample_source):
    """Inactive sources must not perform collection."""
    sample_source.active = False
    db_session.commit()

    mock_collector = MagicMock()
    stats = ingest_from_source(db_session, sample_source, collector=mock_collector)

    assert stats.total_fetched == 0
    assert stats.new_ingested == 0
    mock_collector.collect.assert_not_called()


def test_ingest_different_sources_same_content_accepted(db_session, sample_source):
    """In V0.1, identical content published by two different sources is stored under both sources."""
    from backend.app.models.source import Source

    source2 = Source(
        name="Independent Wire",
        source_type="rss",
        base_url="https://independent.example.com",
        feed_url="https://independent.example.com/rss",
    )
    db_session.add(source2)
    db_session.commit()

    now = datetime(2026, 9, 7, 11, 0, 0, tzinfo=timezone.utc)
    shared_doc1 = build_normalized_document(
        source_name=sample_source.name,
        title="Syndicated Global Report",
        url="https://example.com/syndicated",
        published_at=now,
        description="Wire story picked up by multiple outlets.",
    )
    shared_doc2 = build_normalized_document(
        source_name=source2.name,
        title="Syndicated Global Report",
        url="https://example.com/syndicated",
        published_at=now,
        description="Wire story picked up by multiple outlets.",
    )

    mock_c1 = MagicMock()
    mock_c1.collect.return_value = [shared_doc1]
    stats1 = ingest_from_source(db_session, sample_source, collector=mock_c1)
    assert stats1.new_ingested == 1

    mock_c2 = MagicMock()
    mock_c2.collect.return_value = [shared_doc2]
    stats2 = ingest_from_source(db_session, source2, collector=mock_c2)
    assert stats2.new_ingested == 1
    assert stats2.duplicates_skipped == 0

