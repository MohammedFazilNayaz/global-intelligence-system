from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from backend.app.schemas.entity import EntityRead
from backend.app.schemas.event import ExtractedEventRead


class MemberDocumentRead(BaseModel):
    id: UUID
    source_id: UUID
    source_name: Optional[str] = None
    title: str
    url: Optional[str] = None
    published_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EventClusterMemberRead(BaseModel):
    id: UUID
    event_cluster_id: UUID
    extracted_event_id: UUID
    membership_score: float
    membership_method: str
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_", serialization_alias="metadata")
    created_at: datetime
    extracted_event: Optional[ExtractedEventRead] = None
    document: Optional[MemberDocumentRead] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class EventClusterRead(BaseModel):
    id: UUID
    canonical_title: str
    canonical_summary: Optional[str] = None
    event_type: str
    event_time_start: Optional[datetime] = None
    event_time_end: Optional[datetime] = None
    primary_location_entity_id: Optional[UUID] = None
    confidence: float
    importance: Optional[float] = None
    status: str
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_", serialization_alias="metadata")
    created_at: datetime
    updated_at: datetime
    primary_location_entity: Optional[EntityRead] = None
    members_count: int = 0
    unique_sources_count: int = 0
    member_count: int = 0
    unique_source_count: int = 0

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class EventClusterDetailRead(EventClusterRead):
    members: List[EventClusterMemberRead] = Field(default_factory=list)


class PaginatedEventClusters(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[EventClusterRead]
