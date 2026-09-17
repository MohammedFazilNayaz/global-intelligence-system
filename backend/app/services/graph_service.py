import re
import uuid
from typing import Optional, List, Dict, Any, Tuple, Set
from datetime import datetime, timezone
from sqlalchemy import select, or_, and_, func
from sqlalchemy.orm import Session, joinedload

from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.event import ExtractedEvent
from backend.app.models.relationship import EntityRelationship
from backend.app.models.indicator import EconomicIndicator
from backend.app.models.observation import EconomicObservation
from backend.app.models.market_asset import MarketAsset
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.schemas.relationship import (
    RelationshipType,
    EntityRelationshipCreate,
    KnowledgeGraphResponse,
    GraphNode,
    GraphEdge,
    EventRelationshipsResponse,
    EventImpactAssessmentResponse,
    EconomicContextItem,
    MarketContextItem,
)
from backend.app.schemas.entity import EntityRead
from backend.app.utils.time import utc_now


_CAUSAL_LINTER_REGEX = re.compile(
    r"\b(?:caused|causes|drove|drives|triggered|triggers|because\s+of|led\s+to|leads\s+to|will\s+lead\s+to|will\s+cause|predicts|predicting|responsible\s+for)\b",
    re.IGNORECASE,
)

STANDARD_IMPACT_DISCLAIMER = (
    "Impact assessments represent retrospective, observational associations within historical observation windows. "
    "They do not assert or imply causality, trade recommendations, or future price forecasts."
)


def create_relationship(
    db: Session,
    rel_in: EntityRelationshipCreate,
) -> EntityRelationship:
    """Create a verified entity relationship with strict provenance and orphan prevention."""
    # 1. Provenance validation
    if not rel_in.evidence or not rel_in.evidence.strip():
        raise ValueError("Relationship evidence snippet is required and cannot be empty.")
    if not rel_in.extraction_method or not rel_in.extractor_version:
        raise ValueError("Extraction method and extractor version are mandatory provenance fields.")

    # 2. Confidence validation
    if rel_in.confidence < 0.50:
        raise ValueError(f"Confidence {rel_in.confidence} is below minimum relationship threshold (0.50).")

    # 3. Orphan prevention (Verify foreign keys exist)
    source_ent = db.get(Entity, rel_in.source_entity_id)
    target_ent = db.get(Entity, rel_in.target_entity_id)
    if not source_ent:
        raise ValueError(f"Source entity with ID '{rel_in.source_entity_id}' does not exist.")
    if not target_ent:
        raise ValueError(f"Target entity with ID '{rel_in.target_entity_id}' does not exist.")

    # 4. Check for existing relationship (Idempotency & Deduplication)
    existing = db.execute(
        select(EntityRelationship).where(
            EntityRelationship.source_entity_id == rel_in.source_entity_id,
            EntityRelationship.target_entity_id == rel_in.target_entity_id,
            EntityRelationship.relationship_type == rel_in.relationship_type.value,
        )
    ).scalar_one_or_none()

    if existing:
        # Merge evidence and update timestamp
        if rel_in.evidence not in existing.evidence:
            existing.evidence = f"{existing.evidence} | {rel_in.evidence}"
        existing.confidence = max(existing.confidence, rel_in.confidence)
        existing.updated_at = utc_now()
        db.commit()
        db.refresh(existing)
        return existing

    rel = EntityRelationship(
        source_entity_id=rel_in.source_entity_id,
        target_entity_id=rel_in.target_entity_id,
        relationship_type=rel_in.relationship_type.value,
        confidence=rel_in.confidence,
        source_document_id=rel_in.source_document_id,
        source_event_id=rel_in.source_event_id,
        extraction_method=rel_in.extraction_method,
        extractor_version=rel_in.extractor_version,
        evidence=rel_in.evidence,
        metadata_=rel_in.metadata_,
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


def get_relationship(db: Session, relationship_id: uuid.UUID) -> Optional[EntityRelationship]:
    """Retrieve relationship by UUID with joined entities."""
    return db.execute(
        select(EntityRelationship)
        .options(
            joinedload(EntityRelationship.source_entity),
            joinedload(EntityRelationship.target_entity),
        )
        .where(EntityRelationship.id == relationship_id)
    ).scalar_one_or_none()


def list_relationships(
    db: Session,
    relationship_type: Optional[str] = None,
    source_entity_id: Optional[uuid.UUID] = None,
    target_entity_id: Optional[uuid.UUID] = None,
    min_confidence: Optional[float] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[EntityRelationship], int, int]:
    """Paginated retrieval of relationships with server-side filtering."""
    query = select(EntityRelationship).options(
        joinedload(EntityRelationship.source_entity),
        joinedload(EntityRelationship.target_entity),
    )

    if relationship_type:
        query = query.where(EntityRelationship.relationship_type == relationship_type)
    if source_entity_id:
        query = query.where(EntityRelationship.source_entity_id == source_entity_id)
    if target_entity_id:
        query = query.where(EntityRelationship.target_entity_id == target_entity_id)
    if min_confidence is not None:
        query = query.where(EntityRelationship.confidence >= min_confidence)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = max(1, (total + page_size - 1) // page_size)

    offset = (page - 1) * page_size
    items = db.execute(
        query.order_by(EntityRelationship.created_at.desc()).offset(offset).limit(page_size)
    ).scalars().all()

    return list(items), total, total_pages


def get_entity_relationships(
    db: Session,
    entity_id: uuid.UUID,
) -> Tuple[List[EntityRelationship], List[EntityRelationship]]:
    """Retrieve all outbound and inbound relationships for an entity."""
    outbound = db.execute(
        select(EntityRelationship)
        .options(
            joinedload(EntityRelationship.source_entity),
            joinedload(EntityRelationship.target_entity),
        )
        .where(EntityRelationship.source_entity_id == entity_id)
        .order_by(EntityRelationship.confidence.desc())
    ).scalars().all()

    inbound = db.execute(
        select(EntityRelationship)
        .options(
            joinedload(EntityRelationship.source_entity),
            joinedload(EntityRelationship.target_entity),
        )
        .where(EntityRelationship.target_entity_id == entity_id)
        .order_by(EntityRelationship.confidence.desc())
    ).scalars().all()

    return list(outbound), list(inbound)


def get_entity_subgraph(
    db: Session,
    entity_id: uuid.UUID,
    depth: int = 1,
    max_depth: int = 3,
    limit: int = 50,
) -> KnowledgeGraphResponse:
    """Retrieve a depth-bounded relational knowledge subgraph centered on an entity.

    Guarantees:
    - Bounded traversal: depth is clamped to [1, max_depth] where max_depth <= 3.
    - Cycle detection: maintains a visited set to avoid infinite loops on circular graphs.
    - Anti-N+1: batch-queries relationships per frontier level using IN clauses.
    """
    center_ent = db.get(Entity, entity_id)
    if not center_ent:
        return KnowledgeGraphResponse(
            center_node_id=str(entity_id),
            depth=depth,
            nodes=[],
            edges=[],
            total_nodes=0,
            total_edges=0,
        )

    clamped_depth = max(1, min(depth, max_depth))

    visited_entities: Set[uuid.UUID] = {entity_id}
    frontier: Set[uuid.UUID] = {entity_id}

    nodes_dict: Dict[str, GraphNode] = {
        str(entity_id): GraphNode(
            id=str(center_ent.id),
            label=center_ent.canonical_name,
            type="entity",
            entity_type=center_ent.entity_type,
            country_code=center_ent.country_code,
            metadata=center_ent.metadata_,
        )
    }
    edges_dict: Dict[str, GraphEdge] = {}

    current_hop = 0
    while frontier and current_hop < clamped_depth and len(nodes_dict) < limit:
        current_hop += 1
        # Fetch all relationships connected to current frontier
        rels = db.execute(
            select(EntityRelationship)
            .options(
                joinedload(EntityRelationship.source_entity),
                joinedload(EntityRelationship.target_entity),
            )
            .where(
                or_(
                    EntityRelationship.source_entity_id.in_(frontier),
                    EntityRelationship.target_entity_id.in_(frontier),
                )
            )
        ).scalars().all()

        next_frontier: Set[uuid.UUID] = set()

        for r in rels:
            src_id_str = str(r.source_entity_id)
            tgt_id_str = str(r.target_entity_id)
            edge_id = str(r.id)

            if edge_id not in edges_dict:
                edges_dict[edge_id] = GraphEdge(
                    id=edge_id,
                    source=src_id_str,
                    target=tgt_id_str,
                    relationship_type=r.relationship_type,
                    confidence=r.confidence,
                    evidence=r.evidence,
                    metadata=r.metadata_,
                )

            # Add source node if not present
            if src_id_str not in nodes_dict and len(nodes_dict) < limit:
                if r.source_entity:
                    nodes_dict[src_id_str] = GraphNode(
                        id=src_id_str,
                        label=r.source_entity.canonical_name,
                        type="entity",
                        entity_type=r.source_entity.entity_type,
                        country_code=r.source_entity.country_code,
                        metadata=r.source_entity.metadata_,
                    )
            # Add target node if not present
            if tgt_id_str not in nodes_dict and len(nodes_dict) < limit:
                if r.target_entity:
                    nodes_dict[tgt_id_str] = GraphNode(
                        id=tgt_id_str,
                        label=r.target_entity.canonical_name,
                        type="entity",
                        entity_type=r.target_entity.entity_type,
                        country_code=r.target_entity.country_code,
                        metadata=r.target_entity.metadata_,
                    )

            if r.source_entity_id not in visited_entities:
                next_frontier.add(r.source_entity_id)
                visited_entities.add(r.source_entity_id)
            if r.target_entity_id not in visited_entities:
                next_frontier.add(r.target_entity_id)
                visited_entities.add(r.target_entity_id)

        frontier = next_frontier

    return KnowledgeGraphResponse(
        center_node_id=str(entity_id),
        depth=clamped_depth,
        nodes=list(nodes_dict.values()),
        edges=list(edges_dict.values()),
        total_nodes=len(nodes_dict),
        total_edges=len(edges_dict),
    )


def get_event_relationships(
    db: Session,
    event_id: uuid.UUID,
) -> Optional[EventRelationshipsResponse]:
    """Retrieve structured cross-domain connections for an event."""
    event = db.get(ExtractedEvent, event_id)
    if not event:
        return None

    # 1. Location Entity
    loc_entity = None
    if event.location_entity_id:
        loc_ent = db.get(Entity, event.location_entity_id)
        if loc_ent:
            loc_entity = EntityRead.model_validate(loc_ent)

    # 2. Involved Entities (via document_entities on the parent document)
    doc_entities = db.execute(
        select(DocumentEntity)
        .options(joinedload(DocumentEntity.entity))
        .where(DocumentEntity.document_id == event.document_id)
    ).scalars().all()

    involved_entities: List[EntityRead] = []
    seen_entity_ids = set()
    for de in doc_entities:
        if de.entity and de.entity.id not in seen_entity_ids and de.entity.id != event.location_entity_id:
            seen_entity_ids.add(de.entity.id)
            involved_entities.append(EntityRead.model_validate(de.entity))

    # 3. Associated Economic Indicators (via economic_observations)
    econ_obs = db.execute(
        select(EconomicObservation)
        .options(joinedload(EconomicObservation.indicator))
        .where(EconomicObservation.event_id == event_id)
    ).scalars().all()

    indicators_list = []
    for eo in econ_obs:
        if eo.indicator:
            indicators_list.append({
                "indicator_id": str(eo.indicator.id),
                "canonical_name": eo.indicator.canonical_name,
                "indicator_type": eo.indicator.indicator_type,
                "economic_domain": eo.indicator.economic_domain,
                "reported_value": eo.reported_value,
                "reported_unit": eo.reported_unit,
                "direction": eo.direction,
                "economic_relevance": eo.economic_relevance,
            })

    # 4. Associated Market Assets (via event_market_correlations)
    market_corrs = db.execute(
        select(EventMarketCorrelation)
        .options(joinedload(EventMarketCorrelation.market_asset))
        .where(EventMarketCorrelation.event_id == event_id)
    ).scalars().all()

    assets_list = []
    for mc in market_corrs:
        if mc.market_asset:
            assets_list.append({
                "market_asset_id": str(mc.market_asset.id),
                "symbol": mc.market_asset.symbol,
                "canonical_name": mc.market_asset.canonical_name,
                "asset_type": mc.market_asset.asset_type,
                "window_size": mc.window_size,
                "return_percent": mc.return_percent,
                "volume_change": mc.volume_change,
            })

    # 5. Build Graph Edges
    edges: List[GraphEdge] = []
    ev_id_str = str(event.id)

    if loc_entity:
        edges.append(
            GraphEdge(
                id=f"edge_loc_{event.id}",
                source=ev_id_str,
                target=str(loc_entity.id),
                relationship_type="occurs_in",
                confidence=event.confidence,
                evidence=f"Event occurs in {loc_entity.canonical_name}",
            )
        )

    for ent in involved_entities:
        edges.append(
            GraphEdge(
                id=f"edge_inv_{event.id}_{ent.id}",
                source=ev_id_str,
                target=str(ent.id),
                relationship_type="involves",
                confidence=event.confidence,
                evidence=f"Entity involved in event '{event.event_title}'",
            )
        )

    for ind in indicators_list:
        edges.append(
            GraphEdge(
                id=f"edge_ind_{event.id}_{ind['indicator_id']}",
                source=ev_id_str,
                target=ind["indicator_id"],
                relationship_type="associated_with",
                confidence=ind.get("economic_relevance", 0.5),
                evidence=f"Economic indicator associated via reported observation ({ind.get('reported_value')} {ind.get('reported_unit')})",
            )
        )

    for ast in assets_list:
        edges.append(
            GraphEdge(
                id=f"edge_ast_{event.id}_{ast['market_asset_id']}",
                source=ev_id_str,
                target=ast["market_asset_id"],
                relationship_type="associated_with",
                confidence=0.90,
                evidence=f"Retrospective market observation window {ast['window_size']} return: {ast.get('return_percent'):+.2f}%",
            )
        )

    return EventRelationshipsResponse(
        event_id=str(event.id),
        event_title=event.event_title,
        event_type=event.event_type,
        event_time=event.event_time,
        location_entity=loc_entity,
        involved_entities=involved_entities,
        economic_indicators=indicators_list,
        market_assets=assets_list,
        graph_edges=edges,
    )


def get_event_impact_assessment(
    db: Session,
    event_id: uuid.UUID,
) -> Optional[EventImpactAssessmentResponse]:
    """Produce an explainable, retrospective observational impact assessment.

    Strict Invariants:
    1. Separate event importance, economic relevance, market association, and confidence.
    2. Zero causal claims (no 'caused', 'drove', 'triggered', 'predicts').
    3. Mandatory non-causal disclaimer attached.
    """
    event = db.get(ExtractedEvent, event_id)
    if not event:
        return None

    # 1. Economic Context
    econ_obs = db.execute(
        select(EconomicObservation)
        .options(joinedload(EconomicObservation.indicator))
        .where(EconomicObservation.event_id == event_id)
    ).scalars().all()

    economic_items: List[EconomicContextItem] = []
    for eo in econ_obs:
        if eo.indicator:
            economic_items.append(
                EconomicContextItem(
                    indicator_id=str(eo.indicator.id),
                    canonical_name=eo.indicator.canonical_name,
                    indicator_type=eo.indicator.indicator_type,
                    economic_domain=eo.indicator.economic_domain,
                    observation_period=eo.observation_period,
                    reported_value=eo.reported_value,
                    reported_unit=eo.reported_unit,
                    direction=eo.direction,
                    economic_relevance=eo.economic_relevance,
                )
            )

    # 2. Market Context
    corrs = db.execute(
        select(EventMarketCorrelation)
        .options(joinedload(EventMarketCorrelation.market_asset))
        .where(EventMarketCorrelation.event_id == event_id)
        .order_by(EventMarketCorrelation.window_size)
    ).scalars().all()

    market_items: List[MarketContextItem] = []
    for c in corrs:
        if c.market_asset:
            ret_str = f"{c.return_percent:+.2f}%" if c.return_percent is not None else "N/A"
            neutral_obs = (
                f"{c.market_asset.symbol} exhibited a {ret_str} movement "
                f"within the retrospective {c.window_size} event observation window."
            )
            # Run causal claim linter
            if _CAUSAL_LINTER_REGEX.search(neutral_obs):
                raise ValueError("Causal language detected in market observation sentence.")

            market_items.append(
                MarketContextItem(
                    market_asset_id=str(c.market_asset.id),
                    symbol=c.market_asset.symbol,
                    canonical_name=c.market_asset.canonical_name,
                    asset_type=c.market_asset.asset_type,
                    window_size=c.window_size,
                    pre_event_price=c.pre_event_price,
                    post_event_price=c.post_event_price,
                    return_percent=c.return_percent,
                    volume_change=c.volume_change,
                    neutral_observation=neutral_obs,
                )
            )

    # 3. Overall explanation (Strictly neutral observational phrasing)
    econ_summary_parts = []
    for ei in economic_items:
        val_str = f"{ei.reported_value} {ei.reported_unit or ''}".strip()
        econ_summary_parts.append(f"{ei.canonical_name} ({val_str}, relevance {ei.economic_relevance:.2f})")
    econ_summary = "; ".join(econ_summary_parts) if econ_summary_parts else "No direct economic indicator observations recorded"

    market_summary_parts = []
    for mi in market_items:
        ret_val = f"{mi.return_percent:+.2f}%" if mi.return_percent is not None else "N/A"
        market_summary_parts.append(f"{mi.symbol} ({ret_val} over {mi.window_size})")
    market_summary = "; ".join(market_summary_parts) if market_summary_parts else "No correlated market asset movements recorded"

    explanation = (
        f"Event '{event.event_title}' (importance: {event.importance:.2f}, confidence: {event.confidence:.2f}) "
        f"is associated with economic observations: [{econ_summary}] "
        f"and retrospective market movements: [{market_summary}]."
    )

    # Verify explanation contains zero causal terms
    if _CAUSAL_LINTER_REGEX.search(explanation):
        raise ValueError("Causal language detected in impact assessment explanation.")

    return EventImpactAssessmentResponse(
        event_id=str(event.id),
        event_title=event.event_title,
        event_type=event.event_type,
        event_time=event.event_time,
        event_importance=event.importance,
        confidence=event.confidence,
        economic_context=economic_items,
        market_context=market_items,
        explanation=explanation,
        disclaimer=STANDARD_IMPACT_DISCLAIMER,
    )


def search_graph(
    db: Session,
    query: str,
    depth: int = 1,
    limit: int = 20,
) -> KnowledgeGraphResponse:
    """Search knowledge graph across entity canonical and normalized names."""
    matching_entities = db.execute(
        select(Entity)
        .where(
            or_(
                Entity.canonical_name.ilike(f"%{query}%"),
                Entity.normalized_name.ilike(f"%{query}%"),
            )
        )
        .limit(limit)
    ).scalars().all()

    if not matching_entities:
        return KnowledgeGraphResponse(
            depth=depth,
            nodes=[],
            edges=[],
            total_nodes=0,
            total_edges=0,
        )

    # Combine subgraphs for matching entities
    nodes_dict: Dict[str, GraphNode] = {}
    edges_dict: Dict[str, GraphEdge] = {}

    for ent in matching_entities:
        subgraph = get_entity_subgraph(db, ent.id, depth=depth, limit=limit)
        for node in subgraph.nodes:
            if node.id not in nodes_dict and len(nodes_dict) < limit:
                nodes_dict[node.id] = node
        for edge in subgraph.edges:
            if edge.id not in edges_dict:
                edges_dict[edge.id] = edge

    return KnowledgeGraphResponse(
        depth=depth,
        nodes=list(nodes_dict.values()),
        edges=list(edges_dict.values()),
        total_nodes=len(nodes_dict),
        total_edges=len(edges_dict),
    )
