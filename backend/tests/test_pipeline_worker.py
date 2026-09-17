import pytest
import asyncio
import uuid
from datetime import datetime, timezone
from backend.app.services.pipeline_worker import DocumentPipelineWorkerPool
from backend.app.models.document import Document
from backend.app.models.source import Source
from backend.app.schemas.extraction import ProcessingStatus
from backend.app.utils.time import utc_now


@pytest.mark.asyncio
async def test_pipeline_worker_lifecycle():
    pool = DocumentPipelineWorkerPool(max_queue_size=10, worker_count=1)
    assert not pool.is_running
    assert pool.queue_depth == 0

    pool.start(worker_count=1)
    assert pool.is_running
    assert pool.worker_count == 1

    telemetry = pool.get_telemetry()
    assert telemetry["is_running"] is True
    assert telemetry["worker_count"] == 1
    assert telemetry["queue_depth"] == 0

    await pool.stop()
    assert not pool.is_running


@pytest.mark.asyncio
async def test_pipeline_worker_enqueue_and_process(db_session, monkeypatch):
    pool = DocumentPipelineWorkerPool(max_queue_size=10, worker_count=1)
    
    # Create test source & document
    src = Source(
        id=uuid.uuid4(),
        name="Test Worker Source",
        feed_url="https://example.com/feed",
        base_url="https://example.com",
        source_type="rss",
        active=True,
    )
    db_session.add(src)
    
    doc = Document(
        id=uuid.uuid4(),
        source_id=src.id,
        external_id="test-item-1",
        title="Breaking: Central Bank Announces Rate Decision",
        url="https://example.com/article1",
        content="The Federal Reserve announced an interest rate hike today in Washington.",
        processing_status=ProcessingStatus.RAW.value,
        published_at=utc_now(),
        ingested_at=utc_now(),
        content_hash="test-hash-worker-1",
    )
    db_session.add(doc)
    db_session.commit()

    processed_ids = []

    def mock_process_doc(doc_id):
        processed_ids.append(doc_id)

    monkeypatch.setattr(pool, "_process_single_document", mock_process_doc)

    pool.start(worker_count=1)
    success = pool.enqueue_document(doc.id)
    assert success is True

    # Wait for worker to consume
    for _ in range(20):
        if len(processed_ids) > 0:
            break
        await asyncio.sleep(0.05)

    assert doc.id in processed_ids
    assert pool.get_telemetry()["total_processed"] >= 1

    await pool.stop()
