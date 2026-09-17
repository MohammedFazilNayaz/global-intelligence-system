"""
V0.9-B Geographic Data Contract Test Suite.
Tests the four location states (RESOLVED, APPROXIMATE, REGIONAL, UNRESOLVED),
coordinate provenance, authentic sensor points, invalid coordinate bounds,
maritime non-point regions, multi-location events, zero coordinate fabrication,
read-only API contracts, filtering, and pagination.
"""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.event import ExtractedEvent
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.document import Document
from backend.app.models.source import Source
from backend.app.schemas.geo import (
    LocationState,
    CoordinateSourceType,
    CoordinatePrecision,
    CoordinateProvenance,
    GeographicPoint,
    EventGeographicContext,
    GeoFeatureCollection,
)
from backend.app.services.geo_service import (
    normalize_event_geography,
    get_geo_feature_collection,
    get_unresolved_events,
    _extract_sensor_coordinates,
)
from backend.app.geo.gazetteer import (
    lookup_municipal_centroid,
    is_maritime_zone,
)
from backend.app.utils.time import utc_now


@pytest.fixture
def geo_test_env(db_session):
    """Sets up a clean test document and entities for geographic contract validation."""
    source = Source(
        name="USGS Earthquakes GeoJSON",
        source_type="geojson",
        base_url="https://earthquake.usgs.gov",
        feed_url="https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson",
        active=True,
        is_primary=True,
        region="North America",
        domain="Natural Disasters",
        config_metadata={},
    )
    db_session.add(source)
    db_session.flush()

    doc = Document(
        source_id=source.id,
        title="Global Seismic & Geopolitical Bulletin",
        url="https://earthquake.usgs.gov/test-bulletin",
        content_hash=f"geo_hash_{uuid.uuid4().hex[:12]}",
        published_at=utc_now(),
        raw_metadata={},
    )
    db_session.add(doc)
    db_session.flush()

    # Create entities
    city_tokyo = Entity(
        canonical_name="Tokyo",
        normalized_name="tokyo",
        entity_type="CITY",
        country_code="JP",
        description="Capital of Japan",
    )
    country_germany = Entity(
        canonical_name="Germany",
        normalized_name="germany",
        entity_type="COUNTRY",
        country_code="DE",
        description="Federal Republic in Central Europe",
    )
    country_france = Entity(
        canonical_name="France",
        normalized_name="france",
        entity_type="COUNTRY",
        country_code="FR",
        description="Republic in Western Europe",
    )
    maritime_red_sea = Entity(
        canonical_name="Red Sea",
        normalized_name="red sea",
        entity_type="LOCATION",
        country_code=None,
        description="Strategic seawater inlet of the Indian Ocean",
    )
    org_fed = Entity(
        canonical_name="Federal Reserve",
        normalized_name="federal reserve",
        entity_type="CENTRAL_BANK",
        country_code="US",
        description="US Central Bank",
    )

    db_session.add_all([city_tokyo, country_germany, country_france, maritime_red_sea, org_fed])
    db_session.flush()

    return {
        "db": db_session,
        "source": source,
        "doc": doc,
        "tokyo": city_tokyo,
        "germany": country_germany,
        "france": country_france,
        "red_sea": maritime_red_sea,
        "fed": org_fed,
    }


# ==============================================================================
# 1. RESOLVED LOCATION & AUTHENTIC SENSOR COORDINATES
# ==============================================================================
def test_resolved_location_authentic_sensor(geo_test_env):
    """Case 1 & 5: Authentic USGS sensor coordinates produce RESOLVED state with EXACT_SENSOR_POINT precision."""
    db = geo_test_env["db"]
    doc = geo_test_env["doc"]

    event = ExtractedEvent(
        document_id=doc.id,
        event_type="disaster",
        event_title="M5.2 Earthquake - 45km W of Ternate, Indonesia",
        confidence=0.98,
        importance=0.85,
        event_time=utc_now(),
        metadata_={
            "latitude": "0.7893",
            "longitude": "127.3610",
            "magnitude": 5.2,
            "depth_km": 10.0,
            "sensor_source": "USGS_EARTHQUAKE_HAZARDS",
            "place": "45km W of Ternate, Indonesia",
        },
    )
    db.add(event)
    db.flush()

    geo_ctx = normalize_event_geography(event, db=db)

    assert geo_ctx.location_state == LocationState.RESOLVED
    assert geo_ctx.has_coordinates is True
    assert geo_ctx.primary_location is not None
    assert geo_ctx.primary_location.point is not None
    assert pytest.approx(geo_ctx.primary_location.point.latitude, rel=1e-4) == 0.7893
    assert pytest.approx(geo_ctx.primary_location.point.longitude, rel=1e-4) == 127.3610

    prov = geo_ctx.primary_location.provenance
    assert prov.coordinate_source == "USGS_EARTHQUAKE_HAZARDS"
    assert prov.coordinate_source_type == CoordinateSourceType.SENSOR
    assert prov.coordinate_precision == CoordinatePrecision.EXACT_SENSOR_POINT
    assert prov.location_state == LocationState.RESOLVED
    assert prov.confidence == 0.98


# ==============================================================================
# 2. APPROXIMATE LOCATION & MUNICIPAL CENTROID
# ==============================================================================
def test_approximate_location_municipal_centroid(geo_test_env):
    """Case 2: Known city entity maps to APPROXIMATE state with MUNICIPAL_CENTROID precision."""
    db = geo_test_env["db"]
    doc = geo_test_env["doc"]
    tokyo = geo_test_env["tokyo"]

    event = ExtractedEvent(
        document_id=doc.id,
        event_type="diplomacy",
        event_title="Leaders convene for bilateral summit in Tokyo",
        location_entity_id=tokyo.id,
        confidence=0.92,
        importance=0.75,
        event_time=utc_now(),
        metadata_={},
    )
    db.add(event)
    db.flush()

    geo_ctx = normalize_event_geography(event, db=db)

    assert geo_ctx.location_state == LocationState.APPROXIMATE
    assert geo_ctx.has_coordinates is True
    assert geo_ctx.primary_location is not None
    assert geo_ctx.primary_location.point is not None
    assert pytest.approx(geo_ctx.primary_location.point.latitude, rel=1e-4) == 35.6895
    assert pytest.approx(geo_ctx.primary_location.point.longitude, rel=1e-4) == 139.6917

    prov = geo_ctx.primary_location.provenance
    assert prov.coordinate_source == "CANONICAL_MUNICIPAL_GAZETTEER"
    assert prov.coordinate_source_type == CoordinateSourceType.MUNICIPAL
    assert prov.coordinate_precision == CoordinatePrecision.MUNICIPAL_CENTROID
    # Must NOT be represented as SENSOR or RESOLVED
    assert prov.coordinate_source_type != CoordinateSourceType.SENSOR
    assert prov.location_state != LocationState.RESOLVED


# ==============================================================================
# 3. REGIONAL LOCATION (COUNTRY & JURISDICTION LEVEL)
# ==============================================================================
def test_regional_location_country_level(geo_test_env):
    """Case 3: Country-level event maps to REGIONAL state without fabricating point coordinates."""
    db = geo_test_env["db"]
    doc = geo_test_env["doc"]
    germany = geo_test_env["germany"]

    event = ExtractedEvent(
        document_id=doc.id,
        event_type="economic_policy",
        event_title="Germany announces comprehensive industrial tax package",
        location_entity_id=germany.id,
        confidence=0.90,
        importance=0.70,
        event_time=utc_now(),
        metadata_={},
    )
    db.add(event)
    db.flush()

    geo_ctx = normalize_event_geography(event, db=db)

    assert geo_ctx.location_state == LocationState.REGIONAL
    assert geo_ctx.has_coordinates is False  # Zero fabricated point coordinates
    assert geo_ctx.primary_location is not None
    assert geo_ctx.primary_location.point is None
    assert geo_ctx.primary_location.location_name == "Germany"

    prov = geo_ctx.primary_location.provenance
    assert prov.coordinate_source_type == CoordinateSourceType.COUNTRY
    assert prov.coordinate_precision == CoordinatePrecision.NONE
    assert prov.location_state == LocationState.REGIONAL


# ==============================================================================
# 4. UNRESOLVED LOCATION & MISSING COORDINATE
# ==============================================================================
def test_unresolved_location_missing_spatial_data(geo_test_env):
    """Case 4 & 6: Event with no location entity and no coordinates is strictly UNRESOLVED."""
    db = geo_test_env["db"]
    doc = geo_test_env["doc"]

    event = ExtractedEvent(
        document_id=doc.id,
        event_type="corporate",
        event_title="Tech consortium announces next-generation chip architecture",
        location_entity_id=None,
        confidence=0.85,
        importance=0.60,
        event_time=utc_now(),
        metadata_={},
    )
    db.add(event)
    db.flush()

    geo_ctx = normalize_event_geography(event, db=db)

    assert geo_ctx.location_state == LocationState.UNRESOLVED
    assert geo_ctx.has_coordinates is False
    assert geo_ctx.primary_location is not None
    assert geo_ctx.primary_location.point is None
    assert geo_ctx.primary_location.location_name == "Location Unresolved"

    prov = geo_ctx.primary_location.provenance
    assert prov.coordinate_source is None
    assert prov.coordinate_source_type == CoordinateSourceType.UNKNOWN
    assert prov.coordinate_precision == CoordinatePrecision.NONE
    assert prov.latitude is None
    assert prov.longitude is None


# ==============================================================================
# 7 & 8. INVALID LATITUDE & LONGITUDE BOUNDS
# ==============================================================================
def test_invalid_coordinate_bounds_rejected(geo_test_env):
    """Case 7 & 8: Coordinates exceeding physical WGS-84 bounds are rejected and marked UNRESOLVED."""
    db = geo_test_env["db"]
    doc = geo_test_env["doc"]

    # Invalid latitude > 90.0
    ev_lat_err = ExtractedEvent(
        document_id=doc.id,
        event_type="disaster",
        event_title="Corrupted Latitude Event",
        confidence=0.80,
        importance=0.50,
        metadata_={"latitude": "95.5000", "longitude": "20.0000"},
    )
    db.add(ev_lat_err)
    db.flush()

    geo_ctx_lat = normalize_event_geography(ev_lat_err, db=db)
    assert geo_ctx_lat.location_state == LocationState.UNRESOLVED
    assert geo_ctx_lat.has_coordinates is False
    assert geo_ctx_lat.primary_location.point is None
    assert "out of physical bounds" in geo_ctx_lat.primary_location.provenance.verification_notes

    # Invalid longitude > 180.0
    ev_lon_err = ExtractedEvent(
        document_id=doc.id,
        event_type="disaster",
        event_title="Corrupted Longitude Event",
        confidence=0.80,
        importance=0.50,
        metadata_={"latitude": "10.0000", "longitude": "-195.0000"},
    )
    db.add(ev_lon_err)
    db.flush()

    geo_ctx_lon = normalize_event_geography(ev_lon_err, db=db)
    assert geo_ctx_lon.location_state == LocationState.UNRESOLVED
    assert geo_ctx_lon.has_coordinates is False
    assert geo_ctx_lon.primary_location.point is None
    assert "out of physical bounds" in geo_ctx_lon.primary_location.provenance.verification_notes


# ==============================================================================
# 9. MARITIME EVENTS (NO FABRICATED POINT COORDINATES)
# ==============================================================================
def test_maritime_location_preserves_regional_without_points(geo_test_env):
    """Case 9: Maritime corridor (e.g. Red Sea) is classified as REGIONAL with is_maritime=True and point=None."""
    db = geo_test_env["db"]
    doc = geo_test_env["doc"]
    red_sea = geo_test_env["red_sea"]

    event = ExtractedEvent(
        document_id=doc.id,
        event_type="conflict",
        event_title="Commercial vessel reports drone harassment in the Red Sea",
        location_entity_id=red_sea.id,
        confidence=0.91,
        importance=0.82,
        event_time=utc_now(),
        metadata_={},
    )
    db.add(event)
    db.flush()

    geo_ctx = normalize_event_geography(event, db=db)

    assert geo_ctx.location_state == LocationState.REGIONAL
    assert geo_ctx.has_coordinates is False
    assert geo_ctx.primary_location.is_maritime is True
    assert geo_ctx.primary_location.point is None
    assert geo_ctx.primary_location.provenance.coordinate_source_type == CoordinateSourceType.REGIONAL
    assert "without fabricated point coordinates" in geo_ctx.primary_location.provenance.verification_notes


# ==============================================================================
# 10. MULTI-LOCATION EVENTS
# ==============================================================================
def test_multi_location_bilateral_event(geo_test_env):
    """Case 10: Event involving multiple entities preserves primary and additional locations."""
    db = geo_test_env["db"]
    doc = geo_test_env["doc"]
    germany = geo_test_env["germany"]
    france = geo_test_env["france"]

    # Link France as an additional DocumentEntity to the parent document
    doc_ent = DocumentEntity(
        document_id=doc.id,
        entity_id=france.id,
        mention_text="France",
        entity_role="PARTICIPANT",
        confidence=0.95,
        metadata_={},
    )
    db.add(doc_ent)
    db.flush()

    # Event with primary location = Germany
    event = ExtractedEvent(
        document_id=doc.id,
        event_type="diplomacy",
        event_title="Germany and France sign cross-border energy framework",
        location_entity_id=germany.id,
        confidence=0.93,
        importance=0.78,
        event_time=utc_now(),
        metadata_={},
    )
    db.add(event)
    db.flush()

    geo_ctx = normalize_event_geography(event, db=db, include_additional_locations=True)

    assert geo_ctx.is_multi_location is True
    assert geo_ctx.primary_location.location_name == "Germany"
    assert len(geo_ctx.additional_locations) >= 1
    assert any(loc.location_name == "France" for loc in geo_ctx.additional_locations)
    assert len(geo_ctx.all_locations) >= 2


# ==============================================================================
# 11 & 12. COORDINATE PROVENANCE & ZERO COORDINATE FABRICATION
# ==============================================================================
def test_coordinate_provenance_and_no_fabrication(geo_test_env):
    """Case 11 & 12: Every coordinate has provenance; unresolved events strictly cannot have coordinates."""
    db = geo_test_env["db"]
    doc = geo_test_env["doc"]
    fed = geo_test_env["fed"]  # CENTRAL_BANK entity, non-spatial

    event = ExtractedEvent(
        document_id=doc.id,
        event_type="central_bank_decision",
        event_title="Federal Reserve holds benchmark interest rate steady",
        location_entity_id=fed.id,
        confidence=0.96,
        importance=0.88,
        event_time=utc_now(),
        metadata_={},
    )
    db.add(event)
    db.flush()

    geo_ctx = normalize_event_geography(event, db=db)

    # Invariant: A central bank mention alone does NOT infer or fabricate coordinates
    assert geo_ctx.location_state == LocationState.UNRESOLVED
    assert geo_ctx.has_coordinates is False
    assert geo_ctx.primary_location.point is None
    assert geo_ctx.primary_location.provenance.latitude is None
    assert geo_ctx.primary_location.provenance.longitude is None
    assert geo_ctx.primary_location.provenance.coordinate_source_type == CoordinateSourceType.UNKNOWN


# ==============================================================================
# 13. READ-ONLY API BEHAVIOR
# ==============================================================================
def test_read_only_api_endpoints(geo_test_env, client):
    """Case 13: All geo endpoints are strictly GET/read-only; mutating HTTP methods are disallowed."""
    # Valid GET requests return HTTP 200
    res_get = client.get("/api/v1/geo/features")
    assert res_get.status_code == 200

    res_unresolved = client.get("/api/v1/geo/unresolved")
    assert res_unresolved.status_code == 200

    # Mutating methods (POST, PUT, DELETE, PATCH) on geo features are strictly prohibited
    res_post = client.post("/api/v1/geo/features", json={"data": "test"})
    assert res_post.status_code == 405  # Method Not Allowed

    res_delete = client.delete("/api/v1/geo/features")
    assert res_delete.status_code == 405

    res_put = client.put("/api/v1/geo/features", json={})
    assert res_put.status_code == 405


# ==============================================================================
# 14 & 15. GEOJSON FEATURES API: FILTERING & PAGINATION
# ==============================================================================
def test_geojson_features_api_filtering_and_pagination(geo_test_env, client):
    """Case 14 & 15: GeoJSON endpoint filters by bounding box, location_state, event_type, and paginates."""
    db = geo_test_env["db"]
    doc = geo_test_env["doc"]
    tokyo = geo_test_env["tokyo"]

    # 1. Add event in Tokyo (APPROXIMATE)
    ev_tokyo = ExtractedEvent(
        document_id=doc.id,
        event_type="diplomacy",
        event_title="Tokyo Diplomatic Exchange",
        location_entity_id=tokyo.id,
        confidence=0.95,
        importance=0.85,
        event_time=utc_now(),
        metadata_={},
    )
    # 2. Add event with USGS coordinates in Indonesia (RESOLVED)
    ev_indonesia = ExtractedEvent(
        document_id=doc.id,
        event_type="disaster",
        event_title="M5.0 Earthquake Indonesia",
        confidence=0.99,
        importance=0.90,
        event_time=utc_now(),
        metadata_={"latitude": "0.5000", "longitude": "125.0000", "sensor_source": "USGS"},
    )
    db.add_all([ev_tokyo, ev_indonesia])
    db.commit()

    # Filter by location_state=RESOLVED
    res_resolved = client.get("/api/v1/geo/features?location_state=RESOLVED")
    assert res_resolved.status_code == 200
    data_resolved = res_resolved.json()
    assert data_resolved["type"] == "FeatureCollection"
    for f in data_resolved["features"]:
        assert f["properties"]["location_state"] == "RESOLVED"

    # Filter by event_type=disaster
    res_disaster = client.get("/api/v1/geo/features?event_type=disaster")
    assert res_disaster.status_code == 200
    data_disaster = res_disaster.json()
    for f in data_disaster["features"]:
        assert f["properties"]["event_type"] == "disaster"

    # Bounding Box filter (East Asia / Japan region: lat 30-40, lon 130-145)
    res_bbox = client.get("/api/v1/geo/features?min_lat=30.0&max_lat=40.0&min_lon=130.0&max_lon=145.0")
    assert res_bbox.status_code == 200
    data_bbox = res_bbox.json()
    for f in data_bbox["features"]:
        coords = f["geometry"]["coordinates"]
        assert 130.0 <= coords[0] <= 145.0
        assert 30.0 <= coords[1] <= 40.0

    # Pagination: page_size=1
    res_page = client.get("/api/v1/geo/features?page=1&page_size=1")
    assert res_page.status_code == 200
    data_page = res_page.json()
    assert len(data_page["features"]) <= 1
    assert data_page["page_size"] == 1


# ==============================================================================
# 16. FRESHNESS COMPATIBILITY
# ==============================================================================
def test_freshness_status_compatibility(geo_test_env, client):
    """Case 16: Events correctly map freshness into CURRENT, RECENT, STALE, HISTORICAL."""
    db = geo_test_env["db"]
    doc = geo_test_env["doc"]

    now = utc_now()
    # Event from 2 hours ago -> CURRENT
    ev_current = ExtractedEvent(
        document_id=doc.id,
        event_type="disaster",
        event_title="Recent Seismic Tremor",
        confidence=0.90,
        importance=0.70,
        event_time=now - timedelta(hours=2),
        metadata_={"latitude": "10.0", "longitude": "20.0"},
    )
    # Event from 10 days ago -> STALE
    ev_stale = ExtractedEvent(
        document_id=doc.id,
        event_type="disaster",
        event_title="Past Month Tremor",
        confidence=0.90,
        importance=0.70,
        event_time=now - timedelta(days=10),
        metadata_={"latitude": "12.0", "longitude": "22.0"},
    )
    db.add_all([ev_current, ev_stale])
    db.commit()

    res_curr = client.get("/api/v1/geo/features?freshness=CURRENT")
    assert res_curr.status_code == 200
    for f in res_curr.json()["features"]:
        assert f["properties"]["freshness_status"] == "CURRENT"

    res_stale = client.get("/api/v1/geo/features?freshness=STALE")
    assert res_stale.status_code == 200
    for f in res_stale.json()["features"]:
        assert f["properties"]["freshness_status"] == "STALE"


# ==============================================================================
# 18. ADVERSARIAL TESTS (EXPOSING FABRICATED / INFERRED COORDINATES)
# ==============================================================================
def test_adversarial_attempt_to_fabricate_coordinates(geo_test_env):
    """Adversarial Case: Ensure non-point locations or corrupt input can NEVER generate fake points."""
    db = geo_test_env["db"]
    doc = geo_test_env["doc"]

    # 1. Non-numeric coordinates string
    ev_bad_coords = ExtractedEvent(
        document_id=doc.id,
        event_type="disaster",
        event_title="Attacker injected NaN coordinate string",
        confidence=0.50,
        importance=0.50,
        metadata_={"latitude": "NaN", "longitude": "undefined"},
    )
    # 2. Extreme coordinates injection
    ev_extreme = ExtractedEvent(
        document_id=doc.id,
        event_type="conflict",
        event_title="Overflow Coordinate Injection",
        confidence=0.50,
        importance=0.50,
        metadata_={"latitude": 999999.0, "longitude": -999999.0},
    )
    # 3. Country entity with fake city text in summary
    ev_country_spoof = ExtractedEvent(
        document_id=doc.id,
        event_type="geopolitics",
        event_title="National Summit in Capital",
        event_summary="Discussion on city infrastructure in country",
        location_entity_id=geo_test_env["germany"].id,
        confidence=0.80,
        importance=0.60,
        metadata_={},
    )

    db.add_all([ev_bad_coords, ev_extreme, ev_country_spoof])
    db.flush()

    for ev in [ev_bad_coords, ev_extreme, ev_country_spoof]:
        ctx = normalize_event_geography(ev, db=db)
        # Invariant: Neither corrupted coords nor country events may have valid points
        assert ctx.has_coordinates is False
        assert ctx.primary_location.point is None
        if ctx.location_state == LocationState.UNRESOLVED:
            assert ctx.primary_location.provenance.coordinate_source_type == CoordinateSourceType.UNKNOWN


def test_get_event_geographic_context_endpoint(geo_test_env, client):
    """Verify GET /api/v1/geo/events/{event_id} returns accurate geographic contract and handles 404."""
    db = geo_test_env["db"]
    doc = geo_test_env["doc"]
    tokyo = geo_test_env["tokyo"]

    event = ExtractedEvent(
        document_id=doc.id,
        event_type="diplomacy",
        event_title="Tokyo Ministerial Conference",
        location_entity_id=tokyo.id,
        confidence=0.94,
        importance=0.80,
        event_time=utc_now(),
        metadata_={},
    )
    db.add(event)
    db.commit()

    # Successful retrieval
    res = client.get(f"/api/v1/geo/events/{event.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["event_id"] == str(event.id)
    assert data["location_state"] == "APPROXIMATE"
    assert data["primary_location"]["location_name"] == "Tokyo"
    assert data["primary_location"]["provenance"]["coordinate_source_type"] == "MUNICIPAL"

    # Non-existent event returns 404
    non_existent_id = uuid.uuid4()
    res_404 = client.get(f"/api/v1/geo/events/{non_existent_id}")
    assert res_404.status_code == 404


def test_unresolved_events_queue_endpoint(geo_test_env, client):
    """Verify GET /api/v1/geo/unresolved cleanly filters unlocated events for the triage tray."""
    db = geo_test_env["db"]
    doc = geo_test_env["doc"]

    unresolved_ev = ExtractedEvent(
        document_id=doc.id,
        event_type="cyber",
        event_title="Global Cloud Infrastructure Disruption",
        location_entity_id=None,
        confidence=0.88,
        importance=0.92,
        event_time=utc_now(),
        metadata_={},
    )
    db.add(unresolved_ev)
    db.commit()

    res = client.get("/api/v1/geo/unresolved?min_importance=0.80")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] >= 1
    found = any(item["id"] == str(unresolved_ev.id) for item in data["items"])
    assert found is True


def test_unanchored_municipality_and_maritime_text(geo_test_env):
    """Verify unanchored municipality and text-only maritime mentions."""
    db = geo_test_env["db"]
    doc = geo_test_env["doc"]

    # 1. Unanchored municipality
    unanchored_city = Entity(
        canonical_name="UnknownHillTown",
        normalized_name="unknownhilltown",
        entity_type="CITY",
        country_code="CH",
    )
    db.add(unanchored_city)
    db.flush()

    ev_unanchored = ExtractedEvent(
        document_id=doc.id,
        event_type="protest",
        event_title="Civic protest in UnknownHillTown",
        location_entity_id=unanchored_city.id,
        confidence=0.85,
        importance=0.65,
        event_time=utc_now(),
        metadata_={},
    )
    db.add(ev_unanchored)

    # 2. Text-only maritime mention
    ev_maritime_text = ExtractedEvent(
        document_id=doc.id,
        event_type="conflict",
        event_title="Naval exercises observed across the Persian Gulf",
        location_entity_id=None,
        confidence=0.88,
        importance=0.75,
        event_time=utc_now(),
        metadata_={},
    )
    db.add(ev_maritime_text)
    db.commit()

    ctx_unanchored = normalize_event_geography(ev_unanchored, db=db)
    assert ctx_unanchored.location_state == LocationState.APPROXIMATE
    assert ctx_unanchored.primary_location.point is None
    assert ctx_unanchored.primary_location.provenance.coordinate_source == "UNANCHORED_MUNICIPALITY"

    ctx_maritime = normalize_event_geography(ev_maritime_text, db=db)
    assert ctx_maritime.location_state == LocationState.REGIONAL
    assert ctx_maritime.primary_location.is_maritime is True
    assert ctx_maritime.primary_location.point is None


def test_geo_features_include_unresolved_and_country_filters(geo_test_env, client):
    """Verify include_unresolved=True and country_code filter on geo features API."""
    db = geo_test_env["db"]
    doc = geo_test_env["doc"]
    tokyo = geo_test_env["tokyo"]

    # Tokyo event (JP)
    ev_jp = ExtractedEvent(
        document_id=doc.id,
        event_type="economics",
        event_title="Bank of Japan Policy Assembly in Tokyo",
        location_entity_id=tokyo.id,
        confidence=0.92,
        importance=0.85,
        event_time=utc_now(),
        metadata_={},
    )
    # Unlocated event
    ev_unlocated = ExtractedEvent(
        document_id=doc.id,
        event_type="technology",
        event_title="Decentralized Network Protocol Upgrade",
        location_entity_id=None,
        confidence=0.80,
        importance=0.60,
        event_time=utc_now(),
        metadata_={},
    )
    db.add_all([ev_jp, ev_unlocated])
    db.commit()

    # Query with include_unresolved=True
    res_unres = client.get("/api/v1/geo/features?include_unresolved=true")
    assert res_unres.status_code == 200
    data_unres = res_unres.json()
    has_null_geom = any(f["geometry"] is None for f in data_unres["features"])
    assert has_null_geom is True

    # Query with country_code=JP
    res_jp = client.get("/api/v1/geo/features?country_code=JP")
    assert res_jp.status_code == 200
    data_jp = res_jp.json()
    for f in data_jp["features"]:
        assert f["properties"]["country_code"] == "JP"

    # Query with out-of-bounds bounding box (West Africa: lat 0-10, lon -10-0)
    res_cull = client.get("/api/v1/geo/features?min_lat=0.0&max_lat=10.0&min_lon=-10.0&max_lon=0.0")
    assert res_cull.status_code == 200
    # Tokyo should be culled
    for f in res_cull.json()["features"]:
        coords = f["geometry"]["coordinates"]
        assert -10.0 <= coords[0] <= 0.0
