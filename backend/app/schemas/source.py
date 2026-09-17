from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class SourceBase(BaseModel):
    name: str = Field(..., max_length=128, description="Unique human-readable source name")
    source_type: str = Field(..., max_length=32, description="Type: rss, api, or official_publication")
    base_url: str = Field(..., max_length=512, description="Base domain URL")
    feed_url: str = Field(..., max_length=1024, description="Direct feed or API endpoint URL")
    reliability_score: float = Field(0.8, ge=0.0, le=1.0, description="Confidence/reliability score")
    active: bool = Field(True, description="Whether this source is currently active for ingestion")
    polling_interval_seconds: int = Field(300, ge=30, description="Recommended polling interval in seconds")
    config_metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom headers, auth, or params")
    is_primary: bool = Field(False, description="Whether this is an authoritative primary source")
    region: Optional[str] = Field("Global", description="Operational theatre region")
    country: Optional[str] = Field("XX", description="ISO country code")
    domain: Optional[str] = Field("General", description="Primary intelligence domain")


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    source_type: Optional[str] = Field(None, max_length=32)
    base_url: Optional[str] = Field(None, max_length=512)
    feed_url: Optional[str] = Field(None, max_length=1024)
    reliability_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    active: Optional[bool] = None
    polling_interval_seconds: Optional[int] = Field(None, ge=30)
    config_metadata: Optional[Dict[str, Any]] = None
    is_primary: Optional[bool] = None
    region: Optional[str] = None
    country: Optional[str] = None
    domain: Optional[str] = None
    freshness_status: Optional[str] = None


class SourceRead(SourceBase):
    id: UUID
    last_successful_fetch_at: Optional[datetime] = None
    last_attempted_fetch_at: Optional[datetime] = None
    last_error_message: Optional[str] = None
    consecutive_failures: int = 0
    freshness_status: str = "UNKNOWN"
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedSources(BaseModel):
    total: int
    items: List[SourceRead]

