import pytest
import json
from unittest.mock import MagicMock
from backend.app.collectors.geojson import GeoJSONCollector


SAMPLE_USGS_GEOJSON = {
    "type": "FeatureCollection",
    "metadata": {
        "generated": 1726145000000,
        "url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson",
        "title": "USGS Magnitude 4.5+ Earthquakes, Past Day",
        "status": 200,
        "api": "1.10.3",
        "count": 2,
    },
    "features": [
        {
            "type": "Feature",
            "properties": {
                "mag": 5.4,
                "place": "120 km ENE of Tokyo, Japan",
                "time": 1726140000000,
                "updated": 1726141000000,
                "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000sample1",
                "status": "reviewed",
                "tsunami": 0,
                "sig": 448,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [141.25, 36.10, 35.0],
            },
            "id": "us7000sample1",
        },
        {
            "type": "Feature",
            "properties": {
                "mag": 4.8,
                "place": "45 km S of Ovalle, Chile",
                "time": 1726130000000,
                "updated": 1726131000000,
                "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000sample2",
                "status": "reviewed",
                "tsunami": 0,
                "sig": 354,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-71.20, -30.98, 55.4],
            },
            "id": "us7000sample2",
        },
    ],
}


def test_geojson_collector_parse_and_normalize():
    collector = GeoJSONCollector(
        name="USGS Earthquakes M4.5+",
        feed_url="https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson",
        base_url="https://earthquake.usgs.gov",
    )
    raw_str = json.dumps(SAMPLE_USGS_GEOJSON)
    docs = collector.parse_and_normalize(raw_str)

    assert len(docs) == 2

    d1 = docs[0]
    assert d1.title == "M5.4 Earthquake - 120 km ENE of Tokyo, Japan"
    assert d1.external_id == "us7000sample1"
    assert "Tokyo, Japan" in d1.content
    assert d1.raw_metadata["latitude"] == 36.10
    assert d1.raw_metadata["longitude"] == 141.25
    assert d1.raw_metadata["depth_km"] == 35.0
    assert d1.raw_metadata["magnitude"] == 5.4
    assert d1.raw_metadata["event_type"] == "disaster"

    d2 = docs[1]
    assert d2.title == "M4.8 Earthquake - 45 km S of Ovalle, Chile"
    assert d2.raw_metadata["latitude"] == -30.98
    assert d2.raw_metadata["longitude"] == -71.20
    assert d2.raw_metadata["magnitude"] == 4.8


def test_geojson_collector_malformed():
    collector = GeoJSONCollector(
        name="USGS Earthquakes",
        feed_url="https://earthquake.usgs.gov/dummy.geojson",
        base_url="https://earthquake.usgs.gov",
    )
    with pytest.raises(ValueError, match="Malformed GeoJSON"):
        collector.parse_and_normalize("Not valid json {{{")
