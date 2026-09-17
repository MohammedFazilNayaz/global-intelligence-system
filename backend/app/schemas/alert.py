import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class AlertTriggerType(str, Enum):
    HIGH_IMPORTANCE_EVENT = "HIGH_IMPORTANCE_EVENT"
    MAJOR_GEOPOLITICAL_EVENT = "MAJOR_GEOPOLITICAL_EVENT"
    MAJOR_ECONOMIC_RELEASE = "MAJOR_ECONOMIC_RELEASE"
    SIGNIFICANT_SOURCE_UPDATE = "SIGNIFICANT_SOURCE_UPDATE"
    DATA_QUALITY_FAILURE = "DATA_QUALITY_FAILURE"
    STALE_SOURCE = "STALE_SOURCE"
    MARKET_ASSOCIATION = "MARKET_ASSOCIATION"
    PROCESSING_BACKLOG_EXCEEDED = "PROCESSING_BACKLOG_EXCEEDED"
    HIGH_INGESTION_FAILURE_RATE = "HIGH_INGESTION_FAILURE_RATE"
    SIGNIFICANT_CLUSTER_UPDATE = "SIGNIFICANT_CLUSTER_UPDATE"


class AlertStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class AlertRead(BaseModel):
    id: uuid.UUID
    trigger_type: AlertTriggerType
    alert_title: str
    timestamp: datetime
    importance: float
    confidence: float
    affected_entity_ids: List[str] = Field(default_factory=list)
    affected_event_id: Optional[uuid.UUID] = None
    affected_source_id: Optional[uuid.UUID] = None
    evidence: str
    explanation: str
    status: AlertStatus
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PaginatedAlerts(BaseModel):
    total: int
    items: List[AlertRead]


class AlertAcknowledgeRequest(BaseModel):
    note: Optional[str] = None
