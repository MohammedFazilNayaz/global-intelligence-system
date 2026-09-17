import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["ALLOW_PROD_AUDIT"] = "1"

from backend.app.db.session import SessionLocal
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.cluster import EventCluster
from backend.app.models.event import ExtractedEvent
from backend.app.models.relationship import EntityRelationship
from backend.app.models.market_observation import MarketObservation
from backend.app.models.entity import Entity
from sqlalchemy import select, func, or_

def main():
    db = SessionLocal()
    try:
        print("=" * 80)
        print("PHASE 13: PRODUCTION DATA INTEGRITY & ISOLATION AUDIT")
        print("=" * 80)
        
        findings = {}
        
        # 1. Synthetic / Mock / TEST_* documents
        synth_docs = db.query(Document).filter(
            or_(
                Document.title.startswith("TEST: "),
                Document.title.startswith("[TEST]"),
                Document.title.startswith("MOCK: "),
                Document.external_id.startswith("test_"),
                Document.external_id.startswith("mock_"),
                Document.processing_status == "SYNTHETIC_TEST",
            )
        ).count()
        findings["synthetic_documents"] = synth_docs
        print(f"Synthetic / Mock / TEST_* documents: {synth_docs}")
        
        # 2. Synthetic / Mock / TEST_* event clusters
        synth_clusters = db.query(EventCluster).filter(
            or_(
                EventCluster.canonical_title.startswith("TEST: "),
                EventCluster.canonical_title.startswith("[TEST]"),
                EventCluster.canonical_title.startswith("MOCK: "),
                EventCluster.status == "SYNTHETIC_TEST",
            )
        ).count()
        findings["synthetic_event_clusters"] = synth_clusters
        print(f"Synthetic / Mock / TEST_* event clusters: {synth_clusters}")
        
        # 3. Synthetic / Mock / TEST_* extracted events
        synth_extracted = db.query(ExtractedEvent).filter(
            or_(
                ExtractedEvent.event_title.startswith("TEST: "),
                ExtractedEvent.event_title.startswith("[TEST]"),
                ExtractedEvent.event_title.startswith("MOCK: "),
            )
        ).count()
        findings["synthetic_extracted_events"] = synth_extracted
        print(f"Synthetic / Mock / TEST_* extracted events: {synth_extracted}")
        
        # 4. Synthetic / Mock relationships
        synth_rels = db.query(EntityRelationship).filter(
            or_(
                EntityRelationship.relationship_type.startswith("TEST_"),
                EntityRelationship.relationship_type.startswith("MOCK_"),
                EntityRelationship.extraction_method.ilike("%synthetic%"),
                EntityRelationship.extraction_method.ilike("%mock%"),
            )
        ).count()
        findings["synthetic_relationships"] = synth_rels
        print(f"Synthetic / Mock relationships: {synth_rels}")
        
        # 5. Synthetic market observations
        from sqlalchemy import String as SQLString
        synth_mkts = db.query(MarketObservation).filter(
            or_(
                MarketObservation.metadata_.cast(SQLString).ilike("%synthetic%"),
                MarketObservation.metadata_.cast(SQLString).ilike("%mock%"),
            )
        ).count()
        findings["synthetic_market_observations"] = synth_mkts
        print(f"Synthetic / Mock market observations: {synth_mkts}")
        
        # 6. Fabricated coordinates (entities with lat/lng outside valid ranges [-90,90] and [-180,180])
        total_entities = db.scalar(select(func.count(Entity.id)))
        entities_with_coords = 0
        invalid_coords = 0
        for e in db.query(Entity).all():
            meta = e.metadata_ or {}
            coords = meta.get("coordinates") or meta.get("geo")
            if coords and isinstance(coords, dict):
                entities_with_coords += 1
                lat = coords.get("lat") or coords.get("latitude")
                lng = coords.get("lng") or coords.get("lon") or coords.get("longitude")
                if lat is not None and lng is not None:
                    try:
                        f_lat = float(lat)
                        f_lng = float(lng)
                        if not (-90.0 <= f_lat <= 90.0 and -180.0 <= f_lng <= 180.0):
                            invalid_coords += 1
                    except (ValueError, TypeError):
                        invalid_coords += 1
                        
        findings["total_entities"] = total_entities
        findings["entities_with_coords"] = entities_with_coords
        findings["invalid_coordinates"] = invalid_coords
        print(f"Total entities: {total_entities} (Entities with coords: {entities_with_coords})")
        print(f"Invalid / fabricated coordinates: {invalid_coords}")
        
        # Overall verdict
        clean = (
            synth_docs == 0
            and synth_clusters == 0
            and synth_extracted == 0
            and synth_rels == 0
            and synth_mkts == 0
            and invalid_coords == 0
        )
        print("\nProduction Integrity Verdict: " + ("100% CLEAN — ZERO SYNTHETIC ROWS" if clean else "CONTAMINATION DETECTED"))
        
        with open("scratch/certify_prod_integrity_results.json", "w", encoding="utf-8") as f:
            json.dump({
                "verdict": "CLEAN" if clean else "DIRTY",
                "metrics": findings,
            }, f, indent=2)
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
