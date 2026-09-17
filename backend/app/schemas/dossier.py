import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class EvidenceClass(str, Enum):
    """Rigorous classification of intelligence relationships."""
    OBSERVED = "OBSERVED"
    DIRECT = "DIRECT"
    HISTORICAL_ASSOCIATION = "HISTORICAL_ASSOCIATION"
    ANALYTICAL_IMPLICATION = "ANALYTICAL_IMPLICATION"
    UNKNOWN = "UNKNOWN"


class DossierEntityRef(BaseModel):
    """Reference to an intelligence entity with evidence classification."""
    entity_id: Optional[uuid.UUID] = None
    name: str
    entity_type: str
    role: Optional[str] = None
    evidence_class: EvidenceClass = EvidenceClass.DIRECT
    evidence_snippet: Optional[str] = None


class DossierImpactEntity(BaseModel):
    """Entity with potential beneficiary or exposure assessment (neutral phrasing)."""
    entity_id: Optional[uuid.UUID] = None
    name: str
    entity_type: str
    rationale: str
    evidence_class: EvidenceClass = EvidenceClass.ANALYTICAL_IMPLICATION
    confidence: float = 0.5


class DossierCountryImpact(BaseModel):
    """Country connection with relationship and evidence class."""
    country_code: str
    country_name: str
    relationship_type: str
    evidence_class: EvidenceClass = EvidenceClass.DIRECT


class DossierCompanyImpact(BaseModel):
    """Company affected or involved."""
    entity_id: Optional[uuid.UUID] = None
    name: str
    sector: Optional[str] = None
    exposure_type: str
    evidence_class: EvidenceClass = EvidenceClass.ANALYTICAL_IMPLICATION


class DossierSectorImpact(BaseModel):
    """Economic/industrial sector impacted."""
    sector_name: str
    impact_direction: Optional[str] = None  # e.g., "POTENTIAL_DOWNSTREAM_EFFECT", "EXPOSURE"
    evidence_class: EvidenceClass = EvidenceClass.ANALYTICAL_IMPLICATION
    rationale: Optional[str] = None


class DossierMarketConnection(BaseModel):
    """Market asset connection (Commodity, Currency, Equity, Rate)."""
    asset_symbol: str
    asset_name: str
    asset_type: str  # "COMMODITY", "CURRENCY", "EQUITY", "RATE"
    connection_type: str  # e.g., "TEMPORAL_CO_MOVEMENT", "SECTOR_LINKAGE"
    observation_window: Optional[str] = None
    return_percent: Optional[float] = None
    evidence_class: EvidenceClass = EvidenceClass.OBSERVED
    methodology: str = "window_close_return"


class DossierEconomicIndicator(BaseModel):
    """Economic indicator release associated with the event/region."""
    indicator_code: str
    indicator_name: str
    country_code: Optional[str] = None
    reported_value: Optional[float] = None
    reported_unit: Optional[str] = None
    change_percent: Optional[float] = None
    direction: Optional[str] = None
    evidence_class: EvidenceClass = EvidenceClass.OBSERVED


class DossierGeopoliticalConnection(BaseModel):
    """Geopolitical relationship between involved entities."""
    source_entity: str
    target_entity: str
    relationship_type: str  # e.g., "sanctions", "allied_with", "opposes", "signed_agreement_with"
    evidence_class: EvidenceClass = EvidenceClass.DIRECT
    description: Optional[str] = None


class DossierRelatedEvent(BaseModel):
    """Related event co-clustered or sharing common actors."""
    event_id: uuid.UUID
    title: str
    event_type: str
    event_time: Optional[datetime] = None
    relationship_reason: str
    evidence_class: EvidenceClass = EvidenceClass.DIRECT


class DossierMarketObservation(BaseModel):
    """Direct empirical price point or observation."""
    asset_symbol: str
    price: Optional[float] = None
    change_percent: Optional[float] = None
    timestamp: Optional[datetime] = None
    evidence_class: EvidenceClass = EvidenceClass.OBSERVED


class DossierSourceEvidence(BaseModel):
    """Source provenance and verifiable evidence trace."""
    source_id: Optional[uuid.UUID] = None
    source_name: str
    source_domain: Optional[str] = None
    url: str
    published_at: Optional[datetime] = None
    fetched_at: Optional[datetime] = None
    content_hash: Optional[str] = None
    snippet: Optional[str] = None
    evidence_class: EvidenceClass = EvidenceClass.OBSERVED


class EventIntelligenceDossierResponse(BaseModel):
    """Compact but complete 21-field event intelligence dossier with rigorous provenance."""
    # 1. WHAT_HAPPENED
    what_happened: Dict[str, Any] = Field(
        ...,
        description="Structured summary: event_id, title, summary, event_type, event_time, location"
    )
    # 2. WHY_IT_MATTERS
    why_it_matters: Dict[str, Any] = Field(
        ...,
        description="Significance assessment: calibrated importance score, cluster context, structural impact"
    )
    # 3. DIRECTLY_INVOLVED
    directly_involved: List[DossierEntityRef] = Field(
        default_factory=list,
        description="Entities exercising primary agency in the event"
    )
    # 4. DIRECTLY_AFFECTED
    directly_affected: List[DossierEntityRef] = Field(
        default_factory=list,
        description="Entities directly targeted, impacted, or sanctioned"
    )
    # 5. POTENTIAL_BENEFICIARIES
    potential_beneficiaries: List[DossierImpactEntity] = Field(
        default_factory=list,
        description="Entities with potential structural or market upside (neutral phrasing)"
    )
    # 6. POTENTIAL_EXPOSURES
    potential_exposures: List[DossierImpactEntity] = Field(
        default_factory=list,
        description="Entities or sectors with downside exposure (neutral phrasing)"
    )
    # 7. AFFECTED_COUNTRIES
    affected_countries: List[DossierCountryImpact] = Field(
        default_factory=list,
        description="Countries with verified geographic or institutional nexus"
    )
    # 8. AFFECTED_COMPANIES
    affected_companies: List[DossierCompanyImpact] = Field(
        default_factory=list,
        description="Corporate entities involved or exposed"
    )
    # 9. AFFECTED_SECTORS
    affected_sectors: List[DossierSectorImpact] = Field(
        default_factory=list,
        description="Economic and industry sectors impacted"
    )
    # 10. COMMODITY_CONNECTIONS
    commodity_connections: List[DossierMarketConnection] = Field(
        default_factory=list,
        description="Commodity assets exhibiting temporal correlation or supply linkage"
    )
    # 11. CURRENCY_CONNECTIONS
    currency_connections: List[DossierMarketConnection] = Field(
        default_factory=list,
        description="FX assets exhibiting temporal correlation or sovereign linkage"
    )
    # 12. EQUITY_CONNECTIONS
    equity_connections: List[DossierMarketConnection] = Field(
        default_factory=list,
        description="Equity benchmarks or indices exhibiting temporal correlation"
    )
    # 13. RATE_CONNECTIONS
    rate_connections: List[DossierMarketConnection] = Field(
        default_factory=list,
        description="Sovereign yields or interest rate benchmarks linked to the event"
    )
    # 14. ECONOMIC_INDICATORS
    economic_indicators: List[DossierEconomicIndicator] = Field(
        default_factory=list,
        description="Empirical economic observations related to the geography or period"
    )
    # 15. GEOPOLITICAL_CONNECTIONS
    geopolitical_connections: List[DossierGeopoliticalConnection] = Field(
        default_factory=list,
        description="Evidence-backed state-level and organizational relationships"
    )
    # 16. RELATED_EVENTS
    related_events: List[DossierRelatedEvent] = Field(
        default_factory=list,
        description="Chronologically or cluster-related events"
    )
    # 17. RELATED_ENTITIES
    related_entities: List[DossierEntityRef] = Field(
        default_factory=list,
        description="Peripheral or contextually associated entities"
    )
    # 18. MARKET_OBSERVATIONS
    market_observations: List[DossierMarketObservation] = Field(
        default_factory=list,
        description="Direct observed market prices during the event window"
    )
    # 19. SOURCE_EVIDENCE
    source_evidence: List[DossierSourceEvidence] = Field(
        default_factory=list,
        description="Original document provenance, URLs, hashes, and text snippets"
    )
    # 20. CONFIDENCE
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence score for the extraction and dossier synthesis"
    )
    # 21. LAST_UPDATED
    last_updated: datetime = Field(
        ...,
        description="Timestamp when the intelligence dossier was synthesized or updated"
    )

    # Independent timestamp telemetry (Phase I)
    publication_time: Optional[datetime] = None
    fetch_time: Optional[datetime] = None
    ingestion_time: Optional[datetime] = None
    extraction_time: Optional[datetime] = None
    intelligence_update_time: Optional[datetime] = None
