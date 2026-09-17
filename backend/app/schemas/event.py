from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from backend.app.schemas.entity import EntityRead


class ExtractedEventBase(BaseModel):
    document_id: UUID
    event_type: str
    event_title: str
    event_summary: Optional[str] = None
    event_time: Optional[datetime] = None
    location_entity_id: Optional[UUID] = None
    confidence: float = Field(ge=0.0, le=1.0)
    importance: float = Field(ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ExtractedEventCreate(ExtractedEventBase):
    pass


class ExtractedEventRead(BaseModel):
    id: UUID
    document_id: UUID
    event_type: str
    event_title: str
    event_summary: Optional[str] = None
    event_time: Optional[datetime] = None
    location_entity_id: Optional[UUID] = None
    confidence: float
    importance: float
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime
    location_entity: Optional[EntityRead] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class PaginatedEvents(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[ExtractedEventRead]
