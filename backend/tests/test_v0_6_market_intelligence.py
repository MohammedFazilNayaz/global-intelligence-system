import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session

from backend.app.models.market_asset import MarketAsset
from backend.app.models.market_observation import MarketObservation
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.models.event import ExtractedEvent
from backend.app.models.document import Document
from backend.app.models.source import Source
from backend.app.schemas.market import (
    MarketObservationCreate,
    STANDARD_CORRELATION_DISCLAIMER,
)
from backend.app.market.base import BaseMarketDataProvider
from backend.app.market.quality import MarketDataQualityEngine
from backend.app.market.providers import (
    DeterministicMarketProvider,
    CryptoMarketProvider,
    EquityMarketProvider,
    ForexMarketProvider,
    CommodityMarketProvider,
    RatesMarketProvider,
)
from backend.app.services.market_service import (
    initialize_canonical_market_assets,
    get_or_create_market_asset,
    store_market_observations,
    get_market_assets,
    get_market_asset_detail,
    get_asset_observations,
    get_market_dashboard_summary,
)
from backend.app.services.correlation_service import (
    get_relevant_assets_for_event,
    compute_event_market_correlation,
    correlate_event_across_assets,
    get_events_for_market_asset,
)


@pytest.fixture
def db(db_session: Session):
    """Alias for db_session fixture."""
    return db_session


@pytest.fixture
def base_source_and_doc(db: Session):
    """Fixture providing a source and document for event testing."""
    source = Source(
        name="Market Reuters Feed",
        source_type="rss",
        base_url="https://reuters.com",
        feed_url="https://reuters.com/markets/rss",
        active=True,
    )
    db.add(source)
    db.commit()

    doc = Document(
        source_id=source.id,
        external_id="doc-market-bench-01",
        title="Macro Market Intelligence Benchmark Doc",
        content="Global macro events and market reactions.",
        content_hash="hash-bench-01",
        url="https://reuters.com/markets/bench-01",
        published_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return source, doc


# ===========================================================================
# 20 MANDATORY BENCHMARK TEST CASES
# ===========================================================================

def test_01_btc_price_series(db: Session):
    """Case 1: BTC price series validation, storage, precision, and interval matching."""
    asset = get_or_create_market_asset(
        db, symbol="BTC-USD", canonical_name="Bitcoin", asset_type="crypto", quote_currency="USD"
    )
    provider = DeterministicMarketProvider()
    t0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    bars = provider.generate_series(
        symbol="BTC-USD", asset_id=asset.id, start_time=t0, count=5, interval="1m", start_price=60000.0, price_step=100.0
    )

    inserted, report = store_market_observations(db, bars, interval="1m", asset_id=asset.id)
    assert inserted == 5
    assert report.is_healthy is True
    assert report.total_observations == 5

    stored = get_asset_observations(db, asset.id, interval="1m")
    assert len(stored) == 5
    assert stored[0].close == 60100.0
    assert stored[-1].close == 60500.0


def test_02_eth_price_series(db: Session):
    """Case 2: ETH price series validation."""
    asset = get_or_create_market_asset(
        db, symbol="ETH-USD", canonical_name="Ethereum", asset_type="crypto", quote_currency="USD"
    )
    provider = DeterministicMarketProvider()
    t0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    bars = provider.generate_series(
        symbol="ETH-USD", asset_id=asset.id, start_time=t0, count=4, interval="5m", start_price=3000.0, price_step=-25.0
    )

    inserted, report = store_market_observations(db, bars, interval="5m", asset_id=asset.id)
    assert inserted == 4
    assert report.total_observations == 4
    stored = get_asset_observations(db, asset.id, interval="5m")
    assert stored[0].close == 2975.0


def test_03_equity_index_series(db: Session):
    """Case 3: Equity index series (S&P 500)."""
    asset = get_or_create_market_asset(
        db, symbol="SPX", canonical_name="S&P 500 Index", asset_type="equity_index", quote_currency="USD"
    )
    provider = DeterministicMarketProvider()
    t0 = datetime(2026, 9, 1, 14, 30, tzinfo=timezone.utc)
    bars = provider.generate_series(
        symbol="SPX", asset_id=asset.id, start_time=t0, count=6, interval="1h", start_price=5500.0, price_step=10.0
    )

    inserted, _ = store_market_observations(db, bars, interval="1h", asset_id=asset.id)
    assert inserted == 6
    stored = get_asset_observations(db, asset.id, interval="1h")
    assert len(stored) == 6
    assert stored[-1].close == 5560.0


def test_04_fx_series(db: Session):
    """Case 4: FX series (EUR/USD)."""
    asset = get_or_create_market_asset(
        db, symbol="EUR/USD", canonical_name="Euro / US Dollar", asset_type="forex", quote_currency="USD"
    )
    provider = DeterministicMarketProvider()
    t0 = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    bars = provider.generate_series(
        symbol="EUR/USD", asset_id=asset.id, start_time=t0, count=5, interval="15m", start_price=1.0850, price_step=0.0005
    )

    inserted, _ = store_market_observations(db, bars, interval="15m", asset_id=asset.id)
    assert inserted == 5
    stored = get_asset_observations(db, asset.id, interval="15m")
    assert stored[0].close == 1.0855


def test_05_commodity_series(db: Session):
    """Case 5: Commodity series (Brent Crude)."""
    asset = get_or_create_market_asset(
        db, symbol="BRENT", canonical_name="Brent Crude", asset_type="commodity", quote_currency="USD"
    )
    provider = DeterministicMarketProvider()
    t0 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    bars = provider.generate_series(
        symbol="BRENT", asset_id=asset.id, start_time=t0, count=5, interval="1h", start_price=78.0, price_step=0.5
    )

    inserted, _ = store_market_observations(db, bars, interval="1h", asset_id=asset.id)
    assert inserted == 5
    stored = get_asset_observations(db, asset.id, interval="1h")
    assert stored[-1].close == 80.5


def test_06_rate_series(db: Session):
    """Case 6: Rate series (US 10Y Treasury Yield)."""
    asset = get_or_create_market_asset(
        db, symbol="US10Y", canonical_name="US 10-Year Treasury Yield", asset_type="interest_rate", quote_currency="%"
    )
    provider = DeterministicMarketProvider()
    t0 = datetime(2026, 9, 1, 13, 0, tzinfo=timezone.utc)
    bars = provider.generate_series(
        symbol="US10Y", asset_id=asset.id, start_time=t0, count=5, interval="1d", start_price=3.90, price_step=0.02
    )

    inserted, _ = store_market_observations(db, bars, interval="1d", asset_id=asset.id)
    assert inserted == 5
    stored = get_asset_observations(db, asset.id, interval="1d")
    assert stored[0].close == 3.92


def test_07_duplicate_observation_deduplication(db: Session):
    """Case 7: Duplicate market observation deduplication without crash or double insertion."""
    asset = get_or_create_market_asset(
        db, symbol="BTC-DEDUP", canonical_name="Bitcoin Dedup Test", asset_type="crypto"
    )
    t = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
    obs1 = MarketObservationCreate(
        market_asset_id=asset.id, timestamp=t, open=50000.0, high=50100.0, low=49900.0, close=50050.0, source="FeedA", interval="1m"
    )
    obs2 = MarketObservationCreate(
        market_asset_id=asset.id, timestamp=t, open=50000.0, high=50100.0, low=49900.0, close=50050.0, source="FeedA", interval="1m"
    )

    inserted, report = store_market_observations(db, [obs1, obs2], interval="1m", asset_id=asset.id)
    assert inserted == 1
    assert report.duplicate_count == 1
    stored = get_asset_observations(db, asset.id, interval="1m")
    assert len(stored) == 1


def test_08_missing_candle_detection(db: Session):
    """Case 8: Missing candle detected and reported; ZERO synthetic candles fabricated."""
    asset = get_or_create_market_asset(
        db, symbol="GAP-TEST", canonical_name="Gap Test Asset", asset_type="equity"
    )
    t0 = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
    t_gap = t0 + timedelta(minutes=5)  # 4 missing 1m candles between minute 0 and minute 5

    obs1 = MarketObservationCreate(
        market_asset_id=asset.id, timestamp=t0, open=100.0, high=101.0, low=99.0, close=100.5, source="FeedA", interval="1m"
    )
    obs2 = MarketObservationCreate(
        market_asset_id=asset.id, timestamp=t_gap, open=102.0, high=103.0, low=101.5, close=102.5, source="FeedA", interval="1m"
    )

    inserted, report = store_market_observations(db, [obs1, obs2], interval="1m", asset_id=asset.id)
    assert inserted == 2
    assert report.missing_candles_count == 4
    assert report.gap_count == 1
    assert report.is_healthy is False
    # Verified: exactly 2 rows in database; no fabricated candles
    stored = get_asset_observations(db, asset.id, interval="1m")
    assert len(stored) == 2


def test_09_out_of_order_timestamp_sorting(db: Session):
    """Case 9: Out-of-order timestamps sorted chronologically and flagged as anomalies."""
    asset = get_or_create_market_asset(
        db, symbol="ORDER-TEST", canonical_name="Order Test Asset", asset_type="equity"
    )
    t1 = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 2, 10, 1, tzinfo=timezone.utc)

    obs_late = MarketObservationCreate(
        market_asset_id=asset.id, timestamp=t2, open=101.0, high=102.0, low=100.5, close=101.5, source="FeedA", interval="1m"
    )
    obs_early = MarketObservationCreate(
        market_asset_id=asset.id, timestamp=t1, open=100.0, high=101.0, low=99.5, close=100.5, source="FeedA", interval="1m"
    )

    # Ingest late first, then early
    inserted, report = store_market_observations(db, [obs_late, obs_early], interval="1m", asset_id=asset.id)
    assert inserted == 2
    assert report.out_of_order_count == 1
    stored = get_asset_observations(db, asset.id, interval="1m")
    # Verified stored in strictly increasing chronological order
    assert stored[0].timestamp == t1
    assert stored[1].timestamp == t2


def test_10_timezone_normalization():
    """Case 10: Timezone normalization to UTC from epoch, ISO strings, and local offsets."""
    # Milliseconds epoch
    dt_epoch_ms = BaseMarketDataProvider.normalize_timestamp(1788806400000)
    assert dt_epoch_ms.tzinfo == timezone.utc

    # Seconds epoch
    dt_epoch_s = BaseMarketDataProvider.normalize_timestamp(1788806400)
    assert dt_epoch_s.tzinfo == timezone.utc

    # ISO with offset +05:30
    iso_str = "2026-09-10T15:30:00+05:30"
    dt_offset = BaseMarketDataProvider.normalize_timestamp(iso_str)
    assert dt_offset.tzinfo == timezone.utc
    assert dt_offset.hour == 10  # 15:30 - 5:30 = 10:00 UTC

    # Naive string
    dt_naive = BaseMarketDataProvider.normalize_timestamp("2026-09-10 10:00:00")
    assert dt_naive.tzinfo == timezone.utc


def test_11_event_timestamp_alignment(db: Session, base_source_and_doc):
    """Case 11: Event timestamp alignment with nearest bar/candle."""
    _, doc = base_source_and_doc
    t_event = datetime(2026, 9, 3, 12, 30, 15, tzinfo=timezone.utc)
    event = ExtractedEvent(
        document_id=doc.id,
        event_type="inflation_report",
        event_title="US CPI Release September 2026",
        event_time=t_event,
        confidence=0.95,
        importance=0.85,
    )
    db.add(event)
    db.commit()

    asset = get_or_create_market_asset(db, symbol="BTC-ALIGN", canonical_name="Bitcoin Align", asset_type="crypto")
    provider = DeterministicMarketProvider()
    t_start = t_event - timedelta(minutes=15)
    bars = provider.generate_series(
        symbol="BTC-ALIGN", asset_id=asset.id, start_time=t_start, count=31, interval="1m", start_price=60000.0, price_step=10.0
    )
    store_market_observations(db, bars, interval="1m", asset_id=asset.id)

    corr = compute_event_market_correlation(db, event, asset, window_size="15m")
    assert corr is not None
    # Nearest bar to 12:30:15 is 12:30:00 (index 15 with step=10) -> 60000 + 16 * 10 = 60160.0
    assert corr.event_price == 60160.0


def test_12_pre_event_window_retrieval(db: Session, base_source_and_doc):
    """Case 12: Pre-event window price retrieval (T - W)."""
    _, doc = base_source_and_doc
    t_event = datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc)
    event = ExtractedEvent(
        document_id=doc.id,
        event_type="central_bank_decision",
        event_title="FOMC Rate Decision",
        event_time=t_event,
        confidence=0.98,
        importance=0.90,
    )
    db.add(event)
    db.commit()

    asset = get_or_create_market_asset(db, symbol="SPX-PRE", canonical_name="SPX Pre", asset_type="equity_index")
    provider = DeterministicMarketProvider()
    bars = provider.generate_series(
        symbol="SPX-PRE", asset_id=asset.id, start_time=t_event - timedelta(hours=1), count=13, interval="5m", start_price=5000.0, price_step=10.0
    )
    store_market_observations(db, bars, interval="5m", asset_id=asset.id)

    corr = compute_event_market_correlation(db, event, asset, window_size="1h")
    assert corr is not None
    assert corr.pre_event_price == 5010.0  # Bar 0 close


def test_13_post_event_window_retrieval(db: Session, base_source_and_doc):
    """Case 13: Post-event window price retrieval (T + W)."""
    _, doc = base_source_and_doc
    t_event = datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc)
    event = ExtractedEvent(
        document_id=doc.id,
        event_type="central_bank_decision",
        event_title="FOMC Post Rate",
        event_time=t_event,
        confidence=0.98,
        importance=0.90,
    )
    db.add(event)
    db.commit()

    asset = get_or_create_market_asset(db, symbol="SPX-POST", canonical_name="SPX Post", asset_type="equity_index")
    provider = DeterministicMarketProvider()
    # Generate bars covering T-1h to T+1h (25 5m bars)
    bars = provider.generate_series(
        symbol="SPX-POST", asset_id=asset.id, start_time=t_event - timedelta(hours=1), count=25, interval="5m", start_price=5000.0, price_step=10.0
    )
    store_market_observations(db, bars, interval="5m", asset_id=asset.id)

    corr = compute_event_market_correlation(db, event, asset, window_size="1h")
    assert corr is not None
    assert corr.post_event_price == 5250.0  # Bar 24 close (5000 + 25 * 10)


def test_14_return_calculation(db: Session, base_source_and_doc):
    """Case 14: Return calculation mathematically verified."""
    _, doc = base_source_and_doc
    t_event = datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc)
    event = ExtractedEvent(
        document_id=doc.id,
        event_type="gdp_release",
        event_title="Eurozone GDP Growth",
        event_time=t_event,
        confidence=0.90,
        importance=0.80,
    )
    db.add(event)
    db.commit()

    asset = get_or_create_market_asset(db, symbol="EUR-RET", canonical_name="EUR Return", asset_type="forex")
    # P_pre = 1.0000, P_post = 1.0200 -> Return should be exactly +2.0%
    b1 = MarketObservationCreate(
        market_asset_id=asset.id, timestamp=t_event - timedelta(minutes=5), open=1.0, high=1.01, low=0.99, close=1.0000, source="Feed", interval="1m"
    )
    b2 = MarketObservationCreate(
        market_asset_id=asset.id, timestamp=t_event + timedelta(minutes=5), open=1.015, high=1.025, low=1.01, close=1.0200, source="Feed", interval="1m"
    )
    store_market_observations(db, [b1, b2], interval="1m", asset_id=asset.id)

    corr = compute_event_market_correlation(db, event, asset, window_size="5m")
    assert corr is not None
    assert corr.return_percent == 2.0
    assert corr.absolute_change == 0.02


def test_15_volume_calculation(db: Session, base_source_and_doc):
    """Case 15: Volume calculation mathematically verified."""
    _, doc = base_source_and_doc
    t_event = datetime(2026, 9, 5, 11, 0, tzinfo=timezone.utc)
    event = ExtractedEvent(
        document_id=doc.id,
        event_type="oil_report",
        event_title="OPEC Meeting",
        event_time=t_event,
        confidence=0.92,
        importance=0.75,
    )
    db.add(event)
    db.commit()

    asset = get_or_create_market_asset(db, symbol="BRENT-VOL", canonical_name="Brent Vol", asset_type="commodity")
    # Vol_pre = 100, Vol_post = 250 -> Volume change = +150%
    b1 = MarketObservationCreate(
        market_asset_id=asset.id, timestamp=t_event - timedelta(minutes=15), open=80.0, high=81.0, low=79.0, close=80.0, volume=100.0, source="Feed", interval="5m"
    )
    b2 = MarketObservationCreate(
        market_asset_id=asset.id, timestamp=t_event + timedelta(minutes=15), open=82.0, high=83.0, low=81.5, close=82.0, volume=250.0, source="Feed", interval="5m"
    )
    store_market_observations(db, [b1, b2], interval="5m", asset_id=asset.id)

    corr = compute_event_market_correlation(db, event, asset, window_size="15m")
    assert corr is not None
    assert corr.volume_change == 150.0


def test_16_unavailable_market_data(db: Session, base_source_and_doc):
    """Case 16: Unavailable market data returns null; ZERO synthetic values fabricated."""
    _, doc = base_source_and_doc
    t_event = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
    event = ExtractedEvent(
        document_id=doc.id,
        event_type="trade_balance",
        event_title="Trade Deficit Report",
        event_time=t_event,
        confidence=0.85,
        importance=0.70,
    )
    db.add(event)
    db.commit()

    # Asset with NO observations stored
    asset = get_or_create_market_asset(db, symbol="EMPTY-ASSET", canonical_name="Empty Asset", asset_type="crypto")
    corr = compute_event_market_correlation(db, event, asset, window_size="1h")

    assert corr is not None
    assert corr.pre_event_price is None
    assert corr.post_event_price is None
    assert corr.return_percent is None
    assert corr.metadata_["data_available"] is False


def test_17_multiple_assets_around_one_event(db: Session, base_source_and_doc):
    """Case 17: Multiple assets correlated around a single event (US CPI -> BTC, SPX, US10Y)."""
    _, doc = base_source_and_doc
    t_event = datetime(2026, 9, 7, 12, 30, tzinfo=timezone.utc)
    event = ExtractedEvent(
        document_id=doc.id,
        event_type="inflation_report",
        event_title="US CPI Rose 3.2% in August",
        event_time=t_event,
        confidence=0.98,
        importance=0.90,
    )
    db.add(event)
    db.commit()

    # Create BTC, SPX, and US10Y
    btc = get_or_create_market_asset(db, symbol="BTC-USD", canonical_name="Bitcoin", asset_type="crypto")
    spx = get_or_create_market_asset(db, symbol="SPX", canonical_name="S&P 500", asset_type="equity_index")
    rate = get_or_create_market_asset(db, symbol="US10Y", canonical_name="US 10Y", asset_type="interest_rate")

    provider = DeterministicMarketProvider()
    for a, p in [(btc, 60000.0), (spx, 5500.0), (rate, 4.0)]:
        bars = provider.generate_series(
            symbol=a.symbol, asset_id=a.id, start_time=t_event - timedelta(hours=1), count=25, interval="5m", start_price=p, price_step=1.0
        )
        store_market_observations(db, bars, interval="5m", asset_id=a.id)

    correlations = correlate_event_across_assets(db, event.id, window_sizes=["1h"])
    assert len(correlations) >= 3
    symbols = [c.market_asset.symbol for c in correlations if c.market_asset]
    assert "BTC-USD" in symbols
    assert "SPX" in symbols
    assert "US10Y" in symbols
    for c in correlations:
        assert c.disclaimer == STANDARD_CORRELATION_DISCLAIMER


def test_18_one_asset_around_multiple_events(db: Session, base_source_and_doc):
    """Case 18: One asset correlated across multiple distinct events."""
    _, doc = base_source_and_doc
    asset = get_or_create_market_asset(db, symbol="BTC-MULTI", canonical_name="Bitcoin Multi", asset_type="crypto")

    # Ingest continuous bars
    t0 = datetime(2026, 9, 8, 8, 0, tzinfo=timezone.utc)
    provider = DeterministicMarketProvider()
    bars = provider.generate_series(
        symbol="BTC-MULTI", asset_id=asset.id, start_time=t0, count=60, interval="1m", start_price=60000.0, price_step=5.0
    )
    store_market_observations(db, bars, interval="1m", asset_id=asset.id)

    # Event 1 at 08:15
    e1 = ExtractedEvent(
        document_id=doc.id, event_type="cpi_release", event_title="Inflation Print", event_time=t0 + timedelta(minutes=15), confidence=0.9, importance=0.8
    )
    # Event 2 at 08:45
    e2 = ExtractedEvent(
        document_id=doc.id, event_type="central_bank_speech", event_title="Governor Speech", event_time=t0 + timedelta(minutes=45), confidence=0.85, importance=0.75
    )
    db.add_all([e1, e2])
    db.commit()

    c1 = compute_event_market_correlation(db, e1, asset, window_size="5m")
    c2 = compute_event_market_correlation(db, e2, asset, window_size="5m")

    assert c1 is not None and c2 is not None
    assert c1.event_id != c2.event_id
    assert c1.market_asset_id == c2.market_asset_id
    assert c1.return_percent is not None
    assert c2.return_percent is not None

    # Bidirectional navigation check
    events_for_asset = get_events_for_market_asset(db, asset.id)
    event_ids = [e["event_id"] for e in events_for_asset]
    assert str(e1.id) in event_ids
    assert str(e2.id) in event_ids


def test_19_event_with_no_relevant_market_data(db: Session, base_source_and_doc):
    """Case 19: Event with no relevant market data handles cleanly with empty results and no error."""
    _, doc = base_source_and_doc
    # An obscure local municipal event
    event = ExtractedEvent(
        document_id=doc.id,
        event_type="local_election",
        event_title="Small Village Council Election",
        event_time=datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc),
        confidence=0.80,
        importance=0.20,
    )
    db.add(event)
    db.commit()

    # Pass an empty asset list
    correlations = correlate_event_across_assets(db, event.id, window_sizes=["1h"], asset_ids=[])
    assert correlations == []


def test_20_provider_source_distinction(db: Session):
    """Case 20: Provider / source distinction preserved without overwriting."""
    asset = get_or_create_market_asset(db, symbol="ETH-PROV", canonical_name="Ethereum Multi-Provider", asset_type="crypto")
    t = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)

    # Provider A (Binance) reports 3000.0
    bar_a = MarketObservationCreate(
        market_asset_id=asset.id, timestamp=t, open=3000.0, high=3005.0, low=2995.0, close=3000.0, source="BinanceFeed", interval="1m"
    )
    # Provider B (Coinbase) reports 3001.0 for the exact same timestamp
    bar_b = MarketObservationCreate(
        market_asset_id=asset.id, timestamp=t, open=3001.0, high=3006.0, low=2996.0, close=3001.0, source="CoinbaseFeed", interval="1m"
    )

    store_market_observations(db, [bar_a], interval="1m", asset_id=asset.id)
    store_market_observations(db, [bar_b], interval="1m", asset_id=asset.id)

    stored = get_asset_observations(db, asset.id, interval="1m")
    # Both sources preserved side-by-side with distinct source tags
    assert len(stored) == 2
    sources = {s.source for s in stored}
    assert sources == {"BinanceFeed", "CoinbaseFeed"}
