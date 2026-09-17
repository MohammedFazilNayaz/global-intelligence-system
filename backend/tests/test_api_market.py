import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.market_asset import MarketAsset
from backend.app.models.market_observation import MarketObservation
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.models.event import ExtractedEvent
from backend.app.models.document import Document
from backend.app.models.source import Source
from backend.app.schemas.market import STANDARD_CORRELATION_DISCLAIMER
from backend.app.market.providers import DeterministicMarketProvider
from backend.app.services.market_service import store_market_observations, initialize_canonical_market_assets
from backend.app.services.correlation_service import compute_event_market_correlation


from backend.app.db.session import SessionLocal


@pytest.fixture
def seeded_market_api_data(db_session):
    """Seed sample market assets, observations, and events for API testing."""
    db = db_session
    try:
        # 1. Initialize universe
        initialize_canonical_market_assets(db)
        btc = db.query(MarketAsset).filter(MarketAsset.symbol == "BTC-USD").first()
        spx = db.query(MarketAsset).filter(MarketAsset.symbol == "SPX").first()

        # 2. Add observations
        t0 = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
        provider = DeterministicMarketProvider()
        bars_btc = provider.generate_series(
            symbol="BTC-USD", asset_id=btc.id, start_time=t0, count=30, interval="1m", start_price=60000.0, price_step=50.0
        )
        bars_spx = provider.generate_series(
            symbol="SPX", asset_id=spx.id, start_time=t0, count=30, interval="1m", start_price=5500.0, price_step=5.0
        )
        store_market_observations(db, bars_btc, interval="1m", asset_id=btc.id)
        store_market_observations(db, bars_spx, interval="1m", asset_id=spx.id)

        # 3. Add Source, Document, Event
        source = Source(
            name="API Market Source",
            source_type="rss",
            base_url="https://marketnews.com",
            feed_url="https://marketnews.com/feed.xml",
            active=True,
        )
        db.add(source)
        db.commit()

        doc = Document(
            source_id=source.id,
            external_id="doc-api-market-1",
            title="Fed Rate Decision Statement",
            content="Federal Reserve keeps policy rate unchanged at 5.25%-5.50%.",
            content_hash="hash-api-mkt-1",
            url="https://marketnews.com/fed-decision",
            published_at=t0 + timedelta(minutes=15),
        )
        db.add(doc)
        db.commit()

        event = ExtractedEvent(
            document_id=doc.id,
            event_type="central_bank_decision",
            event_title="Federal Reserve Holds Policy Rate Steady",
            event_time=t0 + timedelta(minutes=15),
            confidence=0.98,
            importance=0.92,
        )
        db.add(event)
        db.commit()

        # 4. Compute correlation
        compute_event_market_correlation(db, event, btc, window_size="15m")
        compute_event_market_correlation(db, event, spx, window_size="15m")

        yield {"btc": btc, "spx": spx, "event": event, "doc": doc}
    finally:
        pass


def test_api_list_market_assets(client, seeded_market_api_data):
    """Test GET /api/v1/market-assets pagination and filters."""
    # List all assets
    res = client.get("/api/v1/market-assets?page=1&page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] >= 16  # Canonical universe
    assert len(data["items"]) == 10

    # Filter by crypto
    res_crypto = client.get("/api/v1/market-assets?asset_type=crypto")
    assert res_crypto.status_code == 200
    crypto_data = res_crypto.json()
    assert crypto_data["total"] >= 2
    assert all(item["asset_type"] == "crypto" for item in crypto_data["items"])

    # Search symbol
    res_search = client.get("/api/v1/market-assets?search=Bitcoin")
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert search_data["total"] >= 1
    assert search_data["items"][0]["symbol"] == "BTC-USD"


def test_api_get_market_asset_detail(client, seeded_market_api_data):
    """Test GET /api/v1/market-assets/{id} detail with data quality."""
    btc = seeded_market_api_data["btc"]
    res = client.get(f"/api/v1/market-assets/{btc.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "BTC-USD"
    assert data["canonical_name"] == "Bitcoin"
    assert data["latest_observation"] is not None
    assert data["data_quality"] is not None
    assert data["data_quality"]["is_healthy"] is True


def test_api_get_asset_observations(client, seeded_market_api_data):
    """Test GET /api/v1/market-assets/{id}/observations bounded timeseries."""
    btc = seeded_market_api_data["btc"]
    res = client.get(f"/api/v1/market-assets/{btc.id}/observations?interval=1m&limit=10")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 10
    assert data[0]["open"] > 0
    assert data[0]["close"] > 0


def test_api_get_market_asset_events(client, seeded_market_api_data):
    """Test bidirectional navigation: GET /api/v1/market-assets/{id}/events."""
    btc = seeded_market_api_data["btc"]
    res = client.get(f"/api/v1/market-assets/{btc.id}/events")
    assert res.status_code == 200
    events = res.json()
    assert len(events) >= 1
    assert events[0]["event_title"] == "Federal Reserve Holds Policy Rate Steady"
    assert events[0]["disclaimer"] == STANDARD_CORRELATION_DISCLAIMER


def test_api_get_event_market_correlations(client, seeded_market_api_data):
    """Test GET /api/v1/events/{id}/market-correlations."""
    event = seeded_market_api_data["event"]
    res = client.get(f"/api/v1/events/{event.id}/market-correlations?window_size=15m")
    assert res.status_code == 200
    corrs = res.json()
    assert len(corrs) >= 2
    for c in corrs:
        assert c["disclaimer"] == STANDARD_CORRELATION_DISCLAIMER
        assert c["window_size"] == "15m"

    btc_corr = next((c for c in corrs if c["market_asset"] and c["market_asset"]["symbol"] == "BTC-USD"), None)
    assert btc_corr is not None
    assert btc_corr["pre_event_price"] is not None
    assert btc_corr["post_event_price"] is not None
    assert btc_corr["return_percent"] is not None


def test_api_post_event_correlate(client, seeded_market_api_data):
    """Test POST /api/v1/events/{id}/correlate for on-demand calculation."""
    event = seeded_market_api_data["event"]
    btc = seeded_market_api_data["btc"]
    payload = {
        "window_sizes": ["15m"],
        "market_asset_ids": [str(btc.id)],
    }
    res = client.post(f"/api/v1/events/{event.id}/correlate", json=payload)
    assert res.status_code == 200
    corrs = res.json()
    assert len(corrs) == 1
    assert corrs[0]["market_asset_id"] == str(btc.id)
    assert corrs[0]["disclaimer"] == STANDARD_CORRELATION_DISCLAIMER


def test_api_market_dashboard_summary(client, seeded_market_api_data):
    """Test GET /api/v1/market/dashboard-summary."""
    res = client.get("/api/v1/market/dashboard-summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total_assets"] >= 16
    assert data["total_observations"] >= 60
    assert data["total_correlations"] >= 2
    assert "crypto" in data["asset_counts_by_type"]
    assert len(data["top_movers"]) > 0
    assert data["disclaimer"] == STANDARD_CORRELATION_DISCLAIMER


def test_api_search_market_asset_and_compound(client, seeded_market_api_data):
    """Test global search with symbol and compound queries."""
    # 1. Search single asset
    res1 = client.get("/api/v1/search?q=BTC")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["total_market_assets"] >= 1
    assert any(a["symbol"] == "BTC-USD" for a in data1["market_assets"])

    # 2. Compound search: "Fed + Bitcoin"
    res2 = client.get("/api/v1/search?q=Fed%20%2B%20Bitcoin")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["total_market_assets"] >= 1
    assert any(a["symbol"] == "BTC-USD" for a in data2["market_assets"])
