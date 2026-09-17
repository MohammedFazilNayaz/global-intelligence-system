from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class EntityBase(BaseModel):
    entity_type: str
    canonical_name: str
    normalized_name: str
    description: Optional[str] = None
    country_code: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class EntityCreate(EntityBase):
    pass


class EntityRead(BaseModel):
    id: UUID
    entity_type: str
    canonical_name: str
    normalized_name: str
    description: Optional[str] = None
    country_code: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class DocumentEntityRead(BaseModel):
    id: UUID
    document_id: UUID
    entity_id: UUID
    mention_text: str
    entity_role: str
    confidence: float
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    entity: Optional[EntityRead] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class PaginatedEntities(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[EntityRead]
