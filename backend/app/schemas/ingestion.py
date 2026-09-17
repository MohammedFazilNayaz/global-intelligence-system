import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class IngestionRunRead(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_name: Optional[str] = None
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    documents_discovered: int = 0
    documents_inserted: int = 0
    duplicates_skipped: int = 0
    failures_count: int = 0
    error_message: Optional[str] = None
    processing_stats: Dict[str, Any] = Field(default_factory=dict)
    duration_seconds: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedIngestionRuns(BaseModel):
    total: int
    items: List[IngestionRunRead]


class SourceHealthSummary(BaseModel):
    source_id: uuid.UUID
    name: str
    source_type: str
    active: bool
    feed_url: str = ""
    polling_interval_seconds: int
    reliability_score: float
    health_status: str = "UNKNOWN"  # HEALTHY, DEGRADED, STALE, FAILED, DISABLED, AUTH_REQUIRED, RATE_LIMITED
    freshness_status: str = "UNKNOWN"  # CURRENT, STALE, FAILED, UNKNOWN
    last_successful_fetch_at: Optional[datetime] = None
    last_attempted_fetch_at: Optional[datetime] = None
    last_successful_ingestion_at: Optional[datetime] = None
    latest_published_at_observed: Optional[datetime] = None
    last_fetch_duration_ms: Optional[float] = None
    last_error_message: Optional[str] = None
    consecutive_failures: int = 0
    total_failures_count: int = 0
    total_documents: int = 0
    latest_document_at: Optional[datetime] = None
    age_seconds: Optional[float] = None



class IngestionSchedulerStatus(BaseModel):
    status: str  # RUNNING, IDLE, STOPPED
    is_active: bool
    active_workers: int
    configured_sources_count: int
    active_sources_count: int
    pending_backlog_count: int
    last_scheduler_run_at: Optional[datetime] = None
    total_runs_completed: int = 0
    total_runs_failed: int = 0
    uptime_seconds: float = 0.0
    queue_depth: int = 0
    worker_pool_size: int = 2
    pipeline_processed_count: int = 0
    pipeline_failed_count: int = 0


class IngestionTriggerRequest(BaseModel):
    source_id: Optional[uuid.UUID] = None
    force: bool = False


class IngestionTriggerResponse(BaseModel):
    triggered_count: int
    run_ids: List[uuid.UUID]
    message: str
