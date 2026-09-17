import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func, desc, and_
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.ingestion_run import IngestionRun
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.utils.time import utc_now
from backend.app.schemas.ingestion import (
    IngestionRunRead,
    PaginatedIngestionRuns,
    IngestionSchedulerStatus,
    IngestionTriggerRequest,
    IngestionTriggerResponse,
)
from backend.app.services.scheduler_service import scheduler
from backend.app.services.ingestion import ingest_from_source, ingest_all_active_sources

router = APIRouter(prefix="/ingestion", tags=["Ingestion & Scheduler"])


@router.get("/runs", response_model=PaginatedIngestionRuns)
def list_ingestion_runs(
    source_id: Optional[uuid.UUID] = Query(None, description="Filter by source ID"),
    status: Optional[str] = Query(None, description="Filter by run status"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
) -> PaginatedIngestionRuns:
    """List historical ingestion runs with execution metrics."""
    query = select(IngestionRun)
    count_query = select(func.count(IngestionRun.id))

    filters = []
    if source_id:
        filters.append(IngestionRun.source_id == source_id)
    if status:
        filters.append(IngestionRun.status == status.upper())

    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    total = db.scalar(count_query) or 0
    runs = list(db.scalars(query.order_by(desc(IngestionRun.started_at)).offset(offset).limit(limit)).all())

    # populate source_name
    items = []
    for r in runs:
        item = IngestionRunRead.model_validate(r)
        if r.source:
            item.source_name = r.source.name
        if r.started_at and r.completed_at:
            item.duration_seconds = round((r.completed_at - r.started_at).total_seconds(), 2)
        items.append(item)

    return PaginatedIngestionRuns(total=total, items=items)


@router.get("/runs/{run_id}", response_model=IngestionRunRead)
def get_ingestion_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> IngestionRunRead:
    """Retrieve details for a specific ingestion run."""
    run = db.get(IngestionRun, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IngestionRun '{run_id}' not found.",
        )
    item = IngestionRunRead.model_validate(run)
    if run.source:
        item.source_name = run.source.name
    if run.started_at and run.completed_at:
        item.duration_seconds = round((run.completed_at - run.started_at).total_seconds(), 2)
    return item


@router.get("/status", response_model=IngestionSchedulerStatus)
def get_scheduler_status(
    db: Session = Depends(get_db),
) -> IngestionSchedulerStatus:
    """Retrieve runtime operational status of the Ingestion Scheduler and backlog queue depth."""
    return scheduler.get_status(db)


@router.post("/trigger", response_model=IngestionTriggerResponse)
def trigger_ingestion(
    request: Optional[IngestionTriggerRequest] = None,
    db: Session = Depends(get_db),
) -> IngestionTriggerResponse:
    """Manually trigger ingestion for a specific source or all active sources."""
    source_id = request.source_id if request else None

    if source_id:
        src = db.get(Source, source_id)
        if not src:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source '{source_id}' not found.",
            )
        stats = ingest_from_source(db, src, trigger_pipeline=True)
        run_ids = [stats.run_id] if stats.run_id else []
        return IngestionTriggerResponse(
            triggered_count=1,
            run_ids=run_ids,
            message=f"Triggered ingestion for '{src.name}': {stats.new_ingested} inserted, {stats.duplicates_skipped} duplicates skipped.",
        )
    else:
        results = ingest_all_active_sources(db, trigger_pipeline=True)
        run_ids = [r.run_id for r in results if r.run_id]
        total_inserted = sum(r.new_ingested for r in results)
        return IngestionTriggerResponse(
            triggered_count=len(results),
            run_ids=run_ids,
            message=f"Triggered ingestion for {len(results)} active sources: {total_inserted} total new documents inserted.",
        )


@router.get("/backlog")
def get_ingestion_backlog(
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Retrieve operational queue depth, status breakdown, and oldest documents in the ingestion backlog."""
    now = utc_now()
    backlog_statuses = ["RAW", "NORMALIZED", "EXTRACTION_PENDING"]

    total_backlog = db.scalar(
        select(func.count(Document.id)).where(Document.processing_status.in_(backlog_statuses))
    ) or 0

    breakdown = {}
    for st in backlog_statuses:
        cnt = db.scalar(select(func.count(Document.id)).where(Document.processing_status == st)) or 0
        breakdown[st] = cnt

    # Oldest document in backlog
    oldest_doc = db.scalar(
        select(Document)
        .where(Document.processing_status.in_(backlog_statuses))
        .order_by(Document.ingested_at.asc())
        .limit(1)
    )

    oldest_age_sec = None
    if oldest_doc and oldest_doc.ingested_at:
        oldest_age_sec = round((now - oldest_doc.ingested_at).total_seconds(), 1)

    # Sample oldest pending documents
    sample_docs = list(
        db.scalars(
            select(Document)
            .where(Document.processing_status.in_(backlog_statuses))
            .order_by(Document.ingested_at.asc())
            .limit(limit)
        ).all()
    )

    return {
        "pending_count": total_backlog,
        "oldest_backlog_document_age_seconds": oldest_age_sec,
        "breakdown_by_status": breakdown,
        "sample_pending": [
            {
                "document_id": str(d.id),
                "title": d.title,
                "processing_status": d.processing_status,
                "ingested_at": d.ingested_at,
                "source_name": d.source.name if d.source else "Unknown",
            }
            for d in sample_docs
        ],
    }
