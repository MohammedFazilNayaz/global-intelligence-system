import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class LiveFeedEntityItem(BaseModel):
    id: uuid.UUID
    canonical_name: str
    entity_type: str
    country_code: Optional[str] = None


class LiveFeedEconomicItem(BaseModel):
    indicator_name: str
    reported_value: Optional[float] = None
    reported_unit: Optional[str] = None
    direction: Optional[str] = None
    economic_relevance: float


class LiveFeedMarketItem(BaseModel):
    symbol: str
    canonical_name: str
    window_size: str
    return_percent: float
    neutral_observation: str


class LiveFeedAlertItem(BaseModel):
    id: uuid.UUID
    trigger_type: str
    alert_title: str
    importance: float
    status: str


class LiveFeedItem(BaseModel):
    event_id: uuid.UUID
    document_id: Optional[uuid.UUID] = None
    event_title: str
    event_summary: Optional[str] = None
    event_type: str
    event_time: Optional[datetime] = None
    published_at: Optional[datetime] = None
    ingested_at: Optional[datetime] = None
    importance: float
    confidence: float
    cluster_id: Optional[uuid.UUID] = None
    cluster_title: Optional[str] = None
    primary_location: Optional[str] = None
    country_code: Optional[str] = None
    source_id: Optional[uuid.UUID] = None
    source_name: Optional[str] = None
    entities: List[LiveFeedEntityItem] = Field(default_factory=list)
    economic_context: List[LiveFeedEconomicItem] = Field(default_factory=list)
    market_context: List[LiveFeedMarketItem] = Field(default_factory=list)
    active_alerts: List[LiveFeedAlertItem] = Field(default_factory=list)
    processed_at: Optional[datetime] = None
    pipeline_duration_seconds: Optional[float] = None
    e2e_latency_seconds: Optional[float] = None
    freshness_status: str = "CURRENT"
    age_seconds: Optional[float] = None
    provenance_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedLiveFeedResponse(BaseModel):
    total: int
    items: List[LiveFeedItem]
    page: int = 1
    page_size: int = 20
    freshness_summary: Dict[str, int] = Field(default_factory=dict)


class SystemFreshnessResponse(BaseModel):
    system_status: str  # HEALTHY, DEGRADED, STALE, UNKNOWN
    current_time_utc: datetime
    sources_total: int
    sources_current: int
    sources_stale: int
    sources_failed: int
    sources_unknown: int
    median_ingestion_latency_seconds: Optional[float] = None
    median_processing_latency_seconds: Optional[float] = None
    median_e2e_latency_seconds: Optional[float] = None
    oldest_backlog_document_age_seconds: Optional[float] = None
    pending_backlog_count: int = 0
    latest_event_time: Optional[datetime] = None
    latest_market_observation_time: Optional[datetime] = None
    source_health_breakdown: List[Dict[str, Any]] = Field(default_factory=list)


class LatencyPercentiles(BaseModel):
    median_seconds: Optional[float] = None
    p90_seconds: Optional[float] = None
    min_seconds: Optional[float] = None
    max_seconds: Optional[float] = None
    sample_size: int = 0


class OperationalMetricsResponse(BaseModel):
    fetch_latency: LatencyPercentiles
    processing_latency: LatencyPercentiles
    e2e_latency: LatencyPercentiles
    pipeline_health: str = "OPERATIONAL"  # OPERATIONAL, DEGRADED, BACKLOG_HIGH
    active_sources_count: int = 0
    pending_backlog_count: int = 0
    calculated_at: datetime

