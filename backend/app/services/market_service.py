import uuid
import math
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, func, desc, and_, or_
from sqlalchemy.orm import Session, joinedload

from backend.app.models.market_asset import MarketAsset
from backend.app.models.market_observation import MarketObservation
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.models.entity import Entity
from backend.app.schemas.market import (
    MarketAssetCreate,
    MarketAssetRead,
    MarketAssetDetailRead,
    MarketObservationCreate,
    MarketObservationRead,
    DataQualityReport,
    MarketDashboardSummaryResponse,
    STANDARD_CORRELATION_DISCLAIMER,
)
from backend.app.market.quality import MarketDataQualityEngine
from backend.app.utils.logger import get_logger

logger = get_logger("service.market")

CANONICAL_UNIVERSE_CONFIG: List[Dict[str, Any]] = [
    # Crypto
    {
        "symbol": "BTC-USD",
        "canonical_name": "Bitcoin",
        "asset_type": "crypto",
        "exchange_venue": "Coinbase / Binance",
        "quote_currency": "USD",
        "base_currency": "BTC",
        "entity_country": None,
    },
    {
        "symbol": "ETH-USD",
        "canonical_name": "Ethereum",
        "asset_type": "crypto",
        "exchange_venue": "Coinbase / Binance",
        "quote_currency": "USD",
        "base_currency": "ETH",
        "entity_country": None,
    },
    # Equity Indices
    {
        "symbol": "SPX",
        "canonical_name": "S&P 500 Index",
        "asset_type": "equity_index",
        "exchange_venue": "Cboe / CME",
        "quote_currency": "USD",
        "base_currency": None,
        "entity_country": "US",
    },
    {
        "symbol": "NDX",
        "canonical_name": "Nasdaq 100",
        "asset_type": "equity_index",
        "exchange_venue": "Nasdaq / CME",
        "quote_currency": "USD",
        "base_currency": None,
        "entity_country": "US",
    },
    {
        "symbol": "DAX",
        "canonical_name": "DAX 40",
        "asset_type": "equity_index",
        "exchange_venue": "Deutsche Börse",
        "quote_currency": "EUR",
        "base_currency": None,
        "entity_country": "DE",
    },
    {
        "symbol": "FTSE",
        "canonical_name": "FTSE 100",
        "asset_type": "equity_index",
        "exchange_venue": "London Stock Exchange",
        "quote_currency": "GBP",
        "base_currency": None,
        "entity_country": "GB",
    },
    {
        "symbol": "N225",
        "canonical_name": "Nikkei 225",
        "asset_type": "equity_index",
        "exchange_venue": "Tokyo Stock Exchange",
        "quote_currency": "JPY",
        "base_currency": None,
        "entity_country": "JP",
    },
    # Forex
    {
        "symbol": "EUR/USD",
        "canonical_name": "Euro / US Dollar",
        "asset_type": "forex",
        "exchange_venue": "Interbank FX",
        "quote_currency": "USD",
        "base_currency": "EUR",
        "entity_country": "EU",
    },
    {
        "symbol": "GBP/USD",
        "canonical_name": "British Pound / US Dollar",
        "asset_type": "forex",
        "exchange_venue": "Interbank FX",
        "quote_currency": "USD",
        "base_currency": "GBP",
        "entity_country": "GB",
    },
    {
        "symbol": "USD/JPY",
        "canonical_name": "US Dollar / Japanese Yen",
        "asset_type": "forex",
        "exchange_venue": "Interbank FX",
        "quote_currency": "JPY",
        "base_currency": "USD",
        "entity_country": "JP",
    },
    {
        "symbol": "USD/INR",
        "canonical_name": "US Dollar / Indian Rupee",
        "asset_type": "forex",
        "exchange_venue": "Interbank FX",
        "quote_currency": "INR",
        "base_currency": "USD",
        "entity_country": "IN",
    },
    # Commodities
    {
        "symbol": "BRENT",
        "canonical_name": "Brent Crude Oil",
        "asset_type": "commodity",
        "exchange_venue": "ICE",
        "quote_currency": "USD",
        "base_currency": "BBL",
        "entity_country": None,
    },
    {
        "symbol": "WTI",
        "canonical_name": "WTI Crude Oil",
        "asset_type": "commodity",
        "exchange_venue": "NYMEX",
        "quote_currency": "USD",
        "base_currency": "BBL",
        "entity_country": "US",
    },
    {
        "symbol": "GOLD",
        "canonical_name": "Gold Spot",
        "asset_type": "commodity",
        "exchange_venue": "COMEX / LBMA",
        "quote_currency": "USD",
        "base_currency": "OZT",
        "entity_country": None,
    },
    # Sovereign Rates
    {
        "symbol": "US2Y",
        "canonical_name": "US 2-Year Treasury Yield",
        "asset_type": "interest_rate",
        "exchange_venue": "Tradeweb / US Treasury",
        "quote_currency": "%",
        "base_currency": "USD",
        "entity_country": "US",
    },
    {
        "symbol": "US10Y",
        "canonical_name": "US 10-Year Treasury Yield",
        "asset_type": "interest_rate",
        "exchange_venue": "Tradeweb / US Treasury",
        "quote_currency": "%",
        "base_currency": "USD",
        "entity_country": "US",
    },
]


def initialize_canonical_market_assets(db: Session) -> List[MarketAsset]:
    """Initialize canonical market universe if not already present."""
    initialized: List[MarketAsset] = []

    for item in CANONICAL_UNIVERSE_CONFIG:
        existing = db.scalar(select(MarketAsset).where(MarketAsset.symbol == item["symbol"]))
        if existing:
            initialized.append(existing)
            continue

        # Look up entity if country code provided
        entity_id = None
        if item.get("entity_country"):
            country_code = item["entity_country"]
            entity = db.scalar(
                select(Entity).where(Entity.country_code == country_code, Entity.entity_type == "GPE").limit(1)
            )
            if entity:
                entity_id = entity.id

        new_asset = MarketAsset(
            symbol=item["symbol"],
            canonical_name=item["canonical_name"],
            asset_type=item["asset_type"],
            exchange_venue=item.get("exchange_venue"),
            quote_currency=item.get("quote_currency"),
            base_currency=item.get("base_currency"),
            entity_id=entity_id,
            metadata_={"canonical_universe": True},
        )
        db.add(new_asset)
        initialized.append(new_asset)

    db.commit()
    for a in initialized:
        db.refresh(a)
    return initialized


def get_or_create_market_asset(
    db: Session,
    symbol: str,
    canonical_name: str,
    asset_type: str,
    exchange_venue: Optional[str] = None,
    quote_currency: Optional[str] = None,
    base_currency: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> MarketAsset:
    """Retrieve or insert a market asset record."""
    asset = db.scalar(select(MarketAsset).where(MarketAsset.symbol == symbol))
    if asset:
        return asset

    asset = MarketAsset(
        symbol=symbol,
        canonical_name=canonical_name,
        asset_type=asset_type,
        exchange_venue=exchange_venue,
        quote_currency=quote_currency,
        base_currency=base_currency,
        entity_id=entity_id,
        metadata_=metadata or {},
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def store_market_observations(
    db: Session,
    observations: List[MarketObservationCreate],
    interval: str = "1m",
    asset_id: Optional[uuid.UUID] = None,
) -> Tuple[int, DataQualityReport]:
    """
    Store market observations with data quality audit and deduplication.
    INVARIANT: Does not fabricate synthetic candles.
    """
    if not observations:
        _, report = MarketDataQualityEngine.audit_and_clean_observations([], interval, asset_id=asset_id)
        return 0, report

    clean_obs, report = MarketDataQualityEngine.audit_and_clean_observations(
        observations, interval, asset_id=asset_id
    )

    inserted_count = 0
    for obs in clean_obs:
        target_asset_id = obs.market_asset_id or asset_id
        if not target_asset_id:
            continue

        # Check if already exists in DB
        ts_utc = obs.timestamp.replace(tzinfo=timezone.utc) if obs.timestamp.tzinfo is None else obs.timestamp
        existing = db.scalar(
            select(MarketObservation.id).where(
                MarketObservation.market_asset_id == target_asset_id,
                MarketObservation.interval == obs.interval,
                MarketObservation.timestamp == ts_utc,
                MarketObservation.source == obs.source,
            )
        )
        if not existing:
            db_obs = MarketObservation(
                market_asset_id=target_asset_id,
                timestamp=ts_utc,
                open=obs.open,
                high=obs.high,
                low=obs.low,
                close=obs.close,
                volume=obs.volume,
                source=obs.source,
                interval=obs.interval,
                metadata_=obs.metadata or {},
            )
            db.add(db_obs)
            inserted_count += 1

    if inserted_count > 0:
        db.commit()

    return inserted_count, report


def get_market_assets(
    db: Session,
    asset_type: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[MarketAsset], int]:
    """Server-side bounded retrieval of market assets."""
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size

    stmt = select(MarketAsset)
    count_stmt = select(func.count(MarketAsset.id))
    filters = [
        ~MarketAsset.symbol.like("TEST_%"),
        ~MarketAsset.symbol.like("USDX_%"),
    ]
    if asset_type:
        filters.append(MarketAsset.asset_type == asset_type)
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                MarketAsset.symbol.ilike(pattern),
                MarketAsset.canonical_name.ilike(pattern),
            )
        )

    stmt = stmt.where(and_(*filters))
    count_stmt = count_stmt.where(and_(*filters))

    total = db.scalar(count_stmt) or 0
    records = list(
        db.scalars(
            stmt.order_by(MarketAsset.asset_type, MarketAsset.symbol)
            .offset(offset)
            .limit(page_size)
        ).all()
    )
    return records, total


def get_market_asset_detail(db: Session, asset_id: uuid.UUID) -> Optional[MarketAssetDetailRead]:
    """Retrieve detailed market asset view including latest bar, 24h change, and data quality."""
    asset = db.scalar(select(MarketAsset).where(MarketAsset.id == asset_id))
    if not asset:
        return None

    # Latest observation
    latest_obs = db.scalar(
        select(MarketObservation)
        .where(MarketObservation.market_asset_id == asset_id)
        .order_by(desc(MarketObservation.timestamp))
        .limit(1)
    )

    # 24h price return calculation
    day_return: Optional[float] = None
    if latest_obs:
        target_24h = latest_obs.timestamp - timedelta(hours=24)
        prev_obs = db.scalar(
            select(MarketObservation)
            .where(
                MarketObservation.market_asset_id == asset_id,
                MarketObservation.interval == latest_obs.interval,
                MarketObservation.timestamp <= target_24h,
            )
            .order_by(desc(MarketObservation.timestamp))
            .limit(1)
        )
        if prev_obs and prev_obs.close > 0:
            day_return = round(((latest_obs.close / prev_obs.close) - 1.0) * 100.0, 2)

    # Recent observations count
    recent_count = db.scalar(
        select(func.count(MarketObservation.id)).where(MarketObservation.market_asset_id == asset_id)
    ) or 0

    # Quick data quality report on latest interval observations
    latest_interval = latest_obs.interval if latest_obs else "1m"
    sample_obs = list(
        db.scalars(
            select(MarketObservation)
            .where(
                MarketObservation.market_asset_id == asset_id,
                MarketObservation.interval == latest_interval,
            )
            .order_by(desc(MarketObservation.timestamp))
            .limit(100)
        ).all()
    )
    sample_obs.reverse()  # Chronological
    _, quality_report = MarketDataQualityEngine.audit_and_clean_observations(
        sample_obs, latest_interval, asset_id=asset.id, symbol=asset.symbol
    )

    latest_read = MarketObservationRead.model_validate(latest_obs) if latest_obs else None

    return MarketAssetDetailRead(
        id=asset.id,
        symbol=asset.symbol,
        canonical_name=asset.canonical_name,
        asset_type=asset.asset_type,
        exchange_venue=asset.exchange_venue,
        quote_currency=asset.quote_currency,
        base_currency=asset.base_currency,
        entity_id=asset.entity_id,
        metadata=asset.metadata_ or {},
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        latest_observation=latest_read,
        recent_observations_count=recent_count,
        day_return_percent=day_return,
        data_quality=quality_report,
    )


def get_asset_observations(
    db: Session,
    asset_id: uuid.UUID,
    interval: str = "1m",
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    limit: int = 100,
) -> List[MarketObservation]:
    """Server-side bounded query for historical time-series bars."""
    limit = min(max(1, limit), 500)  # Bound to max 500 bars per request

    stmt = (
        select(MarketObservation)
        .where(
            MarketObservation.market_asset_id == asset_id,
            MarketObservation.interval == interval,
        )
    )

    if from_time:
        ft = from_time.replace(tzinfo=timezone.utc) if from_time.tzinfo is None else from_time
        stmt = stmt.where(MarketObservation.timestamp >= ft)
    if to_time:
        tt = to_time.replace(tzinfo=timezone.utc) if to_time.tzinfo is None else to_time
        stmt = stmt.where(MarketObservation.timestamp <= tt)

    stmt = stmt.order_by(MarketObservation.timestamp.asc()).limit(limit)
    return list(db.scalars(stmt).all())


def get_market_dashboard_summary(db: Session) -> MarketDashboardSummaryResponse:
    """Produce summary metrics for the Market Intelligence desk."""
    canonical_filter = and_(
        ~MarketAsset.symbol.like("TEST_%"),
        ~MarketAsset.symbol.like("USDX_%"),
    )
    total_assets = db.scalar(select(func.count(MarketAsset.id)).where(canonical_filter)) or 0
    total_obs = db.scalar(select(func.count(MarketObservation.id))) or 0
    total_corr = db.scalar(select(func.count(EventMarketCorrelation.id))) or 0

    # Group by asset type
    type_counts_rows = db.execute(
        select(MarketAsset.asset_type, func.count(MarketAsset.id))
        .where(canonical_filter)
        .group_by(MarketAsset.asset_type)
    ).all()
    type_counts = {row[0]: row[1] for row in type_counts_rows}

    # Top movers from assets with latest observations
    assets = list(db.scalars(select(MarketAsset).where(canonical_filter).limit(20)).all())
    top_movers: List[Dict[str, Any]] = []

    for a in assets:
        latest = db.scalar(
            select(MarketObservation)
            .where(MarketObservation.market_asset_id == a.id)
            .order_by(desc(MarketObservation.timestamp))
            .limit(1)
        )
        if latest:
            prev = db.scalar(
                select(MarketObservation)
                .where(
                    MarketObservation.market_asset_id == a.id,
                    MarketObservation.interval == latest.interval,
                    MarketObservation.timestamp <= (latest.timestamp - timedelta(hours=24)),
                )
                .order_by(desc(MarketObservation.timestamp))
                .limit(1)
            )
            pct = 0.0
            if prev and prev.close > 0:
                pct = round(((latest.close / prev.close) - 1.0) * 100.0, 2)

            top_movers.append({
                "id": str(a.id),
                "symbol": a.symbol,
                "canonical_name": a.canonical_name,
                "asset_type": a.asset_type,
                "price": latest.close,
                "quote_currency": a.quote_currency or "USD",
                "return_24h": pct,
                "timestamp": latest.timestamp.isoformat(),
            })

    top_movers.sort(key=lambda x: abs(x["return_24h"]), reverse=True)

    # Recent event-market correlations
    corrs = list(
        db.scalars(
            select(EventMarketCorrelation)
            .options(
                joinedload(EventMarketCorrelation.market_asset),
                joinedload(EventMarketCorrelation.extracted_event),
            )
            .order_by(desc(EventMarketCorrelation.calculated_at))
            .limit(10)
        ).unique().all()
    )

    corr_reads: List[Any] = []
    for c in corrs:
        corr_reads.append({
            "id": c.id,
            "event_id": c.event_id,
            "cluster_id": c.cluster_id,
            "market_asset_id": c.market_asset_id,
            "window_size": c.window_size,
            "window_start": c.window_start,
            "window_end": c.window_end,
            "pre_event_price": c.pre_event_price,
            "event_price": c.event_price,
            "post_event_price": c.post_event_price,
            "return_percent": c.return_percent,
            "absolute_change": c.absolute_change,
            "volatility": c.volatility,
            "volume_change": c.volume_change,
            "max_excursion": c.max_excursion,
            "min_excursion": c.min_excursion,
            "calculated_at": c.calculated_at,
            "methodology": c.methodology,
            "disclaimer": STANDARD_CORRELATION_DISCLAIMER,
            "market_asset": MarketAssetRead.model_validate(c.market_asset) if c.market_asset else None,
            "event_title": c.extracted_event.event_title if c.extracted_event else None,
            "event_type": c.extracted_event.event_type if c.extracted_event else None,
            "event_time": c.extracted_event.event_time if c.extracted_event else None,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        })

    return MarketDashboardSummaryResponse(
        total_assets=total_assets,
        asset_counts_by_type=type_counts,
        total_observations=total_obs,
        total_correlations=total_corr,
        top_movers=top_movers[:10],
        recent_correlations=corr_reads,
        disclaimer=STANDARD_CORRELATION_DISCLAIMER,
    )


def get_canonical_tickers_summary(db: Session) -> List[Dict[str, Any]]:
    """Retrieve live quotes, provenance sources, and 24h change for all 16 canonical assets."""
    canonical_filter = or_(
        MarketAsset.metadata_["canonical_universe"].as_boolean() == True,
        MarketAsset.symbol.in_([item["symbol"] for item in CANONICAL_UNIVERSE_CONFIG]),
    )
    assets = list(
        db.scalars(
            select(MarketAsset)
            .where(canonical_filter)
            .order_by(MarketAsset.asset_type, MarketAsset.symbol)
        ).all()
    )

    tickers: List[Dict[str, Any]] = []
    for a in assets:
        latest = db.scalar(
            select(MarketObservation)
            .where(MarketObservation.market_asset_id == a.id)
            .order_by(desc(MarketObservation.timestamp))
            .limit(1)
        )
        obs_count = db.scalar(
            select(func.count(MarketObservation.id)).where(MarketObservation.market_asset_id == a.id)
        ) or 0

        day_return = None
        if latest:
            prev = db.scalar(
                select(MarketObservation)
                .where(
                    MarketObservation.market_asset_id == a.id,
                    MarketObservation.interval == latest.interval,
                    MarketObservation.timestamp <= (latest.timestamp - timedelta(hours=24)),
                )
                .order_by(desc(MarketObservation.timestamp))
                .limit(1)
            )
            if prev and prev.close > 0:
                day_return = round(((latest.close / prev.close) - 1.0) * 100.0, 2)

        tickers.append({
            "id": str(a.id),
            "symbol": a.symbol,
            "canonical_name": a.canonical_name,
            "asset_type": a.asset_type,
            "exchange_venue": a.exchange_venue or "Interbank",
            "quote_currency": a.quote_currency or "USD",
            "base_currency": a.base_currency,
            "price": latest.close if latest else None,
            "source": latest.source if latest else "Sensor_Pending",
            "timestamp": latest.timestamp.isoformat() if latest else None,
            "return_24h": day_return,
            "observations_count": obs_count,
        })

    return tickers

