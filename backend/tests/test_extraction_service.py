import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from backend.app.models.document import Document
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.event import ExtractedEvent
from backend.app.services.extraction_service import extract_from_document
from backend.app.schemas.extraction import ProcessingStatus
from backend.app.processors.hasher import compute_content_hash


@pytest.fixture
def extraction_test_document(db_session, sample_source) -> Document:
    """Fixture providing a test document with geopolitical and economic content."""
    now = datetime(2026, 9, 7, 11, 0, 0, tzinfo=timezone.utc)
    title = "United States Imposes New Sanctions on Foreign Drone Manufacturers"
    desc = "The Treasury Department in Washington announced asset freezes affecting export controls."
    content = "Officials confirmed the penalties target components shipped to conflict zones, affecting crude oil shipments."
    content_hash = compute_content_hash(title, "https://example.com/sanctions/01", desc)

    doc = Document(
        source_id=sample_source.id,
        title=title,
        description=desc,
        content=content,
        url="https://example.com/sanctions/01",
        published_at=now,
        content_hash=content_hash,
        processing_status="NORMALIZED",
        raw_metadata={},
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


def test_successful_extraction_pipeline(db_session, extraction_test_document):
    """Verify end-to-end extraction pipeline execution, status transition, and persistence."""
    assert extraction_test_document.processing_status == "NORMALIZED"

    resp = extract_from_document(db_session, extraction_test_document.id)

    db_session.refresh(extraction_test_document)
    assert extraction_test_document.processing_status == ProcessingStatus.EXTRACTED.value
    assert resp.entities_count > 0
    assert resp.events_count > 0

    # Verify document entities were stored in DB
    doc_entities = list(db_session.scalars(
        select(DocumentEntity).where(DocumentEntity.document_id == extraction_test_document.id)
    ).all())
    assert len(doc_entities) == resp.entities_count

    # Verify extracted events were stored in DB
    events = list(db_session.scalars(
        select(ExtractedEvent).where(ExtractedEvent.document_id == extraction_test_document.id)
    ).all())
    assert len(events) == resp.events_count
    assert any(ev.event_type == "sanction" for ev in events)

    # Verify provenance stored in document raw_metadata
    assert "extraction_provenance" in extraction_test_document.raw_metadata
    assert extraction_test_document.raw_metadata["extraction_provenance"]["extractor_name"] == "RuleBasedIntelligenceExtractor"


def test_redundant_extraction_skipped_without_reprocess(db_session, extraction_test_document):
    """Verify subsequent extraction calls on EXTRACTED documents return early unless reprocess=True."""
    # First run
    extract_from_document(db_session, extraction_test_document.id)

    # Second run without reprocess
    resp = extract_from_document(db_session, extraction_test_document.id, reprocess=False)
    assert "already extracted" in resp.message.lower()


def test_reprocessing_capability(db_session, extraction_test_document):
    """Verify reprocess=True archives previous extraction provenance and cleanly updates intelligence."""
    # First run
    extract_from_document(db_session, extraction_test_document.id)

    # Second run with reprocess
    resp2 = extract_from_document(db_session, extraction_test_document.id, reprocess=True)
    assert resp2.processing_status == ProcessingStatus.EXTRACTED.value

    db_session.refresh(extraction_test_document)
    assert "extraction_history" in extraction_test_document.raw_metadata
    assert len(extraction_test_document.raw_metadata["extraction_history"]) >= 1


def test_failed_extraction_rollback_and_status_preservation(db_session, extraction_test_document):
    """Verify that if an extraction error occurs, the transaction rolls back, document is preserved, and status is EXTRACTION_FAILED."""
    class FailingExtractor:
        name = "FailingExtractor"
        version = "0.0.1"
        def extract(self, *args, **kwargs):
            raise RuntimeError("Synthetic extraction failure")

    with pytest.raises(RuntimeError):
        extract_from_document(db_session, extraction_test_document.id, extractor=FailingExtractor())

    db_session.refresh(extraction_test_document)
    assert extraction_test_document.processing_status == ProcessingStatus.EXTRACTION_FAILED.value
    assert "Synthetic extraction failure" in extraction_test_document.raw_metadata.get("extraction_error", "")

    # Ensure document content is intact
    assert extraction_test_document.title == "United States Imposes New Sanctions on Foreign Drone Manufacturers"


def test_entity_deduplication_across_documents(db_session, sample_source):
    """Verify that multiple documents referencing the same entity reuse the same canonical Entity record."""
    now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)

    doc1 = Document(
        source_id=sample_source.id,
        title="China Announces Renewable Energy Targets",
        url="https://example.com/doc1",
        published_at=now,
        content_hash=compute_content_hash("China 1", "https://example.com/doc1"),
    )
    doc2 = Document(
        source_id=sample_source.id,
        title="China Economic Output Expands in Q3",
        url="https://example.com/doc2",
        published_at=now,
        content_hash=compute_content_hash("China 2", "https://example.com/doc2"),
    )
    db_session.add_all([doc1, doc2])
    db_session.commit()

    extract_from_document(db_session, doc1.id)
    extract_from_document(db_session, doc2.id)

    # Check that only ONE canonical entity for "China" exists
    china_entities = list(db_session.scalars(
        select(Entity).where(Entity.canonical_name == "China")
    ).all())
    assert len(china_entities) == 1

    # But both documents have document_entity associations to it
    associations = list(db_session.scalars(
        select(DocumentEntity).where(DocumentEntity.entity_id == china_entities[0].id)
    ).all())
    assert len(associations) == 2
