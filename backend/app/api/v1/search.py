import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session, joinedload

from backend.app.db.session import get_db
from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.models.entity import Entity
from backend.app.models.market_asset import MarketAsset
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.schemas.cluster import EventClusterRead
from backend.app.schemas.entity import EntityRead
from backend.app.schemas.economic import EconomicIndicatorRead, EconomicObservationRead
from backend.app.schemas.market import MarketAssetRead, EventMarketCorrelationRead, STANDARD_CORRELATION_DISCLAIMER
from backend.app.services.economic_service import search_economic_intelligence

router = APIRouter(prefix="/search", tags=["Search"])


class GlobalSearchResult(BaseModel):
    query: str
    total_clusters: int = 0
    total_entities: int = 0
    total_indicators: int = 0
    total_observations: int = 0
    total_market_assets: int = 0
    clusters: List[EventClusterRead]
    entities: List[EntityRead]
    indicators: List[EconomicIndicatorRead] = []
    observations: List[EconomicObservationRead] = []
    market_assets: List[MarketAssetRead] = []
    correlations: List[EventMarketCorrelationRead] = []


@router.get("", response_model=GlobalSearchResult)
def search_intelligence(
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(10, ge=1, le=50, description="Max results per category"),
    db: Session = Depends(get_db),
) -> GlobalSearchResult:
    """
    Execute global text search across:
    - Event clusters
    - Canonical entities
    - Economic indicators & observations
    - Market assets (symbols, names)
    - Compound event + asset relationships (e.g. 'CPI + Bitcoin', 'Fed + S&P 500')
    """
    clean_q = q.strip()

    # Check for compound query (e.g. "CPI + Bitcoin")
    if "+" in clean_q:
        parts = [p.strip() for p in clean_q.split("+") if p.strip()]
    else:
        parts = [clean_q]

    # Build pattern conditions
    cluster_conditions = []
    entity_conditions = []
    asset_conditions = []

    for p in parts:
        sub_pat = f"%{p}%"
        cluster_conditions.append(
            EventCluster.canonical_title.ilike(sub_pat) | EventCluster.canonical_summary.ilike(sub_pat)
        )
        entity_conditions.append(
            Entity.canonical_name.ilike(sub_pat) | Entity.normalized_name.ilike(sub_pat)
        )
        asset_conditions.append(
            MarketAsset.symbol.ilike(sub_pat) | MarketAsset.canonical_name.ilike(sub_pat)
        )

    # 1. Search Event Clusters
    cluster_filter = or_(*cluster_conditions)
    cluster_records = list(
        db.scalars(
            select(EventCluster)
            .options(
                joinedload(EventCluster.primary_location_entity),
                joinedload(EventCluster.members).joinedload(EventClusterMember.extracted_event),
            )
            .where(
                EventCluster.status == "ACTIVE",
                cluster_filter,
            )
            .order_by(EventCluster.event_time_start.desc().nulls_last(), EventCluster.updated_at.desc())
            .limit(limit)
        ).unique().all()
    )

    cluster_reads: List[EventClusterRead] = []
    for c in cluster_records:
        importance_val = (c.metadata_ or {}).get("importance")
        if importance_val is None and c.members:
            importance_val = max(
                (m.extracted_event.importance for m in c.members if m.extracted_event and m.extracted_event.importance is not None),
                default=0.8,
            )

        source_count = (c.metadata_ or {}).get("unique_source_count", 1)
        doc_count = (c.metadata_ or {}).get("document_count", len(c.members))

        cluster_reads.append(
            EventClusterRead(
                id=c.id,
                canonical_title=c.canonical_title,
                canonical_summary=c.canonical_summary,
                event_type=c.event_type,
                event_time_start=c.event_time_start,
                event_time_end=c.event_time_end,
                primary_location_entity_id=c.primary_location_entity_id,
                confidence=c.confidence,
                importance=importance_val or 0.8,
                status=c.status,
                metadata=c.metadata_ or {},
                created_at=c.created_at,
                updated_at=c.updated_at,
                primary_location_entity=c.primary_location_entity,
                members_count=len(c.members) if c.members else doc_count,
                unique_sources_count=source_count,
                member_count=len(c.members) if c.members else doc_count,
                unique_source_count=source_count,
            )
        )

    # 2. Search Entities
    entity_filter = or_(*entity_conditions)
    entity_records = list(
        db.scalars(
            select(Entity)
            .where(entity_filter)
            .limit(limit)
        ).all()
    )
    entity_reads = [EntityRead.model_validate(e) for e in entity_records]

    # 3. Search Economic Intelligence
    econ_results = search_economic_intelligence(db=db, query=parts[0], limit=limit)
    if len(parts) > 1:
        econ2 = search_economic_intelligence(db=db, query=parts[1], limit=limit)
        # Merge unique indicators
        seen_ind = {ind.id for ind in econ_results["indicators"]}
        for ind in econ2["indicators"]:
            if ind.id not in seen_ind:
                econ_results["indicators"].append(ind)
                seen_ind.add(ind.id)
        econ_results["total_indicators"] = len(econ_results["indicators"])

    # 4. Search Market Assets
    asset_filter = or_(*asset_conditions)
    asset_records = list(
        db.scalars(
            select(MarketAsset)
            .where(asset_filter)
            .limit(limit)
        ).all()
    )
    asset_reads = [MarketAssetRead.model_validate(a) for a in asset_records]

    # 5. Correlations if compound search or matching assets/clusters
    correlations: List[EventMarketCorrelationRead] = []
    asset_ids = [a.id for a in asset_records]
    cluster_event_ids = []
    for c in cluster_records:
        if c.members:
            cluster_event_ids.extend([m.extracted_event_id for m in c.members if m.extracted_event_id])

    if asset_ids:
        corr_stmt = (
            select(EventMarketCorrelation)
            .options(
                joinedload(EventMarketCorrelation.market_asset),
                joinedload(EventMarketCorrelation.extracted_event),
            )
            .where(EventMarketCorrelation.market_asset_id.in_(asset_ids))
        )
        if cluster_event_ids:
            corr_stmt = corr_stmt.where(EventMarketCorrelation.event_id.in_(cluster_event_ids))

        corr_records = list(db.scalars(corr_stmt.limit(limit)).unique().all())
        for cr in corr_records:
            correlations.append(
                EventMarketCorrelationRead(
                    id=cr.id,
                    event_id=cr.event_id,
                    cluster_id=cr.cluster_id,
                    market_asset_id=cr.market_asset_id,
                    window_size=cr.window_size,
                    window_start=cr.window_start,
                    window_end=cr.window_end,
                    pre_event_price=cr.pre_event_price,
                    event_price=cr.event_price,
                    post_event_price=cr.post_event_price,
                    return_percent=cr.return_percent,
                    absolute_change=cr.absolute_change,
                    volatility=cr.volatility,
                    volume_change=cr.volume_change,
                    max_excursion=cr.max_excursion,
                    min_excursion=cr.min_excursion,
                    calculated_at=cr.calculated_at,
                    methodology=cr.methodology,
                    disclaimer=STANDARD_CORRELATION_DISCLAIMER,
                    metadata=cr.metadata_ or {},
                    market_asset=cr.market_asset,
                    event_title=cr.extracted_event.event_title if cr.extracted_event else None,
                    event_type=cr.extracted_event.event_type if cr.extracted_event else None,
                    event_time=cr.extracted_event.event_time if cr.extracted_event else None,
                    created_at=cr.created_at,
                    updated_at=cr.updated_at,
                )
            )

    return GlobalSearchResult(
        query=clean_q,
        total_clusters=len(cluster_reads),
        total_entities=len(entity_reads),
        total_indicators=econ_results["total_indicators"],
        total_observations=econ_results["total_observations"],
        total_market_assets=len(asset_reads),
        clusters=cluster_reads,
        entities=entity_reads,
        indicators=econ_results["indicators"],
        observations=econ_results["observations"],
        market_assets=asset_reads,
        correlations=correlations,
    )


@router.get("/graph")
def search_knowledge_graph(
    q: str = Query(..., min_length=1, max_length=100, description="Entity or concept to search within knowledge graph"),
    depth: int = Query(1, ge=1, le=3, description="Graph traversal depth (strictly bounded to max 3)"),
    limit: int = Query(20, ge=1, le=50, description="Max matching nodes"),
    db: Session = Depends(get_db),
):
    """Search knowledge graph for entities and return bounded connected subgraphs."""
    from backend.app.services import graph_service

    clean_q = q.strip()
    if not clean_q:
        return {
            "depth": depth,
            "nodes": [],
            "edges": [],
            "total_nodes": 0,
            "total_edges": 0,
        }

    return graph_service.search_graph(db, query=clean_q, depth=depth, limit=limit)
