from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from backend.app.utils.time import utc_now


class EntityType(str, Enum):
    COUNTRY = "COUNTRY"
    CITY = "CITY"
    LOCATION = "LOCATION"
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    COMPANY = "COMPANY"
    GOVERNMENT = "GOVERNMENT"
    POLITICAL_PARTY = "POLITICAL_PARTY"
    CENTRAL_BANK = "CENTRAL_BANK"
    FINANCIAL_INSTITUTION = "FINANCIAL_INSTITUTION"
    COMMODITY = "COMMODITY"
    CURRENCY = "CURRENCY"
    CRYPTOCURRENCY = "CRYPTOCURRENCY"
    FINANCIAL_ASSET = "FINANCIAL_ASSET"
    INDEX = "INDEX"
    INDUSTRY = "INDUSTRY"
    ECONOMIC_INDICATOR = "ECONOMIC_INDICATOR"
    INTERNATIONAL_ORGANIZATION = "INTERNATIONAL_ORGANIZATION"
    OTHER = "OTHER"


class EntityRole(str, Enum):
    SUBJECT = "subject"
    ACTOR = "actor"
    TARGET = "target"
    LOCATION = "location"
    ORGANIZATION = "organization"
    PERSON = "person"
    COMPANY = "company"
    COMMODITY = "commodity"
    CURRENCY = "currency"
    ASSET = "asset"
    INDICATOR = "indicator"
    OTHER = "other"


class EventType(str, Enum):
    CONFLICT = "conflict"
    ATTACK = "attack"
    MILITARY_ACTION = "military_action"
    DIPLOMATIC_ACTION = "diplomatic_action"
    POLITICAL_DECISION = "political_decision"
    POLITICAL_CHANGE = "political_change"
    GOVERNMENT_DECISION = "government_decision"
    ELECTION = "election"
    PROTEST = "protest"
    COUP = "coup"
    SANCTION = "sanction"
    TARIFF = "tariff"
    TRADE_ACTION = "trade_action"
    ECONOMIC_RELEASE = "economic_release"
    MONETARY_POLICY = "monetary_policy"
    CENTRAL_BANK_DECISION = "central_bank_decision"
    CORPORATE_EVENT = "corporate_event"
    CORPORATE_ACTION = "corporate_action"
    COMMODITY_EVENT = "commodity_event"
    MARKET_EVENT = "market_event"
    DISASTER = "disaster"
    NATURAL_DISASTER = "natural_disaster"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    CYBER_INCIDENT = "cyber_incident"
    ENVIRONMENTAL_EVENT = "environmental_event"
    HUMANITARIAN_EVENT = "humanitarian_event"
    TRANSPORTATION_EVENT = "transportation_event"
    ENERGY_DISRUPTION = "energy_disruption"
    SUPPLY_CHAIN_DISRUPTION = "supply_chain_disruption"
    REGULATORY_ACTION = "regulatory_action"
    INTERNATIONAL_AGREEMENT = "international_agreement"
    OTHER = "other"


class ProcessingStatus(str, Enum):
    RAW = "RAW"
    NORMALIZED = "NORMALIZED"
    EXTRACTION_PENDING = "EXTRACTION_PENDING"
    EXTRACTED = "EXTRACTED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    FAILED = "FAILED"


class ExtractedEntityMention(BaseModel):
    """Extraction output contract for a single entity mention."""
    entity_type: str
    canonical_name: str
    normalized_name: str
    mention_text: str
    role: str = "other"
    confidence: float = Field(ge=0.0, le=1.0)
    country_code: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class ExtractedEventItem(BaseModel):
    """Extraction output contract for a single extracted event."""
    event_type: str
    title: str
    summary: Optional[str] = None
    event_time: Optional[datetime] = None
    location_entity_name: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    importance: float = Field(ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class ExtractionProvenance(BaseModel):
    """Provenance tracking who extracted the intelligence and when."""
    extractor_name: str
    extractor_version: str
    processed_at: datetime = Field(default_factory=utc_now)
    config: Dict[str, Any] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    """Strict internal schema contract returned by all intelligence extractors."""
    entities: List[ExtractedEntityMention] = Field(default_factory=list)
    events: List[ExtractedEventItem] = Field(default_factory=list)
    economic_observations: List[Any] = Field(default_factory=list)
    metadata: ExtractionProvenance

    model_config = ConfigDict(extra="forbid")


class ExtractionTriggerRequest(BaseModel):
    reprocess: bool = False
    extractor_name: Optional[str] = None


class ExtractionTriggerResponse(BaseModel):
    document_id: UUID
    processing_status: str
    entities_count: int
    events_count: int
    duration_seconds: float
    extractor: ExtractionProvenance
    message: str
