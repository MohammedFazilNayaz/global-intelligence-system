import asyncio
import time
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.models.document import Document
from backend.app.schemas.extraction import ProcessingStatus
from backend.app.services import pipeline_service
from backend.app.utils.logger import get_logger

logger = get_logger("service.pipeline_worker")


class DocumentPipelineWorkerPool:
    """Persistent asynchronous worker pool that processes newly ingested documents
    independently from the network fetching scheduler.
    
    This decouples network I/O from CPU/DB-intensive NLP and correlation logic.
    """

    def __init__(self, max_queue_size: int = 1000, worker_count: int = 2):
        self.max_queue_size = max_queue_size
        self.worker_count = worker_count
        self._queue: Optional[asyncio.Queue[uuid.UUID]] = None
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._total_processed = 0
        self._total_failed = 0
        self._start_time: Optional[float] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize() if self._queue else 0

    def start(self, worker_count: Optional[int] = None) -> None:
        """Start the async pipeline worker pool."""
        if self._running:
            logger.warning("PipelineWorkerPool is already running.")
            return

        if worker_count is not None:
            self.worker_count = worker_count

        self._running = True
        self._start_time = time.perf_counter()
        self._queue = asyncio.Queue(maxsize=self.max_queue_size)
        loop = asyncio.get_event_loop()

        self._workers = []
        for i in range(self.worker_count):
            t = loop.create_task(self._worker_loop(worker_id=i + 1))
            self._workers.append(t)

        logger.info(f"PipelineWorkerPool started with {self.worker_count} workers.")

    async def stop(self) -> None:
        """Gracefully stop all pipeline workers."""
        if not self._running:
            return

        logger.info("Stopping PipelineWorkerPool...")
        self._running = False

        for t in self._workers:
            t.cancel()

        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers.clear()
        self._queue = None
        logger.info("PipelineWorkerPool stopped cleanly.")

    def enqueue_document(self, doc_id: uuid.UUID) -> bool:
        """Thread-safe enqueueing of a document ID for background processing."""
        if not self._running or self._queue is None:
            logger.warning("Cannot enqueue document: PipelineWorkerPool is not running.")
            return False

        try:
            self._queue.put_nowait(doc_id)
            return True
        except asyncio.QueueFull:
            logger.error(f"Pipeline processing queue is full ({self.max_queue_size}). Backpressure rejecting doc {doc_id}.")
            return False

    def recover_backlog(self, limit: int = 100) -> int:
        """Recovers documents pending extraction from database upon startup."""
        enqueued_count = 0
        try:
            with SessionLocal() as db:
                stmt = (
                    select(Document.id)
                    .where(Document.processing_status.in_([
                        ProcessingStatus.RAW.value,
                        ProcessingStatus.NORMALIZED.value,
                        ProcessingStatus.EXTRACTION_PENDING.value,
                    ]))
                    .order_by(Document.ingested_at.asc())
                    .limit(limit)
                )
                pending_ids = list(db.scalars(stmt).all())
                for doc_id in pending_ids:
                    if self.enqueue_document(doc_id):
                        enqueued_count += 1
            if enqueued_count > 0:
                logger.info(f"Restart recovery: enqueued {enqueued_count} pending documents into pipeline worker pool.")
        except Exception as exc:
            logger.error(f"Error during backlog recovery in pipeline worker: {exc}")

        return enqueued_count

    async def _worker_loop(self, worker_id: int) -> None:
        """Background worker loop continuously processing document tasks."""
        logger.debug(f"Pipeline worker #{worker_id} ready.")
        while self._running:
            try:
                if self._queue is None:
                    break
                doc_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                await asyncio.to_thread(self._process_single_document, doc_id)
                self._total_processed += 1
            except Exception as exc:
                self._total_failed += 1
                logger.error(f"Worker #{worker_id} failed processing document '{doc_id}': {exc}")
            finally:
                if self._queue:
                    self._queue.task_done()

        logger.debug(f"Pipeline worker #{worker_id} terminated.")

    def _process_single_document(self, doc_id: uuid.UUID) -> Dict[str, Any]:
        """Synchronous wrapper executed in worker thread to run end-to-end pipeline."""
        with SessionLocal() as db:
            return pipeline_service.process_document_end_to_end(db, document_id=doc_id)

    def get_telemetry(self) -> Dict[str, Any]:
        """Telemetry diagnostics for operational monitoring."""
        uptime = 0.0
        if self._start_time and self._running:
            uptime = round(time.perf_counter() - self._start_time, 1)

        return {
            "is_running": self._running,
            "worker_count": len(self._workers),
            "queue_depth": self.queue_depth,
            "max_queue_size": self.max_queue_size,
            "total_processed": self._total_processed,
            "total_failed": self._total_failed,
            "uptime_seconds": uptime,
        }


# Global singleton instance
pipeline_worker_pool = DocumentPipelineWorkerPool()
