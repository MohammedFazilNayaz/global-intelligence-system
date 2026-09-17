"""
Comprehensive Unit and Integration Test Suite for V0.8.5 Expansion.
Verifies all new telemetry providers, canonical ticker endpoints, coverage ratings,
and multi-theatre reporting to guarantee >= 90% line coverage.
"""

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from backend.app.market.providers import (
    CryptoMarketProvider,
    EquityMarketProvider,
    ForexMarketProvider,
    CommodityMarketProvider,
    RatesMarketProvider,
    _fetch_yahoo_chart,
)
from backend.app.services.market_service import (
    get_canonical_tickers_summary,
    initialize_canonical_market_assets,
)
from backend.app.services.coverage_service import coverage_service


def test_fetch_yahoo_chart_mocked():
    """Test _fetch_yahoo_chart parsing logic with mock Yahoo Finance API response."""
    mock_json = {
        "chart": {
            "result": [
                {
                    "timestamp": [1700000000, 1700086400],
                    "indicators": {
                        "quote": [
                            {
                                "open": [5000.0, 5020.0],
                                "high": [5050.0, 5060.0],
                                "low": [4990.0, 5010.0],
                                "close": [5030.0, 5045.0],
                                "volume": [1000000, 1200000],
                            }
                        ]
                    },
                }
            ]
        }
    }

    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_json
        mock_get.return_value = mock_resp

        bars = _fetch_yahoo_chart("SPX", "^GSPC", interval="1d", range_str="5d")
        assert len(bars) == 2
        assert bars[0].open == 5000.0
        assert bars[0].close == 5030.0
        assert bars[0].volume == 1000000.0
        assert bars[0].metadata["canonical_symbol"] == "SPX"


def test_fetch_yahoo_chart_error_handling():
    """Verify _fetch_yahoo_chart returns empty list on network error or invalid JSON."""
    with patch("httpx.Client.get", side_effect=Exception("Connection refused")):
        bars = _fetch_yahoo_chart("SPX", "^GSPC")
        assert bars == []

    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp
        assert _fetch_yahoo_chart("SPX", "^GSPC") == []


def test_crypto_provider_coingecko_and_historical():
    """Verify CryptoMarketProvider handles live CoinGecko quotes and Binance bars."""
    provider = CryptoMarketProvider()

    # 1. CoinGecko quote
    cg_mock = {
        "bitcoin": {
            "usd": 89000.0,
            "usd_24h_vol": 45000000000.0,
            "last_updated_at": 1700000000,
        }
    }
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = cg_mock
        mock_get.return_value = mock_resp

        bar = provider.fetch_latest_bar("BTC-USD")
        assert bar is not None
        assert bar.close == 89000.0
        assert bar.source == "CoinGecko"

    # 2. Binance historical bars
    binance_kline = [
        [1700000000000, "88000.0", "89500.0", "87900.0", "89200.0", "500.0", 1700003600000, "44000000.0", 100, "250.0", "22000000.0", "0"]
    ]
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = binance_kline
        mock_get.return_value = mock_resp

        h_bars = provider.fetch_historical_bars(
            "BTC-USD",
            interval="1h",
            start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        assert len(h_bars) == 1
        assert h_bars[0].close == 89200.0
        assert h_bars[0].source == "Binance"


def test_equity_market_provider():
    """Verify EquityMarketProvider fetches latest and historical bars for indices."""
    provider = EquityMarketProvider()
    assert "SPX" in provider.supported_symbols()
    assert "DAX" in provider.supported_symbols()

    fake_bar = MagicMock()
    fake_bar.close = 5800.0
    fake_bar.timestamp = datetime(2026, 1, 5, tzinfo=timezone.utc)

    with patch("backend.app.market.providers._fetch_yahoo_chart", return_value=[fake_bar]):
        latest = provider.fetch_latest_bar("SPX")
        assert latest is not None
        assert latest.close == 5800.0

        hist = provider.fetch_historical_bars(
            "SPX", "1d", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 10, tzinfo=timezone.utc)
        )
        assert isinstance(hist, list)
        assert len(hist) == 1

    assert provider.fetch_latest_bar("UNKNOWN_INDEX") is None
    assert provider.fetch_historical_bars("UNKNOWN_INDEX", "1d", datetime.now(), datetime.now()) == []


def test_forex_market_provider():
    """Verify ForexMarketProvider handles reference rates and Yahoo fallback."""
    provider = ForexMarketProvider()
    assert "EUR/USD" in provider.supported_symbols()

    # Test Yahoo fallback
    fake_bar = MagicMock()
    fake_bar.close = 1.0850
    fake_bar.timestamp = datetime(2026, 1, 5, tzinfo=timezone.utc)
    fake_bar.source = "YahooFinance_FX"

    with patch("backend.app.market.providers._fetch_yahoo_chart", return_value=[fake_bar]):
        latest = provider.fetch_latest_bar("EUR/USD")
        assert latest is not None
        assert latest.close > 0
        assert latest.source in ("ECB_Reference", "YahooFinance_FX")

        hist = provider.fetch_historical_bars(
            "EUR/USD", "1d", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 10, tzinfo=timezone.utc)
        )
        assert len(hist) == 1

    assert provider.fetch_latest_bar("UNKNOWN_PAIR") is None


def test_commodity_market_provider():
    """Verify CommodityMarketProvider handles BRENT, WTI, and GOLD."""
    provider = CommodityMarketProvider()
    assert "BRENT" in provider.supported_symbols()
    assert "GOLD" in provider.supported_symbols()

    fake_bar = MagicMock()
    fake_bar.close = 75.50
    fake_bar.timestamp = datetime(2026, 1, 5, tzinfo=timezone.utc)

    with patch("backend.app.market.providers._fetch_yahoo_chart", return_value=[fake_bar]):
        latest = provider.fetch_latest_bar("BRENT")
        assert latest is not None
        assert latest.close == 75.50

        hist = provider.fetch_historical_bars(
            "BRENT", "1d", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 10, tzinfo=timezone.utc)
        )
        assert len(hist) == 1

    assert provider.fetch_latest_bar("UNKNOWN_COMMODITY") is None


def test_sovereign_rate_provider():
    """Verify RatesMarketProvider handles US2Y and US10Y yields."""
    provider = RatesMarketProvider()
    assert "US10Y" in provider.supported_symbols()
    assert "US2Y" in provider.supported_symbols()

    fake_bar = MagicMock()
    fake_bar.close = 4.25
    fake_bar.timestamp = datetime(2026, 1, 5, tzinfo=timezone.utc)

    with patch("backend.app.market.providers._fetch_yahoo_chart", return_value=[fake_bar]):
        latest = provider.fetch_latest_bar("US10Y")
        assert latest is not None
        assert latest.close > 0
        assert latest.source in ("US_Treasury", "YahooFinance_Yields")

        hist = provider.fetch_historical_bars(
            "US10Y", "1d", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 10, tzinfo=timezone.utc)
        )
        assert len(hist) == 1

    assert provider.fetch_latest_bar("UNKNOWN_RATE") is None


def test_coverage_service_computations(db_session):
    """Verify coverage service regional ratings, domain coverage, and IQI index."""
    summary = coverage_service.get_global_coverage_summary(db_session)
    assert "regional_coverage" in summary
    assert "domain_coverage" in summary
    assert "primary_source_ratios" in summary
    assert "information_quality_index" in summary

    # Check 11 operational theatres
    theatres = summary["regional_coverage"]["theatres"]
    assert len(theatres) == 11
    assert "North America" in theatres
    assert "Europe" in theatres
    assert "East Asia" in theatres

    # Check primary source ratios
    primary_ratios = summary["primary_source_ratios"]
    assert primary_ratios["textual_primary_target_pct"] == 30.0
    assert "telemetry_primary_pass" in primary_ratios

    # Check IQI
    iqi = summary["information_quality_index"]
    assert isinstance(iqi, float)
    assert iqi > 0.5


def test_canonical_tickers_summary(db_session):
    """Verify get_canonical_tickers_summary returns all 16 canonical assets."""
    initialize_canonical_market_assets(db_session)
    tickers = get_canonical_tickers_summary(db_session)
    assert len(tickers) == 16
    symbols = {t["symbol"] for t in tickers}
    assert "BTC-USD" in symbols
    assert "ETH-USD" in symbols
    assert "SPX" in symbols
    assert "DAX" in symbols
    assert "BRENT" in symbols
    assert "GOLD" in symbols
    assert "US10Y" in symbols


def test_api_coverage_and_tickers_endpoints(client, db_session):
    """Test HTTP API endpoints /system/coverage and /market/tickers."""
    initialize_canonical_market_assets(db_session)

    # 1. System Coverage
    resp_cov = client.get("/api/v1/system/coverage")
    assert resp_cov.status_code == 200
    cov_data = resp_cov.json()
    assert "regional_coverage" in cov_data
    assert "theatres" in cov_data["regional_coverage"]
    assert len(cov_data["regional_coverage"]["theatres"]) == 11

    # 2. Market Tickers
    resp_tick = client.get("/api/v1/market/tickers")
    assert resp_tick.status_code == 200
    tickers_data = resp_tick.json()
    assert len(tickers_data) == 16
    assert any(t["symbol"] == "BTC-USD" for t in tickers_data)
    assert any(t["symbol"] == "SPX" for t in tickers_data)
