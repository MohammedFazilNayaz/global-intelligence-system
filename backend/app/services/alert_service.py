import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, func, desc, and_
from sqlalchemy.orm import Session

from backend.app.models.alert import Alert
from backend.app.models.event import ExtractedEvent
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.ingestion_run import IngestionRun
from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.models.observation import EconomicObservation
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.models.market_asset import MarketAsset
from backend.app.schemas.alert import AlertTriggerType, AlertStatus
from backend.app.utils.time import utc_now
from backend.app.utils.logger import get_logger

logger = get_logger("service.alert")

# Mandatory Non-Causal Linter
_CAUSAL_LINTER_REGEX = re.compile(
    r"\b(?:caused|cause|causing|causes|led\s+to|leads\s+to|leading\s+to|drove|drives|driving|triggered|triggers|triggering|forced|forces|forcing|resulted\s+in|results\s+in)\b",
    re.IGNORECASE,
)


def _assert_non_causal(text: str) -> None:
    match = _CAUSAL_LINTER_REGEX.search(text)
    if match:
        raise ValueError(f"Prohibited causal claim in alert explanation: '{match.group(0)}' in '{text}'")


def evaluate_event_alerts(db: Session, event_id: uuid.UUID) -> List[Alert]:
    """Evaluate deterministic alert criteria for an extracted event.
    
    Generates explainable, evidence-backed alerts with deduplication and zero causal claims.
    """
    event = db.get(ExtractedEvent, event_id)
    if not event:
        return []

    created_alerts: List[Alert] = []
    now = utc_now()

    # Retrieve associated document, entities, economic observations, and market correlations
    doc = event.document
    source_id = doc.source_id if doc else None
    evidence_text = event.event_summary or event.event_title

    affected_entity_ids = []
    if event.location_entity_id:
        affected_entity_ids.append(str(event.location_entity_id))

    # TRIGGER 1: HIGH_IMPORTANCE_EVENT (importance >= 0.85 and confidence >= 0.80)
    if event.importance >= 0.85 and event.confidence >= 0.80:
        existing = db.scalars(
            select(Alert).where(
                Alert.affected_event_id == event.id,
                Alert.trigger_type == AlertTriggerType.HIGH_IMPORTANCE_EVENT.value,
                Alert.status == AlertStatus.ACTIVE.value,
            )
        ).first()
        if not existing:
            explanation = (
                f"Observed high-importance event '{event.event_title}' with calibrated importance score "
                f"{event.importance:.2f} and confidence {event.confidence:.2f}."
            )
            _assert_non_causal(explanation)
            alert = Alert(
                trigger_type=AlertTriggerType.HIGH_IMPORTANCE_EVENT.value,
                alert_title=f"High-Importance Event: {event.event_title[:100]}",
                timestamp=now,
                importance=event.importance,
                confidence=event.confidence,
                affected_entity_ids=affected_entity_ids,
                affected_event_id=event.id,
                affected_source_id=source_id,
                evidence=evidence_text,
                explanation=explanation,
                status=AlertStatus.ACTIVE.value,
                metadata_={"importance": event.importance, "event_type": event.event_type},
            )
            db.add(alert)
            created_alerts.append(alert)

    # TRIGGER 2: MAJOR_GEOPOLITICAL_EVENT
    geopolitical_types = {
        "geopolitical_conflict", "military_conflict", "sanction_imposition",
        "treaty_signing", "diplomatic_summit", "state_visit", "election_outcome"
    }
    if event.event_type.lower() in geopolitical_types and event.importance >= 0.70:
        existing = db.scalars(
            select(Alert).where(
                Alert.affected_event_id == event.id,
                Alert.trigger_type == AlertTriggerType.MAJOR_GEOPOLITICAL_EVENT.value,
                Alert.status == AlertStatus.ACTIVE.value,
            )
        ).first()
        if not existing:
            explanation = (
                f"Observed major geopolitical event of type '{event.event_type}' with importance "
                f"{event.importance:.2f} and confidence {event.confidence:.2f}."
            )
            _assert_non_causal(explanation)
            alert = Alert(
                trigger_type=AlertTriggerType.MAJOR_GEOPOLITICAL_EVENT.value,
                alert_title=f"Geopolitical Alert: {event.event_title[:100]}",
                timestamp=now,
                importance=event.importance,
                confidence=event.confidence,
                affected_entity_ids=affected_entity_ids,
                affected_event_id=event.id,
                affected_source_id=source_id,
                evidence=evidence_text,
                explanation=explanation,
                status=AlertStatus.ACTIVE.value,
                metadata_={"event_type": event.event_type},
            )
            db.add(alert)
            created_alerts.append(alert)

    # TRIGGER 3: MAJOR_ECONOMIC_RELEASE (Central Bank decisions or substantial economic shift)
    econ_obs = list(db.scalars(select(EconomicObservation).where(EconomicObservation.event_id == event.id)).all())
    for obs in econ_obs:
        is_major_econ = (
            (obs.economic_relevance and obs.economic_relevance >= 0.85) or
            (obs.metadata_ and obs.metadata_.get("central_bank_decision")) or
            (event.event_type in ("central_bank_decision", "economic_release") and event.importance >= 0.75)
        )
        if is_major_econ:
            existing = db.scalars(
                select(Alert).where(
                    Alert.affected_event_id == event.id,
                    Alert.trigger_type == AlertTriggerType.MAJOR_ECONOMIC_RELEASE.value,
                    Alert.status == AlertStatus.ACTIVE.value,
                )
            ).first()
            if not existing:
                indicator_name = obs.indicator.canonical_name if obs.indicator else "Economic Metric"
                explanation = (
                    f"Observed major economic release for {indicator_name}: "
                    f"reported {obs.reported_value}{obs.reported_unit or ''} with economic relevance {obs.economic_relevance or 0.80:.2f}."
                )
                _assert_non_causal(explanation)
                alert = Alert(
                    trigger_type=AlertTriggerType.MAJOR_ECONOMIC_RELEASE.value,
                    alert_title=f"Economic Release: {indicator_name}",
                    timestamp=now,
                    importance=max(event.importance, obs.economic_relevance or 0.80),
                    confidence=event.confidence,
                    affected_entity_ids=affected_entity_ids,
                    affected_event_id=event.id,
                    affected_source_id=source_id,
                    evidence=obs.metadata_.get("evidence_snippet", evidence_text) if obs.metadata_ else evidence_text,
                    explanation=explanation,
                    status=AlertStatus.ACTIVE.value,
                    metadata_={"indicator": indicator_name, "reported_value": obs.reported_value},
                )
                db.add(alert)
                created_alerts.append(alert)
            break

    # TRIGGER 7: MARKET_ASSOCIATION (significant observed excursion around event)
    correlations = list(db.scalars(select(EventMarketCorrelation).where(EventMarketCorrelation.event_id == event.id)).all())
    for corr in correlations:
        if abs(corr.return_percent) >= 1.0:
            existing = db.scalars(
                select(Alert).where(
                    Alert.affected_event_id == event.id,
                    Alert.trigger_type == AlertTriggerType.MARKET_ASSOCIATION.value,
                    Alert.status == AlertStatus.ACTIVE.value,
                )
            ).first()
            if not existing:
                asset_sym = corr.market_asset.symbol if corr.market_asset else "Market Asset"
                sign = "+" if corr.return_percent >= 0 else ""
                explanation = (
                    f"Retrospective observation: {asset_sym} exhibited a {sign}{corr.return_percent:.2f}% price change "
                    f"within the {corr.window_size} observation window around '{event.event_title[:60]}'."
                )
                _assert_non_causal(explanation)
                alert = Alert(
                    trigger_type=AlertTriggerType.MARKET_ASSOCIATION.value,
                    alert_title=f"Market Association: {asset_sym} {sign}{corr.return_percent:.2f}% ({corr.window_size})",
                    timestamp=now,
                    importance=min(1.0, event.importance + 0.1),
                    confidence=event.confidence,
                    affected_entity_ids=affected_entity_ids,
                    affected_event_id=event.id,
                    affected_source_id=source_id,
                    evidence=f"Observed return: {sign}{corr.return_percent:.2f}% ({corr.window_size} window)",
                    explanation=explanation,
                    status=AlertStatus.ACTIVE.value,
                    metadata_={"symbol": asset_sym, "return_percent": corr.return_percent, "window": corr.window_size},
                )
                db.add(alert)
                created_alerts.append(alert)
            break

    if created_alerts:
        db.flush()

    return created_alerts


def evaluate_source_alerts(db: Session, source_id: uuid.UUID) -> List[Alert]:
    """Evaluate source health criteria for data quality failures or staleness."""
    source = db.get(Source, source_id)
    if not source:
        return []

    created_alerts: List[Alert] = []
    now = utc_now()

    # DATA_QUALITY_FAILURE (>= 3 consecutive failures)
    if source.consecutive_failures >= 3:
        existing = db.scalars(
            select(Alert).where(
                Alert.affected_source_id == source.id,
                Alert.trigger_type == AlertTriggerType.DATA_QUALITY_FAILURE.value,
                Alert.status == AlertStatus.ACTIVE.value,
            )
        ).first()
        if not existing:
            explanation = (
                f"Source '{source.name}' encountered {source.consecutive_failures} consecutive ingestion failures. "
                f"Last recorded error: {source.last_error_message or 'Unknown connection failure'}."
            )
            _assert_non_causal(explanation)
            alert = Alert(
                trigger_type=AlertTriggerType.DATA_QUALITY_FAILURE.value,
                alert_title=f"Source Quality Failure: {source.name}",
                timestamp=now,
                importance=0.75,
                confidence=1.0,
                affected_entity_ids=[],
                affected_source_id=source.id,
                evidence=source.last_error_message or "Consecutive network/parsing errors",
                explanation=explanation,
                status=AlertStatus.ACTIVE.value,
                metadata_={"consecutive_failures": source.consecutive_failures},
            )
            db.add(alert)
            created_alerts.append(alert)

    # STALE_SOURCE (age > 2 * polling_interval and active)
    if source.active and source.last_successful_fetch_at:
        elapsed = (now - source.last_successful_fetch_at).total_seconds()
        if elapsed > (source.polling_interval_seconds * 2.0) and elapsed > 600:
            existing = db.scalars(
                select(Alert).where(
                    Alert.affected_source_id == source.id,
                    Alert.trigger_type == AlertTriggerType.STALE_SOURCE.value,
                    Alert.status == AlertStatus.ACTIVE.value,
                )
            ).first()
            if not existing:
                explanation = (
                    f"Active source '{source.name}' has not received updates for {int(elapsed)}s "
                    f"(expected cadence: {source.polling_interval_seconds}s)."
                )
                _assert_non_causal(explanation)
                alert = Alert(
                    trigger_type=AlertTriggerType.STALE_SOURCE.value,
                    alert_title=f"Stale Source: {source.name}",
                    timestamp=now,
                    importance=0.65,
                    confidence=0.95,
                    affected_entity_ids=[],
                    affected_source_id=source.id,
                    evidence=f"Last fetch at {source.last_successful_fetch_at.isoformat()}",
                    explanation=explanation,
                    status=AlertStatus.ACTIVE.value,
                    metadata_={"elapsed_seconds": elapsed, "polling_interval": source.polling_interval_seconds},
                )
                db.add(alert)
                created_alerts.append(alert)

    if created_alerts:
        db.flush()

    return created_alerts


def evaluate_system_alerts(db: Session) -> List[Alert]:
    """Evaluate system-level alerts: processing backlog depth and high ingestion failure rates."""
    created_alerts: List[Alert] = []
    now = utc_now()

    # 1. PROCESSING_BACKLOG_EXCEEDED (backlog > 50)
    backlog_count = db.scalar(
        select(func.count(Document.id)).where(
            Document.processing_status.in_(["RAW", "NORMALIZED", "EXTRACTION_PENDING"])
        )
    ) or 0

    if backlog_count > 50:
        existing = db.scalars(
            select(Alert).where(
                Alert.trigger_type == AlertTriggerType.PROCESSING_BACKLOG_EXCEEDED.value,
                Alert.status == AlertStatus.ACTIVE.value,
            )
        ).first()
        if not existing:
            explanation = (
                f"Observed processing backlog of {backlog_count} documents awaiting extraction, "
                f"exceeding normal operational threshold (50)."
            )
            _assert_non_causal(explanation)
            alert = Alert(
                trigger_type=AlertTriggerType.PROCESSING_BACKLOG_EXCEEDED.value,
                alert_title=f"Processing Backlog Elevated: {backlog_count} documents",
                timestamp=now,
                importance=0.75,
                confidence=1.0,
                affected_entity_ids=[],
                evidence=f"Queue depth: {backlog_count} documents in pending state",
                explanation=explanation,
                status=AlertStatus.ACTIVE.value,
                metadata_={"backlog_count": backlog_count},
            )
            db.add(alert)
            created_alerts.append(alert)

    # 2. HIGH_INGESTION_FAILURE_RATE (failure rate >= 50% across last 10 runs)
    recent_runs = list(
        db.scalars(
            select(IngestionRun)
            .order_by(desc(IngestionRun.started_at))
            .limit(10)
        ).all()
    )
    if len(recent_runs) >= 4:
        failed_count = sum(1 for r in recent_runs if r.status == "FAILED")
        failure_rate = failed_count / len(recent_runs)
        if failure_rate >= 0.50:
            existing = db.scalars(
                select(Alert).where(
                    Alert.trigger_type == AlertTriggerType.HIGH_INGESTION_FAILURE_RATE.value,
                    Alert.status == AlertStatus.ACTIVE.value,
                )
            ).first()
            if not existing:
                explanation = (
                    f"Observed {failed_count} failures across {len(recent_runs)} recent source ingestion runs "
                    f"({failure_rate * 100:.1f}% failure rate)."
                )
                _assert_non_causal(explanation)
                alert = Alert(
                    trigger_type=AlertTriggerType.HIGH_INGESTION_FAILURE_RATE.value,
                    alert_title=f"High Ingestion Failure Rate: {failure_rate * 100:.0f}%",
                    timestamp=now,
                    importance=0.80,
                    confidence=1.0,
                    affected_entity_ids=[],
                    evidence=f"{failed_count} of {len(recent_runs)} recent runs failed",
                    explanation=explanation,
                    status=AlertStatus.ACTIVE.value,
                    metadata_={"failure_rate": failure_rate, "sample_size": len(recent_runs)},
                )
                db.add(alert)
                created_alerts.append(alert)

    if created_alerts:
        db.flush()

    return created_alerts


def evaluate_cluster_alerts(db: Session, cluster_id: uuid.UUID) -> List[Alert]:
    """Evaluate alerts for significant event cluster updates with multi-source corroboration."""
    cluster = db.get(EventCluster, cluster_id)
    if not cluster:
        return []

    created_alerts: List[Alert] = []
    now = utc_now()

    # Count events in cluster
    member_count = db.scalar(
        select(func.count(EventClusterMember.id)).where(
            EventClusterMember.event_cluster_id == cluster.id
        )
    ) or 0

    if member_count >= 3 and cluster.confidence >= 0.80:
        active_cluster_alerts = list(
            db.scalars(
                select(Alert).where(
                    Alert.trigger_type == AlertTriggerType.SIGNIFICANT_CLUSTER_UPDATE.value,
                    Alert.status == AlertStatus.ACTIVE.value,
                )
            ).all()
        )
        already_alerted = any(
            (a.metadata_ or {}).get("cluster_id") == str(cluster.id)
            for a in active_cluster_alerts
        )
        if not already_alerted:
            explanation = (
                f"Observed significant event cluster '{cluster.canonical_title}' with {member_count} "
                f"corroborated events and confidence score {cluster.confidence:.2f}."
            )
            _assert_non_causal(explanation)
            loc_id = str(cluster.primary_location_entity_id) if cluster.primary_location_entity_id else None
            alert = Alert(
                trigger_type=AlertTriggerType.SIGNIFICANT_CLUSTER_UPDATE.value,
                alert_title=f"Significant Cluster: {cluster.canonical_title[:80]}",
                timestamp=now,
                importance=min(1.0, 0.70 + (member_count * 0.05)),
                confidence=cluster.confidence,
                affected_entity_ids=[loc_id] if loc_id else [],
                evidence=f"{member_count} member events in cluster with confidence {cluster.confidence:.2f}",
                explanation=explanation,
                status=AlertStatus.ACTIVE.value,
                metadata_={"cluster_id": str(cluster.id), "member_count": member_count},
            )
            db.add(alert)
            created_alerts.append(alert)

    if created_alerts:
        db.flush()

    return created_alerts



def list_alerts(
    db: Session,
    status: Optional[str] = None,
    trigger_type: Optional[str] = None,
    min_importance: Optional[float] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Alert], int]:
    """List paginated alerts with filters."""
    query = select(Alert)
    count_query = select(func.count(Alert.id))

    filters = []
    if status:
        filters.append(Alert.status == status.upper())
    if trigger_type:
        filters.append(Alert.trigger_type == trigger_type.upper())
    if min_importance is not None:
        filters.append(Alert.importance >= min_importance)

    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    total = db.scalar(count_query) or 0
    items = list(db.scalars(query.order_by(desc(Alert.timestamp)).offset(offset).limit(limit)).all())
    return items, total


def get_alert_by_id(db: Session, alert_id: uuid.UUID) -> Optional[Alert]:
    return db.get(Alert, alert_id)


def acknowledge_alert(db: Session, alert_id: uuid.UUID, note: Optional[str] = None) -> Optional[Alert]:
    alert = db.get(Alert, alert_id)
    if not alert:
        return None
    alert.status = AlertStatus.ACKNOWLEDGED.value
    if note:
        meta = dict(alert.metadata_)
        meta["acknowledgment_note"] = note
        meta["acknowledged_at"] = utc_now().isoformat()
        alert.metadata_ = meta
    db.commit()
    db.refresh(alert)
    return alert
