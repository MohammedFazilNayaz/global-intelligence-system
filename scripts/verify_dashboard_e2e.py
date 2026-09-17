"""
V0.4 E2E Verification Script against live PostgreSQL database.
Validates all dashboard queries, provenance traces, cluster explanations, and invariants.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.app.main import app

def run_verification():
    client = TestClient(app)
    print("=== STARTING V0.4 REAL POSTGRESQL E2E VERIFICATION ===")

    # 1. Health endpoint
    health_res = client.get("/api/v1/health")
    assert health_res.status_code == 200, f"Health check failed: {health_res.text}"
    health = health_res.json()
    assert health["status"] == "healthy"
    print("[PASS] 1. API Health Check: Status is healthy.")

    # 2. Dashboard Summary
    summary_res = client.get("/api/v1/dashboard/summary")
    assert summary_res.status_code == 200, f"Dashboard summary failed: {summary_res.text}"
    summary = summary_res.json()
    assert summary["active_clusters_count"] >= 5, f"Expected >= 5 clusters, got {summary['active_clusters_count']}"
    assert summary["total_events_count"] >= 8, f"Expected >= 8 events, got {summary['total_events_count']}"
    assert summary["total_documents_count"] >= 8, f"Expected >= 8 docs, got {summary['total_documents_count']}"
    assert summary["active_sources_count"] >= 5, f"Expected >= 5 sources, got {summary['active_sources_count']}"
    assert summary["high_importance_events_count"] >= 2, f"Expected >= 2 high importance, got {summary['high_importance_events_count']}"
    assert "central_bank_decision" in summary["event_types_breakdown"]
    assert "inflation_report" in summary["event_types_breakdown"]
    print(f"[PASS] 2. Dashboard Summary: {summary['active_clusters_count']} clusters, {summary['total_events_count']} events, {summary['total_documents_count']} documents, {summary['active_sources_count']} active sources.")

    # 3. Clusters Feed with Sorting and Filtering
    # 3a. Default (newest)
    clusters_res = client.get("/api/v1/event-clusters?limit=10&offset=0")
    assert clusters_res.status_code == 200
    clusters_data = clusters_res.json()
    assert clusters_data["total"] >= 5
    assert len(clusters_data["items"]) >= 5
    print(f"[PASS] 3a. Cluster Feed Pagination: returned {len(clusters_data['items'])} of {clusters_data['total']} clusters.")

    # 3b. Sort by highest importance
    hi_res = client.get("/api/v1/event-clusters?order_by=highest_importance")
    assert hi_res.status_code == 200
    hi_items = hi_res.json()["items"]
    importances = [c["importance"] for c in hi_items if c["importance"] is not None]
    assert importances == sorted(importances, reverse=True), f"Not sorted by importance: {importances}"
    print(f"[PASS] 3b. Sorting by Highest Importance verified: {importances[:3]}")

    # 3c. Sort by highest confidence
    conf_res = client.get("/api/v1/event-clusters?order_by=highest_confidence")
    assert conf_res.status_code == 200
    conf_items = conf_res.json()["items"]
    confidences = [c["confidence"] for c in conf_items]
    assert confidences == sorted(confidences, reverse=True), f"Not sorted by confidence: {confidences}"
    print(f"[PASS] 3c. Sorting by Highest Confidence verified: {confidences[:3]}")

    # 3d. Filter by category (inflation_report)
    cat_res = client.get("/api/v1/event-clusters?event_type=inflation_report")
    assert cat_res.status_code == 200
    cat_items = cat_res.json()["items"]
    assert all(c["event_type"] == "inflation_report" for c in cat_items)
    print(f"[PASS] 3d. Category Filter verified: {len(cat_items)} inflation report clusters.")

    # 3e. Filter by min_importance >= 0.75
    imp_filter_res = client.get("/api/v1/event-clusters?min_importance=0.75")
    assert imp_filter_res.status_code == 200
    imp_items = imp_filter_res.json()["items"]
    for c in imp_items:
        assert c["importance"] is not None and c["importance"] >= 0.75, f"Cluster {c['id']} has imp {c['importance']} < 0.75"
    print(f"[PASS] 3e. Min Importance Filter (>= 0.75) verified: {len(imp_items)} clusters match.")

    # 4. Cluster Detail and Provenance Trace: Cluster -> Extracted Event -> Document -> Source
    # Find a multi-report cluster (Fed Rate Decision)
    fed_cluster = next((c for c in clusters_data["items"] if "Federal Reserve Holds Benchmark Policy Rate" in c["canonical_title"]), None)
    assert fed_cluster is not None, "Fed rate decision cluster not found in PostgreSQL"
    cluster_id = fed_cluster["id"]

    detail_res = client.get(f"/api/v1/event-clusters/{cluster_id}")
    assert detail_res.status_code == 200, f"Detail lookup failed: {detail_res.text}"
    detail = detail_res.json()
    assert detail["member_count"] == 3
    assert detail["unique_source_count"] == 3
    assert len(detail["members"]) == 3

    # Check provenance trace on members
    source_names = set()
    has_explanation_scores = False
    for member in detail["members"]:
        assert member["extracted_event"] is not None, "Missing extracted_event in member"
        assert member["document"] is not None, "Missing document in member"
        assert member["document"]["source_name"], "Missing source_name in document"
        source_names.add(member["document"]["source_name"])
        
        # Check explanation scores
        scores = (member.get("metadata_") or member.get("metadata") or {}).get("scores")
        if scores:
            has_explanation_scores = True
            assert "final_score" in scores
            assert "event_type_score" in scores
            assert "temporal_score" in scores
            assert "location_score" in scores

    assert len(source_names) == 3, f"Expected 3 distinct sources, got {source_names}"
    assert has_explanation_scores, "Expected multi-report member to have explanation scores"
    print(f"[PASS] 4. Provenance & Evidence Trace verified: Cluster {cluster_id} links 3 events across sources: {source_names}")
    print("[PASS]    Cluster explanation scores validated for multi-report clustering.")

    # 5. Missing Data Invariants (Requirement 14 & 15)
    # Find cluster 5 (Global Logistics Disruptions)
    missing_data_cluster = next((c for c in clusters_data["items"] if "Logistics Disruptions" in c["canonical_title"]), None)
    assert missing_data_cluster is not None, "Missing data test cluster not found"
    assert missing_data_cluster.get("event_time_start") is None, "event_time_start should be None when unknown"
    assert missing_data_cluster.get("primary_location_entity") is None, "primary_location_entity should be None when unknown"
    print("[PASS] 5. Missing Data Invariants preserved: null event_time_start and primary_location_entity returned as None (not fabricated).")

    # 6. Canonical Entities and Linked Events
    entities_res = client.get("/api/v1/entities?search=Federal%20Reserve")
    assert entities_res.status_code == 200
    entities_data = entities_res.json()
    assert entities_data["total"] >= 1
    fed_entity = entities_data["items"][0]
    assert fed_entity["canonical_name"] == "Federal Reserve"
    assert fed_entity["country_code"] == "US"
    print(f"[PASS] 6a. Entity Directory: Found '{fed_entity['canonical_name']}' ({fed_entity['entity_type']}).")

    # Linked events for entity
    ent_events_res = client.get(f"/api/v1/entities/{fed_entity['id']}/events")
    assert ent_events_res.status_code == 200
    ent_events = ent_events_res.json()
    assert isinstance(ent_events, list)
    assert len(ent_events) >= 1, f"Expected >= 1 linked events, got {len(ent_events)}"
    assert any("Federal Reserve" in str(ev.get("event_title", "")) or "Fed" in str(ev.get("event_title", "")) for ev in ent_events)
    print(f"[PASS] 6b. Entity-to-Events link verified: {len(ent_events)} events linked to {fed_entity['canonical_name']}.")

    # 7. Global Cross-Cutting Search
    search_res = client.get("/api/v1/search?q=Inflation")
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total_clusters"] >= 1, f"Expected >= 1 matched cluster for 'Inflation', got {search_data['total_clusters']}"
    assert any("Inflation" in c["canonical_title"] for c in search_data["clusters"])
    print(f"[PASS] 7. Global Search verified: '{search_data['query']}' matched {search_data['total_clusters']} clusters.")

    print("\n=== ALL V0.4 REAL POSTGRESQL E2E VERIFICATION CHECKS PASSED ===")

if __name__ == "__main__":
    run_verification()
