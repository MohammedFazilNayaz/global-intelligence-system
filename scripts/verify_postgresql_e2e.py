"""End-to-End PostgreSQL 16 Verification Script for V0.1."""

import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
import psycopg
from sqlalchemy import text, select, func
from sqlalchemy.exc import IntegrityError

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.config.settings import get_settings
from backend.app.db.test_session import test_engine as engine, TestSessionLocal as SessionLocal, init_test_db
from backend.app.db.session import get_db
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.services.source_service import create_source, get_source_by_name
from backend.app.services.ingestion import ingest_from_source
from backend.app.schemas.source import SourceCreate
from backend.app.processors.hasher import compute_content_hash
from backend.app.main import app

def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

def run_verification():
    init_test_db()
    settings = get_settings()
    print("=" * 70)
    print(f"POSTGRESQL END-TO-END VERIFICATION ON TEST DB: {engine.url}")
    print("=" * 70)

    # 1. Database Connection & Engine probe
    print("\n>>> 1. Verifying Database Connection & Engine Probe...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version(), current_database(), current_user;")).fetchone()
        print(f"  Connected to: {result[1]} as {result[2]}")
        print(f"  PostgreSQL Engine: {result[0]}")
        assert "PostgreSQL" in result[0], "Connected engine is NOT PostgreSQL!"

    db = SessionLocal()
    try:
        # 2. Source Creation & Field Types (UUID, JSON, UTC Timestamp)
        print("\n>>> 2. Verifying Source Creation, UUID, JSON, and UTC Timestamps...")
        test_source_name = f"PG Verified Source {uuid.uuid4().hex[:6]}"
        source_in = SourceCreate(
            name=test_source_name,
            source_type="rss",
            base_url="https://feeds.bbci.co.uk",
            feed_url="https://feeds.bbci.co.uk/news/world/rss.xml",
            reliability_score=0.95,
            active=True,
            polling_interval_seconds=300,
            config_metadata={"region": "global", "tags": ["world", "verified"]},
        )
        source = create_source(db, source_in)
        print(f"  Created Source ID (UUID): {source.id}")
        assert isinstance(source.id, uuid.UUID), "Source ID is not a UUID!"
        print(f"  Source created_at: {source.created_at} (tz: {source.created_at.tzinfo})")
        assert source.created_at.tzinfo is not None, "Timestamp is not timezone-aware!"
        print(f"  Source config_metadata (JSON): {source.config_metadata}")
        assert source.config_metadata["region"] == "global", "JSON field serialization failed!"

        # 3. Document Insertion & Constraints
        print("\n>>> 3. Verifying Document Insertion, Foreign Key, and Unique Constraints...")
        now = datetime.now(timezone.utc)
        doc_hash = compute_content_hash("Postgres Verification Headline", "https://example.com/pg-doc-1")
        doc1 = Document(
            source_id=source.id,
            title="Postgres Verification Headline",
            url="https://example.com/pg-doc-1",
            published_at=now,
            content_hash=doc_hash,
            raw_metadata={"verified_on": "PostgreSQL 16", "test_id": 42},
            processing_status="NORMALIZED",
        )
        db.add(doc1)
        db.commit()
        db.refresh(doc1)
        print(f"  Inserted Document ID (UUID): {doc1.id}")
        print(f"  Document published_at: {doc1.published_at} (tz: {doc1.published_at.tzinfo})")
        assert doc1.published_at.tzinfo is not None, "Document published_at is not timezone-aware!"
        assert doc1.raw_metadata["test_id"] == 42, "Document raw_metadata JSON failed!"

        # Verify Unique Constraint on (source_id, content_hash)
        print("  Testing duplicate (source_id, content_hash) constraint...")
        doc_dup = Document(
            source_id=source.id,
            title="Postgres Verification Headline (Duplicate)",
            url="https://example.com/pg-doc-1",
            published_at=now,
            content_hash=doc_hash,
        )
        db.add(doc_dup)
        try:
            db.commit()
            raise AssertionError("Duplicate content hash constraint was NOT enforced by PostgreSQL!")
        except IntegrityError:
            db.rollback()
            print("  Constraint enforced: IntegrityError raised and transaction rolled back successfully.")

        # Verify Foreign Key Constraint
        print("  Testing Foreign Key constraint with invalid source_id...")
        fake_source_id = uuid.uuid4()
        orphan_doc = Document(
            source_id=fake_source_id,
            title="Orphan Document",
            url="https://example.com/orphan",
            published_at=now,
            content_hash=compute_content_hash("Orphan", "https://example.com/orphan"),
        )
        db.add(orphan_doc)
        try:
            db.commit()
            raise AssertionError("Foreign Key constraint was NOT enforced by PostgreSQL!")
        except IntegrityError:
            db.rollback()
            print("  Foreign Key constraint enforced: IntegrityError raised and transaction rolled back.")

        # 4. Live RSS Ingestion against BBC World News on PostgreSQL
        print("\n>>> 4. Executing Live Ingestion against BBC World News into PostgreSQL...")
        stats1 = ingest_from_source(db, source)
        print(f"  First Ingestion: fetched={stats1.total_fetched}, new={stats1.new_ingested}, duplicates={stats1.duplicates_skipped} in {stats1.duration_seconds:.2f}s")
        assert stats1.new_ingested > 0, "No documents were ingested from live feed!"

        # Live Deduplication Verification
        print("  Executing second ingestion run to verify deduplication on PostgreSQL...")
        stats2 = ingest_from_source(db, source)
        print(f"  Second Ingestion: fetched={stats2.total_fetched}, new={stats2.new_ingested}, duplicates={stats2.duplicates_skipped} in {stats2.duration_seconds:.2f}s")
        assert stats2.new_ingested == 0, f"Expected 0 new documents on duplicate run, got {stats2.new_ingested}!"
        assert stats2.duplicates_skipped == stats1.new_ingested, "Duplicates count mismatch!"

        # 5. Testing Actual FastAPI API Endpoints with PostgreSQL
        print("\n>>> 5. Testing Actual FastAPI REST Endpoints backed by PostgreSQL...")
        client = TestClient(app)

        # GET /health
        h_resp = client.get("/health")
        print(f"  GET /health: {h_resp.status_code}, data={h_resp.json()}")
        assert h_resp.status_code == 200
        assert h_resp.json()["status"] == "healthy"
        assert h_resp.json()["database"] == "connected"

        # GET /api/v1/health
        h_v1_resp = client.get("/api/v1/health")
        print(f"  GET /api/v1/health: {h_v1_resp.status_code}")
        assert h_v1_resp.status_code == 200

        # GET /api/v1/sources
        s_resp = client.get("/api/v1/sources")
        print(f"  GET /api/v1/sources: {s_resp.status_code}, total={s_resp.json()['total']}")
        assert s_resp.status_code == 200
        assert s_resp.json()["total"] >= 1

        # POST /api/v1/sources
        new_source_name = f"API Source {uuid.uuid4().hex[:6]}"
        post_s_resp = client.post("/api/v1/sources", json={
            "name": new_source_name,
            "source_type": "rss",
            "base_url": "https://example.com",
            "feed_url": "https://example.com/rss",
        })
        print(f"  POST /api/v1/sources: {post_s_resp.status_code}, id={post_s_resp.json()['id']}")
        assert post_s_resp.status_code == 201

        # GET /api/v1/documents with pagination & ordering
        d_resp = client.get(f"/api/v1/documents?source_id={source.id}&page=1&page_size=5&order_by=published_at_desc")
        print(f"  GET /api/v1/documents (paginated): {d_resp.status_code}, total={d_resp.json()['total']}, items={len(d_resp.json()['items'])}")
        assert d_resp.status_code == 200
        assert len(d_resp.json()["items"]) == 5
        first_doc_id = d_resp.json()["items"][0]["id"]

        # GET /api/v1/documents/{id}
        single_doc_resp = client.get(f"/api/v1/documents/{first_doc_id}")
        print(f"  GET /api/v1/documents/{first_doc_id}: {single_doc_resp.status_code}, title='{single_doc_resp.json()['title'][:40]}...'")
        assert single_doc_resp.status_code == 200
        assert single_doc_resp.json()["id"] == first_doc_id

        print("\n" + "=" * 70)
        print("ALL POSTGRESQL VERIFICATIONS PASSED SUCCESSFULLY!")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    run_verification()
