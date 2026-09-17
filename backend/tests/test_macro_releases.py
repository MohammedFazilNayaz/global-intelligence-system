"""Tests for macroeconomic indicator ingestion and revision tracking."""

import pytest
from sqlalchemy import select, text
from backend.app.models.indicator import EconomicIndicator
from backend.app.models.observation import EconomicObservation
from backend.app.services.macro_ingestion_service import MacroeconomicIngestionService, SERIES_REGISTRY


def test_macro_series_ingestion_mock_data(db_session):
    """Verify that macro time-series parse and persist with accurate deltas."""
    service = MacroeconomicIngestionService()
    
    mock_csv_data = [
        ("2026-06-01", 332.568),
        ("2026-07-01", 332.813),
        ("2026-08-01", 334.131),
    ]
    
    count = service.ingest_series(db_session, "CPI_US", limit_recent=3, csv_data=mock_csv_data)
    assert count == 3
    
    # Verify indicator was created
    ind = db_session.scalars(select(EconomicIndicator).where(EconomicIndicator.symbol == "CPI_US")).first()
    assert ind is not None
    assert ind.canonical_name == "US Consumer Price Index (CPI)"
    assert ind.economic_domain == "Inflation"
    
    # Verify observations
    obs_list = list(
        db_session.scalars(
            select(EconomicObservation)
            .where(EconomicObservation.indicator_id == ind.id)
            .order_by(EconomicObservation.observation_date.asc())
        ).all()
    )
    assert len(obs_list) == 3
    
    # First point
    assert obs_list[0].reported_value == 332.568
    assert obs_list[0].observation_period == "2026-06"
    assert obs_list[0].is_revision is False
    assert obs_list[0].revision_number == 0
    
    # Second point
    assert obs_list[1].reported_value == 332.813
    assert obs_list[1].previous_value == 332.568
    assert obs_list[1].change_value == pytest.approx(0.245, abs=1e-3)
    assert obs_list[1].direction == "increase"
    
    # Third point
    assert obs_list[2].reported_value == 334.131
    assert obs_list[2].previous_value == 332.813
    assert obs_list[2].change_value == pytest.approx(1.318, abs=1e-3)
    assert obs_list[2].direction == "increase"


def test_macro_revision_tracking(db_session):
    """Verify that amended observation values trigger revision tracking."""
    service = MacroeconomicIngestionService()
    
    initial_data = [
        ("2026-07-01", 4.1),
    ]
    service.ingest_series(db_session, "UNRATE_US", limit_recent=1, csv_data=initial_data)
    
    ind = db_session.scalars(select(EconomicIndicator).where(EconomicIndicator.symbol == "UNRATE_US")).first()
    obs = db_session.scalars(
        select(EconomicObservation).where(EconomicObservation.indicator_id == ind.id)
    ).first()
    assert obs.reported_value == 4.1
    assert obs.is_revision is False
    assert obs.revision_number == 0
    
    # Revised release comes in with updated unemployment rate 4.2
    revised_data = [
        ("2026-07-01", 4.2),
    ]
    service.ingest_series(db_session, "UNRATE_US", limit_recent=1, csv_data=revised_data)
    
    db_session.refresh(obs)
    assert obs.reported_value == 4.2
    assert obs.previous_value == 4.1
    assert obs.revised_value == 4.2
    assert obs.is_revision is True
    assert obs.revision_number == 1


def test_macro_acceptance_query(db_session):
    """Verify the exact GATE-16 SQL query on test database session."""
    service = MacroeconomicIngestionService()
    service.ingest_series(db_session, "FEDFUNDS", limit_recent=2, csv_data=[("2026-07-01", 3.63), ("2026-08-01", 3.63)])
    
    sql = text("SELECT ind.symbol, COUNT(obs.id) FROM economic_indicators ind JOIN economic_observations obs ON ind.id = obs.indicator_id GROUP BY ind.symbol;")
    rows = db_session.execute(sql).fetchall()
    assert len(rows) > 0
    symbols = [r[0] for r in rows]
    assert "FEDFUNDS" in symbols
