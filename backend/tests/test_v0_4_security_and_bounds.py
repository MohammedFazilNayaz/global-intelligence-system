"""
Security, validation, parameter boundary, and SQL injection safety tests for V0.4 API.
"""
import uuid
import pytest
from fastapi.testclient import TestClient


def test_invalid_uuid_handling_returns_422(client: TestClient):
    """Passing malformed UUIDs should be rejected cleanly by FastAPI validation with 422, not 500."""
    # 1. Event cluster detail with non-UUID string
    res = client.get("/api/v1/event-clusters/not-a-valid-uuid")
    assert res.status_code == 422
    data = res.json()
    assert "detail" in data
    assert any("uuid" in str(err.get("msg", "")).lower() or "uuid" in str(err.get("type", "")).lower() for err in data["detail"])

    # 2. Entity detail with invalid UUID
    res_ent = client.get("/api/v1/entities/xyz-123-invalid")
    assert res_ent.status_code == 422

    # 3. Document detail with invalid UUID
    res_doc = client.get("/api/v1/documents/not-a-uuid")
    assert res_doc.status_code == 422

    # 4. Filter location_entity_id with invalid UUID
    res_filt = client.get("/api/v1/event-clusters?location_entity_id=bad-uuid")
    assert res_filt.status_code == 422


def test_pagination_bounds_enforcement(client: TestClient):
    """Pagination query params should reject negative numbers and page_size exceeding bounds."""
    # 1. Negative page
    res_neg_page = client.get("/api/v1/event-clusters?page=-1")
    assert res_neg_page.status_code == 422

    # 2. Page 0 (minimum is 1)
    res_zero_page = client.get("/api/v1/event-clusters?page=0")
    assert res_zero_page.status_code == 422

    # 3. page_size > 100 on clusters
    res_big_clusters = client.get("/api/v1/event-clusters?page_size=500")
    assert res_big_clusters.status_code == 422

    # 4. page_size > 100 on entities
    res_big_entities = client.get("/api/v1/entities?page_size=250")
    assert res_big_entities.status_code == 422

    # 5. limit > 50 on search
    res_big_search = client.get("/api/v1/search?q=test&limit=200")
    assert res_big_search.status_code == 422


def test_invalid_sort_order_parameter(client: TestClient):
    """Invalid sort order should be rejected with HTTP 422."""
    res = client.get("/api/v1/event-clusters?order_by=invalid_sort_mode")
    assert res.status_code == 422


def test_min_confidence_and_importance_bounds(client: TestClient):
    """Confidence and importance filters must stay within [0.0, 1.0]."""
    # 1. min_confidence > 1.0
    res1 = client.get("/api/v1/event-clusters?min_confidence=1.5")
    assert res1.status_code == 422

    # 2. min_confidence < 0.0
    res2 = client.get("/api/v1/event-clusters?min_confidence=-0.1")
    assert res2.status_code == 422

    # 3. min_importance > 1.0
    res3 = client.get("/api/v1/event-clusters?min_importance=2.0")
    assert res3.status_code == 422


def test_sql_injection_safety_in_search_and_filters(client: TestClient):
    """SQL injection payloads in search and filter parameters must execute safely without leaking DB schema or corrupting data."""
    sql_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE event_clusters; --",
        "\" UNION SELECT id, name, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL FROM sources --",
        "1' OR 1=1 --",
        "' UNION ALL SELECT @@version --",
    ]

    for payload in sql_payloads:
        # Search endpoint
        res_search = client.get(f"/api/v1/search?q={payload}")
        assert res_search.status_code == 200
        data = res_search.json()
        assert "clusters" in data
        assert "entities" in data
        assert isinstance(data["clusters"], list)

        # Event clusters search filter
        res_clusters = client.get(f"/api/v1/event-clusters?search={payload}")
        assert res_clusters.status_code == 200
        c_data = res_clusters.json()
        assert "items" in c_data

        # Entities search filter
        res_entities = client.get(f"/api/v1/entities?search={payload}")
        assert res_entities.status_code == 200
        e_data = res_entities.json()
        assert "items" in e_data


def test_no_sensitive_secrets_in_health_response(client: TestClient):
    """Health check endpoint must not expose database credentials, passwords, or connection strings."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    raw_str = str(data).lower()
    assert "password" not in raw_str
    assert "secret" not in raw_str
    assert "token" not in raw_str
    assert "postgres:@" not in raw_str
    assert "postgresql://" not in raw_str
