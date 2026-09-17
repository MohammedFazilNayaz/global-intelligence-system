import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.entity import EntityRead


class RelationshipType(str, Enum):
    ALLIED_WITH = "allied_with"
    MEMBER_OF = "member_of"
    LOCATED_IN = "located_in"
    HEADQUARTERED_IN = "headquartered_in"
    BORDERS = "borders"
    TRADES_WITH = "trades_with"
    IMPORTS_FROM = "imports_from"
    EXPORTS_TO = "exports_to"
    EXPORTS = "exports"
    SANCTIONS = "sanctions"
    SANCTIONED_BY = "sanctioned_by"
    SUPPORTS = "supports"
    OPPOSES = "opposes"
    OWNS = "owns"
    SUBSIDIARY_OF = "subsidiary_of"
    SUPPLIES = "supplies"
    DEPENDS_ON = "depends_on"
    OPERATES = "operates"
    OPERATES_IN = "operates_in"
    ATTACKS = "attacks"
    NEGOTIATES_WITH = "negotiates_with"
    SIGNED_AGREEMENT_WITH = "signed_agreement_with"
    LEADS = "leads"
    GOVERNS = "governs"
    PRODUCES = "produces"


class EntityRelationshipBase(BaseModel):
    source_entity_id: uuid.UUID
    target_entity_id: uuid.UUID
    relationship_type: RelationshipType
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_document_id: Optional[uuid.UUID] = None
    source_event_id: Optional[uuid.UUID] = None
    extraction_method: str = "rule_based_v0.7"
    extractor_version: str = "v0.7.0"
    evidence: str = Field(..., min_length=1, description="Verbatim textual evidence or structured proof")
    metadata_: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    def __init__(self, **data):
        if "metadata" in data and "metadata_" not in data:
            data["metadata_"] = data.pop("metadata")
        super().__init__(**data)

    @property
    def metadata(self) -> Dict[str, Any]:
        return self.metadata_


class EntityRelationshipCreate(EntityRelationshipBase):
    pass


class EntityRelationshipRead(EntityRelationshipBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class EntityRelationshipWithEntities(EntityRelationshipRead):
    source_entity: Optional[EntityRead] = None
    target_entity: Optional[EntityRead] = None


class PaginatedRelationships(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[EntityRelationshipWithEntities]


# Graph Types
class GraphNode(BaseModel):
    id: str
    label: Optional[str] = None
    canonical_name: Optional[str] = None
    type: str = "entity"  # entity, event, economic_indicator, market_asset
    entity_type: Optional[str] = None
    country_code: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data):
        if "label" in data and "canonical_name" not in data:
            data["canonical_name"] = data["label"]
        if "canonical_name" in data and "label" not in data:
            data["label"] = data["canonical_name"]
        if "type" not in data and "entity_type" in data:
            data["type"] = data["entity_type"]
        super().__init__(**data)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship_type: str
    confidence: float
    evidence: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeGraphResponse(BaseModel):
    center_node_id: Optional[str] = None
    depth: int = 1
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    total_nodes: int
    total_edges: int


# Cross-Domain & Event Relationships
class EventRelationshipsResponse(BaseModel):
    event_id: str
    event_title: str
    event_type: str
    event_time: Optional[datetime] = None
    location_entity: Optional[EntityRead] = None
    involved_entities: List[EntityRead] = Field(default_factory=list)
    economic_indicators: List[Dict[str, Any]] = Field(default_factory=list)
    market_assets: List[Dict[str, Any]] = Field(default_factory=list)
    graph_edges: List[GraphEdge] = Field(default_factory=list)


# Impact Assessment Layer (Separation of Metrics & Zero Causality)
class EconomicContextItem(BaseModel):
    indicator_id: str
    canonical_name: str
    indicator_type: str
    economic_domain: str
    observation_period: Optional[str] = None
    reported_value: Optional[float] = None
    reported_unit: Optional[str] = None
    direction: Optional[str] = None
    economic_relevance: float = Field(..., ge=0.0, le=1.0, description="Observational economic relevance score")


class MarketContextItem(BaseModel):
    market_asset_id: str
    symbol: str
    canonical_name: str
    asset_type: str
    window_size: str
    pre_event_price: Optional[float] = None
    post_event_price: Optional[float] = None
    return_percent: Optional[float] = None
    volume_change: Optional[float] = None
    neutral_observation: str = Field(..., description="Neutral observational statement without causal claims")


class EventImpactAssessmentResponse(BaseModel):
    event_id: str
    event_title: str
    event_type: str
    event_time: Optional[datetime] = None
    event_importance: float = Field(..., ge=0.0, le=1.0, description="Retrospective event significance score")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction and data confidence")
    economic_context: List[EconomicContextItem] = Field(default_factory=list)
    market_context: List[MarketContextItem] = Field(default_factory=list)
    explanation: str = Field(..., description="Explainable observational summary")
    disclaimer: str = Field(
        default="Impact assessments represent retrospective, observational associations within historical observation windows. They do not assert or imply causality, trade recommendations, or future price forecasts.",
        description="Mandatory non-causal disclaimer",
    )
