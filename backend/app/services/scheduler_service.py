import asyncio
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.ingestion_run import IngestionRun
from backend.app.schemas.ingestion import IngestionSchedulerStatus
from backend.app.services.ingestion import ingest_from_source, IngestionStats
from backend.app.services import pipeline_service
from backend.app.services import freshness_service
from backend.app.services.pipeline_worker import pipeline_worker_pool
from backend.app.utils.logger import get_logger
from backend.app.utils.time import utc_now

logger = get_logger("service.scheduler")


class IngestionScheduler:
    """Orchestrates scheduled background ingestion across all configured sources.
    
    Features:
    - Decoupled architecture: concurrent network fetching isolated from document pipeline workers
    - Per-source cadence with exponential backoff on error
    - Strict timeout enforcement and failure isolation
    - Idempotent backlog catch-up upon restart
    - Safe cooperative shutdown
    """

    def __init__(self, check_interval_seconds: float = 5.0, per_source_timeout: float = 15.0, max_concurrent_fetches: int = 10):
        self.check_interval_seconds = check_interval_seconds
        self.per_source_timeout = per_source_timeout
        self.max_concurrent_fetches = max_concurrent_fetches
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._start_time: Optional[float] = None
        self._last_run_at: Optional[datetime] = None
        self._total_completed = 0
        self._total_failed = 0
        self._active_workers = 0
        self._running_sources: set[UUID] = set()

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start the background scheduler task and document pipeline worker pool."""
        if self._running:
            logger.warning("IngestionScheduler is already running.")
            return

        self._running = True
        self._start_time = time.perf_counter()
        self._semaphore = asyncio.Semaphore(self.max_concurrent_fetches)

        # Start decoupled document processing workers
        pipeline_worker_pool.start(worker_count=2)
        pipeline_worker_pool.recover_backlog(limit=100)

        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run_loop())
        logger.info(f"IngestionScheduler started with max {self.max_concurrent_fetches} concurrent fetchers.")

    async def stop(self) -> None:
        """Cooperative shutdown of the scheduler and pipeline workers."""
        if not self._running:
            return

        logger.info("Stopping IngestionScheduler and worker pool...")
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        await pipeline_worker_pool.stop()
        self._running_sources.clear()
        logger.info("IngestionScheduler and pipeline workers stopped cleanly.")

    async def _run_loop(self) -> None:
        """Main periodic polling loop."""
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as loop_err:
                logger.error(f"Unhandled error in IngestionScheduler loop: {loop_err}", exc_info=True)

            try:
                await asyncio.sleep(self.check_interval_seconds)
            except asyncio.CancelledError:
                break

    async def _tick(self) -> None:
        """Check all active sources and trigger ingestion concurrently if due."""
        self._last_run_at = utc_now()
        now = self._last_run_at

        # Determine which sources are due
        due_sources: List[UUID] = []
        with SessionLocal() as db:
            sources = list(db.scalars(select(Source).where(Source.active.is_(True))).all())
            for s in sources:
                interval = s.polling_interval_seconds
                # Bounded exponential backoff factor if consecutive failures exist
                if s.consecutive_failures > 0:
                    backoff = min(8.0, 1.5 ** s.consecutive_failures)
                    interval = min(3600, int(interval * backoff))

                if s.last_attempted_fetch_at is None:
                    due_sources.append(s.id)
                else:
                    elapsed = (now - s.last_attempted_fetch_at).total_seconds()
                    if elapsed >= interval:
                        due_sources.append(s.id)

        if not due_sources or not self._running:
            return

        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent_fetches)

        # Dispatch concurrent fetches bounded by semaphore
        async def _fetch_single_source(source_id: UUID) -> None:
            if not self._running:
                return
            if source_id in self._running_sources:
                logger.debug(f"Source '{source_id}' is already executing an active ingestion run. Skipping overlapping cycle.")
                return

            async with self._semaphore:
                self._running_sources.add(source_id)
                self._active_workers += 1
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(self._sync_ingest_source, source_id),
                        timeout=self.per_source_timeout,
                    )
                    self._total_completed += 1
                except asyncio.TimeoutError:
                    self._total_failed += 1
                    logger.error(f"Source ingestion timed out for source ID '{source_id}' after {self.per_source_timeout}s.")
                    await asyncio.to_thread(self._record_source_timeout, source_id)
                except Exception as exc:
                    self._total_failed += 1
                    logger.error(f"Isolated failure during ingestion for source '{source_id}': {exc}")
                finally:
                    self._running_sources.discard(source_id)
                    self._active_workers = max(0, self._active_workers - 1)

        tasks = [_fetch_single_source(sid) for sid in due_sources]
        await asyncio.gather(*tasks, return_exceptions=True)

    def _sync_ingest_source(self, source_id: UUID) -> IngestionStats:
        """Synchronous wrapper to execute ingestion in worker thread.
        Note: trigger_pipeline=False decouples network fetch from document NLP/clustering,
        dispatching new documents to the asynchronous worker pool.
        """
        with SessionLocal() as db:
            source = db.get(Source, source_id)
            if not source or not source.active:
                return IngestionStats(source_id=source_id, source_name="unknown")
            return ingest_from_source(db, source, trigger_pipeline=False)

    def _record_source_timeout(self, source_id: UUID) -> None:
        """Record timeout error on source and ingestion run."""
        try:
            with SessionLocal() as db:
                source = db.get(Source, source_id)
                if source:
                    source.consecutive_failures += 1
                    source.total_failures_count += 1
                    source.last_error_message = f"Ingestion timed out after {self.per_source_timeout}s"
                    if source.consecutive_failures >= 3:
                        source.freshness_status = "FAILED"
                    db.commit()
        except Exception as db_err:
            logger.error(f"Failed to record timeout on source '{source_id}': {db_err}")

    def get_status(self, db: Session) -> IngestionSchedulerStatus:
        """Retrieve runtime telemetry and backlog status."""
        total_sources = db.scalar(select(func.count(Source.id))) or 0
        active_sources = db.scalar(select(func.count(Source.id)).where(Source.active.is_(True))) or 0
        backlog_count = db.scalar(
            select(func.count(Document.id)).where(Document.processing_status.in_(["RAW", "NORMALIZED", "EXTRACTION_PENDING"]))
        ) or 0

        uptime = 0.0
        if self._start_time and self._running:
            uptime = round(time.perf_counter() - self._start_time, 1)

        status_str = "RUNNING" if self._running else "STOPPED"
        worker_telemetry = pipeline_worker_pool.get_telemetry()

        return IngestionSchedulerStatus(
            status=status_str,
            is_active=self._running,
            active_workers=self._active_workers,
            configured_sources_count=total_sources,
            active_sources_count=active_sources,
            pending_backlog_count=backlog_count,
            last_scheduler_run_at=self._last_run_at,
            total_runs_completed=self._total_completed,
            total_runs_failed=self._total_failed,
            uptime_seconds=uptime,
            queue_depth=worker_telemetry.get("queue_depth", 0),
            worker_pool_size=worker_telemetry.get("worker_count", 2),
            pipeline_processed_count=worker_telemetry.get("total_processed", 0),
            pipeline_failed_count=worker_telemetry.get("total_failed", 0),
        )


# Global singleton instance
scheduler = IngestionScheduler()
