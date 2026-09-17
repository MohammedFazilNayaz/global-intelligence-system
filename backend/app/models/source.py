from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import String, Float, Boolean, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, UTCDateTime


class Source(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Database model representing an intelligence information source."""
    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    feed_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    reliability_score: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    polling_interval_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    config_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Operational Telemetry (V0.8 Real-Time)
    last_successful_fetch_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    last_attempted_fetch_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    last_error_message: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    freshness_status: Mapped[str] = mapped_column(String(20), default="UNKNOWN", index=True, nullable=False)

    @property
    def health_status(self) -> str:
        """Deterministic 7-state operational classification for source reliability."""
        if not self.active:
            return "DISABLED"
        
        meta = self.config_metadata or {}
        err = (self.last_error_message or "").lower()
        
        if meta.get("auth_required") or "api key" in err or "unauthorized" in err or "401" in err:
            return "AUTH_REQUIRED"
        if "429" in err or "rate limit" in err:
            return "RATE_LIMITED"
            
        failures = self.consecutive_failures or 0
        freshness = self.freshness_status or "UNKNOWN"
        
        if failures >= 3 or freshness == "FAILED":
            return "FAILED"
        if freshness == "STALE":
            return "STALE"
        if failures > 0 or freshness == "DEGRADED":
            return "DEGRADED"
        if freshness == "CURRENT" and failures == 0:
            return "HEALTHY"
        return "UNKNOWN"

    @property
    def last_successful_ingestion_at(self) -> Optional[datetime]:
        meta = self.config_metadata or {}
        val = meta.get("last_successful_ingestion_at")
        if val:
            try:
                return datetime.fromisoformat(val)
            except Exception:
                return None
        return None

    @last_successful_ingestion_at.setter
    def last_successful_ingestion_at(self, dt: Optional[datetime]) -> None:
        meta = dict(self.config_metadata or {})
        meta["last_successful_ingestion_at"] = dt.isoformat() if dt else None
        self.config_metadata = meta

    @property
    def latest_published_at_observed(self) -> Optional[datetime]:
        meta = self.config_metadata or {}
        val = meta.get("latest_published_at_observed")
        if val:
            try:
                return datetime.fromisoformat(val)
            except Exception:
                return None
        return None

    @latest_published_at_observed.setter
    def latest_published_at_observed(self, dt: Optional[datetime]) -> None:
        meta = dict(self.config_metadata or {})
        meta["latest_published_at_observed"] = dt.isoformat() if dt else None
        self.config_metadata = meta

    @property
    def latest_document_ingested_at(self) -> Optional[datetime]:
        meta = self.config_metadata or {}
        val = meta.get("latest_document_ingested_at")
        if val:
            try:
                return datetime.fromisoformat(val)
            except Exception:
                return None
        return None

    @latest_document_ingested_at.setter
    def latest_document_ingested_at(self, dt: Optional[datetime]) -> None:
        meta = dict(self.config_metadata or {})
        meta["latest_document_ingested_at"] = dt.isoformat() if dt else None
        self.config_metadata = meta

    @property
    def last_fetch_duration_ms(self) -> Optional[float]:
        return (self.config_metadata or {}).get("last_fetch_duration_ms")

    @last_fetch_duration_ms.setter
    def last_fetch_duration_ms(self, duration_ms: Optional[float]) -> None:
        meta = dict(self.config_metadata or {})
        meta["last_fetch_duration_ms"] = duration_ms
        self.config_metadata = meta

    @property
    def total_failures_count(self) -> int:
        return (self.config_metadata or {}).get("total_failures_count", 0)

    @total_failures_count.setter
    def total_failures_count(self, count: int) -> None:
        meta = dict(self.config_metadata or {})
        meta["total_failures_count"] = count
        self.config_metadata = meta

    # Fleet & Geographic Metadata
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    region: Mapped[Optional[str]] = mapped_column(String(64), index=True, default="Global", nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(8), index=True, default="XX", nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(128), index=True, default="General", nullable=True)

    # Relationship to ingested documents
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="source",
        cascade="all, delete-orphan",
    )

    # Relationship to ingestion runs
    ingestion_runs: Mapped[List["IngestionRun"]] = relationship(
        "IngestionRun",
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="desc(IngestionRun.started_at)",
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id} name='{self.name}' type='{self.source_type}' status='{self.freshness_status}'>"

