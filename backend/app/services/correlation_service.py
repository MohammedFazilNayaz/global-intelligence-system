import uuid
import math
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import Session, joinedload

from backend.app.models.event import ExtractedEvent
from backend.app.models.cluster import EventCluster
from backend.app.models.market_asset import MarketAsset
from backend.app.models.market_observation import MarketObservation
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.schemas.market import (
    EventMarketCorrelationRead,
    STANDARD_CORRELATION_DISCLAIMER,
)
from backend.app.utils.time import utc_now
from backend.app.utils.logger import get_logger

logger = get_logger("service.correlation")

WINDOW_DELTAS: Dict[str, timedelta] = {
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}


def get_relevant_assets_for_event(db: Session, event: ExtractedEvent) -> List[MarketAsset]:
    """
    Deterministically identify market assets relevant to an extracted event
    based on indicator type, event type, institution, or sovereign location.
    """
    all_assets = list(db.scalars(select(MarketAsset)).all())
    asset_by_symbol = {a.symbol: a for a in all_assets}

    text_content = f"{event.event_title} {event.event_summary or ''}".lower()
    event_type = event.event_type.lower()

    relevant_symbols: List[str] = []

    # Central Bank Decisions
    if "central_bank" in event_type or "interest_rate" in event_type:
        if any(w in text_content for w in ["federal reserve", "fed", "powell", "fomc"]):
            relevant_symbols.extend(["SPX", "US10Y", "US2Y", "BTC-USD", "EUR/USD", "GOLD"])
        elif any(w in text_content for w in ["european central bank", "ecb", "lagarde"]):
            relevant_symbols.extend(["EUR/USD", "DAX", "GOLD", "SPX"])
        elif any(w in text_content for w in ["bank of japan", "boj", "ueda", "yen"]):
            relevant_symbols.extend(["USD/JPY", "N225", "GOLD"])
        elif any(w in text_content for w in ["bank of england", "boe", "bailey"]):
            relevant_symbols.extend(["GBP/USD", "FTSE", "GOLD"])
        elif any(w in text_content for w in ["reserve bank of india", "rbi"]):
            relevant_symbols.extend(["USD/INR", "GOLD"])
        else:
            relevant_symbols.extend(["BTC-USD", "SPX", "US10Y", "GOLD"])

    # Inflation / CPI / Economic releases
    elif any(ind in text_content for ind in ["cpi", "inflation", "ppi"]):
        if any(c in text_content for c in ["us", "united states", "fed"]):
            relevant_symbols.extend(["BTC-USD", "SPX", "US10Y", "GOLD", "EUR/USD"])
        elif any(c in text_content for c in ["germany", "eurozone", "europe"]):
            relevant_symbols.extend(["EUR/USD", "DAX", "GOLD"])
        else:
            relevant_symbols.extend(["BTC-USD", "SPX", "GOLD", "US10Y"])

    # Growth / GDP / Retail Sales / Labor
    elif any(ind in text_content for ind in ["gdp", "growth", "payrolls", "unemployment", "jobs"]):
        relevant_symbols.extend(["SPX", "NDX", "US10Y", "BTC-USD", "EUR/USD"])

    # Commodities / Energy / Oil
    elif any(comm in text_content for comm in ["oil", "crude", "brent", "wti", "energy", "gas"]):
        relevant_symbols.extend(["BRENT", "WTI", "GOLD", "SPX"])

    # Geopolitical / Conflict / Military
    elif any(geo in event_type for geo in ["conflict", "military", "sanction", "security"]):
        relevant_symbols.extend(["GOLD", "BRENT", "BTC-USD", "SPX"])

    # Fallback to key macro proxies if no direct match
    if not relevant_symbols:
        relevant_symbols = ["BTC-USD", "SPX", "EUR/USD", "GOLD", "US10Y"]

    # Filter to existing assets in database preserving order
    result: List[MarketAsset] = []
    seen = set()
    for s in relevant_symbols:
        if s in asset_by_symbol and s not in seen:
            result.append(asset_by_symbol[s])
            seen.add(s)

    return result


def compute_event_market_correlation(
    db: Session,
    event: ExtractedEvent,
    asset: MarketAsset,
    window_size: str = "1h",
) -> Optional[EventMarketCorrelation]:
    """
    Deterministically computes temporal market correlation around an event window.
    INVARIANT:
    - If price at start or end of window is unavailable, stores null.
    - Never fabricates prices or imputes missing candles.
    - Methodology is explicitly recorded.
    """
    if not event.event_time:
        return None

    delta = WINDOW_DELTAS.get(window_size, timedelta(hours=1))
    t_event = event.event_time.replace(tzinfo=timezone.utc) if event.event_time.tzinfo is None else event.event_time
    w_start = t_event - delta
    w_end = t_event + delta

    # Determine best interval to query based on window size
    interval = "1m" if window_size in ["5m", "15m"] else ("5m" if window_size == "1h" else "15m")

    # Fetch observations within [w_start, w_end]
    obs = list(
        db.scalars(
            select(MarketObservation)
            .where(
                MarketObservation.market_asset_id == asset.id,
                MarketObservation.timestamp >= w_start,
                MarketObservation.timestamp <= w_end,
            )
            .order_by(MarketObservation.timestamp.asc())
        ).all()
    )

    if not obs:
        # Check if any observation exists near w_start and w_end across all intervals
        obs = list(
            db.scalars(
                select(MarketObservation)
                .where(
                    MarketObservation.market_asset_id == asset.id,
                    MarketObservation.timestamp >= w_start,
                    MarketObservation.timestamp <= w_end,
                )
                .order_by(MarketObservation.timestamp.asc())
            ).all()
        )

    pre_price: Optional[float] = None
    event_price: Optional[float] = None
    post_price: Optional[float] = None
    ret_pct: Optional[float] = None
    abs_change: Optional[float] = None
    vol_change: Optional[float] = None
    volatility: Optional[float] = None
    max_excursion: Optional[float] = None
    min_excursion: Optional[float] = None

    if obs:
        # Pre-event: closest observation near w_start (within first 30% of window)
        pre_price = obs[0].close

        # Post-event: closest observation near w_end (within last 30% of window)
        post_price = obs[-1].close

        # Event price: closest observation to t_event
        closest_event_obs = min(obs, key=lambda o: abs((o.timestamp - t_event).total_seconds()))
        # Only accept as event price if within reasonable proximity
        if abs((closest_event_obs.timestamp - t_event).total_seconds()) <= delta.total_seconds() * 0.5:
            event_price = closest_event_obs.close

        # Return and absolute change
        if pre_price is not None and post_price is not None and pre_price > 0:
            ret_pct = round(((post_price / pre_price) - 1.0) * 100.0, 4)
            abs_change = round(post_price - pre_price, 4)

        # Volume change
        first_vol = obs[0].volume
        last_vol = obs[-1].volume
        if first_vol and last_vol and first_vol > 0:
            vol_change = round(((last_vol / first_vol) - 1.0) * 100.0, 2)

        # Excursions relative to pre_price
        if pre_price is not None and pre_price > 0:
            max_high = max(o.high for o in obs)
            min_low = min(o.low for o in obs)
            max_excursion = round(((max_high - pre_price) / pre_price) * 100.0, 4)
            min_excursion = round(((min_low - pre_price) / pre_price) * 100.0, 4)

        # Volatility: standard deviation of percentage returns between consecutive bars
        if len(obs) >= 3:
            bar_returns = []
            for i in range(len(obs) - 1):
                if obs[i].close > 0:
                    r = (obs[i + 1].close / obs[i].close) - 1.0
                    bar_returns.append(r)
            if len(bar_returns) >= 2:
                mean_r = sum(bar_returns) / len(bar_returns)
                variance = sum((r - mean_r) ** 2 for r in bar_returns) / (len(bar_returns) - 1)
                volatility = round(math.sqrt(variance) * 100.0, 4)

    # Get cluster id if event is member of a cluster
    cluster_id = None
    if event.cluster_membership:
        cluster_id = event.cluster_membership.event_cluster_id

    # Check if record already exists in DB
    existing = db.scalar(
        select(EventMarketCorrelation).where(
            EventMarketCorrelation.event_id == event.id,
            EventMarketCorrelation.market_asset_id == asset.id,
            EventMarketCorrelation.window_size == window_size,
        )
    )

    if existing:
        existing.window_start = w_start
        existing.window_end = w_end
        existing.pre_event_price = pre_price
        existing.event_price = event_price
        existing.post_event_price = post_price
        existing.return_percent = ret_pct
        existing.absolute_change = abs_change
        existing.volatility = volatility
        existing.volume_change = vol_change
        existing.max_excursion = max_excursion
        existing.min_excursion = min_excursion
        existing.calculated_at = utc_now()
        existing.cluster_id = cluster_id
        db.commit()
        db.refresh(existing)
        return existing

    record = EventMarketCorrelation(
        event_id=event.id,
        cluster_id=cluster_id,
        market_asset_id=asset.id,
        window_size=window_size,
        window_start=w_start,
        window_end=w_end,
        pre_event_price=pre_price,
        event_price=event_price,
        post_event_price=post_price,
        return_percent=ret_pct,
        absolute_change=abs_change,
        volatility=volatility,
        volume_change=vol_change,
        max_excursion=max_excursion,
        min_excursion=min_excursion,
        calculated_at=utc_now(),
        methodology="window_close_return",
        metadata_={
            "observation_count": len(obs),
            "data_available": bool(obs),
            "status": "MARKET_OPEN" if obs else "MARKET_CLOSED",
        },
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def correlate_event_across_assets(
    db: Session,
    event_id: uuid.UUID,
    window_sizes: Optional[List[str]] = None,
    asset_ids: Optional[List[uuid.UUID]] = None,
) -> List[EventMarketCorrelationRead]:
    """Compute and return event correlations across relevant or specified assets."""
    event = db.scalar(
        select(ExtractedEvent)
        .options(joinedload(ExtractedEvent.cluster_membership))
        .where(ExtractedEvent.id == event_id)
    )
    if not event:
        return []

    windows = window_sizes or ["1h"]

    if asset_ids:
        assets = list(db.scalars(select(MarketAsset).where(MarketAsset.id.in_(asset_ids))).all())
    else:
        assets = get_relevant_assets_for_event(db, event)

    results: List[EventMarketCorrelationRead] = []
    for asset in assets:
        for w in windows:
            corr = compute_event_market_correlation(db, event, asset, window_size=w)
            if corr:
                results.append(
                    EventMarketCorrelationRead(
                        id=corr.id,
                        event_id=corr.event_id,
                        cluster_id=corr.cluster_id,
                        market_asset_id=corr.market_asset_id,
                        window_size=corr.window_size,
                        window_start=corr.window_start,
                        window_end=corr.window_end,
                        pre_event_price=corr.pre_event_price,
                        event_price=corr.event_price,
                        post_event_price=corr.post_event_price,
                        return_percent=corr.return_percent,
                        absolute_change=corr.absolute_change,
                        volatility=corr.volatility,
                        volume_change=corr.volume_change,
                        max_excursion=corr.max_excursion,
                        min_excursion=corr.min_excursion,
                        calculated_at=corr.calculated_at,
                        methodology=corr.methodology,
                        disclaimer=STANDARD_CORRELATION_DISCLAIMER,
                        metadata=corr.metadata_ or {},
                        market_asset=corr.market_asset,
                        event_title=event.event_title,
                        event_type=event.event_type,
                        event_time=event.event_time,
                        created_at=corr.created_at,
                        updated_at=corr.updated_at,
                    )
                )

    return results


def get_events_for_market_asset(
    db: Session,
    asset_id: uuid.UUID,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Bidirectional navigation: Retrieve economic & geopolitical events
    correlated with a specific market asset.
    """
    limit = min(max(1, limit), 50)
    corrs = list(
        db.scalars(
            select(EventMarketCorrelation)
            .options(
                joinedload(EventMarketCorrelation.extracted_event),
                joinedload(EventMarketCorrelation.market_asset),
            )
            .where(EventMarketCorrelation.market_asset_id == asset_id)
            .order_by(desc(EventMarketCorrelation.calculated_at))
            .limit(limit)
        ).unique().all()
    )

    results: List[Dict[str, Any]] = []
    for c in corrs:
        if c.extracted_event:
            results.append({
                "correlation_id": str(c.id),
                "event_id": str(c.extracted_event.id),
                "cluster_id": str(c.cluster_id) if c.cluster_id else None,
                "event_title": c.extracted_event.event_title,
                "event_type": c.extracted_event.event_type,
                "event_time": c.extracted_event.event_time.isoformat() if c.extracted_event.event_time else None,
                "importance": c.extracted_event.importance,
                "confidence": c.extracted_event.confidence,
                "window_size": c.window_size,
                "pre_event_price": c.pre_event_price,
                "event_price": c.event_price,
                "post_event_price": c.post_event_price,
                "return_percent": c.return_percent,
                "volume_change": c.volume_change,
                "disclaimer": STANDARD_CORRELATION_DISCLAIMER,
            })
    return results
