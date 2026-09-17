import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.app.models.event import ExtractedEvent
from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.document import Document
from backend.app.models.source import Source
from backend.app.models.relationship import EntityRelationship
from backend.app.models.observation import EconomicObservation
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.models.market_asset import MarketAsset
from backend.app.models.indicator import EconomicIndicator
from backend.app.schemas.dossier import (
    EvidenceClass,
    EventIntelligenceDossierResponse,
    DossierEntityRef,
    DossierImpactEntity,
    DossierCountryImpact,
    DossierCompanyImpact,
    DossierSectorImpact,
    DossierMarketConnection,
    DossierEconomicIndicator,
    DossierGeopoliticalConnection,
    DossierRelatedEvent,
    DossierMarketObservation,
    DossierSourceEvidence,
)
from backend.app.utils.time import utc_now


SECTOR_MAPPINGS: Dict[str, Dict[str, str]] = {
    "ENERGY": {
        "sector": "Energy & Natural Resources",
        "exposure": "Supply chain disruption and fuel cost volatility",
    },
    "OIL": {
        "sector": "Energy & Natural Resources",
        "exposure": "Petroleum feedstock volatility and transport cost impact",
    },
    "GAS": {
        "sector": "Utilities & Power Infrastructure",
        "exposure": "Thermal power margin compression and regional shortages",
    },
    "DEFENSE": {
        "sector": "Aerospace & Defense",
        "exposure": "Procurement cycle acceleration and sovereign defense realignment",
    },
    "MILITARY": {
        "sector": "Aerospace & Defense",
        "exposure": "Security risk premium and border trade restriction",
    },
    "CONFLICT": {
        "sector": "Insurance & Maritime Logistics",
        "exposure": "War risk insurance surcharges and rerouting friction",
    },
    "SANCTIONS": {
        "sector": "International Banking & Trade Finance",
        "exposure": "Secondary sanctions compliance and settlement friction",
    },
    "INFLATION": {
        "sector": "Consumer Discretionary & Retail",
        "exposure": "Purchasing power degradation and input cost pass-through",
    },
    "INTEREST_RATE": {
        "sector": "Commercial Banking & Real Estate",
        "exposure": "Debt refinancing cost expansion and valuation headwinds",
    },
    "TECH": {
        "sector": "Technology & Semiconductors",
        "exposure": "Export controls, technology transfer limits, and hardware lead times",
    },
    "CHIP": {
        "sector": "Semiconductors & Electronics",
        "exposure": "Advanced fabrication input bottlenecks and licensing friction",
    },
    "SHIPPING": {
        "sector": "Maritime Logistics & Freight",
        "exposure": "Chokepoint transit delays and container repositioning costs",
    },
    "MARITIME": {
        "sector": "Maritime Logistics & Freight",
        "exposure": "Route deviation fuel overhead and insurance adjustments",
    },
    "CRISIS": {
        "sector": "Sovereign Debt & Risk Management",
        "exposure": "Capital flight pressure and sovereign credit spread widening",
    },
    "CLIMATE": {
        "sector": "Agriculture & Catastrophe Reinsurance",
        "exposure": "Harvest yield impairment and disaster recovery capital outlays",
    },
    "TRADE": {
        "sector": "Multinational Manufacturing & Distribution",
        "exposure": "Tariff burden shifting and tariff origin verification costs",
    },
}


def build_event_intelligence_dossier(
    db: Session,
    event_id: uuid.UUID,
) -> Optional[EventIntelligenceDossierResponse]:
    """Synthesize a complete, non-hallucinatory, provenance-backed 21-field event intelligence dossier."""
    # 1. Fetch event with primary relations
    stmt = (
        select(ExtractedEvent)
        .options(
            joinedload(ExtractedEvent.document).joinedload(Document.source),
            joinedload(ExtractedEvent.location_entity),
            joinedload(ExtractedEvent.cluster_membership).joinedload(EventClusterMember.cluster),
        )
        .where(ExtractedEvent.id == event_id)
    )
    event = db.execute(stmt).scalar_one_or_none()
    if not event:
        return None

    doc = event.document
    src = doc.source if doc else None
    cluster = event.cluster_membership.cluster if (event.cluster_membership and event.cluster_membership.cluster) else None

    now = utc_now()

    # 1. WHAT_HAPPENED
    what_happened = {
        "event_id": str(event.id),
        "title": event.event_title,
        "summary": event.event_summary or (doc.description if doc else None),
        "event_type": event.event_type,
        "event_time": event.event_time.isoformat() if event.event_time else None,
        "location": event.location_entity.canonical_name if event.location_entity else None,
        "country_code": event.location_entity.country_code if event.location_entity else None,
    }

    # 2. WHY_IT_MATTERS
    importance_grade = "CRITICAL" if event.importance >= 0.8 else "HIGH" if event.importance >= 0.6 else "MODERATE"
    cluster_title = cluster.canonical_title if cluster else None
    why_it_matters = {
        "importance_score": round(event.importance, 3),
        "importance_grade": importance_grade,
        "significance_summary": (
            f"Event assessed with {importance_grade} operational importance ({round(event.importance, 2)}). "
            + (f"Part of ongoing intelligence cluster '{cluster_title}'. " if cluster_title else "")
            + f"Classified under '{event.event_type}' domain."
        ),
        "cluster_id": str(cluster.id) if cluster else None,
        "cluster_title": cluster_title,
        "cluster_status": cluster.status if cluster else None,
    }

    # Query document entities
    doc_entities = []
    if doc:
        doc_entities_stmt = (
            select(DocumentEntity)
            .options(joinedload(DocumentEntity.entity))
            .where(DocumentEntity.document_id == doc.id)
        )
        doc_entities = db.execute(doc_entities_stmt).scalars().all()

    # 3. DIRECTLY_INVOLVED & 4. DIRECTLY_AFFECTED & 17. RELATED_ENTITIES
    directly_involved: List[DossierEntityRef] = []
    directly_affected: List[DossierEntityRef] = []
    related_entities: List[DossierEntityRef] = []
    affected_countries_map: Dict[str, DossierCountryImpact] = {}
    affected_companies: List[DossierCompanyImpact] = []

    # If location entity exists, register it
    if event.location_entity and event.location_entity.country_code:
        affected_countries_map[event.location_entity.country_code] = DossierCountryImpact(
            country_code=event.location_entity.country_code,
            country_name=event.location_entity.canonical_name,
            relationship_type="PRIMARY_EVENT_LOCATION",
            evidence_class=EvidenceClass.DIRECT,
        )

    entity_ids_seen = set()
    for de in doc_entities:
        ent = de.entity
        if not ent:
            continue

        ref = DossierEntityRef(
            entity_id=ent.id,
            name=ent.canonical_name,
            entity_type=ent.entity_type,
            role=de.entity_role,
            evidence_class=EvidenceClass.DIRECT,
            evidence_snippet=de.mention_text,
        )

        role_lower = (de.entity_role or "").lower()
        if any(r in role_lower for r in ["subject", "agent", "actor", "initiator", "primary", "author"]):
            directly_involved.append(ref)
        elif any(r in role_lower for r in ["object", "target", "affected", "victim", "sanctioned"]):
            directly_affected.append(ref)
        else:
            related_entities.append(ref)

        entity_ids_seen.add(ent.id)

        # Country collection
        if ent.country_code and ent.country_code not in affected_countries_map:
            affected_countries_map[ent.country_code] = DossierCountryImpact(
                country_code=ent.country_code,
                country_name=ent.canonical_name if ent.entity_type in ("COUNTRY", "LOCATION") else ent.country_code,
                relationship_type="ENTITY_JURISDICTION",
                evidence_class=EvidenceClass.DIRECT,
            )

        # Company collection
        if ent.entity_type in ("ORGANIZATION", "COMPANY", "FINANCIAL_INSTITUTION"):
            affected_companies.append(
                DossierCompanyImpact(
                    entity_id=ent.id,
                    name=ent.canonical_name,
                    sector=ent.metadata_.get("sector") if ent.metadata_ else None,
                    exposure_type=f"Identified as {de.entity_role} in primary event reporting",
                    evidence_class=EvidenceClass.DIRECT,
                )
            )

    # 15. GEOPOLITICAL_CONNECTIONS & Graph-backed relationships
    geopolitical_connections: List[DossierGeopoliticalConnection] = []
    potential_beneficiaries: List[DossierImpactEntity] = []
    potential_exposures: List[DossierImpactEntity] = []

    if entity_ids_seen:
        rel_stmt = (
            select(EntityRelationship)
            .options(
                joinedload(EntityRelationship.source_entity),
                joinedload(EntityRelationship.target_entity),
            )
            .where(
                or_(
                    EntityRelationship.source_entity_id.in_(entity_ids_seen),
                    EntityRelationship.target_entity_id.in_(entity_ids_seen),
                    EntityRelationship.source_event_id == event.id,
                )
            )
            .limit(50)
        )
        relationships = db.execute(rel_stmt).scalars().all()

        for rel in relationships:
            src_name = rel.source_entity.canonical_name if rel.source_entity else "Unknown"
            tgt_name = rel.target_entity.canonical_name if rel.target_entity else "Unknown"

            evidence_cls = EvidenceClass.DIRECT if rel.source_event_id == event.id else EvidenceClass.HISTORICAL_ASSOCIATION

            geopolitical_connections.append(
                DossierGeopoliticalConnection(
                    source_entity=src_name,
                    target_entity=tgt_name,
                    relationship_type=rel.relationship_type,
                    evidence_class=evidence_cls,
                    description=rel.evidence if rel.evidence else f"{src_name} {rel.relationship_type} {tgt_name}",
                )
            )

            # Deterministic, neutral beneficiary & exposure assessments
            rel_type = rel.relationship_type.lower()
            if rel_type in ("sanctions", "attacks", "opposes"):
                # Neutral wording
                potential_exposures.append(
                    DossierImpactEntity(
                        entity_id=rel.target_entity_id,
                        name=tgt_name,
                        entity_type=rel.target_entity.entity_type if rel.target_entity else "ENTITY",
                        rationale=f"Potential exposure: Target of {rel.relationship_type} action by {src_name}",
                        evidence_class=EvidenceClass.ANALYTICAL_IMPLICATION,
                        confidence=round(rel.confidence * 0.9, 2),
                    )
                )
                potential_exposures.append(
                    DossierImpactEntity(
                        entity_id=rel.source_entity_id,
                        name=src_name,
                        entity_type=rel.source_entity.entity_type if rel.source_entity else "ENTITY",
                        rationale=f"Potential exposure: Operational friction or counter-measures resulting from {rel.relationship_type}",
                        evidence_class=EvidenceClass.ANALYTICAL_IMPLICATION,
                        confidence=round(rel.confidence * 0.85, 2),
                    )
                )
            elif rel_type in ("supplies", "trades_with"):
                potential_beneficiaries.append(
                    DossierImpactEntity(
                        entity_id=rel.source_entity_id,
                        name=src_name,
                        entity_type=rel.source_entity.entity_type if rel.source_entity else "ENTITY",
                        rationale=f"Potential beneficiary: Commercial trade/supply integration with {tgt_name}",
                        evidence_class=EvidenceClass.ANALYTICAL_IMPLICATION,
                        confidence=round(rel.confidence * 0.8, 2),
                    )
                )
            elif rel_type in ("allied_with", "supports", "signed_agreement_with"):
                potential_beneficiaries.append(
                    DossierImpactEntity(
                        entity_id=rel.target_entity_id,
                        name=tgt_name,
                        entity_type=rel.target_entity.entity_type if rel.target_entity else "ENTITY",
                        rationale=f"Potential beneficiary: Bilateral coordination with {src_name}",
                        evidence_class=EvidenceClass.ANALYTICAL_IMPLICATION,
                        confidence=round(rel.confidence * 0.8, 2),
                    )
                )

    # 9. AFFECTED_SECTORS
    affected_sectors: List[DossierSectorImpact] = []
    text_to_scan = f"{event.event_title} {event.event_type} {event.event_summary or ''}".upper()
    sectors_matched = set()
    for keyword, mapping in SECTOR_MAPPINGS.items():
        if keyword in text_to_scan and mapping["sector"] not in sectors_matched:
            sectors_matched.add(mapping["sector"])
            affected_sectors.append(
                DossierSectorImpact(
                    sector_name=mapping["sector"],
                    impact_direction="POTENTIAL_DOWNSTREAM_EFFECT",
                    evidence_class=EvidenceClass.ANALYTICAL_IMPLICATION,
                    rationale=f"Potential downstream effect: {mapping['exposure']}",
                )
            )

    # 10. COMMODITY, 11. CURRENCY, 12. EQUITY, 13. RATE, 18. MARKET_OBSERVATIONS
    commodity_connections: List[DossierMarketConnection] = []
    currency_connections: List[DossierMarketConnection] = []
    equity_connections: List[DossierMarketConnection] = []
    rate_connections: List[DossierMarketConnection] = []
    market_observations: List[DossierMarketObservation] = []

    corr_stmt = (
        select(EventMarketCorrelation)
        .options(joinedload(EventMarketCorrelation.market_asset))
        .where(
            or_(
                EventMarketCorrelation.event_id == event.id,
                and_(
                    EventMarketCorrelation.cluster_id == cluster.id if cluster else False,
                )
            )
        )
    )
    correlations = db.execute(corr_stmt).scalars().all()

    for corr in correlations:
        asset = corr.market_asset
        if not asset:
            continue

        asset_type_upper = (asset.asset_type or "COMMODITY").upper()
        conn = DossierMarketConnection(
            asset_symbol=asset.symbol,
            asset_name=asset.canonical_name,
            asset_type=asset_type_upper,
            connection_type="TEMPORAL_CO_MOVEMENT",
            observation_window=corr.window_size,
            return_percent=round(corr.return_percent, 2) if corr.return_percent is not None else None,
            evidence_class=EvidenceClass.OBSERVED,
            methodology=corr.methodology or "window_close_return",
        )

        if "COMMODITY" in asset_type_upper or "OIL" in asset.symbol or "GAS" in asset.symbol or "GOLD" in asset.symbol:
            commodity_connections.append(conn)
        elif "CURRENCY" in asset_type_upper or "FX" in asset_type_upper or "/" in asset.symbol or "USD" in asset.symbol:
            currency_connections.append(conn)
        elif "EQUITY" in asset_type_upper or "INDEX" in asset_type_upper or "SPX" in asset.symbol or "NDX" in asset.symbol:
            equity_connections.append(conn)
        elif "RATE" in asset_type_upper or "YIELD" in asset_type_upper or "BOND" in asset_type_upper:
            rate_connections.append(conn)
        else:
            commodity_connections.append(conn)

        if corr.event_price is not None or corr.post_event_price is not None:
            market_observations.append(
                DossierMarketObservation(
                    asset_symbol=asset.symbol,
                    price=corr.post_event_price or corr.event_price,
                    change_percent=round(corr.return_percent, 2) if corr.return_percent is not None else None,
                    timestamp=corr.window_end,
                    evidence_class=EvidenceClass.OBSERVED,
                )
            )

    # 14. ECONOMIC_INDICATORS
    economic_indicators: List[DossierEconomicIndicator] = []
    obs_stmt = (
        select(EconomicObservation)
        .options(
            joinedload(EconomicObservation.indicator).joinedload(EconomicIndicator.country_entity)
        )
        .where(
            or_(
                EconomicObservation.event_id == event.id,
                EconomicObservation.document_id == doc.id if doc else False,
            )
        )
        .limit(20)
    )
    economic_obs = db.execute(obs_stmt).scalars().all()

    # If no direct obs, check for indicators matching affected countries
    if not economic_obs and affected_countries_map:
        country_codes = [c for c in affected_countries_map.keys() if c]
        if country_codes:
            fallback_obs_stmt = (
                select(EconomicObservation)
                .join(EconomicObservation.indicator)
                .join(EconomicIndicator.country_entity)
                .options(
                    joinedload(EconomicObservation.indicator).joinedload(EconomicIndicator.country_entity)
                )
                .where(Entity.country_code.in_(country_codes))
                .order_by(desc(EconomicObservation.created_at))
                .limit(5)
            )
            economic_obs = db.execute(fallback_obs_stmt).scalars().all()

    for obs in economic_obs:
        ind = obs.indicator
        if not ind:
            continue
        country_cd = ind.country_entity.country_code if ind.country_entity else None
        economic_indicators.append(
            DossierEconomicIndicator(
                indicator_code=ind.symbol or ind.canonical_name,
                indicator_name=ind.canonical_name,
                country_code=country_cd,
                reported_value=obs.reported_value,
                reported_unit=obs.reported_unit or ind.default_unit,
                change_percent=obs.change_percent,
                direction=obs.direction,
                evidence_class=EvidenceClass.OBSERVED,
            )
        )

    # 16. RELATED_EVENTS
    related_events: List[DossierRelatedEvent] = []
    if cluster:
        related_stmt = (
            select(ExtractedEvent)
            .join(EventClusterMember)
            .where(
                and_(
                    EventClusterMember.event_cluster_id == cluster.id,
                    ExtractedEvent.id != event.id,
                )
            )
            .order_by(desc(ExtractedEvent.event_time))
            .limit(10)
        )
        sibling_events = db.execute(related_stmt).scalars().all()
        for sib in sibling_events:
            related_events.append(
                DossierRelatedEvent(
                    event_id=sib.id,
                    title=sib.event_title,
                    event_type=sib.event_type,
                    event_time=sib.event_time,
                    relationship_reason=f"Co-clustered within narrative cluster '{cluster.canonical_title}'",
                    evidence_class=EvidenceClass.DIRECT,
                )
            )

    # 19. SOURCE_EVIDENCE
    source_evidence: List[DossierSourceEvidence] = []
    if doc:
        source_evidence.append(
            DossierSourceEvidence(
                source_id=src.id if src else None,
                source_name=src.name if src else "Original Reporting Source",
                source_domain=src.config_metadata.get("domain") if src and src.config_metadata else None,
                url=doc.url,
                published_at=doc.published_at,
                fetched_at=doc.ingested_at,
                content_hash=doc.content_hash,
                snippet=(doc.description or doc.title)[:400] if doc else None,
                evidence_class=EvidenceClass.OBSERVED,
            )
        )

    return EventIntelligenceDossierResponse(
        what_happened=what_happened,
        why_it_matters=why_it_matters,
        directly_involved=directly_involved,
        directly_affected=directly_affected,
        potential_beneficiaries=potential_beneficiaries,
        potential_exposures=potential_exposures,
        affected_countries=list(affected_countries_map.values()),
        affected_companies=affected_companies,
        affected_sectors=affected_sectors,
        commodity_connections=commodity_connections,
        currency_connections=currency_connections,
        equity_connections=equity_connections,
        rate_connections=rate_connections,
        economic_indicators=economic_indicators,
        geopolitical_connections=geopolitical_connections,
        related_events=related_events,
        related_entities=related_entities,
        market_observations=market_observations,
        source_evidence=source_evidence,
        confidence=round(event.confidence, 3),
        last_updated=event.updated_at or now,
        publication_time=doc.published_at if doc else None,
        fetch_time=doc.ingested_at if doc else None,
        ingestion_time=doc.ingested_at if doc else None,
        extraction_time=event.created_at,
        intelligence_update_time=event.updated_at or now,
    )
