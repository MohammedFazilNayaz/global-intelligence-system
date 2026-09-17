from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
import uuid

from backend.app.schemas.market import (
    DataQualityReport,
    MarketObservationRead,
    MarketObservationCreate,
)

INTERVAL_SECONDS: Dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


class MarketDataQualityEngine:
    """Deterministic validation and anomaly detection engine for market time-series data."""

    @staticmethod
    def get_expected_interval_seconds(interval: str) -> int:
        return INTERVAL_SECONDS.get(interval, 60)

    @classmethod
    def audit_and_clean_observations(
        cls,
        observations: List[Any],
        interval: str,
        asset_id: Optional[uuid.UUID] = None,
        symbol: Optional[str] = None,
    ) -> Tuple[List[Any], DataQualityReport]:
        """
        Audits raw observations for:
        - Duplicate observations (identical timestamp + interval + source)
        - Out-of-order timestamps (sorts chronologically, flags anomalies)
        - Missing candles / gaps (counts expected bars vs actual, flags periods)
        - Stale flatline prices (multiple consecutive identical bars)

        INVARIANT: Never fabricates or synthesizes missing candle values.
        Returns: (deduplicated_sorted_observations, DataQualityReport)
        """
        if not observations:
            report = DataQualityReport(
                asset_id=asset_id,
                symbol=symbol,
                interval=interval,
                is_healthy=True,
                total_observations=0,
                duplicate_count=0,
                missing_candles_count=0,
                out_of_order_count=0,
                stale_price_count=0,
                gap_count=0,
                gap_details=[],
                latest_observation_time=None,
                earliest_observation_time=None,
                continuity_ratio=1.0,
            )
            return [], report

        expected_step = cls.get_expected_interval_seconds(interval)

        # 1. Check for Out-of-Order timestamps before sorting
        out_of_order_count = 0
        for i in range(len(observations) - 1):
            t_curr = observations[i].timestamp
            t_next = observations[i + 1].timestamp
            if t_curr.tzinfo is None:
                t_curr = t_curr.replace(tzinfo=timezone.utc)
            if t_next.tzinfo is None:
                t_next = t_next.replace(tzinfo=timezone.utc)
            if t_curr > t_next:
                out_of_order_count += 1

        # 2. Sort observations chronologically
        sorted_obs = sorted(
            observations,
            key=lambda o: (
                o.timestamp.replace(tzinfo=timezone.utc) if o.timestamp.tzinfo is None else o.timestamp
            ),
        )

        # 3. Deduplicate
        seen_keys = set()
        deduped: List[Any] = []
        duplicate_count = 0

        for obs in sorted_obs:
            ts = obs.timestamp.replace(tzinfo=timezone.utc) if obs.timestamp.tzinfo is None else obs.timestamp
            source = getattr(obs, "source", "default")
            key = (ts, interval, source)
            if key in seen_keys:
                duplicate_count += 1
            else:
                seen_keys.add(key)
                deduped.append(obs)

        # 4. Detect Gaps and Missing Candles
        gap_details: List[Dict[str, Any]] = []
        missing_candles_count = 0
        stale_price_count = 0
        flatline_run = 1

        for i in range(len(deduped) - 1):
            t_curr = deduped[i].timestamp.replace(tzinfo=timezone.utc) if deduped[i].timestamp.tzinfo is None else deduped[i].timestamp
            t_next = deduped[i + 1].timestamp.replace(tzinfo=timezone.utc) if deduped[i + 1].timestamp.tzinfo is None else deduped[i + 1].timestamp
            delta_sec = (t_next - t_curr).total_seconds()

            if delta_sec > (expected_step * 1.5):
                missing_in_gap = int(round(delta_sec / expected_step)) - 1
                if missing_in_gap > 0:
                    missing_candles_count += missing_in_gap
                    gap_details.append({
                        "gap_start": t_curr.isoformat(),
                        "gap_end": t_next.isoformat(),
                        "duration_seconds": delta_sec,
                        "missing_candles": missing_in_gap,
                    })

            # Check for stale prices (flatline OHLC)
            if (
                deduped[i].open == deduped[i + 1].open
                and deduped[i].high == deduped[i + 1].high
                and deduped[i].low == deduped[i + 1].low
                and deduped[i].close == deduped[i + 1].close
            ):
                flatline_run += 1
                if flatline_run >= 4:
                    stale_price_count += 1
            else:
                flatline_run = 1

        earliest = deduped[0].timestamp if deduped else None
        latest = deduped[-1].timestamp if deduped else None

        total_actual = len(deduped)
        total_expected = total_actual + missing_candles_count
        continuity_ratio = round(total_actual / total_expected, 4) if total_expected > 0 else 1.0

        is_healthy = (
            duplicate_count == 0
            and out_of_order_count == 0
            and missing_candles_count == 0
            and stale_price_count == 0
        )

        report = DataQualityReport(
            asset_id=asset_id,
            symbol=symbol,
            interval=interval,
            is_healthy=is_healthy,
            total_observations=total_actual,
            duplicate_count=duplicate_count,
            missing_candles_count=missing_candles_count,
            out_of_order_count=out_of_order_count,
            stale_price_count=stale_price_count,
            gap_count=len(gap_details),
            gap_details=gap_details,
            latest_observation_time=latest,
            earliest_observation_time=earliest,
            continuity_ratio=continuity_ratio,
        )

        return deduped, report
