import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.market_asset import MarketAsset
from backend.app.models.market_observation import MarketObservation
from backend.app.schemas.market import MarketObservationCreate
from backend.app.market.providers import (
    CryptoMarketProvider,
    EquityMarketProvider,
    ForexMarketProvider,
    CommodityMarketProvider,
    RatesMarketProvider,
)
from backend.app.services.market_service import (
    store_market_observations,
    initialize_canonical_market_assets,
)
from backend.app.utils.logger import get_logger
from backend.app.utils.time import utc_now

logger = get_logger("service.market_ingestion")


class MarketIngestionService:
    """Orchestrates scheduled live telemetry ingestion across all 16 canonical assets."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.crypto_provider = CryptoMarketProvider(timeout=timeout)
        self.equity_provider = EquityMarketProvider(timeout=timeout)
        self.forex_provider = ForexMarketProvider(timeout=timeout)
        self.commodity_provider = CommodityMarketProvider(timeout=timeout)
        self.rates_provider = RatesMarketProvider(timeout=timeout)

    def get_provider_for_asset(self, asset: MarketAsset):
        """Map asset class to the verified provider adapter."""
        asset_type = (asset.asset_type or "").lower()
        if asset_type == "crypto":
            return self.crypto_provider
        elif asset_type in ("equity_index", "equity"):
            return self.equity_provider
        elif asset_type == "forex":
            return self.forex_provider
        elif asset_type == "commodity":
            return self.commodity_provider
        elif asset_type in ("interest_rate", "rates", "bond"):
            return self.rates_provider
        return None

    def ingest_asset_telemetry(
        self,
        db: Session,
        asset: MarketAsset,
        interval: str = "1d",
    ) -> Optional[MarketObservationCreate]:
        """Fetch latest price observation for a single canonical asset and persist to DB."""
        provider = self.get_provider_for_asset(asset)
        if not provider:
            logger.warning(f"No provider found for asset class '{asset.asset_type}' (symbol: {asset.symbol})")
            return None

        try:
            bar = provider.fetch_latest_bar(symbol=asset.symbol, interval=interval)
            if not bar:
                logger.debug(f"Provider {provider.provider_name} returned no bar for {asset.symbol}")
                return None

            bar.market_asset_id = asset.id
            inserted, report = store_market_observations(
                db, observations=[bar], interval=interval, asset_id=asset.id
            )
            logger.debug(f"Ingested observation for {asset.symbol}: close={bar.close} {bar.source} (new={inserted})")
            return bar
        except Exception as exc:
            logger.error(f"Failed ingesting market telemetry for '{asset.symbol}': {exc}")
            return None

    def ingest_all_canonical_assets(
        self,
        db: Session,
        interval: str = "1d",
    ) -> Dict[str, Any]:
        """Ingest live price telemetry across the entire 16-asset canonical universe."""
        start_time = time.perf_counter()
        assets = list(db.scalars(select(MarketAsset).order_by(MarketAsset.symbol)).all())
        if not assets:
            logger.info("Initializing canonical market assets before ingestion...")
            assets = initialize_canonical_market_assets(db)

        successful_symbols = []
        failed_symbols = []

        for asset in assets:
            obs = self.ingest_asset_telemetry(db, asset, interval=interval)
            if obs:
                successful_symbols.append(asset.symbol)
            else:
                failed_symbols.append(asset.symbol)

        duration = round(time.perf_counter() - start_time, 2)
        summary = {
            "total_assets": len(assets),
            "successful_count": len(successful_symbols),
            "failed_count": len(failed_symbols),
            "successful_symbols": successful_symbols,
            "failed_symbols": failed_symbols,
            "duration_seconds": duration,
            "timestamp": utc_now().isoformat(),
        }
        logger.info(
            f"Market ingestion run complete: {len(successful_symbols)}/{len(assets)} assets updated in {duration}s."
        )
        return summary

    def backfill_asset_history(
        self,
        db: Session,
        asset: MarketAsset,
        start_time: datetime,
        end_time: datetime,
        interval: str = "1d",
    ) -> int:
        """Backfill historical bars for an asset to enable pre/post event correlation windows."""
        provider = self.get_provider_for_asset(asset)
        if not provider:
            return 0

        try:
            bars = provider.fetch_historical_bars(
                symbol=asset.symbol,
                interval=interval,
                start_time=start_time,
                end_time=end_time,
            )
            if not bars:
                return 0

            for b in bars:
                b.market_asset_id = asset.id

            inserted, _ = store_market_observations(
                db, observations=bars, interval=interval, asset_id=asset.id
            )
            logger.info(f"Backfilled {inserted} historical bars for {asset.symbol}")
            return inserted
        except Exception as exc:
            logger.error(f"Failed backfilling history for {asset.symbol}: {exc}")
            return 0


# Global singleton instance
market_ingestion_service = MarketIngestionService()
