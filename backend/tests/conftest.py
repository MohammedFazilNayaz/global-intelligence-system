import os
import sys
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.main import app
from backend.app.processors.hasher import compute_content_hash

# NOTE: Default pytest fixtures below utilize an isolated, in-memory SQLite engine
# for fast, hermetic unit testing of business logic, schemas, and API handlers.
# For full database engine verification against live PostgreSQL 16, see:
# - backend/tests/test_postgres_integration.py
# - scripts/verify_postgresql_e2e.py
TEST_DATABASE_URL = os.environ.get("UNIT_TEST_DATABASE_URL", "sqlite:///:memory:")
os.environ["UNIT_TEST_DATABASE_URL"] = TEST_DATABASE_URL

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False} if TEST_DATABASE_URL.startswith("sqlite") else {},
    poolclass=StaticPool if TEST_DATABASE_URL.startswith("sqlite") else None,
)

if TEST_DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    expire_on_commit=False,
)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database schema for each test."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_source(db_session) -> Source:
    """Fixture providing a saved test Source."""
    source = Source(
        name="Test Intelligence Feed",
        source_type="rss",
        base_url="https://example.com",
        feed_url="https://example.com/rss.xml",
        reliability_score=0.85,
        active=True,
        polling_interval_seconds=300,
        config_metadata={"category": "global_security"},
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source


@pytest.fixture
def sample_document(db_session, sample_source) -> Document:
    """Fixture providing a saved test Document."""
    now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
    content_hash = compute_content_hash(
        title="Major Energy Accord Signed",
        url="https://example.com/news/101",
        description="Key global powers agree to strategic energy framework.",
    )
    doc = Document(
        source_id=sample_source.id,
        external_id="guid-101",
        title="Major Energy Accord Signed",
        description="Key global powers agree to strategic energy framework.",
        content="Full report on the multinational energy agreement...",
        url="https://example.com/news/101",
        author="Diplomatic Bureau",
        published_at=now,
        ingested_at=now,
        content_hash=content_hash,
        language="en",
        raw_metadata={"raw_key": "raw_val"},
        processing_status="NORMALIZED",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


@pytest.fixture
def sample_rss_xml() -> str:
    """Realistic XML string for RSS testing."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Global Wire News</title>
    <link>https://example.com</link>
    <description>International reporting</description>
    <language>en-US</language>
    <item>
      <title>Summit Concludes with Trade Pact</title>
      <link>https://example.com/trade-pact-2026</link>
      <guid isPermaLink="true">https://example.com/trade-pact-2026</guid>
      <description>&lt;p&gt;Ministers announced a landmark trade corridor agreement.&lt;/p&gt;</description>
      <dc:creator>Elena Rostova</dc:creator>
      <pubDate>Mon, 07 Sep 2026 10:00:00 GMT</pubDate>
      <category>Trade</category>
      <category>Economy</category>
    </item>
    <item>
      <title>Central Banks Coordinate Liquidity Facility</title>
      <link>https://example.com/central-banks-facility</link>
      <guid isPermaLink="true">https://example.com/central-banks-facility</guid>
      <description>Joint statement issued regarding cross-border currency swap lines.</description>
      <pubDate>Mon, 07 Sep 2026 09:30:00 GMT</pubDate>
      <category>Finance</category>
    </item>
  </channel>
</rss>"""
