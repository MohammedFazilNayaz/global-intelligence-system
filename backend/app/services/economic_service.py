"""
Economic Intelligence Service for V0.5.
Provides transactional indicator/observation persistence, server-side pagination,
filtering, domain grouping, country economic profiles, and bounded search.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.app.models.indicator import EconomicIndicator
from backend.app.models.observation import EconomicObservation
from backend.app.models.entity import Entity
from backend.app.models.document import Document
from backend.app.models.source import Source
from backend.app.models.event import ExtractedEvent
from backend.app.schemas.economic import (
    EconomicDomain,
    IndicatorType,
    INDICATOR_DOMAIN_MAP,
    ExtractedEconomicObservation,
    EconomicIndicatorRead,
    EconomicObservationRead,
    EconomicObservationDetailRead,
    CountryEconomicProfileResponse,
    IndicatorLatestObservation,
    EconomicSummaryResponse,
)
from backend.app.utils.time import utc_now


def get_or_create_economic_indicator(
    db: Session,
    indicator_type: str,
    country_entity_id: Optional[UUID],
    canonical_name: str,
    economic_domain: Optional[str] = None,
    default_unit: Optional[str] = None,
    description: Optional[str] = None,
    metadata_: Optional[Dict[str, Any]] = None,
) -> EconomicIndicator:
    """Find existing canonical economic indicator or create a new one."""
    normalized_name = canonical_name.strip().lower()

    # Try matching on indicator_type + country_entity_id
    query = select(EconomicIndicator).where(
        EconomicIndicator.indicator_type == indicator_type,
        EconomicIndicator.country_entity_id == country_entity_id,
    )
    existing = db.scalars(query).first()
    if existing:
        return existing

    # Fallback match on normalized_name
    query_name = select(EconomicIndicator).where(
        EconomicIndicator.normalized_name == normalized_name
    )
    existing_by_name = db.scalars(query_name).first()
    if existing_by_name:
        return existing_by_name

    # Determine domain if not provided
    if not economic_domain:
        try:
            domain_enum = INDICATOR_DOMAIN_MAP.get(IndicatorType(indicator_type), EconomicDomain.GROWTH)
            economic_domain = domain_enum.value
        except ValueError:
            economic_domain = EconomicDomain.GROWTH.value

    new_indicator = EconomicIndicator(
        id=uuid.uuid4(),
        canonical_name=canonical_name,
        normalized_name=normalized_name,
        indicator_type=indicator_type,
        economic_domain=economic_domain,
        country_entity_id=country_entity_id,
        default_unit=default_unit,
        description=description,
        metadata_=metadata_ or {},
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(new_indicator)
    db.flush()
    return new_indicator


def get_economic_indicators(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    domain: Optional[str] = None,
    country_id: Optional[UUID] = None,
    indicator_type: Optional[str] = None,
    search: Optional[str] = None,
) -> Tuple[List[EconomicIndicator], int]:
    """Retrieve paginated economic indicators with server-side filters."""
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    offset = (page - 1) * page_size

    conditions = []
    if domain:
        conditions.append(EconomicIndicator.economic_domain == domain)
    if country_id:
        conditions.append(EconomicIndicator.country_entity_id == country_id)
    if indicator_type:
        conditions.append(EconomicIndicator.indicator_type == indicator_type)
    if search:
        search_pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                EconomicIndicator.canonical_name.ilike(search_pattern),
                EconomicIndicator.normalized_name.ilike(search_pattern),
                EconomicIndicator.indicator_type.ilike(search_pattern),
            )
        )

    # Count query
    count_query = select(func.count(EconomicIndicator.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total = db.scalar(count_query) or 0

    # Data query with eager loading
    stmt = (
        select(EconomicIndicator)
        .options(joinedload(EconomicIndicator.country_entity))
        .order_by(EconomicIndicator.canonical_name.asc())
        .limit(page_size)
        .offset(offset)
    )
    if conditions:
        stmt = stmt.where(and_(*conditions))

    items = list(db.scalars(stmt).unique().all())
    return items, total


def get_economic_indicator_by_id(
    db: Session,
    indicator_id: UUID,
) -> Optional[EconomicIndicator]:
    """Retrieve single economic indicator by ID."""
    stmt = (
        select(EconomicIndicator)
        .options(joinedload(EconomicIndicator.country_entity))
        .where(EconomicIndicator.id == indicator_id)
    )
    return db.scalars(stmt).first()


def get_economic_observations(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    indicator_id: Optional[UUID] = None,
    domain: Optional[str] = None,
    country_id: Optional[UUID] = None,
    direction: Optional[str] = None,
    min_relevance: Optional[float] = None,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
) -> Tuple[List[EconomicObservation], int]:
    """Retrieve paginated economic observations with server-side filters."""
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    offset = (page - 1) * page_size

    conditions = []
    if indicator_id:
        conditions.append(EconomicObservation.indicator_id == indicator_id)
    if direction:
        conditions.append(EconomicObservation.direction == direction)
    if min_relevance is not None:
        conditions.append(EconomicObservation.economic_relevance >= min_relevance)
    if from_time:
        conditions.append(
            or_(
                EconomicObservation.observation_date >= from_time,
                and_(
                    EconomicObservation.observation_date.is_(None),
                    EconomicObservation.created_at >= from_time,
                ),
            )
        )
    if to_time:
        conditions.append(
            or_(
                EconomicObservation.observation_date <= to_time,
                and_(
                    EconomicObservation.observation_date.is_(None),
                    EconomicObservation.created_at <= to_time,
                ),
            )
        )

    # Join Indicator for domain or country filtering
    needs_indicator_join = bool(domain or country_id)

    # Count query
    count_query = select(func.count(EconomicObservation.id))
    if needs_indicator_join:
        count_query = count_query.join(EconomicIndicator, EconomicIndicator.id == EconomicObservation.indicator_id)
        if domain:
            conditions.append(EconomicIndicator.economic_domain == domain)
        if country_id:
            conditions.append(EconomicIndicator.country_entity_id == country_id)

    if conditions:
        count_query = count_query.where(and_(*conditions))
    total = db.scalar(count_query) or 0

    # Data query with eager loading of indicator and country
    stmt = (
        select(EconomicObservation)
        .options(
            joinedload(EconomicObservation.indicator).joinedload(EconomicIndicator.country_entity),
            joinedload(EconomicObservation.document),
            joinedload(EconomicObservation.extracted_event),
        )
        .order_by(
            EconomicObservation.observation_date.desc().nulls_last(),
            EconomicObservation.created_at.desc(),
        )
        .limit(page_size)
        .offset(offset)
    )
    if needs_indicator_join:
        stmt = stmt.join(EconomicIndicator, EconomicIndicator.id == EconomicObservation.indicator_id)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    items = list(db.scalars(stmt).unique().all())
    return items, total


def get_economic_observation_by_id(
    db: Session,
    observation_id: UUID,
) -> Optional[EconomicObservation]:
    """Retrieve detailed economic observation by ID with full provenance."""
    stmt = (
        select(EconomicObservation)
        .options(
            joinedload(EconomicObservation.indicator).joinedload(EconomicIndicator.country_entity),
            joinedload(EconomicObservation.document).joinedload(Document.source),
            joinedload(EconomicObservation.extracted_event),
        )
        .where(EconomicObservation.id == observation_id)
    )
    return db.scalars(stmt).first()


def get_country_economic_profile(
    db: Session,
    country_entity_id: UUID,
) -> Optional[CountryEconomicProfileResponse]:
    """Generate structured economic intelligence profile for a country or jurisdiction entity."""
    country_entity = db.get(Entity, country_entity_id)
    if not country_entity:
        return None

    # Fetch all indicators linked to this country entity
    indicators_stmt = (
        select(EconomicIndicator)
        .options(joinedload(EconomicIndicator.country_entity))
        .where(EconomicIndicator.country_entity_id == country_entity_id)
        .order_by(EconomicIndicator.canonical_name.asc())
    )
    indicators = list(db.scalars(indicators_stmt).unique().all())

    domains_map: Dict[str, List[IndicatorLatestObservation]] = {}
    total_obs_count = 0

    for ind in indicators:
        # Get latest observation for this indicator
        latest_obs = db.scalars(
            select(EconomicObservation)
            .options(joinedload(EconomicObservation.indicator))
            .where(EconomicObservation.indicator_id == ind.id)
            .order_by(
                EconomicObservation.observation_date.desc().nulls_last(),
                EconomicObservation.created_at.desc(),
            )
            .limit(1)
        ).first()

        ind_read = EconomicIndicatorRead.model_validate(ind)
        obs_read = EconomicObservationRead.model_validate(latest_obs) if latest_obs else None

        domain_key = ind.economic_domain
        if domain_key not in domains_map:
            domains_map[domain_key] = []
        domains_map[domain_key].append(
            IndicatorLatestObservation(indicator=ind_read, latest_observation=obs_read)
        )

    # Fetch recent observations for this country
    recent_obs_stmt = (
        select(EconomicObservation)
        .join(EconomicIndicator, EconomicIndicator.id == EconomicObservation.indicator_id)
        .options(joinedload(EconomicObservation.indicator).joinedload(EconomicIndicator.country_entity))
        .where(EconomicIndicator.country_entity_id == country_entity_id)
        .order_by(
            EconomicObservation.observation_date.desc().nulls_last(),
            EconomicObservation.created_at.desc(),
        )
        .limit(15)
    )
    recent_obs = list(db.scalars(recent_obs_stmt).unique().all())
    total_obs_count = db.scalar(
        select(func.count(EconomicObservation.id))
        .join(EconomicIndicator, EconomicIndicator.id == EconomicObservation.indicator_id)
        .where(EconomicIndicator.country_entity_id == country_entity_id)
    ) or 0

    # Extract central bank decisions from metadata or observations
    recent_cb_decisions: List[Dict[str, Any]] = []
    for obs in recent_obs:
        cb_info = (obs.metadata_ or {}).get("central_bank_decision")
        if cb_info:
            recent_cb_decisions.append({
                "observation_id": str(obs.id),
                "indicator_name": obs.indicator.canonical_name if obs.indicator else "Central Bank Rate",
                "period": obs.observation_period,
                "target_rate": cb_info.get("target_rate"),
                "previous_rate": cb_info.get("previous_rate"),
                "rate_change_bps": cb_info.get("rate_change_bps"),
                "decision_type": cb_info.get("decision_type"),
                "direction": obs.direction,
                "date": obs.observation_date.isoformat() if obs.observation_date else obs.created_at.isoformat(),
            })

    return CountryEconomicProfileResponse(
        country_entity=country_entity,
        domains=domains_map,
        recent_central_bank_decisions=recent_cb_decisions[:10],
        recent_observations=[EconomicObservationRead.model_validate(o) for o in recent_obs],
        indicators_count=len(indicators),
        observations_count=total_obs_count,
    )


def search_economic_intelligence(
    db: Session,
    query: str,
    limit: int = 10,
) -> Dict[str, Any]:
    """Search indicators and observations boundedly."""
    pattern = f"%{query.strip()}%"
    limit = min(50, max(1, limit))

    # Match indicators
    ind_stmt = (
        select(EconomicIndicator)
        .options(joinedload(EconomicIndicator.country_entity))
        .where(
            or_(
                EconomicIndicator.canonical_name.ilike(pattern),
                EconomicIndicator.normalized_name.ilike(pattern),
                EconomicIndicator.indicator_type.ilike(pattern),
                EconomicIndicator.economic_domain.ilike(pattern),
            )
        )
        .limit(limit)
    )
    indicators = list(db.scalars(ind_stmt).unique().all())

    # Match observations by period or indicator name
    obs_stmt = (
        select(EconomicObservation)
        .join(EconomicIndicator, EconomicIndicator.id == EconomicObservation.indicator_id)
        .options(joinedload(EconomicObservation.indicator).joinedload(EconomicIndicator.country_entity))
        .where(
            or_(
                EconomicObservation.observation_period.ilike(pattern),
                EconomicObservation.direction.ilike(pattern),
                EconomicIndicator.canonical_name.ilike(pattern),
                EconomicIndicator.economic_domain.ilike(pattern),
            )
        )
        .order_by(EconomicObservation.economic_relevance.desc())
        .limit(limit)
    )
    observations = list(db.scalars(obs_stmt).unique().all())

    return {
        "indicators": [EconomicIndicatorRead.model_validate(i) for i in indicators],
        "observations": [EconomicObservationRead.model_validate(o) for o in observations],
        "total_indicators": len(indicators),
        "total_observations": len(observations),
    }


def get_economic_dashboard_summary(db: Session) -> EconomicSummaryResponse:
    """Generate high-level economic intelligence summary metrics."""
    total_ind = db.scalar(select(func.count(EconomicIndicator.id))) or 0
    total_obs = db.scalar(select(func.count(EconomicObservation.id))) or 0

    # Domain breakdown
    domain_rows = db.execute(
        select(EconomicIndicator.economic_domain, func.count(EconomicObservation.id))
        .join(EconomicObservation, EconomicObservation.indicator_id == EconomicIndicator.id)
        .group_by(EconomicIndicator.economic_domain)
    ).all()
    domains_breakdown = {row[0]: row[1] for row in domain_rows}

    # Central bank decisions count
    cb_count = db.scalar(
        select(func.count(EconomicObservation.id)).where(
            EconomicObservation.direction.in_(["hike", "cut", "hold"])
        )
    ) or 0

    # High relevance observations (>= 0.8)
    high_rel_count = db.scalar(
        select(func.count(EconomicObservation.id)).where(
            EconomicObservation.economic_relevance >= 0.8
        )
    ) or 0

    # Top recent key releases
    key_releases = list(
        db.scalars(
            select(EconomicObservation)
            .options(joinedload(EconomicObservation.indicator).joinedload(EconomicIndicator.country_entity))
            .order_by(
                EconomicObservation.economic_relevance.desc(),
                EconomicObservation.created_at.desc(),
            )
            .limit(6)
        ).unique().all()
    )

    return EconomicSummaryResponse(
        total_indicators_count=total_ind,
        total_observations_count=total_obs,
        domains_breakdown=domains_breakdown,
        central_bank_decisions_count=cb_count,
        high_relevance_observations_count=high_rel_count,
        recent_key_releases=[EconomicObservationRead.model_validate(r) for r in key_releases],
    )
