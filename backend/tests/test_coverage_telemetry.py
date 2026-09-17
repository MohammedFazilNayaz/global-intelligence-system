"""Tests for Coverage Intelligence Engine and telemetry metrics."""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.coverage_service import coverage_service, CANONICAL_REGIONS, CANONICAL_35_DOMAINS


def test_regional_coverage_canonical_theatres(db_session):
    """Verify that regional ratings include all 11 global theatres."""
    ratings = coverage_service.calculate_regional_ratings(db_session)
    assert len(ratings) == 11
    for region in CANONICAL_REGIONS:
        assert region in ratings
        item = ratings[region]
        assert "score" in item
        assert item["rating"] in ("GOOD", "PARTIAL", "POOR", "NONE")
        assert "active_sources" in item
        assert "weekly_events" in item


def test_domain_coverage_35_universe(db_session):
    """Verify that domain coverage tracks all 35 canonical domains."""
    domains = coverage_service.calculate_domain_coverage(db_session)
    assert domains["total_domains"] == 35
    assert "coverage_percent" in domains
    assert len(domains["domains"]) == 35
    assert "Geopolitics" in domains["domains"]
    assert "Central Banks" in domains["domains"]
    assert "Natural Disasters" in domains["domains"]


def test_disaggregated_primary_ratios_formula(db_session):
    """Verify disaggregated primary ratio calculation logic."""
    ratios = coverage_service.calculate_primary_ratios(db_session)
    assert "textual_primary_ratio_pct" in ratios
    assert "telemetry_primary_ratio_pct" in ratios
    assert ratios["textual_primary_target_pct"] == 30.0
    assert isinstance(ratios["textual_primary_pass"], bool)
    assert ratios["telemetry_primary_pass"] is True


def test_information_quality_index():
    """Verify Information Quality Index calculation."""
    iqi = coverage_service.calculate_information_quality_index(None)
    assert 0.80 <= iqi <= 1.0


def test_coverage_api_endpoint(client: TestClient):
    """Verify GET /api/v1/system/coverage returns complete telemetry payload."""
    resp = client.get("/api/v1/system/coverage")
    assert resp.status_code == 200
    data = resp.json()
    assert "timestamp" in data
    assert "regional_coverage" in data
    assert "domain_coverage" in data
    assert "primary_source_ratios" in data
    assert "information_quality_index" in data
    assert len(data["regional_coverage"]["theatres"]) == 11
