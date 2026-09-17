import uuid
from datetime import datetime, timezone, timedelta
import pytest
from backend.app.models.document import Document
from backend.app.processors.hasher import compute_content_hash


def test_list_documents_pagination(client, db_session, sample_source):
    """Verify document listing returns correct pagination envelopes."""
    now = datetime.now(timezone.utc)

    # Seed 5 test documents
    for i in range(5):
        doc = Document(
            source_id=sample_source.id,
            title=f"Report Item {i}",
            url=f"https://example.com/report/{i}",
            published_at=now - timedelta(hours=i),
            content_hash=compute_content_hash(f"Report Item {i}", f"https://example.com/report/{i}"),
            processing_status="NORMALIZED",
        )
        db_session.add(doc)
    db_session.commit()

    # Query page 1 with page_size 2
    resp = client.get("/api/v1/documents?page=1&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total_pages"] == 3
    assert len(data["items"]) == 2

    # Query page 3 with page_size 2
    resp3 = client.get("/api/v1/documents?page=3&page_size=2")
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert len(data3["items"]) == 1


def test_filter_documents_by_source(client, db_session, sample_source):
    """Verify filtering by source_id returns only that source's documents."""
    now = datetime.now(timezone.utc)
    doc = Document(
        source_id=sample_source.id,
        title="Source Specific Headline",
        url="https://example.com/source-doc",
        published_at=now,
        content_hash=compute_content_hash("Source Specific Headline", "https://example.com/source-doc"),
    )
    db_session.add(doc)
    db_session.commit()

    # Filter with matching source_id
    resp = client.get(f"/api/v1/documents?source_id={sample_source.id}")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    # Filter with random source_id
    random_id = str(uuid.uuid4())
    resp_empty = client.get(f"/api/v1/documents?source_id={random_id}")
    assert resp_empty.status_code == 200
    assert resp_empty.json()["total"] == 0


def test_get_document_by_id(client, sample_document):
    """Retrieve document by ID."""
    resp = client.get(f"/api/v1/documents/{sample_document.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(sample_document.id)
    assert data["title"] == sample_document.title
    assert data["content_hash"] == sample_document.content_hash


def test_get_nonexistent_document(client):
    """Retrieve non-existent document returns 404."""
    random_id = str(uuid.uuid4())
    resp = client.get(f"/api/v1/documents/{random_id}")
    assert resp.status_code == 404


def test_filter_documents_by_date_and_order(client, db_session, sample_source):
    """Verify published_after, published_before, and order_by parameters."""
    t1 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)

    for i, t in enumerate([t1, t2, t3]):
        doc = Document(
            source_id=sample_source.id,
            title=f"Dated Report {i}",
            url=f"https://example.com/dated/{i}",
            published_at=t,
            content_hash=compute_content_hash(f"Dated Report {i}", f"https://example.com/dated/{i}"),
            processing_status="NORMALIZED",
        )
        db_session.add(doc)
    db_session.commit()

    # Filter published_after 2026-09-04
    resp = client.get("/api/v1/documents?published_after=2026-09-04T00:00:00Z")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2

    # Filter published_before 2026-09-06
    resp_before = client.get("/api/v1/documents?published_before=2026-09-06T00:00:00Z")
    assert resp_before.status_code == 200
    assert resp_before.json()["total"] == 2

    # Order ascending
    resp_asc = client.get("/api/v1/documents?order_by=published_at_asc")
    assert resp_asc.status_code == 200
    items = resp_asc.json()["items"]
    assert items[0]["title"] == "Dated Report 0"

