"""
Macroeconomic Intelligence Ingestion Service for V0.8.5.
Provides automated ingestion of official sovereign statistical series from FRED
with revision tracking, exact release timestamps, and canonical indicator binding.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
import httpx
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from backend.app.models.indicator import EconomicIndicator
from backend.app.models.observation import EconomicObservation
from backend.app.models.entity import Entity
from backend.app.utils.time import utc_now
from backend.app.utils.logger import setup_logger

logger = setup_logger("services.macro_ingestion")

# Canonical series specifications
SERIES_REGISTRY: Dict[str, Dict[str, Any]] = {
    "CPI_US": {
        "series_id": "CPIAUCSL",
        "symbol": "CPI_US",
        "canonical_name": "US Consumer Price Index (CPI)",
        "indicator_type": "cpi",
        "economic_domain": "Inflation",
        "country_code": "US",
        "default_unit": "Index",
        "relevance": 0.95,
        "cadence": "monthly",
    },
    "UNRATE_US": {
        "series_id": "UNRATE",
        "symbol": "UNRATE_US",
        "canonical_name": "US Unemployment Rate",
        "indicator_type": "unemployment",
        "economic_domain": "Employment",
        "country_code": "US",
        "default_unit": "%",
        "relevance": 0.92,
        "cadence": "monthly",
    },
    "FEDFUNDS": {
        "series_id": "FEDFUNDS",
        "symbol": "FEDFUNDS",
        "canonical_name": "Effective Federal Funds Rate",
        "indicator_type": "interest_rate",
        "economic_domain": "Monetary Policy",
        "country_code": "US",
        "default_unit": "%",
        "relevance": 0.98,
        "cadence": "monthly",
    },
    "GDP_US": {
        "series_id": "GDP",
        "symbol": "GDP_US",
        "canonical_name": "US Gross Domestic Product (GDP)",
        "indicator_type": "gdp",
        "economic_domain": "Growth",
        "country_code": "US",
        "default_unit": "Billions USD",
        "relevance": 0.96,
        "cadence": "quarterly",
    },
}

FRED_CSV_BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


class MacroeconomicIngestionService:
    """Service to ingest and manage official macroeconomic time series."""

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.8",
        }

    def fetch_series_csv(self, series_id: str) -> List[Tuple[str, float]]:
        """Fetch raw CSV series from FRED and parse (date_str, float_value) tuples."""
        url = f"{FRED_CSV_BASE_URL}?id={series_id}"
        with httpx.Client(headers=self.headers, timeout=self.timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()

        lines = resp.text.strip().split("\n")
        results: List[Tuple[str, float]] = []
        if len(lines) <= 1:
            return results

        # Header is lines[0]: DATE,SERIES_ID
        for line in lines[1:]:
            parts = line.strip().split(",")
            if len(parts) >= 2:
                date_str = parts[0].strip()
                val_str = parts[1].strip()
                if val_str and val_str != ".":
                    try:
                        results.append((date_str, float(val_str)))
                    except ValueError:
                        continue
        return results

    def get_or_create_indicator(self, db: Session, symbol: str) -> EconomicIndicator:
        """Find or create canonical EconomicIndicator with symbol."""
        spec = SERIES_REGISTRY.get(symbol)
        if not spec:
            raise ValueError(f"Unknown indicator symbol: {symbol}")

        # Match by symbol first
        stmt = select(EconomicIndicator).where(EconomicIndicator.symbol == symbol)
        indicator = db.scalars(stmt).first()
        if indicator:
            return indicator

        # Match by canonical_name fallback
        stmt_name = select(EconomicIndicator).where(
            EconomicIndicator.canonical_name == spec["canonical_name"]
        )
        indicator = db.scalars(stmt_name).first()
        if indicator:
            indicator.symbol = symbol
            db.flush()
            return indicator

        # Resolve US country entity
        us_entity = db.scalars(
            select(Entity).where(Entity.country_code == spec["country_code"])
        ).first()

        indicator = EconomicIndicator(
            id=uuid.uuid4(),
            symbol=symbol,
            canonical_name=spec["canonical_name"],
            normalized_name=spec["canonical_name"].strip().lower(),
            indicator_type=spec["indicator_type"],
            economic_domain=spec["economic_domain"],
            country_entity_id=us_entity.id if us_entity else None,
            default_unit=spec["default_unit"],
            description=f"Official {spec['canonical_name']} published by Federal Reserve Bank of St. Louis (FRED).",
            metadata_={"source": "FRED", "series_id": spec["series_id"], "cadence": spec["cadence"]},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(indicator)
        db.flush()
        return indicator

    def ingest_series(
        self,
        db: Session,
        symbol: str,
        limit_recent: int = 12,
        csv_data: Optional[List[Tuple[str, float]]] = None,
    ) -> int:
        """
        Ingest observations for a canonical macroeconomic indicator.
        Maintains revision tracking and non-fabrication guarantees.
        """
        spec = SERIES_REGISTRY.get(symbol)
        if not spec:
            raise ValueError(f"Unknown indicator symbol: {symbol}")

        indicator = self.get_or_create_indicator(db, symbol)

        if csv_data is not None:
            data_points = csv_data
        else:
            try:
                data_points = self.fetch_series_csv(spec["series_id"])
            except Exception as e:
                logger.error(f"Failed to fetch FRED series {spec['series_id']}: {e}")
                return 0

        if not data_points:
            return 0

        # Take the most recent data points up to limit_recent
        slice_points = data_points[-limit_recent:]
        inserted_count = 0

        for i, (date_str, val) in enumerate(slice_points):
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            period_str = dt.strftime("%Y-%m") if spec["cadence"] == "monthly" else f"{dt.year}-Q{(dt.month-1)//3 + 1}"
            period_start = dt
            if spec["cadence"] == "monthly":
                # next month minus 1 day
                next_month = dt.month % 12 + 1
                year_delta = dt.year + (1 if next_month == 1 else 0)
                period_end = datetime(year_delta, next_month, 1, tzinfo=timezone.utc) - timedelta(days=1)
            else:
                period_end = dt + timedelta(days=90)

            # Previous point value for delta calculation
            prior_val: Optional[float] = None
            if i > 0:
                prior_val = slice_points[i - 1][1]
            elif len(data_points) > len(slice_points):
                # Look at previous element before slice
                prior_index = len(data_points) - len(slice_points) - 1
                if prior_index >= 0:
                    prior_val = data_points[prior_index][1]

            change_val: Optional[float] = None
            change_pct: Optional[float] = None
            direction: Optional[str] = None
            if prior_val is not None:
                change_val = round(val - prior_val, 4)
                if prior_val != 0:
                    change_pct = round((change_val / abs(prior_val)) * 100, 2)
                if change_val > 0:
                    direction = "increase"
                elif change_val < 0:
                    direction = "decrease"
                else:
                    direction = "unchanged"

            # Check if observation already exists for this indicator and period
            existing_obs = db.scalars(
                select(EconomicObservation).where(
                    and_(
                        EconomicObservation.indicator_id == indicator.id,
                        EconomicObservation.observation_period == period_str,
                    )
                )
            ).first()

            if existing_obs:
                # If value changed, record revision
                if existing_obs.reported_value != val:
                    existing_obs.previous_value = existing_obs.reported_value
                    existing_obs.revised_value = val
                    existing_obs.reported_value = val
                    existing_obs.is_revision = True
                    existing_obs.revision_number += 1
                    existing_obs.release_timestamp = utc_now()
                    existing_obs.updated_at = utc_now()
                    logger.info(
                        f"Recorded revision #{existing_obs.revision_number} for {symbol} "
                        f"period {period_str}: {existing_obs.previous_value} -> {val}"
                    )
                continue

            # Create new observation
            obs = EconomicObservation(
                id=uuid.uuid4(),
                indicator_id=indicator.id,
                document_id=None,
                event_id=None,
                observation_period=period_str,
                observation_date=dt,
                period_start=period_start,
                period_end=period_end,
                release_timestamp=dt,
                is_revision=False,
                revision_number=0,
                reported_value=val,
                reported_unit=spec["default_unit"],
                previous_value=prior_val,
                expected_value=None,
                revised_value=None,
                direction=direction,
                change_value=change_val,
                change_percent=change_pct,
                calculation_method="official_statistical_agency",
                economic_relevance=spec["relevance"],
                metadata_={
                    "source": "FRED",
                    "series_id": spec["series_id"],
                    "frequency": spec["cadence"],
                    "provenance": "St. Louis Fed Federal Reserve Economic Data",
                },
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            db.add(obs)
            inserted_count += 1

        db.commit()
        logger.info(f"Ingested {inserted_count} macroeconomic observations for {symbol}.")
        return inserted_count

    def ingest_all_macro_indicators(self, db: Session, limit_recent: int = 12) -> Dict[str, int]:
        """Ingest all configured canonical macroeconomic indicators."""
        results: Dict[str, int] = {}
        for symbol in SERIES_REGISTRY:
            results[symbol] = self.ingest_series(db, symbol, limit_recent=limit_recent)
        return results


macro_ingestion_service = MacroeconomicIngestionService()
