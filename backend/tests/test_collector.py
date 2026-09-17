from unittest.mock import MagicMock
import pytest
from backend.app.collectors.rss import RSSCollector
from backend.app.collectors.api import APICollector
from backend.app.collectors.registry import get_collector_class, register_collector
from backend.app.collectors.base import CollectorError


def test_rss_collector_parsing(sample_rss_xml):
    """Verify RSSCollector extracts and normalizes entries from raw XML."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = sample_rss_xml
    mock_client.get.return_value = mock_response

    collector = RSSCollector(
        name="Global Wire",
        feed_url="https://example.com/rss.xml",
        base_url="https://example.com",
        http_client=mock_client,
    )

    documents = collector.collect()
    assert len(documents) == 2

    first_doc = documents[0]
    assert first_doc.title == "Summit Concludes with Trade Pact"
    assert first_doc.url == "https://example.com/trade-pact-2026"
    assert first_doc.author == "Elena Rostova"
    assert "Trade" in first_doc.raw_metadata.get("tags", [])
    assert first_doc.published_at.year == 2026
    assert len(first_doc.content_hash) == 64


def test_rss_collector_malformed_xml():
    """Verify malformed feed raises CollectorError without crashing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    # Malformed XML with fatal tag mismatch and no entries
    mock_response.text = "NOT XML AT ALL <<< >>>"
    mock_client.get.return_value = mock_response

    collector = RSSCollector(
        name="Broken Feed",
        feed_url="https://example.com/bad.xml",
        base_url="https://example.com",
        http_client=mock_client,
    )

    with pytest.raises(CollectorError):
        collector.collect()


def test_api_collector_parsing():
    """Verify APICollector parses JSON responses using field mappings."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "articles": [
            {
                "headline": "Semiconductor Supply Chain Stabilizes",
                "link": "https://example.com/chips-2026",
                "summary": "Manufacturing output reaches pre-crisis levels.",
                "source_id": "item-771",
                "date": "2026-09-07T11:00:00Z",
            }
        ]
    }
    mock_client.get.return_value = mock_response

    collector = APICollector(
        name="Tech Feed",
        feed_url="https://api.example.com/news",
        base_url="https://api.example.com",
        config_metadata={
            "items_path": "articles",
            "field_mapping": {
                "title": "headline",
                "url": "link",
                "description": "summary",
                "id": "source_id",
                "published_at": "date",
            },
        },
        http_client=mock_client,
    )

    documents = collector.collect()
    assert len(documents) == 1
    assert documents[0].title == "Semiconductor Supply Chain Stabilizes"
    assert documents[0].url == "https://example.com/chips-2026"
    assert documents[0].external_id == "item-771"


def test_collector_registry():
    """Verify collector registry resolves correct classes and errors on unknown types."""
    assert get_collector_class("rss") == RSSCollector
    assert get_collector_class("api") == APICollector

    with pytest.raises(ValueError):
        get_collector_class("unsupported_custom_protocol")
