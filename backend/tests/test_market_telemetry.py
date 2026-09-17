import pytest
import uuid
from datetime import datetime, timezone, timedelta
from backend.app.market.providers import (
    CryptoMarketProvider,
    EquityMarketProvider,
    ForexMarketProvider,
    CommodityMarketProvider,
    RatesMarketProvider,
)
from backend.app.models.market_asset import MarketAsset
from backend.app.schemas.market import MarketObservationCreate
from backend.app.services.market_ingestion_service import MarketIngestionService
from backend.app.services.market_service import initialize_canonical_market_assets
from backend.app.utils.time import utc_now


def test_market_providers_supported_symbols():
    crypto = CryptoMarketProvider()
    assert set(crypto.supported_symbols()) == {"BTC-USD", "ETH-USD"}

    equity = EquityMarketProvider()
    assert set(equity.supported_symbols()) == {"SPX", "NDX", "DAX", "FTSE", "N225"}

    forex = ForexMarketProvider()
    assert set(forex.supported_symbols()) == {"EUR/USD", "GBP/USD", "USD/JPY", "USD/INR"}

    commodity = CommodityMarketProvider()
    assert set(commodity.supported_symbols()) == {"BRENT", "WTI", "GOLD"}

    rates = RatesMarketProvider()
    assert set(rates.supported_symbols()) == {"US2Y", "US10Y"}

    # Total canonical universe equals exactly 16 assets
    total_symbols = (
        crypto.supported_symbols()
        + equity.supported_symbols()
        + forex.supported_symbols()
        + commodity.supported_symbols()
        + rates.supported_symbols()
    )
    assert len(total_symbols) == 16
    assert len(set(total_symbols)) == 16


def test_market_ingestion_service_provider_mapping():
    service = MarketIngestionService()

    asset_crypto = MarketAsset(symbol="BTC-USD", canonical_name="Bitcoin", asset_type="crypto")
    assert service.get_provider_for_asset(asset_crypto) == service.crypto_provider

    asset_equity = MarketAsset(symbol="SPX", canonical_name="S&P 500", asset_type="equity_index")
    assert service.get_provider_for_asset(asset_equity) == service.equity_provider

    asset_forex = MarketAsset(symbol="EUR/USD", canonical_name="Euro", asset_type="forex")
    assert service.get_provider_for_asset(asset_forex) == service.forex_provider

    asset_comm = MarketAsset(symbol="GOLD", canonical_name="Gold", asset_type="commodity")
    assert service.get_provider_for_asset(asset_comm) == service.commodity_provider

    asset_rates = MarketAsset(symbol="US10Y", canonical_name="US 10Y", asset_type="interest_rate")
    assert service.get_provider_for_asset(asset_rates) == service.rates_provider


def test_market_ingestion_service_ingest_mock(db_session, monkeypatch):
    service = MarketIngestionService()
    assets = initialize_canonical_market_assets(db_session)
    assert len(assets) == 16

    now = utc_now()
    sample_bar = MarketObservationCreate(
        timestamp=now,
        open=100.0,
        high=105.0,
        low=99.0,
        close=103.5,
        volume=1000.0,
        source="TestProvider",
        interval="1d",
        metadata_={"is_live": True},
    )

    # Mock provider fetch
    monkeypatch.setattr(service.equity_provider, "fetch_latest_bar", lambda symbol, interval="1d": sample_bar)

    spx_asset = next(a for a in assets if a.symbol == "SPX")
    result = service.ingest_asset_telemetry(db_session, spx_asset, interval="1d")
    assert result is not None
    assert result.close == 103.5
