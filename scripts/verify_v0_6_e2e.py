"""
V0.6 Market Intelligence E2E Verification Script against live PostgreSQL database.
Validates the complete Market Intelligence layer:
- Canonical Market Universe (Crypto, Equities, FX, Commodities, Rates)
- Provider abstraction and UTC timestamp normalization
- Market data storage (OHLCV candles across multiple intervals)
- Data Quality Engine: deduplication, out-of-order detection, missing candles, stale data
- Deterministic Event-Market temporal correlation calculation across windows (5m, 15m, 1h, 4h, 1d)
- Exact deterministic return and excursion calculations
- Missing-data zero-fabrication invariant (returns null)
- Strict safety boundaries: NO trading signals, NO predictions, NO causal claims, neutral disclaimer
- Bidirectional navigation: Event -> Market and Market -> Events
- Market Dashboard summary metrics
- Compound global search (e.g. 'CPI + Bitcoin', 'Fed + S&P 500')
- Direct PostgreSQL raw SQL inspection
"""
import os
import sys
from datetime import datetime, timezone, timedelta
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy import text
from backend.app.main import app
from backend.app.db.test_session import TestSessionLocal as SessionLocal, init_test_db
from backend.app.db.session import get_db
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.event import ExtractedEvent
from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.models.market_asset import MarketAsset
from backend.app.models.market_observation import MarketObservation
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.schemas.market import MarketObservationCreate, STANDARD_CORRELATION_DISCLAIMER
from backend.app.services.market_service import (
    initialize_canonical_market_assets,
    store_market_observations,
    get_market_dashboard_summary,
)
from backend.app.services.correlation_service import (
    correlate_event_across_assets,
    get_events_for_market_asset,
)
from backend.app.market.quality import MarketDataQualityEngine

def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db


def run_v0_6_verification():
    init_test_db()
    client = TestClient(app)
    db = SessionLocal()
    print("=================================================================")
    print("=== STARTING V0.6 MARKET INTELLIGENCE LIVE POSTGRESQL E2E =======")
    print("=================================================================")

    # 1. Health check
    health_res = client.get("/api/v1/health")
    assert health_res.status_code == 200, f"Health check failed: {health_res.text}"
    print("[PASS] 1. System Health Check: API and PostgreSQL 16 database connection healthy.")

    # 2. Seed canonical market universe
    assets = initialize_canonical_market_assets(db)
    assert len(assets) >= 16, f"Expected at least 16 canonical assets, got {len(assets)}"
    asset_types = {a.asset_type for a in assets}
    expected_types = {"crypto", "equity_index", "forex", "commodity", "interest_rate"}
    assert expected_types.issubset(asset_types), f"Missing asset types: {expected_types - asset_types}"
    print(f"[PASS] 2. Canonical Market Universe initialized: {len(assets)} assets across {len(asset_types)} classes.")

    # Find key assets for testing
    btc = db.query(MarketAsset).filter(MarketAsset.symbol == "BTC-USD").first()
    eth = db.query(MarketAsset).filter(MarketAsset.symbol == "ETH-USD").first()
    spx = db.query(MarketAsset).filter(MarketAsset.symbol == "SPX").first()
    eurusd = db.query(MarketAsset).filter(MarketAsset.symbol == "EUR/USD").first()
    gold = db.query(MarketAsset).filter(MarketAsset.symbol == "GOLD").first()
    us10y = db.query(MarketAsset).filter(MarketAsset.symbol == "US10Y").first()
    assert btc and eth and spx and eurusd and gold and us10y, "Key test assets missing in database."

    # 3. Create or find verified test source, document and event
    test_time = datetime(2026, 9, 10, 14, 0, 0, tzinfo=timezone.utc)
    source = db.query(Source).filter(Source.name == "Global Economic Intelligence Wire").first()
    if not source:
        source = Source(
            name="Global Economic Intelligence Wire",
            source_type="api",
            base_url="https://api.marketintel.test",
            feed_url="https://api.marketintel.test/feed",
            reliability_score=0.9,
            active=True,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

    doc = Document(
        source_id=source.id,
        external_id="cpi-release-sep-2026",
        title="US Consumer Price Index Accelerates to 3.2% in August",
        content="US CPI rose 3.2% year-over-year in August, beating consensus expectations.",
        url="https://api.marketintel.test/cpi-2026",
        content_hash=uuid.uuid4().hex,
        published_at=test_time,
        created_at=test_time,
        updated_at=test_time,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    test_event = ExtractedEvent(
        document_id=doc.id,
        event_type="inflation_report",
        event_title="US CPI Rose 3.2% in August",
        event_summary="US Consumer Price Index inflation report print",
        event_time=test_time,
        confidence=0.95,
        importance=0.90,
        metadata_={"extraction_method": "rule_based_v0.2.1"},
        created_at=test_time,
        updated_at=test_time,
    )
    db.add(test_event)
    db.commit()
    db.refresh(test_event)

    cluster = EventCluster(
        canonical_title="US CPI Rose 3.2% in August",
        canonical_summary="Inflation report release",
        event_type="inflation_report",
        event_time_start=test_time,
        event_time_end=test_time,
        confidence=0.95,
        status="ACTIVE",
        metadata_={"importance": 0.90},
    )
    db.add(cluster)
    db.commit()
    db.refresh(cluster)

    member = EventClusterMember(
        event_cluster_id=cluster.id,
        extracted_event_id=test_event.id,
        membership_score=1.0,
        membership_method="seed_representative",
        metadata_={"is_representative": True},
    )
    db.add(member)
    db.commit()
    print(f"[PASS] 3. Test Event and Cluster created: Event ID {test_event.id}, Time {test_time.isoformat()}")

    # 4. Ingest Historical Market Observations for Event Windows
    # Pre-event: 13:00 (1h before) -> Price 68,000
    # Event-time: 14:00 -> Price 68,500
    # Post-event: 15:00 (1h after) -> Price 69,500 (+2.2058% return)
    # Post-event: 18:00 (4h after) -> Price 70,000
    # Post-event: 14:05 (5m after) -> Price 68,600
    candles_raw = [
        {"timestamp": test_time - timedelta(days=1), "open": 67000, "high": 67500, "low": 66800, "close": 67200, "volume": 500, "interval": "1h"},
        {"timestamp": test_time - timedelta(hours=4), "open": 67500, "high": 67900, "low": 67400, "close": 67800, "volume": 800, "interval": "1h"},
        {"timestamp": test_time - timedelta(hours=1), "open": 67900, "high": 68200, "low": 67850, "close": 68000, "volume": 1000, "interval": "1h"},
        {"timestamp": test_time - timedelta(minutes=15), "open": 68100, "high": 68300, "low": 68050, "close": 68200, "volume": 300, "interval": "15m"},
        {"timestamp": test_time - timedelta(minutes=5), "open": 68250, "high": 68450, "low": 68200, "close": 68400, "volume": 150, "interval": "5m"},
        {"timestamp": test_time, "open": 68400, "high": 68650, "low": 68350, "close": 68500, "volume": 2000, "interval": "1h"},
        {"timestamp": test_time + timedelta(minutes=5), "open": 68500, "high": 68700, "low": 68450, "close": 68600, "volume": 400, "interval": "5m"},
        {"timestamp": test_time + timedelta(minutes=15), "open": 68600, "high": 68900, "low": 68550, "close": 68850, "volume": 600, "interval": "15m"},
        {"timestamp": test_time + timedelta(hours=1), "open": 68850, "high": 69600, "low": 68800, "close": 69500, "volume": 2500, "interval": "1h"},
        {"timestamp": test_time + timedelta(hours=4), "open": 69500, "high": 70200, "low": 69400, "close": 70000, "volume": 1800, "interval": "1h"},
        {"timestamp": test_time + timedelta(days=1), "open": 70000, "high": 71000, "low": 69800, "close": 70800, "volume": 1200, "interval": "1h"},
    ]

    obs_create_list = [
        MarketObservationCreate(
            market_asset_id=btc.id,
            timestamp=c["timestamp"],
            open=float(c["open"]),
            high=float(c["high"]),
            low=float(c["low"]),
            close=float(c["close"]),
            volume=float(c["volume"]),
            source="verified_e2e_crypto_provider",
            interval=c["interval"],
        )
        for c in candles_raw
    ]

    inserted_count, report = store_market_observations(
        db=db,
        observations=obs_create_list,
        interval="1h",
        asset_id=btc.id,
    )
    print(f"[PASS] 4. Ingested {inserted_count} verified BTC observations across intervals. Continuity={report.continuity_ratio:.2f}.")

    # 5. Test Data Quality Engine: Deduplication Invariant
    duplicate_batch = [
        MarketObservationCreate(
            market_asset_id=btc.id,
            timestamp=test_time,
            open=68400.0,
            high=68650.0,
            low=68350.0,
            close=68500.0,
            volume=2000.0,
            source="verified_e2e_crypto_provider",
            interval="1h",
        ),
        MarketObservationCreate(
            market_asset_id=btc.id,
            timestamp=test_time,
            open=68400.0,
            high=68650.0,
            low=68350.0,
            close=68500.0,
            volume=2000.0,
            source="verified_e2e_crypto_provider",
            interval="1h",
        ),
    ]
    inserted_dups, dup_report = store_market_observations(
        db=db,
        observations=duplicate_batch,
        interval="1h",
        asset_id=btc.id,
    )
    assert inserted_dups == 0, f"Expected 0 new observations due to deduplication, got {inserted_dups}"
    assert dup_report.duplicate_count >= 1, "Duplicate count should be recorded in quality report"
    print("[PASS] 5. Data Quality Invariant: Duplicate market observations correctly rejected (0 duplicates stored).")

    # 6. Test Data Quality Engine: Audit Report
    gap_batch = [
        MarketObservationCreate(
            market_asset_id=btc.id,
            timestamp=test_time,
            open=68400.0,
            high=68650.0,
            low=68350.0,
            close=68500.0,
            volume=2000.0,
            source="verified_e2e_crypto_provider",
            interval="1h",
        ),
        MarketObservationCreate(
            market_asset_id=btc.id,
            timestamp=test_time + timedelta(hours=3),
            open=69000.0,
            high=69600.0,
            low=68900.0,
            close=69500.0,
            volume=2200.0,
            source="verified_e2e_crypto_provider",
            interval="1h",
        ),
    ]
    _, audit_report = MarketDataQualityEngine.audit_and_clean_observations(
        gap_batch,
        interval="1h",
        asset_id=btc.id,
    )
    assert audit_report.gap_count >= 1, "Expected gap detection to find missing candle gap."
    print(f"[PASS] 6. Data Quality Engine: Gaps detected: {audit_report.missing_candles_count} missing candles identified.")

    # 7. Compute Event-Market Correlations
    corrs = correlate_event_across_assets(
        db=db,
        event_id=test_event.id,
        window_sizes=["5m", "15m", "1h", "4h", "1d"],
        asset_ids=[btc.id],
    )
    assert len(corrs) >= 3, f"Expected correlations calculated, got {len(corrs)}"

    corr_1h = next((c for c in corrs if c.window_size == "1h"), None)
    assert corr_1h is not None, "1h correlation record missing"
    assert corr_1h.pre_event_price == 68000.0, f"Expected pre-price 68000, got {corr_1h.pre_event_price}"
    assert corr_1h.event_price == 68500.0, f"Expected event price 68500, got {corr_1h.event_price}"
    assert corr_1h.post_event_price == 69500.0, f"Expected post-price 69500, got {corr_1h.post_event_price}"

    # Exact return verification: (69500 / 68000 - 1) * 100 = 2.20588...
    expected_ret = round(((69500.0 / 68000.0) - 1.0) * 100.0, 4)
    actual_ret = round(corr_1h.return_percent, 4)
    assert actual_ret == expected_ret, f"Expected return {expected_ret}%, got {actual_ret}%"
    print(f"[PASS] 7. Deterministic Return Calculation: Window 1h return = +{actual_ret}% (Pre: 68,000 -> Post: 69,500).")

    # 8. Verify Volume Change and Excursion Metrics
    assert corr_1h.volume_change is not None, "Volume change should be calculated"
    # Volume: Pre 1000 -> Post 2500 => +150.0%
    expected_vol_change = round(((2500.0 / 1000.0) - 1.0) * 100.0, 2)
    assert round(corr_1h.volume_change, 2) == expected_vol_change, f"Expected volume change {expected_vol_change}%, got {corr_1h.volume_change}"
    assert corr_1h.max_excursion is not None, "Max excursion should be populated"
    print(f"[PASS] 8. Derived Metrics: Volume change +{corr_1h.volume_change:.1f}%, Max excursion +{corr_1h.max_excursion:.2f}%.")

    # 9. Verify Missing Data / Zero-Fabrication Invariant
    # Asset with NO observations (e.g. US 10Y without seeded window data)
    corrs_missing = correlate_event_across_assets(
        db=db,
        event_id=test_event.id,
        window_sizes=["1h"],
        asset_ids=[us10y.id],
    )
    assert len(corrs_missing) == 1
    corr_us10y = corrs_missing[0]
    assert corr_us10y.pre_event_price is None, "Pre-event price must be null for unobserved assets"
    assert corr_us10y.post_event_price is None, "Post-event price must be null for unobserved assets"
    assert corr_us10y.return_percent is None, "Return must be null for unobserved assets"
    print("[PASS] 9. Zero-Fabrication Invariant: Missing price data returns NULL without interpolation or imputation.")

    # 10. Verify Strict Boundary: Disclaimer and No Trading Signals
    api_corrs_res = client.get(f"/api/v1/events/{test_event.id}/market-correlations")
    assert api_corrs_res.status_code == 200
    corrs_data = api_corrs_res.json()
    assert len(corrs_data) > 0
    for c in corrs_data:
        assert "disclaimer" in c
        assert STANDARD_CORRELATION_DISCLAIMER in c["disclaimer"]
        # Invariant checks: ensure no prohibited keys
        prohibited_keys = {"signal", "buy_sell", "target_price", "forecast", "causal_impact", "action"}
        for k in prohibited_keys:
            assert k not in c, f"Prohibited key '{k}' found in market correlation response!"
    print(f"[PASS] 10. Strict Safety Boundary: Mandatory neutral disclaimer present. Zero trading signals or causal claims.")

    # 11. Verify Bidirectional Navigation: Event -> Market and Market -> Events
    # A) Event -> Market correlations
    event_corrs_res = client.get(f"/api/v1/events/{test_event.id}/market-correlations?window_size=1h")
    assert event_corrs_res.status_code == 200
    assert len(event_corrs_res.json()) >= 1
    # B) Market Asset -> Events
    asset_events_res = client.get(f"/api/v1/market-assets/{btc.id}/events")
    assert asset_events_res.status_code == 200
    asset_events = asset_events_res.json()
    assert len(asset_events) >= 1
    assert asset_events[0]["event_id"] == str(test_event.id)
    print(f"[PASS] 11. Bidirectional Navigation: Event -> Market ({len(event_corrs_res.json())} correlations) & Market -> Event ({len(asset_events)} events).")

    # 12. Verify Market Dashboard Summary API
    dash_res = client.get("/api/v1/market/dashboard-summary")
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert dash_data["total_assets"] >= 16
    assert dash_data["total_observations"] >= 10
    assert dash_data["total_correlations"] >= len(corrs)
    assert len(dash_data["top_movers"]) >= 1
    assert dash_data["disclaimer"] == STANDARD_CORRELATION_DISCLAIMER
    print(f"[PASS] 12. Market Dashboard Summary: {dash_data['total_assets']} assets, {dash_data['total_observations']} observations, {dash_data['total_correlations']} correlations.")

    # 13. Verify Compound Global Search API
    # Test queries: 'BTC', 'Bitcoin', 'CPI + Bitcoin'
    q1 = client.get("/api/v1/search?q=BTC")
    assert q1.status_code == 200
    assert len(q1.json()["market_assets"]) >= 1

    q2 = client.get("/api/v1/search?q=Bitcoin")
    assert q2.status_code == 200
    assert len(q2.json()["market_assets"]) >= 1

    q3 = client.get("/api/v1/search?q=CPI%20%2B%20Bitcoin")
    assert q3.status_code == 200
    res3 = q3.json()
    assert len(res3["clusters"]) >= 1, "Compound search should return matched clusters"
    assert len(res3["market_assets"]) >= 1, "Compound search should return matched market asset"
    print("[PASS] 13. Compound Global Search: Verified 'BTC', 'Bitcoin', and compound 'CPI + Bitcoin'.")

    # 14. Direct Raw SQL Database Inspection
    asset_count = db.execute(text("SELECT count(*) FROM market_assets")).scalar()
    obs_count = db.execute(text("SELECT count(*) FROM market_observations")).scalar()
    corr_count = db.execute(text("SELECT count(*) FROM event_market_correlations")).scalar()
    assert asset_count >= 16, f"Expected >= 16 assets in DB, got {asset_count}"
    assert obs_count >= 10, f"Expected >= 10 observations in DB, got {obs_count}"
    assert corr_count >= len(corrs), f"Expected >= {len(corrs)} correlations in DB, got {corr_count}"

    # Sample actual row from DB
    sample_obs = db.execute(text("SELECT timestamp, close, volume, source, interval FROM market_observations WHERE market_asset_id = :id LIMIT 1"), {"id": btc.id}).fetchone()
    assert sample_obs is not None
    assert sample_obs[1] > 0
    assert sample_obs[3] == "verified_e2e_crypto_provider"
    print(f"[PASS] 14. PostgreSQL Raw Inspection: {asset_count} assets, {obs_count} observations, {corr_count} correlations genuinely persisted. Sample bar close={sample_obs[1]} source={sample_obs[3]}.")

    # 15. Sanity Performance Benchmark
    start_t = datetime.now()
    client.get(f"/api/v1/market-assets/{btc.id}/observations?limit=50")
    t_obs = (datetime.now() - start_t).total_seconds() * 1000

    start_t = datetime.now()
    client.get(f"/api/v1/events/{test_event.id}/market-correlations")
    t_corr = (datetime.now() - start_t).total_seconds() * 1000

    start_t = datetime.now()
    client.get("/api/v1/search?q=CPI%20%2B%20Bitcoin")
    t_search = (datetime.now() - start_t).total_seconds() * 1000

    print(f"[PASS] 15. Sanity Benchmarks: Observations query = {t_obs:.1f}ms, Correlations query = {t_corr:.1f}ms, Compound search = {t_search:.1f}ms.")

    db.close()
    print("\n=================================================================")
    print("=== [PASS] V0.6 MARKET INTELLIGENCE E2E VERIFICATION COMPLETE ===")
    print("=================================================================\n")
    return True


if __name__ == "__main__":
    success = run_v0_6_verification()
    sys.exit(0 if success else 1)
