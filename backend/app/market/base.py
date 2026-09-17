import abc
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union
from dateutil import parser as date_parser

from backend.app.schemas.market import (
    MarketObservationCreate,
    DataQualityReport,
)


class BaseMarketDataProvider(abc.ABC):
    """Abstract Base Class for Market Data Providers."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Name of the data provider / exchange venue."""
        pass

    @abc.abstractmethod
    def supported_symbols(self) -> List[str]:
        """List of canonical symbols supported by this provider."""
        pass

    @abc.abstractmethod
    def fetch_latest_bar(
        self, symbol: str, interval: str = "1m"
    ) -> Optional[MarketObservationCreate]:
        """Fetch latest OHLCV bar for a given symbol and interval."""
        pass

    @abc.abstractmethod
    def fetch_historical_bars(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[MarketObservationCreate]:
        """Fetch historical OHLCV bars over a given UTC time window."""
        pass

    @staticmethod
    def normalize_timestamp(
        raw_timestamp: Union[int, float, str, datetime],
        raw_timezone: Optional[str] = None,
    ) -> datetime:
        """
        Strictly normalize any provider timestamp into a UTC-aware datetime.
        Preserves microsecond precision where present.
        """
        if isinstance(raw_timestamp, (int, float)):
            # Distinguish milliseconds vs seconds
            val = float(raw_timestamp)
            if val > 1e11:  # Milliseconds epoch
                val = val / 1000.0
            return datetime.fromtimestamp(val, tz=timezone.utc)

        if isinstance(raw_timestamp, str):
            dt = date_parser.parse(raw_timestamp)
            if dt.tzinfo is None:
                # If naive string, treat as UTC or apply raw_timezone if known
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt

        if isinstance(raw_timestamp, datetime):
            if raw_timestamp.tzinfo is None:
                return raw_timestamp.replace(tzinfo=timezone.utc)
            return raw_timestamp.astimezone(timezone.utc)

        raise ValueError(f"Unsupported timestamp format: {type(raw_timestamp)}")
