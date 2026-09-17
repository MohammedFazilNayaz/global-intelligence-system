import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.market import (
    MarketAssetRead,
    MarketAssetDetailRead,
    MarketObservationRead,
    EventMarketCorrelationRead,
    MarketCorrelationComputeRequest,
    MarketDashboardSummaryResponse,
    STANDARD_CORRELATION_DISCLAIMER,
)
from backend.app.services.market_service import (
    get_market_assets,
    get_market_asset_detail,
    get_asset_observations,
    get_market_dashboard_summary,
    initialize_canonical_market_assets,
    get_canonical_tickers_summary,
)
from backend.app.services.correlation_service import (
    correlate_event_across_assets,
    get_events_for_market_asset,
)

router = APIRouter(prefix="", tags=["Market Intelligence"])


class PaginatedMarketAssets(BaseModel):
    items: List[MarketAssetRead]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Market Asset Endpoints
# ---------------------------------------------------------------------------

@router.get("/market/tickers")
def get_canonical_market_tickers_endpoint(
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Retrieve live quotes, data providers, and 24h performance for all 16 canonical assets."""
    return get_canonical_tickers_summary(db)


@router.get("/market-assets", response_model=PaginatedMarketAssets)
def list_market_assets_endpoint(
    asset_type: Optional[str] = Query(None, description="Filter by asset type (crypto, equity_index, etc)"),
    search: Optional[str] = Query(None, description="Search symbol or name"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> PaginatedMarketAssets:
    """Retrieve paginated canonical market assets with optional filtering."""
    # Ensure universe is initialized if empty
    records, total = get_market_assets(db, asset_type=asset_type, search=search, page=page, page_size=page_size)
    if total == 0 and not search and not asset_type:
        initialize_canonical_market_assets(db)
        records, total = get_market_assets(db, asset_type=asset_type, search=search, page=page, page_size=page_size)

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedMarketAssets(
        items=[MarketAssetRead.model_validate(r) for r in records],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/market-assets/{asset_id}", response_model=MarketAssetDetailRead)
def get_market_asset_endpoint(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> MarketAssetDetailRead:
    """Retrieve detailed view of a market asset with data quality report and latest quote."""
    detail = get_market_asset_detail(db, asset_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Market asset {asset_id} not found")
    return detail


@router.get("/market-assets/{asset_id}/observations", response_model=List[MarketObservationRead])
def get_market_asset_observations_endpoint(
    asset_id: uuid.UUID,
    interval: str = Query("1m", description="Bar interval: 1m, 5m, 15m, 1h, 1d"),
    from_time: Optional[datetime] = Query(None, description="Start timestamp UTC"),
    to_time: Optional[datetime] = Query(None, description="End timestamp UTC"),
    limit: int = Query(100, ge=1, le=500, description="Max observations to return"),
    db: Session = Depends(get_db),
) -> List[MarketObservationRead]:
    """Retrieve bounded historical time-series observations for an asset."""
    obs = get_asset_observations(
        db, asset_id=asset_id, interval=interval, from_time=from_time, to_time=to_time, limit=limit
    )
    return [MarketObservationRead.model_validate(o) for o in obs]


@router.get("/market-assets/{asset_id}/events")
def get_market_asset_events_endpoint(
    asset_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=50, description="Max events to return"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Bidirectional navigation: Retrieve events temporally correlated with this asset."""
    return get_events_for_market_asset(db, asset_id=asset_id, limit=limit)


# ---------------------------------------------------------------------------
# Event-Market Correlation Endpoints
# ---------------------------------------------------------------------------

@router.get("/events/{event_id}/market-correlations", response_model=List[EventMarketCorrelationRead])
def get_event_market_correlations_endpoint(
    event_id: uuid.UUID,
    window_size: Optional[str] = Query(None, description="Filter by window size (5m, 15m, 1h, 4h, 1d)"),
    db: Session = Depends(get_db),
) -> List[EventMarketCorrelationRead]:
    """
    Retrieve market correlations observed around an extracted event.
    INVARIANT: Movement is temporally associated and does not establish causation.
    """
    windows = [window_size] if window_size else ["5m", "15m", "1h", "4h", "1d"]
    return correlate_event_across_assets(db, event_id=event_id, window_sizes=windows)


@router.post("/events/{event_id}/correlate", response_model=List[EventMarketCorrelationRead])
def compute_event_correlations_endpoint(
    event_id: uuid.UUID,
    payload: MarketCorrelationComputeRequest,
    db: Session = Depends(get_db),
) -> List[EventMarketCorrelationRead]:
    """On-demand calculation of event-market temporal window correlations."""
    windows = payload.window_sizes or ["1h"]
    return correlate_event_across_assets(
        db, event_id=event_id, window_sizes=windows, asset_ids=payload.market_asset_ids
    )


# ---------------------------------------------------------------------------
# Market Dashboard Summary Endpoint
# ---------------------------------------------------------------------------

@router.get("/market/dashboard-summary", response_model=MarketDashboardSummaryResponse)
def get_market_dashboard_summary_endpoint(
    db: Session = Depends(get_db),
) -> MarketDashboardSummaryResponse:
    """Retrieve aggregate market summary metrics and top moves for the Market Intelligence desk."""
    return get_market_dashboard_summary(db)
