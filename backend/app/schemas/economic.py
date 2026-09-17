from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from backend.app.schemas.entity import EntityRead


class EconomicDomain(str, Enum):
    MONETARY_POLICY = "Monetary Policy"
    FISCAL_POLICY = "Fiscal Policy"
    INFLATION = "Inflation"
    GROWTH = "Growth"
    EMPLOYMENT = "Employment"
    TRADE = "Trade"
    CONSUMER = "Consumer"
    INDUSTRY = "Industry"
    HOUSING = "Housing"
    COMMODITIES = "Commodities"
    FOREIGN_EXCHANGE = "Foreign Exchange"


class IndicatorType(str, Enum):
    INFLATION = "inflation"
    CPI = "cpi"
    PPI = "ppi"
    GDP = "gdp"
    EMPLOYMENT = "employment"
    UNEMPLOYMENT = "unemployment"
    PAYROLLS = "payrolls"
    WAGES = "wages"
    INTEREST_RATE = "interest_rate"
    CENTRAL_BANK_RATE = "central_bank_rate"
    MONETARY_POLICY = "monetary_policy"
    FISCAL_POLICY = "fiscal_policy"
    GOVERNMENT_DEBT = "government_debt"
    PUBLIC_DEFICIT = "public_deficit"
    RETAIL_SALES = "retail_sales"
    INDUSTRIAL_PRODUCTION = "industrial_production"
    PMI = "pmi"
    CONSUMER_CONFIDENCE = "consumer_confidence"
    BUSINESS_CONFIDENCE = "business_confidence"
    TRADE_BALANCE = "trade_balance"
    EXPORTS = "exports"
    IMPORTS = "imports"
    CURRENT_ACCOUNT = "current_account"
    FOREIGN_EXCHANGE = "foreign_exchange"
    HOUSING = "housing"
    MANUFACTURING = "manufacturing"
    SERVICES = "services"
    COMMODITIES = "commodities"
    ENERGY = "energy"
    OIL = "oil"
    NATURAL_GAS = "natural_gas"
    METALS = "metals"
    AGRICULTURE = "agriculture"
    OTHER_ECONOMIC_INDICATOR = "other_economic_indicator"


class CentralBankDecisionType(str, Enum):
    RATE_HIKE = "rate_hike"
    RATE_CUT = "rate_cut"
    RATE_HOLD = "rate_hold"
    MONETARY_POLICY_STATEMENT = "monetary_policy_statement"
    QUANTITATIVE_EASING = "quantitative_easing"
    BALANCE_SHEET = "balance_sheet"
    FORWARD_GUIDANCE = "forward_guidance"


class ObservationDirection(str, Enum):
    INCREASE = "increase"
    DECREASE = "decrease"
    UNCHANGED = "unchanged"
    HIKE = "hike"
    CUT = "cut"
    HOLD = "hold"


# Mapping from IndicatorType to default EconomicDomain
INDICATOR_DOMAIN_MAP: Dict[IndicatorType, EconomicDomain] = {
    IndicatorType.INFLATION: EconomicDomain.INFLATION,
    IndicatorType.CPI: EconomicDomain.INFLATION,
    IndicatorType.PPI: EconomicDomain.INFLATION,
    IndicatorType.GDP: EconomicDomain.GROWTH,
    IndicatorType.EMPLOYMENT: EconomicDomain.EMPLOYMENT,
    IndicatorType.UNEMPLOYMENT: EconomicDomain.EMPLOYMENT,
    IndicatorType.PAYROLLS: EconomicDomain.EMPLOYMENT,
    IndicatorType.WAGES: EconomicDomain.EMPLOYMENT,
    IndicatorType.INTEREST_RATE: EconomicDomain.MONETARY_POLICY,
    IndicatorType.CENTRAL_BANK_RATE: EconomicDomain.MONETARY_POLICY,
    IndicatorType.MONETARY_POLICY: EconomicDomain.MONETARY_POLICY,
    IndicatorType.FISCAL_POLICY: EconomicDomain.FISCAL_POLICY,
    IndicatorType.GOVERNMENT_DEBT: EconomicDomain.FISCAL_POLICY,
    IndicatorType.PUBLIC_DEFICIT: EconomicDomain.FISCAL_POLICY,
    IndicatorType.RETAIL_SALES: EconomicDomain.CONSUMER,
    IndicatorType.CONSUMER_CONFIDENCE: EconomicDomain.CONSUMER,
    IndicatorType.BUSINESS_CONFIDENCE: EconomicDomain.GROWTH,
    IndicatorType.INDUSTRIAL_PRODUCTION: EconomicDomain.INDUSTRY,
    IndicatorType.PMI: EconomicDomain.INDUSTRY,
    IndicatorType.MANUFACTURING: EconomicDomain.INDUSTRY,
    IndicatorType.SERVICES: EconomicDomain.GROWTH,
    IndicatorType.TRADE_BALANCE: EconomicDomain.TRADE,
    IndicatorType.EXPORTS: EconomicDomain.TRADE,
    IndicatorType.IMPORTS: EconomicDomain.TRADE,
    IndicatorType.CURRENT_ACCOUNT: EconomicDomain.TRADE,
    IndicatorType.FOREIGN_EXCHANGE: EconomicDomain.FOREIGN_EXCHANGE,
    IndicatorType.HOUSING: EconomicDomain.HOUSING,
    IndicatorType.COMMODITIES: EconomicDomain.COMMODITIES,
    IndicatorType.ENERGY: EconomicDomain.COMMODITIES,
    IndicatorType.OIL: EconomicDomain.COMMODITIES,
    IndicatorType.NATURAL_GAS: EconomicDomain.COMMODITIES,
    IndicatorType.METALS: EconomicDomain.COMMODITIES,
    IndicatorType.AGRICULTURE: EconomicDomain.COMMODITIES,
    IndicatorType.OTHER_ECONOMIC_INDICATOR: EconomicDomain.GROWTH,
}


# --- Pydantic Schemas for API Contracts ---

class EconomicIndicatorRead(BaseModel):
    id: UUID
    canonical_name: str
    normalized_name: str
    indicator_type: str
    economic_domain: str
    country_entity_id: Optional[UUID] = None
    default_unit: Optional[str] = None
    description: Optional[str] = None
    metadata_: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime
    country_entity: Optional[EntityRead] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class EconomicIndicatorListResponse(BaseModel):
    items: List[EconomicIndicatorRead]
    total: int
    page: int
    page_size: int


class EconomicObservationRead(BaseModel):
    id: UUID
    indicator_id: UUID
    event_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    observation_period: Optional[str] = None
    observation_date: Optional[datetime] = None
    reported_value: Optional[float] = None
    reported_unit: Optional[str] = None
    previous_value: Optional[float] = None
    expected_value: Optional[float] = None
    revised_value: Optional[float] = None
    direction: Optional[str] = None
    change_value: Optional[float] = None
    change_percent: Optional[float] = None
    calculation_method: Optional[str] = None
    economic_relevance: float = Field(ge=0.0, le=1.0)
    metadata_: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime
    indicator: Optional[EconomicIndicatorRead] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class EconomicObservationDetailRead(EconomicObservationRead):
    source_name: Optional[str] = None
    document_title: Optional[str] = None
    document_url: Optional[str] = None
    evidence_snippet: Optional[str] = None


class EconomicObservationListResponse(BaseModel):
    items: List[EconomicObservationRead]
    total: int
    page: int
    page_size: int


class ExtractedEconomicObservation(BaseModel):
    """Schema produced by the extraction engine during document processing."""
    indicator_type: str
    indicator_canonical_name: str
    economic_domain: str
    country_name: Optional[str] = None
    country_code: Optional[str] = None
    observation_period: Optional[str] = None
    observation_date: Optional[datetime] = None
    reported_value: Optional[float] = None
    reported_unit: Optional[str] = None
    previous_value: Optional[float] = None
    expected_value: Optional[float] = None
    revised_value: Optional[float] = None
    direction: Optional[str] = None
    change_value: Optional[float] = None
    change_percent: Optional[float] = None
    calculation_method: Optional[str] = None
    economic_relevance: float = Field(ge=0.0, le=1.0)
    evidence_snippet: Optional[str] = None
    central_bank_decision: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class IndicatorLatestObservation(BaseModel):
    indicator: EconomicIndicatorRead
    latest_observation: Optional[EconomicObservationRead] = None


class CountryEconomicProfileResponse(BaseModel):
    country_entity: EntityRead
    domains: Dict[str, List[IndicatorLatestObservation]]
    recent_central_bank_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    recent_observations: List[EconomicObservationRead] = Field(default_factory=list)
    indicators_count: int
    observations_count: int


class EconomicSummaryResponse(BaseModel):
    total_indicators_count: int
    total_observations_count: int
    domains_breakdown: Dict[str, int]
    central_bank_decisions_count: int
    high_relevance_observations_count: int
    recent_key_releases: List[EconomicObservationRead] = Field(default_factory=list)
