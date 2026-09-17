import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, func, desc, and_, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.app.models.event import ExtractedEvent
from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.document import Document
from backend.app.models.source import Source
from backend.app.models.observation import EconomicObservation
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.models.alert import Alert
from backend.app.schemas.intelligence_feed import (
    LiveFeedItem,
    LiveFeedEntityItem,
    LiveFeedEconomicItem,
    LiveFeedMarketItem,
    LiveFeedAlertItem,
    PaginatedLiveFeedResponse,
)
from backend.app.utils.time import utc_now


def get_live_intelligence_feed(
    db: Session,
    since: Optional[datetime] = None,
    hours: Optional[int] = None,
    min_importance: Optional[float] = None,
    min_confidence: Optional[float] = None,
    event_type: Optional[str] = None,
    country_code: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    source_id: Optional[uuid.UUID] = None,
    limit: int = 20,
    offset: int = 0,
) -> Tuple[List[LiveFeedItem], int, Dict[str, int]]:
    """Retrieve chronologically ordered real-time intelligence feed items with batch-loaded context."""
    now = utc_now()
    filters = []

    if hours:
        since = now - timedelta(hours=hours)
    if since:
        filters.append(
            or_(
                ExtractedEvent.event_time >= since,
                and_(ExtractedEvent.event_time.is_(None), ExtractedEvent.created_at >= since),
            )
        )
    if min_importance is not None:
        filters.append(ExtractedEvent.importance >= min_importance)
    if min_confidence is not None:
        filters.append(ExtractedEvent.confidence >= min_confidence)
    if event_type:
        filters.append(ExtractedEvent.event_type.ilike(f"%{event_type}%"))
    if source_id:
        filters.append(Document.source_id == source_id)

    # Base query joined with Document and Location Entity
    query = (
        select(ExtractedEvent)
        .outerjoin(Document, Document.id == ExtractedEvent.document_id)
        .options(
            joinedload(ExtractedEvent.document).joinedload(Document.source),
            joinedload(ExtractedEvent.location_entity),
        )
    )

    count_query = (
        select(func.count(ExtractedEvent.id))
        .outerjoin(Document, Document.id == ExtractedEvent.document_id)
    )

    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    # Order by event_time desc, then created_at desc
    query = query.order_by(
        ExtractedEvent.event_time.desc().nullslast(),
        ExtractedEvent.created_at.desc(),
    )

    total = db.scalar(count_query) or 0
    events = list(db.scalars(query.offset(offset).limit(min(100, limit))).all())

    if not events:
        return [], total, {"CURRENT": 0, "STALE": 0, "TOTAL": 0}

    event_ids = [e.id for e in events]
    doc_ids = [e.document_id for e in events if e.document_id]

    # Batch load clusters for events
    cluster_member_stmt = (
        select(EventClusterMember.extracted_event_id, EventCluster.id, EventCluster.canonical_title)
        .join(EventCluster, EventCluster.id == EventClusterMember.event_cluster_id)
        .where(EventClusterMember.extracted_event_id.in_(event_ids))
    )
    cluster_rows = db.execute(cluster_member_stmt).all()
    cluster_by_event: Dict[uuid.UUID, Tuple[uuid.UUID, str]] = {
        row[0]: (row[1], row[2]) for row in cluster_rows
    }

    # Batch load entities mentioned in documents
    entity_stmt = (
        select(DocumentEntity.document_id, Entity.id, Entity.canonical_name, Entity.entity_type, Entity.country_code)
        .join(Entity, Entity.id == DocumentEntity.entity_id)
        .where(DocumentEntity.document_id.in_(doc_ids))
    )
    doc_entity_rows = db.execute(entity_stmt).all()
    entities_by_doc: Dict[uuid.UUID, List[LiveFeedEntityItem]] = {}
    for r in doc_entity_rows:
        entities_by_doc.setdefault(r[0], []).append(
            LiveFeedEntityItem(id=r[1], canonical_name=r[2], entity_type=r[3], country_code=r[4])
        )

    # Batch load economic observations
    econ_stmt = (
        select(EconomicObservation)
        .options(joinedload(EconomicObservation.indicator))
        .where(EconomicObservation.event_id.in_(event_ids))
    )
    econ_obs = list(db.scalars(econ_stmt).all())
    econ_by_event: Dict[uuid.UUID, List[LiveFeedEconomicItem]] = {}
    for obs in econ_obs:
        ind_name = obs.indicator.canonical_name if obs.indicator else "Economic Metric"
        econ_by_event.setdefault(obs.event_id, []).append(
            LiveFeedEconomicItem(
                indicator_name=ind_name,
                reported_value=obs.reported_value,
                reported_unit=obs.reported_unit,
                direction=obs.direction,
                economic_relevance=obs.economic_relevance or 0.8,
            )
        )

    # Batch load market correlations
    corr_stmt = (
        select(EventMarketCorrelation)
        .options(joinedload(EventMarketCorrelation.market_asset))
        .where(EventMarketCorrelation.event_id.in_(event_ids))
    )
    corrs = list(db.scalars(corr_stmt).all())
    corrs_by_event: Dict[uuid.UUID, List[LiveFeedMarketItem]] = {}
    for c in corrs:
        sym = c.market_asset.symbol if c.market_asset else "ASSET"
        cname = c.market_asset.canonical_name if c.market_asset else sym
        ret_val = c.return_percent if c.return_percent is not None else 0.0
        sign = "+" if ret_val >= 0 else ""
        neutral = f"{sym} exhibited a {sign}{ret_val:.2f}% price change within {c.window_size}."
        corrs_by_event.setdefault(c.event_id, []).append(
            LiveFeedMarketItem(
                symbol=sym,
                canonical_name=cname,
                window_size=c.window_size,
                return_percent=ret_val,
                neutral_observation=neutral,
            )
        )

    # Batch load active alerts for these events
    alert_stmt = (
        select(Alert)
        .where(Alert.affected_event_id.in_(event_ids))
    )
    alerts_list = list(db.scalars(alert_stmt).all())
    alerts_by_event: Dict[uuid.UUID, List[LiveFeedAlertItem]] = {}
    for a in alerts_list:
        alerts_by_event.setdefault(a.affected_event_id, []).append(
            LiveFeedAlertItem(
                id=a.id,
                trigger_type=a.trigger_type,
                alert_title=a.alert_title,
                importance=a.importance,
                status=a.status,
            )
        )

    from backend.app.services.freshness_service import compute_item_freshness_status

    feed_items: List[LiveFeedItem] = []
    current_count = 0
    stale_count = 0
    freshness_breakdown: Dict[str, int] = {}

    for ev in events:
        doc = ev.document
        src = doc.source if doc else None

        cluster_info = cluster_by_event.get(ev.id)
        cluster_id = cluster_info[0] if cluster_info else None
        cluster_title = cluster_info[1] if cluster_info else None

        loc_name = ev.location_entity.canonical_name if ev.location_entity else None
        loc_country = ev.location_entity.country_code if ev.location_entity else None

        pub_time = doc.published_at if doc else None
        freshness, age_sec = compute_item_freshness_status(
            event_time=ev.event_time,
            published_at=pub_time,
            metadata=ev.metadata_,
            now=now,
        )

        if freshness == "CURRENT":
            current_count += 1
        else:
            stale_count += 1

        freshness_breakdown[freshness] = freshness_breakdown.get(freshness, 0) + 1

        # Operational latency calculations
        proc_time = (doc.updated_at if doc and doc.processing_status == "EXTRACTED" else None) or ev.created_at
        pipe_dur = None
        if doc and doc.ingested_at and proc_time:
            p_delta = (proc_time - doc.ingested_at).total_seconds()
            if p_delta >= 0:
                pipe_dur = round(p_delta, 2)

        e2e_lat = None
        if pub_time and proc_time:
            e_delta = (proc_time - pub_time).total_seconds()
            if e_delta >= 0:
                e2e_lat = round(e_delta, 2)

        feed_items.append(
            LiveFeedItem(
                event_id=ev.id,
                document_id=ev.document_id,
                event_title=ev.event_title,
                event_summary=ev.event_summary,
                event_type=ev.event_type,
                event_time=ev.event_time,
                published_at=pub_time,
                ingested_at=doc.ingested_at if doc else None,
                processed_at=proc_time,
                pipeline_duration_seconds=pipe_dur,
                e2e_latency_seconds=e2e_lat,
                importance=ev.importance,
                confidence=ev.confidence,
                cluster_id=cluster_id,
                cluster_title=cluster_title,
                primary_location=loc_name,
                country_code=loc_country,
                source_id=src.id if src else None,
                source_name=src.name if src else None,
                entities=entities_by_doc.get(ev.document_id, []) if ev.document_id else [],
                economic_context=econ_by_event.get(ev.id, []),
                market_context=corrs_by_event.get(ev.id, []),
                active_alerts=alerts_by_event.get(ev.id, []),
                freshness_status=freshness,
                age_seconds=age_sec,
                provenance_url=doc.url if doc else None,
                created_at=ev.created_at,
            )
        )

    freshness_summary = {
        "CURRENT": current_count,
        "STALE": stale_count,
        "TOTAL": len(feed_items),
        **freshness_breakdown,
    }

    return feed_items, total, freshness_summary
