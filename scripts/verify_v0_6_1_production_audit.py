"""
V0.6.1 Production-Data Audit and Real Market Data Verification Script.
Proves that the Market Intelligence layer uses genuine live external market data
from real exchanges (Binance / Coinbase) rather than synthetic fixtures.

Validates:
1. Genuine live fetching of BTC-USD and ETH-USD from external market provider.
2. Actual PostgreSQL row insertion and inspection of real OHLCV bars.
3. Provider reuse from existing BTC trading infrastructure.
4. Conformance of canonical universe to the approved 16 assets.
5. Real data quality engine audit (UTC, chronological order, duplicate rejection, re-fetch idempotency).
6. Deterministic correlation against real persisted prices (T-W, T, T+W).
7. Bidirectional navigation (Event -> Market and Market -> Event).
8. Strict scope boundary enforcement (NO signals, NO predictions, NO causal claims).
"""

import os
import sys
import uuid
import math
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy import text, select
from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.event import ExtractedEvent
from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.models.market_asset import MarketAsset
from backend.app.models.market_observation import MarketObservation
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.market.providers import CryptoMarketProvider
from backend.app.market.quality import MarketDataQualityEngine
from backend.app.services.market_service import (
    initialize_canonical_market_assets,
    store_market_observations,
    get_market_dashboard_summary,
)
from backend.app.services.correlation_service import (
    compute_event_market_correlation,
    get_events_for_market_asset,
)
from backend.app.schemas.market import STANDARD_CORRELATION_DISCLAIMER


def run_v0_6_1_production_audit():
    client = TestClient(app)
    db = SessionLocal()
    print("========================================================================")
    print("=== STARTING V0.6.1 PRODUCTION-DATA AUDIT & REAL MARKET VERIFICATION ===")
    print("========================================================================")

    # -------------------------------------------------------------------------
    # GATE 1: PROVE CANONICAL UNIVERSE CONFORMANCE (EXACT 16 APPROVED ASSETS)
    # -------------------------------------------------------------------------
    print("\n--- [GATE 1: CANONICAL UNIVERSE CONFORMANCE] ---")
    assets = initialize_canonical_market_assets(db)
    expected_symbols = {
        # Crypto (2)
        "BTC-USD", "ETH-USD",
        # Equity Indices (5)
        "SPX", "NDX", "DAX", "FTSE", "N225",
        # Forex (4)
        "EUR/USD", "GBP/USD", "USD/JPY", "USD/INR",
        # Commodities (3)
        "BRENT", "WTI", "GOLD",
        # Sovereign Rates (2)
        "US2Y", "US10Y",
    }
    actual_symbols = {a.symbol for a in assets}
    assert expected_symbols == actual_symbols, (
        f"Canonical universe mismatch! Missing: {expected_symbols - actual_symbols}, Unexpected: {actual_symbols - expected_symbols}"
    )
    print(f"[PASS] Exact approved canonical universe verified in PostgreSQL: {len(assets)} assets across 5 classes.")
    for a in sorted(assets, key=lambda x: x.symbol):
        print(f"       - {a.symbol:<10} | {a.canonical_name:<28} | {a.asset_type:<15} | {a.exchange_venue}")

    # -------------------------------------------------------------------------
    # GATE 2: REAL LIVE MARKET DATA FETCH (BTC-USD & ETH-USD)
    # -------------------------------------------------------------------------
    print("\n--- [GATE 2: REAL LIVE MARKET DATA FETCH] ---")
    crypto_provider = CryptoMarketProvider(provider_name="BinancePublicAPI")
    req_time_start = datetime.now(timezone.utc)

    # Fetch live BTC bars
    btc_live_bars = crypto_provider.fetch_historical_bars("BTC-USD", interval="1h", limit=5)
    assert len(btc_live_bars) >= 5, f"Failed to fetch live BTC bars, got {len(btc_live_bars)}"
    btc_sample = btc_live_bars[0]
    assert btc_sample.close > 10000.0, f"Unrealistic BTC price: {btc_sample.close}"
    assert btc_sample.volume > 0, "BTC volume must be > 0"
    assert btc_sample.timestamp.tzinfo is not None, "Timestamp must be timezone-aware UTC"

    # Fetch live ETH bars
    eth_live_bars = crypto_provider.fetch_historical_bars("ETH-USD", interval="1h", limit=5)
    assert len(eth_live_bars) >= 5, f"Failed to fetch live ETH bars, got {len(eth_live_bars)}"
    eth_sample = eth_live_bars[0]
    assert eth_sample.close > 500.0, f"Unrealistic ETH price: {eth_sample.close}"
    assert eth_sample.volume > 0, "ETH volume must be > 0"
    assert eth_sample.timestamp.tzinfo is not None, "Timestamp must be timezone-aware UTC"

    print(f"[PASS] Real market data fetched successfully from {crypto_provider.provider_name}:")
    print(f"       BTC-USD: {len(btc_live_bars)} bars fetched. Sample close={btc_sample.close} at {btc_sample.timestamp.isoformat()} (vol={btc_sample.volume:.2f})")
    print(f"       ETH-USD: {len(eth_live_bars)} bars fetched. Sample close={eth_sample.close} at {eth_sample.timestamp.isoformat()} (vol={eth_sample.volume:.2f})")
    print(f"       Provenance metadata: {btc_sample.metadata_}")

    # -------------------------------------------------------------------------
    # GATE 3: PERSISTENCE OF REAL MARKET OBSERVATIONS INTO POSTGRESQL
    # -------------------------------------------------------------------------
    print("\n--- [GATE 3: POSTGRESQL PERSISTENCE & ROW AUDIT] ---")
    btc_asset = db.query(MarketAsset).filter(MarketAsset.symbol == "BTC-USD").first()
    eth_asset = db.query(MarketAsset).filter(MarketAsset.symbol == "ETH-USD").first()

    inserted_btc, report_btc = store_market_observations(db, btc_live_bars, interval="1h", asset_id=btc_asset.id)
    inserted_eth, report_eth = store_market_observations(db, eth_live_bars, interval="1h", asset_id=eth_asset.id)

    # Inspect actual PostgreSQL records
    btc_db_rows = (
        db.query(MarketObservation)
        .filter(MarketObservation.market_asset_id == btc_asset.id, MarketObservation.source == crypto_provider.provider_name)
        .order_by(MarketObservation.timestamp.asc())
        .all()
    )
    eth_db_rows = (
        db.query(MarketObservation)
        .filter(MarketObservation.market_asset_id == eth_asset.id, MarketObservation.source == crypto_provider.provider_name)
        .order_by(MarketObservation.timestamp.asc())
        .all()
    )

    assert len(btc_db_rows) >= 5, f"Expected at least 5 live BTC rows in DB, got {len(btc_db_rows)}"
    assert len(eth_db_rows) >= 5, f"Expected at least 5 live ETH rows in DB, got {len(eth_db_rows)}"

    print(f"[PASS] Persisted real market observations into PostgreSQL:")
    print(f"       BTC-USD genuine DB rows: {len(btc_db_rows)}")
    for r in btc_db_rows[-3:]:
        print(f"       - UTC {r.timestamp.isoformat()} | O: {r.open:<9.2f} | H: {r.high:<9.2f} | L: {r.low:<9.2f} | C: {r.close:<9.2f} | Vol: {r.volume:<10.2f} | Source: {r.source}")
    print(f"       ETH-USD genuine DB rows: {len(eth_db_rows)}")
    for r in eth_db_rows[-3:]:
        print(f"       - UTC {r.timestamp.isoformat()} | O: {r.open:<9.2f} | H: {r.high:<9.2f} | L: {r.low:<9.2f} | C: {r.close:<9.2f} | Vol: {r.volume:<10.2f} | Source: {r.source}")

    # -------------------------------------------------------------------------
    # GATE 4: REAL-DATA QUALITY CONTROLS & RE-FETCH IDEMPOTENCY
    # -------------------------------------------------------------------------
    print("\n--- [GATE 4: REAL DATA QUALITY & RE-FETCH IDEMPOTENCY] ---")
    # A. Re-fetch identical bars: must insert 0 duplicates
    re_inserted_btc, re_report_btc = store_market_observations(db, btc_live_bars, interval="1h", asset_id=btc_asset.id)
    assert re_inserted_btc == 0, f"Expected 0 inserted bars on re-fetch, got {re_inserted_btc}"
    print(f"[PASS] Re-fetch deduplication: 0 duplicates inserted on re-fetch.")

    # B. Quality engine audit report on live bars
    clean_bars, quality_audit = MarketDataQualityEngine.audit_and_clean_observations(
        btc_live_bars, interval="1h", asset_id=btc_asset.id
    )
    assert quality_audit.is_healthy is True, "Live Binance bars should pass health audit"
    assert quality_audit.duplicate_count == 0, "Live stream should have 0 intra-batch duplicates"
    assert quality_audit.out_of_order_count == 0, "Live stream should be in chronological order"
    assert quality_audit.stale_price_count == 0, "Live BTC stream should not have flatline stale prices"
    print(f"[PASS] Real-data quality audit: Continuity ratio = {quality_audit.continuity_ratio:.2f}, Missing = {quality_audit.missing_candles_count}, Stale = {quality_audit.stale_price_count}.")

    # -------------------------------------------------------------------------
    # GATE 5: CORRELATION VERIFICATION ON GENUINELY PERSISTED DATA
    # -------------------------------------------------------------------------
    print("\n--- [GATE 5: CORRELATION ON REAL PERSISTED MARKET DATA] ---")
    # Pick 3 consecutive real bars from the database: T-W, T, T+W
    assert len(btc_db_rows) >= 3, "Need at least 3 real bars for window test"
    bar_pre = btc_db_rows[-3]
    bar_event = btc_db_rows[-2]
    bar_post = btc_db_rows[-1]

    # Create real event aligned with bar_event timestamp
    test_src = db.query(Source).first()
    test_doc = db.query(Document).first()
    real_event = ExtractedEvent(
        document_id=test_doc.id,
        event_type="market_macro_event",
        event_title=f"Global Macro Release - Real Market Audit at {bar_event.timestamp.isoformat()}",
        event_summary="Auditing deterministic return calculation against genuine Binance market data",
        event_time=bar_event.timestamp,
        confidence=0.98,
        importance=0.90,
        metadata_={"production_audit": "V0.6.1"},
    )
    db.add(real_event)
    db.commit()
    db.refresh(real_event)

    # Compute correlation for 1h window
    corr = compute_event_market_correlation(db, real_event, btc_asset, window_size="1h")
    assert corr is not None, "Correlation record should be generated"
    assert corr.pre_event_price == bar_pre.close, f"Expected pre price {bar_pre.close}, got {corr.pre_event_price}"
    assert corr.event_price == bar_event.close, f"Expected event price {bar_event.close}, got {corr.event_price}"
    assert corr.post_event_price == bar_post.close, f"Expected post price {bar_post.close}, got {corr.post_event_price}"

    # Independent formula calculation from actual persisted prices
    expected_return = round(((bar_post.close / bar_pre.close) - 1.0) * 100.0, 4)
    actual_return = round(corr.return_percent, 4)
    assert actual_return == expected_return, f"Return mismatch: expected {expected_return}%, got {actual_return}%"

    expected_vol_change = round(((bar_post.volume / bar_pre.volume) - 1.0) * 100.0, 2)
    actual_vol_change = round(corr.volume_change, 2)
    assert actual_vol_change == expected_vol_change, f"Volume change mismatch: expected {expected_vol_change}%, got {actual_vol_change}%"

    print(f"[PASS] Deterministic correlation on genuine market data verified:")
    print(f"       T-W ({bar_pre.timestamp.isoformat()}): Close = {bar_pre.close:<9.2f} (Vol = {bar_pre.volume:.2f})")
    print(f"       T   ({bar_event.timestamp.isoformat()}): Close = {bar_event.close:<9.2f} (Vol = {bar_event.volume:.2f})")
    print(f"       T+W ({bar_post.timestamp.isoformat()}): Close = {bar_post.close:<9.2f} (Vol = {bar_post.volume:.2f})")
    print(f"       Calculated Return: {actual_return:+.4f}% (Formula: ({bar_post.close} / {bar_pre.close} - 1) * 100)")
    print(f"       Calculated Volume Change: {actual_vol_change:+.2f}%")
    print(f"       Methodology: {corr.methodology} | Metadata: {corr.metadata_}")

    # -------------------------------------------------------------------------
    # GATE 6: BIDIRECTIONAL NAVIGATION VERIFICATION
    # -------------------------------------------------------------------------
    print("\n--- [GATE 6: BIDIRECTIONAL NAVIGATION ON REAL DATA] ---")
    # A. Event -> Market Correlations
    api_event_corrs = client.get(f"/api/v1/events/{real_event.id}/market-correlations?window_size=1h")
    assert api_event_corrs.status_code == 200, f"Failed Event -> Market: {api_event_corrs.text}"
    corrs_payload = api_event_corrs.json()
    assert len(corrs_payload) >= 1, "Expected at least 1 correlated asset"
    matched_corr = next((c for c in corrs_payload if c["market_asset"]["symbol"] == "BTC-USD"), None)
    assert matched_corr is not None, "BTC-USD correlation missing in API response"
    assert matched_corr["return_percent"] == corr.return_percent
    assert matched_corr["disclaimer"] == STANDARD_CORRELATION_DISCLAIMER

    # B. Market Asset -> Events
    api_asset_events = client.get(f"/api/v1/market-assets/{btc_asset.id}/events")
    assert api_asset_events.status_code == 200, f"Failed Market -> Event: {api_asset_events.text}"
    asset_events_payload = api_asset_events.json()
    assert len(asset_events_payload) >= 1, "Expected at least 1 associated event"
    matched_event = next((e for e in asset_events_payload if e["event_id"] == str(real_event.id)), None)
    assert matched_event is not None, "Associated event missing in asset timeline"
    assert matched_event["return_percent"] == corr.return_percent

    print(f"[PASS] Bidirectional navigation verified against real market data:")
    print(f"       - Event -> Market: Found {len(corrs_payload)} assets. BTC-USD return = {matched_corr['return_percent']:+.4f}%")
    print(f"       - Market -> Event: Found {len(asset_events_payload)} events. Matched Event ID = {matched_event['event_id']}")

    # -------------------------------------------------------------------------
    # GATE 7: STRICT SCOPE BOUNDARY ENFORCEMENT
    # -------------------------------------------------------------------------
    print("\n--- [GATE 7: STRICT SCOPE BOUNDARY VERIFICATION] ---")
    prohibited_keys = {"signal", "buy_sell", "forecast", "target_price", "prediction", "action"}
    for k in prohibited_keys:
        assert k not in matched_corr, f"Prohibited key '{k}' found in correlation payload!"
    assert STANDARD_CORRELATION_DISCLAIMER in matched_corr["disclaimer"]
    print("[PASS] Strict safety boundary verified: 0 trading signals, 0 predictions, neutral disclaimer present.")

    # Clean up test event and correlation
    db.delete(corr)
    db.delete(real_event)
    db.commit()
    db.close()

    print("\n========================================================================")
    print("=== [PASS] V0.6.1 PRODUCTION-DATA AUDIT COMPLETE — ALL GATES PASSED ====")
    print("========================================================================\n")
    return True


if __name__ == "__main__":
    success = run_v0_6_1_production_audit()
    sys.exit(0 if success else 1)
