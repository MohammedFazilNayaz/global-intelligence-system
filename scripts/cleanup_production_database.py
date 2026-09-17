"""
Forensic Production Database Cleanup Script.
Removes synthetic benchmark/verification records from 'global_intelligence' in dependency-safe order.
Preserves canonical market assets (16) and canonical geopolitical entities (20).
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Explicit permission flag required for intentional maintenance
os.environ["ALLOW_PROD_DB_MUTATION"] = "1"

from sqlalchemy import text, delete, select, func
from backend.app.db.session import SessionLocal
from backend.app.models.alert import Alert
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.models.market_observation import MarketObservation
from backend.app.models.market_asset import MarketAsset
from backend.app.models.observation import EconomicObservation
from backend.app.models.indicator import EconomicIndicator
from backend.app.models.relationship import EntityRelationship
from backend.app.models.cluster import EventClusterMember, EventCluster
from backend.app.models.event import ExtractedEvent
from backend.app.models.entity import DocumentEntity, Entity
from backend.app.models.document import Document
from backend.app.models.source import Source
from backend.app.models.ingestion_run import IngestionRun

CANONICAL_SYMBOLS = [
    "BTC-USD", "ETH-USD", "SPX", "NDX", "DAX", "FTSE", "N225",
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/INR",
    "BRENT", "WTI", "GOLD", "US2Y", "US10Y"
]


def run_cleanup():
    db = SessionLocal()
    try:
        print("=" * 70)
        print("=== PRODUCTION DATABASE FORENSIC CLEANUP: global_intelligence ===")
        print("=" * 70)

        # Inventory before
        print("\n--- INVENTORY BEFORE CLEANUP ---")
        before_counts = {
            "alerts": db.scalar(select(func.count(Alert.id))) or 0,
            "correlations": db.scalar(select(func.count(EventMarketCorrelation.id))) or 0,
            "market_observations": db.scalar(select(func.count(MarketObservation.id))) or 0,
            "market_assets": db.scalar(select(func.count(MarketAsset.id))) or 0,
            "economic_observations": db.scalar(select(func.count(EconomicObservation.id))) or 0,
            "economic_indicators": db.scalar(select(func.count(EconomicIndicator.id))) or 0,
            "relationships": db.scalar(select(func.count(EntityRelationship.id))) or 0,
            "cluster_members": db.scalar(select(func.count(EventClusterMember.id))) or 0,
            "clusters": db.scalar(select(func.count(EventCluster.id))) or 0,
            "extracted_events": db.scalar(select(func.count(ExtractedEvent.id))) or 0,
            "document_entities": db.scalar(select(func.count(DocumentEntity.document_id))) or 0,
            "documents": db.scalar(select(func.count(Document.id))) or 0,
            "sources": db.scalar(select(func.count(Source.id))) or 0,
            "entities": db.scalar(select(func.count(Entity.id))) or 0,
            "ingestion_runs": db.scalar(select(func.count(IngestionRun.id))) or 0,
        }
        for k, v in before_counts.items():
            print(f"  {k:22}: {v}")

        print("\n>>> Executing dependency-safe deletion of synthetic test records...")

        # 1. Alerts
        del_alerts = db.execute(delete(Alert)).rowcount
        print(f"  [1/15] Deleted {del_alerts} alerts.")

        # 2. Market Correlations
        del_corrs = db.execute(delete(EventMarketCorrelation)).rowcount
        print(f"  [2/15] Deleted {del_corrs} market correlations.")

        # 3. Market Observations
        del_mobs = db.execute(delete(MarketObservation)).rowcount
        print(f"  [3/15] Deleted {del_mobs} market observations.")

        # 4. Market Assets (TEST_* and USDX_*, strictly preserving canonical 16)
        test_assets_stmt = delete(MarketAsset).where(
            (MarketAsset.symbol.like("TEST_%")) | (MarketAsset.symbol.like("USDX_%"))
        )
        del_assets = db.execute(test_assets_stmt).rowcount
        print(f"  [4/15] Deleted {del_assets} synthetic test market assets (TEST_*/USDX_*).")

        # 5. Economic Observations
        del_eobs = db.execute(delete(EconomicObservation)).rowcount
        print(f"  [5/15] Deleted {del_eobs} economic observations.")

        # 6. Economic Indicators (Only synthetic test indicators)
        test_ind_stmt = delete(EconomicIndicator).where(
            EconomicIndicator.canonical_name.like("Test Indicator %")
        )
        del_inds = db.execute(test_ind_stmt).rowcount
        print(f"  [6/15] Deleted {del_inds} test indicators.")

        # 7. Entity Relationships
        del_rels = db.execute(delete(EntityRelationship)).rowcount
        print(f"  [7/15] Deleted {del_rels} test entity relationships.")

        # 8. Event Cluster Members
        del_mems = db.execute(delete(EventClusterMember)).rowcount
        print(f"  [8/15] Deleted {del_mems} event cluster members.")

        # 9. Event Clusters
        del_clusters = db.execute(delete(EventCluster)).rowcount
        print(f"  [9/15] Deleted {del_clusters} event clusters.")

        # 10. Extracted Events
        del_events = db.execute(delete(ExtractedEvent)).rowcount
        print(f"  [10/15] Deleted {del_events} extracted events.")

        # 11. Document Entities
        del_doc_ents = db.execute(delete(DocumentEntity)).rowcount
        print(f"  [11/15] Deleted {del_doc_ents} document entity mentions.")

        # 12. Documents (Resolves stuck backlog)
        del_docs = db.execute(delete(Document)).rowcount
        print(f"  [12/15] Deleted {del_docs} synthetic test documents (backlog cleared).")

        # 13. Test Sources
        del_sources = db.execute(delete(Source)).rowcount
        print(f"  [13/15] Deleted {del_sources} synthetic/dummy sources.")

        # 14. Test Entities (Only E2E Test entities, preserving 20 canonical institutional entities)
        test_ents_stmt = delete(Entity).where(
            Entity.canonical_name.like("E2E Test %")
        )
        del_ents = db.execute(test_ents_stmt).rowcount
        print(f"  [14/15] Deleted {del_ents} explicit test entities.")

        # 15. Ingestion Runs
        del_runs = db.execute(delete(IngestionRun)).rowcount
        print(f"  [15/15] Deleted {del_runs} failed test ingestion runs.")

        db.commit()
        print("\n>>> Transaction committed successfully.")

        # Inventory after
        print("\n--- INVENTORY AFTER CLEANUP ---")
        after_counts = {
            "alerts": db.scalar(select(func.count(Alert.id))) or 0,
            "correlations": db.scalar(select(func.count(EventMarketCorrelation.id))) or 0,
            "market_observations": db.scalar(select(func.count(MarketObservation.id))) or 0,
            "market_assets": db.scalar(select(func.count(MarketAsset.id))) or 0,
            "economic_observations": db.scalar(select(func.count(EconomicObservation.id))) or 0,
            "economic_indicators": db.scalar(select(func.count(EconomicIndicator.id))) or 0,
            "relationships": db.scalar(select(func.count(EntityRelationship.id))) or 0,
            "cluster_members": db.scalar(select(func.count(EventClusterMember.id))) or 0,
            "clusters": db.scalar(select(func.count(EventCluster.id))) or 0,
            "extracted_events": db.scalar(select(func.count(ExtractedEvent.id))) or 0,
            "document_entities": db.scalar(select(func.count(DocumentEntity.document_id))) or 0,
            "documents": db.scalar(select(func.count(Document.id))) or 0,
            "sources": db.scalar(select(func.count(Source.id))) or 0,
            "entities": db.scalar(select(func.count(Entity.id))) or 0,
            "ingestion_runs": db.scalar(select(func.count(IngestionRun.id))) or 0,
        }
        for k, v in after_counts.items():
            print(f"  {k:22}: {v}")

        # Post-cleanup assertions
        remaining_assets = list(db.scalars(select(MarketAsset)).all())
        assert len(remaining_assets) == 16, f"Expected exactly 16 canonical assets, found {len(remaining_assets)}"
        for a in remaining_assets:
            assert a.symbol in CANONICAL_SYMBOLS, f"Non-canonical asset found: {a.symbol}"
            assert not a.symbol.startswith("TEST_") and not a.symbol.startswith("USDX_"), f"Test asset remained: {a.symbol}"
        print(f"\n[PASS] Verified 16 canonical market assets preserved with 0 test assets.")

        remaining_entities = list(db.scalars(select(Entity)).all())
        assert len(remaining_entities) == 20, f"Expected 20 canonical entities, found {len(remaining_entities)}"
        for e in remaining_entities:
            assert not e.canonical_name.startswith("E2E Test"), f"Test entity remained: {e.canonical_name}"
        print(f"[PASS] Verified 20 canonical institutional entities preserved with 0 test entities.")

        print("\n[SUCCESS] Production database forensic cleanup is COMPLETE.")
    except Exception as exc:
        db.rollback()
        print(f"\n[FAIL] Forensic cleanup failed with rollback: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_cleanup()
