import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class AssetType(str, Enum):
    CRYPTO = "crypto"
    EQUITY = "equity"
    EQUITY_INDEX = "equity_index"
    FOREX = "forex"
    COMMODITY = "commodity"
    BOND = "bond"
    INTEREST_RATE = "interest_rate"
    ETF = "etf"
    OTHER = "other"


class MarketInterval(str, Enum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"


class CorrelationWindow(str, Enum):
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"


# ---------------------------------------------------------------------------
# Market Asset Schemas
# ---------------------------------------------------------------------------

class MarketAssetBase(BaseModel):
    symbol: str
    canonical_name: str
    asset_type: str
    exchange_venue: Optional[str] = None
    quote_currency: Optional[str] = None
    base_currency: Optional[str] = None
    entity_id: Optional[uuid.UUID] = None
    metadata_: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    def __init__(self, **data):
        if "metadata" in data and "metadata_" not in data:
            data["metadata_"] = data.pop("metadata")
        super().__init__(**data)

    @property
    def metadata(self) -> Dict[str, Any]:
        return self.metadata_


class MarketAssetCreate(MarketAssetBase):
    pass


class MarketAssetRead(MarketAssetBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Market Observation (Candle / Bar) Schemas
# ---------------------------------------------------------------------------

class MarketObservationBase(BaseModel):
    market_asset_id: Optional[uuid.UUID] = None
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None
    source: str
    interval: str
    metadata_: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    def __init__(self, **data):
        if "metadata" in data and "metadata_" not in data:
            data["metadata_"] = data.pop("metadata")
        super().__init__(**data)

    @property
    def metadata(self) -> Dict[str, Any]:
        return self.metadata_


class MarketObservationCreate(MarketObservationBase):
    pass


class MarketObservationRead(MarketObservationBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Data Quality Schemas
# ---------------------------------------------------------------------------

class DataQualityReport(BaseModel):
    asset_id: Optional[uuid.UUID] = None
    symbol: Optional[str] = None
    interval: Optional[str] = None
    is_healthy: bool = True
    total_observations: int = 0
    duplicate_count: int = 0
    missing_candles_count: int = 0
    out_of_order_count: int = 0
    stale_price_count: int = 0
    gap_count: int = 0
    gap_details: List[Dict[str, Any]] = Field(default_factory=list)
    latest_observation_time: Optional[datetime] = None
    earliest_observation_time: Optional[datetime] = None
    continuity_ratio: float = 1.0


class MarketAssetDetailRead(MarketAssetRead):
    latest_observation: Optional[MarketObservationRead] = None
    recent_observations_count: int = 0
    day_return_percent: Optional[float] = None
    data_quality: Optional[DataQualityReport] = None


# ---------------------------------------------------------------------------
# Event-Market Correlation Schemas
# ---------------------------------------------------------------------------

STANDARD_CORRELATION_DISCLAIMER = (
    "Market movement is temporally associated with the event and does not establish causation."
)


class EventMarketCorrelationBase(BaseModel):
    event_id: uuid.UUID
    cluster_id: Optional[uuid.UUID] = None
    market_asset_id: uuid.UUID
    window_size: str
    window_start: datetime
    window_end: datetime
    pre_event_price: Optional[float] = None
    event_price: Optional[float] = None
    post_event_price: Optional[float] = None
    return_percent: Optional[float] = None
    absolute_change: Optional[float] = None
    volatility: Optional[float] = None
    volume_change: Optional[float] = None
    max_excursion: Optional[float] = None
    min_excursion: Optional[float] = None
    calculated_at: datetime
    methodology: str = "window_close_return"
    metadata_: Dict[str, Any] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    def __init__(self, **data):
        if "metadata" in data and "metadata_" not in data:
            data["metadata_"] = data.pop("metadata")
        super().__init__(**data)

    @property
    def metadata(self) -> Dict[str, Any]:
        return self.metadata_


class EventMarketCorrelationCreate(EventMarketCorrelationBase):
    pass


class EventMarketCorrelationRead(EventMarketCorrelationBase):
    id: uuid.UUID
    disclaimer: str = STANDARD_CORRELATION_DISCLAIMER
    market_asset: Optional[MarketAssetRead] = None
    event_title: Optional[str] = None
    event_type: Optional[str] = None
    event_time: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class MarketCorrelationComputeRequest(BaseModel):
    window_sizes: List[str] = ["5m", "15m", "1h", "4h", "1d"]
    market_asset_ids: Optional[List[uuid.UUID]] = None


# ---------------------------------------------------------------------------
# Dashboard & Summary Schemas
# ---------------------------------------------------------------------------

class MarketDashboardSummaryResponse(BaseModel):
    total_assets: int = 0
    asset_counts_by_type: Dict[str, int] = Field(default_factory=dict)
    total_observations: int = 0
    total_correlations: int = 0
    top_movers: List[Dict[str, Any]] = Field(default_factory=list)
    recent_correlations: List[EventMarketCorrelationRead] = Field(default_factory=list)
    disclaimer: str = STANDARD_CORRELATION_DISCLAIMER
