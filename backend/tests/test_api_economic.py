"""
Integration tests for V0.5 Economic Intelligence REST API endpoints.
Tests pagination bounds, server-side filtering, provenance tracing,
country economic profiles, global search extension, and dashboard summary.
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.models.entity import Entity
from backend.app.models.indicator import EconomicIndicator
from backend.app.models.observation import EconomicObservation
from backend.app.models.document import Document
from backend.app.models.source import Source
from backend.app.models.event import ExtractedEvent
from backend.app.processors.hasher import compute_content_hash
from backend.app.utils.time import utc_now
from backend.app.schemas.economic import EconomicObservationRead


@pytest.fixture
def seeded_economic_db(db_session):
    db = db_session
    try:
        now = utc_now()

        # 1. Source
        src = Source(
            id=uuid.uuid4(),
            name="Econ Test Bureau",
            base_url="https://econbureau.example",
            feed_url="https://econbureau.example/feed",
            source_type="rss",
            reliability_score=0.95,
            config_metadata={},
            created_at=now,
            updated_at=now,
        )
        db.add(src)
        db.flush()

        # 2. Country Entity (get or create)
        us_entity = db.query(Entity).filter(
            Entity.entity_type == "COUNTRY",
            Entity.normalized_name == "united states",
        ).first()
        if not us_entity:
            us_entity = Entity(
                id=uuid.uuid4(),
                entity_type="COUNTRY",
                canonical_name="United States",
                normalized_name="united states",
                description="United States of America",
                country_code="US",
                metadata_={},
                created_at=now,
                updated_at=now,
            )
            db.add(us_entity)
            db.flush()

        # 3. Document
        doc_url = f"https://econbureau.example/news/{uuid.uuid4()}"
        raw_text = "US CPI rose 3.2% year-over-year in August, compared with 3.0% previously."
        doc = Document(
            id=uuid.uuid4(),
            source_id=src.id,
            title="US Inflation Edges Up in August",
            content=raw_text,
            content_format="text/plain",
            url=doc_url,
            published_at=now,
            ingested_at=now,
            content_hash=compute_content_hash(raw_text, doc_url),
            language="en",
            processing_status="EXTRACTED",
            raw_metadata={},
            created_at=now,
            updated_at=now,
        )
        db.add(doc)
        db.flush()

        # 4. Extracted Event
        ev = ExtractedEvent(
            id=uuid.uuid4(),
            document_id=doc.id,
            event_type="economic_release",
            event_title="US CPI Rose 3.2%",
            event_summary=raw_text,
            event_time=now,
            location_entity_id=us_entity.id,
            confidence=0.92,
            importance=0.88,
            metadata_={"economic_domain": "Inflation"},
            created_at=now,
            updated_at=now,
        )
        db.add(ev)
        db.flush()

        # 5. Economic Indicator (get or create)
        ind = db.query(EconomicIndicator).filter(
            EconomicIndicator.indicator_type == "cpi",
            EconomicIndicator.country_entity_id == us_entity.id,
        ).first()
        if not ind:
            ind = EconomicIndicator(
                id=uuid.uuid4(),
                canonical_name="US Consumer Price Index (CPI)",
                normalized_name="us cpi",
                indicator_type="cpi",
                economic_domain="Inflation",
                country_entity_id=us_entity.id,
                default_unit="%",
                description="US headline consumer price index",
                metadata_={},
                created_at=now,
                updated_at=now,
            )
            db.add(ind)
            db.flush()

        # 6. Economic Observation
        obs = EconomicObservation(
            id=uuid.uuid4(),
            indicator_id=ind.id,
            event_id=ev.id,
            document_id=doc.id,
            observation_period="August 2026",
            observation_date=now,
            reported_value=3.2,
            reported_unit="%",
            previous_value=3.0,
            expected_value=3.1,
            revised_value=None,
            direction="increase",
            change_value=0.2,
            change_percent=6.67,
            calculation_method="derived_difference",
            economic_relevance=0.92,
            metadata_={"evidence_snippet": raw_text},
            created_at=now,
            updated_at=now,
        )
        db.add(obs)
        db.commit()

        yield {
            "source": src,
            "entity": us_entity,
            "document": doc,
            "event": ev,
            "indicator": ind,
            "observation": obs,
        }
    finally:
        pass


def test_list_economic_indicators(client, seeded_economic_db):
    target_ind = seeded_economic_db["indicator"]
    target_country = seeded_economic_db["entity"]
    res = client.get(f"/api/v1/economic-indicators?country_id={target_country.id}&indicator_type=cpi&page=1&page_size=50")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    item = next((it for it in data["items"] if it["id"] == str(target_ind.id)), None)
    assert item is not None
    assert item["canonical_name"] == target_ind.canonical_name
    assert item["economic_domain"] == "Inflation"
    assert item["country_entity"]["canonical_name"] == "United States"


def test_get_economic_indicator_detail(client, seeded_economic_db):
    ind_id = seeded_economic_db["indicator"].id
    res = client.get(f"/api/v1/economic-indicators/{ind_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(ind_id)
    assert data["indicator_type"] == "cpi"

    # 404 for random UUID
    res_404 = client.get(f"/api/v1/economic-indicators/{uuid.uuid4()}")
    assert res_404.status_code == 404


def test_get_indicator_observations_timeseries(client, seeded_economic_db):
    ind_id = seeded_economic_db["indicator"].id
    res = client.get(f"/api/v1/economic-indicators/{ind_id}/observations")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert data["items"][0]["reported_value"] == 3.2


def test_list_economic_observations_filtering(client, seeded_economic_db):
    # Filter by domain
    res_domain = client.get("/api/v1/economic-observations?domain=Inflation")
    assert res_domain.status_code == 200
    assert res_domain.json()["total"] >= 1

    # Filter by min_relevance
    res_rel = client.get("/api/v1/economic-observations?min_relevance=0.85")
    assert res_rel.status_code == 200
    assert res_rel.json()["total"] >= 1
    for item in res_rel.json()["items"]:
        assert item["economic_relevance"] >= 0.85

    # Filter by direction
    res_dir = client.get("/api/v1/economic-observations?direction=increase")
    assert res_dir.status_code == 200
    assert res_dir.json()["total"] >= 1

    # Bounds validation (page_size > 100 -> 422)
    res_bound = client.get("/api/v1/economic-observations?page_size=150")
    assert res_bound.status_code == 422


def test_get_economic_observation_provenance(client, seeded_economic_db):
    obs_id = seeded_economic_db["observation"].id
    res = client.get(f"/api/v1/economic-observations/{obs_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(obs_id)
    assert data["reported_value"] == 3.2
    assert data["previous_value"] == 3.0
    assert data["source_name"] == "Econ Test Bureau"
    assert data["document_title"] == "US Inflation Edges Up in August"
    assert "US CPI rose 3.2%" in data["evidence_snippet"]


def test_country_economic_profile(client, seeded_economic_db):
    entity_id = seeded_economic_db["entity"].id
    res = client.get(f"/api/v1/entities/{entity_id}/economic-profile")
    assert res.status_code == 200
    data = res.json()
    assert data["country_entity"]["canonical_name"] == "United States"
    assert "Inflation" in data["domains"]
    assert len(data["domains"]["Inflation"]) >= 1
    latest_item = data["domains"]["Inflation"][0]
    assert latest_item["indicator"]["canonical_name"] == "US Consumer Price Index (CPI)"
    assert latest_item["latest_observation"]["reported_value"] == 3.2


def test_economic_global_search(client, seeded_economic_db):
    res = client.get("/api/v1/search?q=CPI")
    assert res.status_code == 200
    data = res.json()
    assert data["total_indicators"] >= 1
    assert any("CPI" in ind["canonical_name"] for ind in data["indicators"])


def test_dashboard_summary_includes_economic(client, seeded_economic_db):
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert "economic_summary" in data
    assert data["economic_summary"] is not None
    assert data["economic_summary"]["total_indicators_count"] >= 1
    assert data["economic_summary"]["total_observations_count"] >= 1
    assert "Inflation" in data["economic_summary"]["domains_breakdown"]


def test_direct_macro_telemetry_without_document_in_summary(client, db_session, seeded_economic_db):
    """Verify that direct macro telemetry observations with document_id=None (e.g. FRED/ECB feeds)
    serialize cleanly in EconomicObservationRead and GET /api/v1/dashboard/summary without 500 errors."""
    now = utc_now()
    indicator = seeded_economic_db["indicator"]

    direct_obs = EconomicObservation(
        id=uuid.uuid4(),
        indicator_id=indicator.id,
        document_id=None,
        event_id=None,
        observation_period="2026-Q1",
        observation_date=now,
        reported_value=3.4,
        reported_unit="%",
        previous_value=3.2,
        direction="increase",
        economic_relevance=0.99,
        metadata_={"source": "FRED", "series_id": "CPIAUCSL"},
        created_at=now,
        updated_at=now,
    )
    db_session.add(direct_obs)
    db_session.commit()

    # 1. Verify schema serialization directly
    read_model = EconomicObservationRead.model_validate(direct_obs)
    assert read_model.document_id is None
    assert read_model.reported_value == 3.4

    # 2. Verify dashboard summary endpoint returns 200 with this observation
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    releases = data["economic_summary"]["recent_key_releases"]
    assert any(r["id"] == str(direct_obs.id) and r["document_id"] is None for r in releases)
