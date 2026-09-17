from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, HttpUrl


class NormalizedDocument(BaseModel):
    """Internal standardized representation of an ingested document."""
    source_name: str
    external_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    content_format: str = "text/plain"
    url: str
    author: Optional[str] = None
    published_at: datetime
    language: str = "en"
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)
    content_hash: str

    model_config = ConfigDict(extra="ignore")


class DocumentBase(BaseModel):
    source_id: UUID
    external_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    content_format: str = "text/plain"
    url: str
    author: Optional[str] = None
    published_at: datetime
    language: str = "en"
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)
    processing_status: str = "NORMALIZED"


class DocumentCreate(DocumentBase):
    content_hash: str


class DocumentRead(DocumentBase):
    id: UUID
    content_hash: str
    ingested_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedDocuments(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[DocumentRead]
