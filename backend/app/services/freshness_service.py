import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.event import ExtractedEvent
from backend.app.models.market_observation import MarketObservation
from backend.app.models.observation import EconomicObservation
from backend.app.schemas.intelligence_feed import (
    SystemFreshnessResponse,
    LatencyPercentiles,
    OperationalMetricsResponse,
)
from backend.app.schemas.ingestion import SourceHealthSummary
from backend.app.utils.time import utc_now


from backend.app.config.settings import get_settings

def compute_source_freshness_status(source: Source, now: Optional[datetime] = None) -> str:
    """Evaluate deterministic freshness status for a given source considering both check and content freshness."""
    if not source.active:
        return "DISABLED"
    if source.consecutive_failures >= 3:
        return "FAILED"
    if not source.last_successful_fetch_at:
        return "UNKNOWN"

    settings = get_settings()
    now = now or utc_now()

    # 1. Check cadence: Has the source been checked within its expected polling multiplier?
    fetch_age = (now - source.last_successful_fetch_at).total_seconds()
    fetch_threshold = source.polling_interval_seconds * settings.SOURCE_STALE_MULTIPLIER
    if fetch_age > fetch_threshold:
        return "STALE"

    # 2. Content cadence: When did the source last produce content?
    ref_pub = source.latest_published_at_observed or source.latest_document_ingested_at
    if not ref_pub:
        return "CURRENT"

    if ref_pub.tzinfo is None:
        ref_pub = ref_pub.replace(tzinfo=timezone.utc)

    content_age = (now - ref_pub).total_seconds()
    current_threshold = settings.FRESHNESS_CURRENT_HOURS * 3600
    if content_age <= current_threshold:
        return "CURRENT"
    return "STALE"


def get_all_sources_health(db: Session) -> List[SourceHealthSummary]:
    """Retrieve detailed health, telemetry, and freshness for all configured sources."""
    sources = list(db.scalars(select(Source).order_by(Source.name)).all())
    now = utc_now()
    results: List[SourceHealthSummary] = []

    for s in sources:
        freshness = compute_source_freshness_status(s, now)
        # update if status changed in DB
        if s.freshness_status != freshness:
            s.freshness_status = freshness

        # Query total docs and latest document
        doc_count = db.scalar(select(func.count(Document.id)).where(Document.source_id == s.id)) or 0
        latest_doc = db.scalar(
            select(Document.published_at)
            .where(Document.source_id == s.id)
            .order_by(desc(Document.published_at))
            .limit(1)
        )

        age_sec = None
        if s.last_successful_fetch_at:
            age_sec = round((now - s.last_successful_fetch_at).total_seconds(), 1)

        results.append(
            SourceHealthSummary(
                source_id=s.id,
                name=s.name,
                source_type=s.source_type,
                active=s.active,
                feed_url=s.feed_url,
                polling_interval_seconds=s.polling_interval_seconds,
                reliability_score=s.reliability_score,
                health_status=s.health_status,
                freshness_status=freshness,
                last_successful_fetch_at=s.last_successful_fetch_at,
                last_attempted_fetch_at=s.last_attempted_fetch_at,
                last_successful_ingestion_at=s.last_successful_ingestion_at,
                latest_published_at_observed=s.latest_published_at_observed or latest_doc,
                last_fetch_duration_ms=s.last_fetch_duration_ms,
                last_error_message=s.last_error_message,
                consecutive_failures=s.consecutive_failures,
                total_failures_count=s.total_failures_count,
                total_documents=doc_count,
                latest_document_at=latest_doc,
                age_seconds=age_sec,
            )
        )

    return results


def compute_item_freshness_status(
    event_time: Optional[datetime],
    published_at: Optional[datetime],
    metadata: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Tuple[str, Optional[float]]:
    """
    Evaluate deterministic freshness state for an intelligence item.
    States:
    - SYNTHETIC_TEST: synthetic/test record
    - CURRENT: age <= 24 hours (86,400s)
    - RECENT: age > 24 hours and <= 7 days (604,800s)
    - STALE: age > 7 days and <= 30 days (2,592,000s)
    - HISTORICAL: age > 30 days
    - UNKNOWN: missing event and publication timestamps
    
    INVARIANT: created_at in the database is NEVER used as a proxy for event/publication freshness.
    """
    if metadata and (metadata.get("is_synthetic") or metadata.get("is_test") or metadata.get("synthetic_benchmark")):
        return "SYNTHETIC_TEST", None

    now = now or utc_now()
    ref_time = event_time or published_at
    if ref_time is None:
        return "UNKNOWN", None

    if ref_time.tzinfo is None:
        ref_time = ref_time.replace(tzinfo=timezone.utc)

    age_sec = round((now - ref_time).total_seconds(), 1)
    if age_sec < 0:
        return "RECENT", age_sec

    settings = get_settings()
    current_threshold = settings.FRESHNESS_CURRENT_HOURS * 3600
    recent_threshold = settings.FRESHNESS_RECENT_DAYS * 86400
    stale_threshold = settings.FRESHNESS_STALE_DAYS * 86400

    if age_sec <= current_threshold:
        return "CURRENT", age_sec
    elif age_sec <= recent_threshold:
        return "RECENT", age_sec
    elif age_sec <= stale_threshold:
        return "STALE", age_sec
    else:
        return "HISTORICAL", age_sec


def get_system_freshness_summary(db: Session) -> SystemFreshnessResponse:
    """Generate overall system freshness metrics, pipeline backlog age, and latency percentiles."""
    now = utc_now()
    health_list = get_all_sources_health(db)

    total_sources = len(health_list)
    current_cnt = sum(1 for h in health_list if h.freshness_status == "CURRENT")
    stale_cnt = sum(1 for h in health_list if h.freshness_status in ("STALE", "RECENT"))
    failed_cnt = sum(1 for h in health_list if h.freshness_status == "FAILED")
    unknown_cnt = sum(1 for h in health_list if h.freshness_status in ("UNKNOWN", "INACTIVE"))

    # System status: never display UNKNOWN as HEALTHY
    if total_sources == 0 or unknown_cnt == total_sources:
        sys_status = "UNKNOWN"
    elif failed_cnt > 0 or stale_cnt > (total_sources // 2):
        sys_status = "DEGRADED"
    elif stale_cnt > 0:
        sys_status = "STALE"
    elif current_cnt > 0:
        sys_status = "HEALTHY"
    else:
        sys_status = "UNKNOWN"

    # Pending backlog
    backlog_statuses = ("RAW", "NORMALIZED", "EXTRACTION_PENDING")
    backlog_docs = list(
        db.scalars(
            select(Document)
            .where(Document.processing_status.in_(backlog_statuses))
            .order_by(Document.ingested_at)
        ).all()
    )
    pending_backlog_count = len(backlog_docs)
    oldest_backlog_age = None
    if backlog_docs and backlog_docs[0].ingested_at:
        oldest_backlog_age = round((now - backlog_docs[0].ingested_at).total_seconds(), 1)

    # Ingestion & Processing latencies on recent 100 documents
    recent_docs = list(
        db.scalars(
            select(Document)
            .where(Document.processing_status == "EXTRACTED")
            .order_by(desc(Document.ingested_at))
            .limit(100)
        ).all()
    )

    ingestion_latencies = []
    processing_latencies = []
    e2e_latencies = []
    for d in recent_docs:
        if d.published_at and d.ingested_at:
            delta = (d.ingested_at - d.published_at).total_seconds()
            if delta >= 0:
                ingestion_latencies.append(delta)
        if d.ingested_at and d.updated_at:
            delta = (d.updated_at - d.ingested_at).total_seconds()
            if delta >= 0:
                processing_latencies.append(delta)
        if d.published_at and d.updated_at:
            delta = (d.updated_at - d.published_at).total_seconds()
            if delta >= 0:
                e2e_latencies.append(delta)

    median_ingestion = None
    if ingestion_latencies:
        ingestion_latencies.sort()
        median_ingestion = round(ingestion_latencies[len(ingestion_latencies) // 2], 2)

    median_processing = None
    if processing_latencies:
        processing_latencies.sort()
        median_processing = round(processing_latencies[len(processing_latencies) // 2], 2)

    median_e2e = None
    if e2e_latencies:
        e2e_latencies.sort()
        median_e2e = round(e2e_latencies[len(e2e_latencies) // 2], 2)

    # Latest event and market observation timestamps
    latest_event = db.scalar(select(ExtractedEvent.event_time).order_by(desc(ExtractedEvent.event_time)).limit(1))
    latest_market = db.scalar(select(MarketObservation.timestamp).order_by(desc(MarketObservation.timestamp)).limit(1))

    breakdown = [
        {
            "source_id": str(h.source_id),
            "name": h.name,
            "freshness": h.freshness_status,
            "age_seconds": h.age_seconds,
            "failures": h.consecutive_failures,
        }
        for h in health_list
    ]

    return SystemFreshnessResponse(
        system_status=sys_status,
        current_time_utc=now,
        sources_total=total_sources,
        sources_current=current_cnt,
        sources_stale=stale_cnt,
        sources_failed=failed_cnt,
        sources_unknown=unknown_cnt,
        median_ingestion_latency_seconds=median_ingestion,
        median_processing_latency_seconds=median_processing,
        median_e2e_latency_seconds=median_e2e,
        oldest_backlog_document_age_seconds=oldest_backlog_age,
        pending_backlog_count=pending_backlog_count,
        latest_event_time=latest_event,
        latest_market_observation_time=latest_market,
        source_health_breakdown=breakdown,
    )


def _calc_percentiles(data: List[float]) -> LatencyPercentiles:
    """Calculate median, p90, min, and max for latency distribution."""
    if not data:
        return LatencyPercentiles(sample_size=0)
    data.sort()
    n = len(data)
    med = data[n // 2]
    p90_idx = min(n - 1, int(n * 0.9))
    p90 = data[p90_idx]
    return LatencyPercentiles(
        median_seconds=round(med, 2),
        p90_seconds=round(p90, 2),
        min_seconds=round(data[0], 2),
        max_seconds=round(data[-1], 2),
        sample_size=n,
    )


def get_operational_metrics(db: Session) -> OperationalMetricsResponse:
    """Calculate comprehensive operational latency distributions across fetch, processing, and E2E."""
    now = utc_now()
    recent_docs = list(
        db.scalars(
            select(Document)
            .where(Document.processing_status == "EXTRACTED")
            .order_by(desc(Document.ingested_at))
            .limit(200)
        ).all()
    )
    fetch_latencies = []
    processing_latencies = []
    e2e_latencies = []

    for d in recent_docs:
        if d.published_at and d.ingested_at:
            f_delta = (d.ingested_at - d.published_at).total_seconds()
            if f_delta >= 0:
                fetch_latencies.append(f_delta)
        if d.ingested_at and d.updated_at:
            p_delta = (d.updated_at - d.ingested_at).total_seconds()
            if p_delta >= 0:
                processing_latencies.append(p_delta)
        if d.published_at and d.updated_at:
            e_delta = (d.updated_at - d.published_at).total_seconds()
            if e_delta >= 0:
                e2e_latencies.append(e_delta)

    backlog_count = db.scalar(
        select(func.count(Document.id)).where(
            Document.processing_status.in_(["RAW", "NORMALIZED", "EXTRACTION_PENDING"])
        )
    ) or 0

    active_sources = db.scalar(
        select(func.count(Source.id)).where(Source.active.is_(True))
    ) or 0

    pipeline_health = "OPERATIONAL"
    if backlog_count > 50:
        pipeline_health = "BACKLOG_HIGH"
    elif backlog_count > 20:
        pipeline_health = "DEGRADED"

    return OperationalMetricsResponse(
        fetch_latency=_calc_percentiles(fetch_latencies),
        processing_latency=_calc_percentiles(processing_latencies),
        e2e_latency=_calc_percentiles(e2e_latencies),
        pipeline_health=pipeline_health,
        active_sources_count=active_sources,
        pending_backlog_count=backlog_count,
        calculated_at=now,
    )
