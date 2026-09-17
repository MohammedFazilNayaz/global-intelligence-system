"""Deterministic End-to-End Verification Script for V0.2 — Intelligence Extraction."""

import os
import sys
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import text, select, func

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.config.settings import get_settings
from backend.app.db.test_session import test_engine as engine, TestSessionLocal as SessionLocal, init_test_db
from backend.app.db.session import get_db
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.event import ExtractedEvent
from backend.app.services.source_service import create_source
from backend.app.services.extraction_service import extract_from_document
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


def run_v0_2_verification():
    init_test_db()
    settings = get_settings()
    print("=" * 80)
    print(f"V0.2 INTELLIGENCE EXTRACTION E2E VERIFICATION ON TEST DB: {engine.url}")
    print("=" * 80)

    # 1. Database Connection & Schema Verification
    print("\n>>> 1. Verifying Database Connection and V0.2 Schema Tables...")
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
        )).fetchall()
        table_names = {r[0] for r in result}
        print(f"  Existing tables in PostgreSQL: {sorted(list(table_names))}")
        assert "entities" in table_names, "Missing 'entities' table!"
        assert "document_entities" in table_names, "Missing 'document_entities' table!"
        assert "extracted_events" in table_names, "Missing 'extracted_events' table!"
        assert "documents" in table_names, "Missing 'documents' table!"
        assert "sources" in table_names, "Missing 'sources' table!"
        print("  All V0.1 and V0.2 tables present in PostgreSQL 16.")

    db = SessionLocal()
    client = TestClient(app)

    try:
        # 2. Register Source & Create Deterministic Documents
        print("\n>>> 2. Creating Deterministic Test Intelligence Documents in PostgreSQL...")
        source_in = SourceCreate(
            name=f"V0.2 Intel Wire {uuid.uuid4().hex[:6]}",
            source_type="rss",
            base_url="https://intel.example.com",
            feed_url="https://intel.example.com/rss",
            reliability_score=0.95,
            config_metadata={"region": "global", "sector": "macro_geopolitical"},
        )
        source = create_source(db, source_in)
        print(f"  Created Source ID: {source.id}")

        now = datetime(2026, 9, 7, 14, 0, 0, tzinfo=timezone.utc)

        # Document 1: Central Bank Decision & Currency
        doc1_title = "Federal Reserve Holds Benchmark Rates Steady Amid Inflation Moderation"
        doc1_desc = "Policymakers in Washington maintained the target range citing stable US Dollar conditions."
        doc1_content = "Chairman Powell stated that benchmark rates remain appropriate as consumer price index figures cool."
        doc1 = Document(
            source_id=source.id,
            title=doc1_title,
            description=doc1_desc,
            content=doc1_content,
            url=f"https://intel.example.com/report/{uuid.uuid4().hex[:8]}",
            published_at=now,
            content_hash=compute_content_hash(doc1_title, "url1", doc1_desc),
            processing_status="NORMALIZED",
        )

        # Document 2: Geopolitics & Energy Commodities
        doc2_title = "OPEC Agrees on Crude Oil Production Quotas Following Vienna Summit"
        doc2_desc = "Ministers from Saudi Arabia and UAE reached consensus on production limits to stabilize Brent Crude."
        doc2_content = "The strategic energy accord was finalized with backing from Russian representatives."
        doc2 = Document(
            source_id=source.id,
            title=doc2_title,
            description=doc2_desc,
            content=doc2_content,
            url=f"https://intel.example.com/report/{uuid.uuid4().hex[:8]}",
            published_at=now,
            content_hash=compute_content_hash(doc2_title, "url2", doc2_desc),
            processing_status="NORMALIZED",
        )

        db.add_all([doc1, doc2])
        db.commit()
        db.refresh(doc1)
        db.refresh(doc2)
        print(f"  Inserted Document 1: {doc1.id} ('{doc1.title[:45]}...')")
        print(f"  Inserted Document 2: {doc2.id} ('{doc2.title[:45]}...')")

        # 3. Execute Extraction Pipeline
        print("\n>>> 3. Executing V0.2 Intelligence Extraction Pipeline...")
        resp1 = extract_from_document(db, doc1.id)
        resp2 = extract_from_document(db, doc2.id)

        print(f"  Doc 1 Extraction: {resp1.entities_count} entities, {resp1.events_count} events in {resp1.duration_seconds}s")
        print(f"  Doc 2 Extraction: {resp2.entities_count} entities, {resp2.events_count} events in {resp2.duration_seconds}s")
        assert resp1.entities_count >= 3
        assert resp1.events_count >= 1
        assert resp2.entities_count >= 3
        assert resp2.events_count >= 1

        db.refresh(doc1)
        db.refresh(doc2)
        assert doc1.processing_status == ProcessingStatus.EXTRACTED.value
        assert doc2.processing_status == ProcessingStatus.EXTRACTED.value
        print("  Both documents transitioned to 'EXTRACTED' processing status.")

        # 4. Inspect Resulting Canonical Entities
        print("\n>>> 4. Inspecting Stored Entities & Canonical Normalization in PostgreSQL...")
        entities = list(db.scalars(select(Entity)).all())
        print(f"  Total canonical entities in DB: {len(entities)}")
        entity_types = {e.entity_type for e in entities}
        print(f"  Observed Entity Types: {sorted(list(entity_types))}")

        # Verify specific canonical entities
        names = {e.canonical_name: e for e in entities}
        assert "Federal Reserve" in names, "Federal Reserve not in canonical entities!"
        assert "US Dollar" in names, "US Dollar not in canonical entities!"
        assert "Crude Oil" in names, "Crude Oil not in canonical entities!"
        assert "Saudi Arabia" in names, "Saudi Arabia not in canonical entities!"
        fed_ent = names["Federal Reserve"]
        print(f"  Verified Entity: id={fed_ent.id}, type={fed_ent.entity_type}, canonical='{fed_ent.canonical_name}', cc={fed_ent.country_code}")

        # 5. Inspect Document/Entity Associations
        print("\n>>> 5. Inspecting Document <-> Entity Associations & Roles...")
        doc1_associations = list(db.scalars(
            select(DocumentEntity).where(DocumentEntity.document_id == doc1.id)
        ).all())
        for de in doc1_associations:
            print(f"  [Doc 1 Mention] text='{de.mention_text}', role='{de.entity_role}', confidence={de.confidence}")
            assert de.confidence >= 0.70
            assert de.entity_role in ["actor", "location", "currency", "indicator", "subject", "other"]

        # 6. Inspect Extracted Events & Score Separation
        print("\n>>> 6. Inspecting Extracted Events & Score Separation...")
        events = list(db.scalars(
            select(ExtractedEvent).where(ExtractedEvent.document_id.in_([doc1.id, doc2.id]))
        ).all())
        print(f"  Total Extracted Events for Test Documents: {len(events)}")
        for ev in events:
            print(f"  [Event] type='{ev.event_type}', title='{ev.event_title[:45]}...', conf={ev.confidence}, imp={ev.importance}")
            assert ev.confidence > 0.0 and ev.confidence <= 1.0
            assert ev.importance > 0.0 and ev.importance <= 1.0
            assert ev.confidence != ev.importance, "Confidence and Importance should not be identical arbitrary scores!"
            assert ev.document_id in [doc1.id, doc2.id]

        # 7. Verify Provenance
        print("\n>>> 7. Verifying Extraction Provenance...")
        assert "extraction_provenance" in doc1.raw_metadata
        prov = doc1.raw_metadata["extraction_provenance"]
        print(f"  Provenance Metadata: {prov}")
        assert prov["extractor_name"] == "RuleBasedIntelligenceExtractor"
        assert prov["extractor_version"] in ("0.2.0", "0.2.1")
        assert "processed_at" in prov

        # 8. Verify Reprocessing Capability
        print("\n>>> 8. Verifying Reprocessing Capability...")
        reproc_resp = extract_from_document(db, doc1.id, reprocess=True)
        assert reproc_resp.processing_status == ProcessingStatus.EXTRACTED.value
        db.refresh(doc1)
        assert "extraction_history" in doc1.raw_metadata
        print(f"  Extraction history audit records: {len(doc1.raw_metadata['extraction_history'])}")
        assert len(doc1.raw_metadata["extraction_history"]) >= 1
        print("  Reprocessing successfully archived previous provenance and updated intelligence.")

        # 9. Verify Rollback on Extraction Failure
        print("\n>>> 9. Verifying Failed Extraction Transaction Rollback...")
        class IntentionalFailExtractor:
            name = "FailExtractor"
            version = "0.0.1"
            def extract(self, *args, **kwargs):
                raise ValueError("Simulated pipeline crash for rollback verification")

        try:
            extract_from_document(db, doc2.id, extractor=IntentionalFailExtractor(), reprocess=True)
        except ValueError:
            print("  Exception caught as expected.")

        db.refresh(doc2)
        print(f"  Doc 2 Status after failure: {doc2.processing_status}")
        assert doc2.processing_status == ProcessingStatus.EXTRACTION_FAILED.value
        assert "Simulated pipeline crash" in doc2.raw_metadata.get("extraction_error", "")
        assert doc2.title == doc2_title, "Original document title was corrupted!"
        print("  Transaction cleanly rolled back, failure recorded, and document evidence preserved.")

        # 10. Verify FastAPI REST API Endpoints
        print("\n>>> 10. Verifying FastAPI REST Endpoints for V0.2...")

        # GET /api/v1/entities
        e_resp = client.get("/api/v1/entities?page=1&page_size=10")
        assert e_resp.status_code == 200
        print(f"  GET /api/v1/entities: total={e_resp.json()['total']}, page_size={e_resp.json()['page_size']}")

        # GET /api/v1/entities/{id}
        first_ent_id = e_resp.json()["items"][0]["id"]
        single_e_resp = client.get(f"/api/v1/entities/{first_ent_id}")
        assert single_e_resp.status_code == 200
        print(f"  GET /api/v1/entities/{first_ent_id}: canonical='{single_e_resp.json()['canonical_name']}'")

        # GET /api/v1/documents/{id}/entities
        doc_e_resp = client.get(f"/api/v1/documents/{doc1.id}/entities")
        assert doc_e_resp.status_code == 200
        print(f"  GET /api/v1/documents/{doc1.id}/entities: count={len(doc_e_resp.json())}")

        # GET /api/v1/documents/{id}/events
        doc_ev_resp = client.get(f"/api/v1/documents/{doc1.id}/events")
        assert doc_ev_resp.status_code == 200
        print(f"  GET /api/v1/documents/{doc1.id}/events: count={len(doc_ev_resp.json())}")

        # GET /api/v1/events
        ev_list_resp = client.get("/api/v1/events?min_confidence=0.5&order_by=importance_desc")
        assert ev_list_resp.status_code == 200
        print(f"  GET /api/v1/events: total={ev_list_resp.json()['total']}")

        # POST /api/v1/documents/{id}/extract
        api_extract_resp = client.post(f"/api/v1/documents/{doc1.id}/extract?reprocess=true")
        assert api_extract_resp.status_code == 200
        print(f"  POST /api/v1/documents/{doc1.id}/extract: status={api_extract_resp.json()['processing_status']}")

        print("\n" + "=" * 80)
        print("ALL V0.2 E2E VERIFICATIONS PASSED SUCCESSFULLY AGAINST POSTGRESQL 16!")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    run_v0_2_verification()
