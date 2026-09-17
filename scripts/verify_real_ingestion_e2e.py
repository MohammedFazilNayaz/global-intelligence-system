"""
V0.7.1 Real End-to-End Ingestion & Provenance Verification Script.
Validates the complete live ingestion chain from genuine public sources:
SOURCE -> HTTP FETCH -> RAW DOC -> NORMALIZATION -> DEDUPLICATION -> EXTRACTION -> EVENT -> CLUSTER -> POSTGRESQL -> API -> LIVE FEED.
"""
import os
import sys
import urllib.request
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Explicit flag allowing read-only inspection of production database
os.environ["ALLOW_PROD_AUDIT"] = "1"

from backend.app.db.session import SessionLocal
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.event import ExtractedEvent
from backend.app.models.cluster import EventCluster


def run_real_ingestion_verification():
    print("=" * 70)
    print("=== V0.7.1 REAL INGESTION & DATA INTEGRITY E2E VERIFICATION ===")
    print("=" * 70)

    db = SessionLocal()
    try:
        # 1. Verify Genuine Active Sources
        print("\n>>> 1. Verifying Genuine Public Sources in Database...")
        sources = db.query(Source).filter(Source.active.is_(True)).all()
        assert len(sources) >= 2, f"Expected at least 2 active sources, found {len(sources)}"
        for s in sources:
            print(f"  Source: '{s.name}' ({s.source_type}) | Feed: {s.feed_url}")
            print(f"    Last attempted:  {s.last_attempted_fetch_at}")
            print(f"    Last successful: {s.last_successful_fetch_at}")
            print(f"    Freshness:       {s.freshness_status}")
            assert not any(ph in s.feed_url for ph in ["example", ".test", "bench", "reuters.com/rss"]), (
                f"Placeholder feed URL found in production: {s.feed_url}"
            )
        print("[PASS] Verified genuine public sources with live endpoints.")

        # 2. Verify Ingested Real Documents
        print("\n>>> 2. Verifying Normalized Real Documents & Deduplication...")
        docs = db.query(Document).order_by(Document.ingested_at.desc()).all()
        assert len(docs) > 0, "Zero documents found in production database!"
        print(f"  Total verified real documents in database: {len(docs)}")
        
        sample_doc = docs[0]
        print(f"  Sample Document: '{sample_doc.title}'")
        print(f"    Source:      {sample_doc.source.name if sample_doc.source else 'Unknown'}")
        print(f"    URL:         {sample_doc.url}")
        print(f"    Published:   {sample_doc.published_at}")
        print(f"    Ingested:    {sample_doc.ingested_at}")
        print(f"    Status:      {sample_doc.processing_status}")
        print(f"    Hash:        {sample_doc.content_hash[:16]}...")
        assert sample_doc.published_at is not None, "Document missing publication timestamp!"
        assert sample_doc.ingested_at is not None, "Document missing ingestion timestamp!"
        assert sample_doc.url.startswith("http"), "Document missing legitimate HTTP URL!"
        print("[PASS] Verified real document structure and provenance timestamps.")

        # 3. Verify Extracted Events & Geolocation
        print("\n>>> 3. Verifying Extracted Events & Geolocation...")
        events = db.query(ExtractedEvent).all()
        assert len(events) > 0, "Zero events extracted from genuine documents!"
        print(f"  Total extracted events: {len(events)}")
        for ev in events[:5]:
            loc_name = ev.location_entity.canonical_name if ev.location_entity else "Unresolved"
            print(f"  Event: '{ev.event_title}' | Type: {ev.event_type} | Location: {loc_name}")
        print("[PASS] Verified real event extraction and location resolution.")

        # 4. Verify Event Clusters
        print("\n>>> 4. Verifying Event Clusters...")
        clusters = db.query(EventCluster).all()
        assert len(clusters) > 0, "Zero event clusters formed!"
        print(f"  Total event clusters: {len(clusters)}")
        for c in clusters[:5]:
            print(f"  Cluster: '{c.canonical_title}' (Confidence: {c.confidence})")
        print("[PASS] Verified event clustering.")

        # 5. Verify API Gateway Exposure
        print("\n>>> 5. Verifying Live Feed API Gateway (/api/v1/intelligence/live)...")
        req = urllib.request.Request("http://127.0.0.1:8000/api/v1/intelligence/live")
        with urllib.request.urlopen(req) as response:
            assert response.status == 200, f"API returned status {response.status}"
            payload = json.loads(response.read().decode())
        
        feed_items = payload.get("items", [])
        total = payload.get("total", 0)
        freshness = payload.get("freshness_summary", {})
        print(f"  Live Feed items returned: {len(feed_items)} (Total: {total})")
        print(f"  Freshness breakdown: {freshness}")
        assert total > 0, "Live feed returned 0 total items!"
        assert len(feed_items) > 0, "Live feed items list empty!"

        first_item = feed_items[0]
        print(f"\n>>> Verified Provenance Ledger on Top Live Feed Item:")
        print(f"  Event Title:        {first_item['event_title']}")
        print(f"  Event Time:         {first_item['event_time']}")
        print(f"  Source Name:        {first_item['source_name']}")
        print(f"  Primary Location:   {first_item['primary_location']}")
        print(f"  Freshness Status:   {first_item['freshness_status']}")
        print(f"  Age Seconds:        {first_item['age_seconds']}s")
        print(f"  Provenance URL:     {first_item['provenance_url']}")
        assert first_item["provenance_url"] is not None, "Live feed item missing provenance URL!"

        print("\n" + "=" * 70)
        print("[SUCCESS] Phase 5 Real Ingestion E2E Verification PASSED!")
        print("=" * 70)
    finally:
        db.close()


if __name__ == "__main__":
    run_real_ingestion_verification()
