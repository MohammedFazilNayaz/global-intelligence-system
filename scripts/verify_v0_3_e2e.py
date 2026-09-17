"""Deterministic End-to-End Verification Script for V0.3 — Deduplication + Event Clustering."""

import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import text, select, func

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.config.settings import get_settings
from backend.app.db.test_session import test_engine as engine, TestSessionLocal as SessionLocal, init_test_db, clean_test_db
from backend.app.db.session import get_db
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.event import ExtractedEvent
from backend.app.models.cluster import EventCluster, EventClusterMember
from backend.app.services.source_service import create_source
from backend.app.services.extraction_service import extract_from_document
from backend.app.services.clustering_service import (
    cluster_extracted_event,
    cluster_document_events,
    get_event_cluster,
    get_cluster_for_event,
)
from backend.app.schemas.source import SourceCreate
from backend.app.schemas.extraction import ProcessingStatus
from backend.app.processors.hasher import compute_content_hash
from backend.app.main import app

def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db


def run_v0_3_verification():
    clean_test_db()
    settings = get_settings()
    print("=" * 80)
    print(f"V0.3 DEDUPLICATION + CLUSTERING E2E VERIFICATION ON TEST DB: {engine.url}")
    print("=" * 80)

    # 1. Database Connection & Schema Verification
    print("\n>>> 1. Verifying Database Connection and V0.3 Cluster Schema Tables...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1;"))
        assert result.scalar() == 1, "Database connectivity check failed!"
        print("  Database connection: OK")

        # Check V0.3 tables
        tables_res = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND table_name IN ('event_clusters', 'event_cluster_members');
        """)).fetchall()
        found_tables = {r[0] for r in tables_res}
        assert "event_clusters" in found_tables, "Missing table 'event_clusters'"
        assert "event_cluster_members" in found_tables, "Missing table 'event_cluster_members'"
        print(f"  V0.3 Tables verified in PostgreSQL: {sorted(found_tables)}")

    db = SessionLocal()
    client = TestClient(app)

    try:
        # Clean test state
        db.query(EventClusterMember).delete()
        db.query(EventCluster).delete()
        db.query(ExtractedEvent).delete()
        db.query(DocumentEntity).delete()
        db.query(Document).delete()
        db.query(Entity).delete()
        db.query(Source).delete()
        db.commit()

        # 2. Setup Sources & Ingest Documents
        print("\n>>> 2. Ingesting Documents Across Multiple Sources...")
        src1 = Source(
            name="E2E Global Wire Reuters",
            source_type="rss",
            base_url="https://reuters.com",
            feed_url="https://reuters.com/feed",
            active=True,
        )
        src2 = Source(
            name="E2E Global Wire Bloomberg",
            source_type="rss",
            base_url="https://bloomberg.com",
            feed_url="https://bloomberg.com/feed",
            active=True,
        )
        db.add_all([src1, src2])
        db.commit()

        t0 = datetime(2026, 9, 7, 14, 0, tzinfo=timezone.utc)

        # Document 1 (Source 1): ECB Rate Hike
        doc1 = Document(
            source_id=src1.id,
            title="European Central Bank Raises Benchmark Interest Rates by 25 Basis Points",
            description="The European Central Bank in Frankfurt increased its benchmark rate.",
            content="European Central Bank raises benchmark interest rates by 25 basis points.",
            url="https://reuters.com/ecb-hike",
            published_at=t0,
            content_hash=compute_content_hash("ECB 1", "https://reuters.com/ecb-hike"),
            processing_status="NORMALIZED",
        )
        # Document 2 (Source 2): Corroborating ECB Report
        doc2 = Document(
            source_id=src2.id,
            title="ECB Increases Key Benchmark Rate Amid Moderating Inflation",
            description="European Central Bank policymakers lifted interest rates.",
            content="ECB increases key benchmark rate by quarter percentage point.",
            url="https://bloomberg.com/ecb-rate-move",
            published_at=t0 + timedelta(minutes=20),
            content_hash=compute_content_hash("ECB 2", "https://bloomberg.com/ecb-rate-move"),
            processing_status="NORMALIZED",
        )
        # Document 3 (Source 1): Distinct Event (Natural Disaster in Tokyo)
        doc3 = Document(
            source_id=src1.id,
            title="Major 6.9 Magnitude Earthquake Strikes Off the Coast of Tokyo",
            description="Tremors shook eastern Japan.",
            content="Major 6.9 magnitude earthquake strikes off the coast of Tokyo.",
            url="https://reuters.com/tokyo-quake",
            published_at=t0,
            content_hash=compute_content_hash("Quake 1", "https://reuters.com/tokyo-quake"),
            processing_status="NORMALIZED",
        )
        db.add_all([doc1, doc2, doc3])
        db.commit()

        # 3. Execute Extraction with Auto-Clustering
        print("\n>>> 3. Executing Intelligence Extraction & Auto-Clustering...")
        resp1 = extract_from_document(db, doc1.id, auto_cluster=True)
        resp2 = extract_from_document(db, doc2.id, auto_cluster=True)
        resp3 = extract_from_document(db, doc3.id, auto_cluster=True)

        assert resp1.events_count >= 1
        assert resp2.events_count >= 1
        assert resp3.events_count >= 1

        # 4. Verify Event Clusters
        print("\n>>> 4. Verifying Event Clusters Formed in PostgreSQL...")
        clusters = list(db.scalars(select(EventCluster).where(EventCluster.status == "ACTIVE")).all())
        print(f"  Total Active Clusters Formed: {len(clusters)}")
        assert len(clusters) == 2, f"Expected exactly 2 distinct event clusters, got {len(clusters)}"

        ecb_cluster = next(c for c in clusters if c.event_type == "central_bank_decision")
        quake_cluster = next(c for c in clusters if c.event_type == "natural_disaster")

        print(f"  ECB Cluster: id={ecb_cluster.id}, title='{ecb_cluster.canonical_title[:40]}...', conf={ecb_cluster.confidence}")
        print(f"  Quake Cluster: id={quake_cluster.id}, title='{quake_cluster.canonical_title[:40]}...', conf={quake_cluster.confidence}")

        # 5. Verify Multi-Source Independence and Corroboration
        print("\n>>> 5. Verifying Multi-Source Independence & Evidence Tracking...")
        meta = ecb_cluster.metadata_
        print(f"  ECB Cluster Metadata: {meta}")
        assert meta["document_count"] == 2
        assert meta["unique_source_count"] == 2
        assert len(meta["source_ids"]) == 2
        assert str(src1.id) in meta["source_ids"]
        assert str(src2.id) in meta["source_ids"]

        # Corroboration bonus: multi-source cluster receives confidence boost
        assert ecb_cluster.confidence >= 0.95

        # 6. Verify Explainable Score Breakdown in EventClusterMember
        print("\n>>> 6. Verifying Decomposable Match Explanation...")
        members = list(db.scalars(
            select(EventClusterMember).where(EventClusterMember.event_cluster_id == ecb_cluster.id)
        ).all())
        assert len(members) == 2
        non_founding = [m for m in members if not m.metadata_.get("founding_member", False)]
        assert len(non_founding) == 1
        explanation = non_founding[0].metadata_
        print(f"  Decomposable Score Metadata: {explanation}")
        assert explanation["event_type_score"] == 1.0
        assert explanation["temporal_score"] > 0.95
        assert explanation["final_score"] >= explanation["threshold"]
        assert not explanation["is_vetoed"]

        # 7. Verify Idempotent Reprocessing and Cluster Consistency
        print("\n>>> 7. Verifying Reprocessing and Atomic Cluster Migration...")
        # Reprocess doc2
        extract_from_document(db, doc2.id, reprocess=True, auto_cluster=True)
        db.refresh(ecb_cluster)
        assert ecb_cluster.metadata_["document_count"] == 2
        total_memberships = db.scalar(select(func.count(EventClusterMember.id)))
        assert total_memberships == 3  # 2 for ECB, 1 for Quake

        # 8. Verify REST API Endpoints
        print("\n>>> 8. Verifying FastAPI REST API Endpoints...")
        # GET /api/v1/event-clusters
        r_list = client.get("/api/v1/event-clusters")
        assert r_list.status_code == 200
        data_list = r_list.json()
        assert data_list["total"] == 2

        # GET /api/v1/event-clusters/{id}
        r_detail = client.get(f"/api/v1/event-clusters/{ecb_cluster.id}")
        assert r_detail.status_code == 200
        data_detail = r_detail.json()
        assert len(data_detail["members"]) == 2
        assert data_detail["unique_sources_count"] == 2

        # GET /api/v1/events/{id}/cluster
        ev1 = db.scalars(select(ExtractedEvent).where(ExtractedEvent.document_id == doc1.id)).first()
        r_ev_clust = client.get(f"/api/v1/events/{ev1.id}/cluster")
        assert r_ev_clust.status_code == 200
        assert r_ev_clust.json()["event_cluster_id"] == str(ecb_cluster.id)

        # GET /api/v1/event-clusters/{id}/events
        r_clust_evs = client.get(f"/api/v1/event-clusters/{ecb_cluster.id}/events")
        assert r_clust_evs.status_code == 200
        assert len(r_clust_evs.json()) == 2

        # POST /api/v1/documents/{id}/cluster
        r_post_clust = client.post(f"/api/v1/documents/{doc1.id}/cluster")
        assert r_post_clust.status_code == 200

        print("  All V0.3 REST API endpoints returned HTTP 200 and valid schema models.")

        print("\n" + "=" * 80)
        print("ALL V0.3 E2E VERIFICATIONS PASSED SUCCESSFULLY AGAINST POSTGRESQL 16!")
        print("=" * 80)
        return True

    finally:
        db.close()


if __name__ == "__main__":
    success = run_v0_3_verification()
    sys.exit(0 if success else 1)
