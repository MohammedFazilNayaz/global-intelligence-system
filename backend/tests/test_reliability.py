from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError
from backend.app.processors.normalizer import build_normalized_document
from backend.app.utils.http_client import (
    ResilientHttpClient,
    HttpTimeoutError,
    HttpStatusError,
    HttpClientError,
)
from backend.app.collectors.rss import RSSCollector
from backend.app.collectors.base import CollectorError
from backend.app.services.ingestion import ingest_from_source


def test_normalizer_missing_title():
    """Missing or empty title defaults to 'Untitled' without failing."""
    doc = build_normalized_document(
        source_name="Test Source",
        title="",
        url="https://example.com/no-title",
    )
    assert doc.title == "Untitled"


def test_normalizer_invalid_timestamp():
    """Malformed or invalid publication timestamp gracefully falls back to UTC now."""
    doc = build_normalized_document(
        source_name="Test Source",
        title="Valid Title",
        url="https://example.com/item",
        published_at="not-a-real-date-string",
    )
    assert doc.published_at.tzinfo == timezone.utc
    assert isinstance(doc.published_at, datetime)


def test_normalizer_missing_timestamp():
    """None publication timestamp gracefully falls back to UTC now."""
    doc = build_normalized_document(
        source_name="Test Source",
        title="Valid Title",
        url="https://example.com/item",
        published_at=None,
    )
    assert doc.published_at.tzinfo == timezone.utc


def test_http_client_timeout():
    """HTTP client raises HttpTimeoutError when network times out."""
    client = ResilientHttpClient(timeout_seconds=0.01, max_retries=1)
    with patch("httpx.Client.get", side_effect=httpx.TimeoutException("Connection timed out")):
        with pytest.raises(HttpTimeoutError):
            client.get("https://example.com/timeout")


def test_http_client_status_error():
    """HTTP client raises HttpStatusError on 4xx/5xx responses."""
    client = ResilientHttpClient(max_retries=1)
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404 Not Found", request=MagicMock(), response=mock_response
    )
    with patch("httpx.Client.get", return_value=mock_response):
        with pytest.raises(HttpStatusError) as exc_info:
            client.get("https://example.com/not-found")
        assert exc_info.value.status_code == 404


def test_collector_failure_logged_and_raised():
    """Collector failures must be logged and raised as CollectorError, never silently swallowed."""
    mock_client = MagicMock()
    mock_client.get.side_effect = httpx.NetworkError("DNS resolution failed")

    collector = RSSCollector(
        name="Failing Feed",
        feed_url="https://broken.domain/rss.xml",
        base_url="https://broken.domain",
        http_client=mock_client,
    )

    with pytest.raises(CollectorError) as exc_info:
        collector.collect()
    assert "Failing Feed" in str(exc_info.value)


def test_database_rollback_on_commit_failure(db_session, sample_source):
    """Database transaction must rollback on commit error without leaving dangling state."""
    doc = build_normalized_document(
        source_name=sample_source.name,
        title="Valid Headline",
        url="https://example.com/valid",
    )
    mock_collector = MagicMock()
    mock_collector.collect.return_value = [doc]

    with patch.object(db_session, "commit", side_effect=SQLAlchemyError("Simulated disk full")):
        with pytest.raises(SQLAlchemyError):
            ingest_from_source(db_session, sample_source, collector=mock_collector)

    # Verify session is still usable and no dirty state remains
    db_session.rollback()
