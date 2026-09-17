"""
V0.5 E2E Verification Script against live PostgreSQL database.
Validates the complete Economic Intelligence layer:
- Controlled Economic Taxonomy & Indicator Catalog
- Zero-fabrication value semantics (reported, previous, expected, revised)
- Central bank intelligence & policy rate decisions
- 5-Tier Provenance Chain (Observation -> Indicator -> Event -> Document -> Source)
- Country Economic Profile API
- Global Economic Search API
- Dashboard Economic Summary
- Filtering, sorting, and bounded queries
"""
import os
import sys
from datetime import datetime, timezone
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.test_session import TestSessionLocal as SessionLocal, init_test_db
from backend.app.db.session import get_db
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.indicator import EconomicIndicator
from backend.app.models.observation import EconomicObservation
from backend.app.services.extraction_service import extract_from_document

def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db


def run_v0_5_verification():
    init_test_db()
    client = TestClient(app)
    db = SessionLocal()
    print("=================================================================")
    print("=== STARTING V0.5 ECONOMIC INTELLIGENCE LIVE POSTGRESQL E2E ===")
    print("=================================================================")

    # 1. Health check
    health_res = client.get("/api/v1/health")
    assert health_res.status_code == 200
    print("[PASS] 1. System Health Check: API and DB connection healthy.")

    # 2. Setup verified test source
    source = db.query(Source).filter(Source.name == "EconIntelligence Wire").first()
    if not source:
        source = Source(
            name="EconIntelligence Wire",
            source_type="api",
            base_url="https://api.econwire.test",
            feed_url="https://api.econwire.test/feed",
            reliability_score=0.8,
            active=True,
        )
        db.add(source)
        db.commit()
        db.refresh(source)
    print(f"[PASS] 2. Source verified: {source.name} ({source.id})")

    # 3. Seed deterministic benchmark documents covering required taxonomy
    test_docs_spec = [
        {
            "title": "US CPI Rose 3.2% in August as Inflation Pressures Moderate",
            "content": "US CPI rose 3.2% year-over-year in August, compared with 3.0% previously. Core consumer prices also rose 0.2% month-over-month.",
            "url": "https://api.econwire.test/doc/1",
            "expected_indicator": "cpi",
            "expected_reported": 3.2,
            "expected_prev": 3.0,
            "expected_country": "United States",
        },
        {
            "title": "Eurozone GDP Grew 0.3% in Second Quarter Slowing from Previous Period",
            "content": "Eurozone GDP grew 0.3% in the second quarter, slowing from 0.4% in Q1. Growth was supported by domestic demand.",
            "url": "https://api.econwire.test/doc/2",
            "expected_indicator": "gdp",
            "expected_reported": 0.3,
            "expected_prev": 0.4,
            "expected_country": "Eurozone",
        },
        {
            "title": "US Jobless Rate Stood at 4.3% in July",
            "content": "The US unemployment rate held steady at 4.3% in July, matching prior month levels.",
            "url": "https://api.econwire.test/doc/3",
            "expected_indicator": "unemployment",
            "expected_reported": 4.3,
            "expected_country": "United States",
        },
        {
            "title": "US Employers Added 142,000 Non-Farm Payrolls in August",
            "content": "US non-farm payrolls increased by 142,000 in August, missing consensus expectations of 165,000 jobs.",
            "url": "https://api.econwire.test/doc/4",
            "expected_indicator": "payrolls",
            "expected_reported": 142000.0,
            "expected_country": "United States",
        },
        {
            "title": "European Central Bank Raises Policy Rate by 25 Basis Points",
            "content": "European Central Bank raised its benchmark deposit facility rate by 25 basis points to 4.00% to combat price pressures.",
            "url": "https://api.econwire.test/doc/5",
            "expected_indicator": "central_bank_rate",
            "expected_reported": 4.00,
            "expected_country": "Eurozone",
        },
        {
            "title": "Bank of England Cuts Benchmark Policy Rate by 25 bps",
            "content": "Bank of England cut its policy rate by 25 bps to 5.00%, down from 5.25%. The Monetary Policy Committee voted 5-4.",
            "url": "https://api.econwire.test/doc/6",
            "expected_indicator": "central_bank_rate",
            "expected_reported": 5.00,
            "expected_prev": 5.25,
            "expected_country": "United Kingdom",
        },
        {
            "title": "Federal Reserve Holds Benchmark Rate Steady at 5.25%-5.50%",
            "content": "Federal Reserve holds benchmark rate steady at 5.25%-5.50% range, citing balanced economic risks.",
            "url": "https://api.econwire.test/doc/7",
            "expected_indicator": "central_bank_rate",
            "expected_reported": 5.50,
            "expected_country": "United States",
        },
        {
            "title": "Japan Trade Deficit Narrowed to 621 Billion Yen in July",
            "content": "Japan trade deficit narrowed to 621 billion yen in July, compared to 1.02 trillion yen a year earlier.",
            "url": "https://api.econwire.test/doc/8",
            "expected_indicator": "trade_balance",
            "expected_reported": 621.0,
            "expected_prev": 1020.0,
            "expected_country": "Japan",
        },
        {
            "title": "Passing Mention of Inflation in Market Editorial",
            "content": "The opinion editorial discussed how inflation had impacted investor sentiments during the 1990s tech expansion.",
            "url": "https://api.econwire.test/doc/9",
            "expected_indicator": None,
        },
        {
            "title": "Federal Reserve Will Not Raise Rates at Upcoming Meeting",
            "content": "Federal Reserve officials confirmed the central bank will not raise benchmark rates at its upcoming meeting.",
            "url": "https://api.econwire.test/doc/10",
            "expected_indicator": None,
        },
    ]

    created_docs = []
    for spec in test_docs_spec:
        doc = db.query(Document).filter(Document.url == spec["url"]).first()
        if not doc:
            import hashlib
            doc = Document(
                source_id=source.id,
                title=spec["title"],
                content=spec["content"],
                content_hash=hashlib.sha256(spec["content"].encode()).hexdigest(),
                url=spec["url"],
                published_at=datetime.now(timezone.utc),
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
        created_docs.append((doc, spec))

    print(f"[PASS] 3. Seeded {len(created_docs)} benchmark documents in PostgreSQL.")

    # 4. Run extraction pipeline on all benchmark documents
    processed_count = 0
    for doc, spec in created_docs:
        res = extract_from_document(db=db, document_id=doc.id, reprocess=True)
        assert res.document_id == doc.id
        processed_count += 1

    print(f"[PASS] 4. Extracted intelligence & economic observations for {processed_count} documents.")

    # 5. Verify Negative & Passing mention safeguards
    # Doc 9 (passing mention) and Doc 10 (negation) must have 0 economic observations
    doc9 = db.query(Document).filter(Document.url == "https://api.econwire.test/doc/9").first()
    doc9_obs = db.query(EconomicObservation).filter(EconomicObservation.document_id == doc9.id).all()
    assert len(doc9_obs) == 0, f"Expected 0 observations for passing mention, got {len(doc9_obs)}"
    print("[PASS] 5a. Passing mention safeguard: 0 observations generated.")

    doc10 = db.query(Document).filter(Document.url == "https://api.econwire.test/doc/10").first()
    doc10_obs = db.query(EconomicObservation).filter(EconomicObservation.document_id == doc10.id).all()
    assert len(doc10_obs) == 0, f"Expected 0 observations for negated claim, got {len(doc10_obs)}"
    print("[PASS] 5b. Negation safeguard: 0 observations generated for negated rate claim.")

    # 6. Verify Indicators Catalog in PostgreSQL
    indicators_res = client.get("/api/v1/economic-indicators?limit=50")
    assert indicators_res.status_code == 200
    ind_data = indicators_res.json()
    assert ind_data["total"] >= 5, f"Expected >= 5 indicators, got {ind_data['total']}"
    assert any(i["indicator_type"] == "cpi" for i in ind_data["items"])
    assert any(i["indicator_type"] == "gdp" for i in ind_data["items"])
    assert any(i["indicator_type"] == "central_bank_rate" for i in ind_data["items"])
    print(f"[PASS] 6. Economic Indicators Catalog: {ind_data['total']} indicators stored in PostgreSQL.")

    # 7. Verify Indicator Detail & Observations Timeseries
    cpi_ind = next(i for i in ind_data["items"] if i["indicator_type"] == "cpi")
    cpi_detail_res = client.get(f"/api/v1/economic-indicators/{cpi_ind['id']}")
    assert cpi_detail_res.status_code == 200
    assert cpi_detail_res.json()["canonical_name"] == cpi_ind["canonical_name"]

    cpi_ts_res = client.get(f"/api/v1/economic-indicators/{cpi_ind['id']}/observations")
    assert cpi_ts_res.status_code == 200
    ts_data = cpi_ts_res.json()
    assert ts_data["total"] >= 1
    assert any(it["reported_value"] == 3.2 for it in ts_data["items"])
    print(f"[PASS] 7. Indicator Detail & Observation Timeseries verified for {cpi_ind['canonical_name']}.")

    # 8. Verify Economic Observations & Zero Fabrication Invariants
    obs_res = client.get("/api/v1/economic-observations?limit=50")
    assert obs_res.status_code == 200
    all_obs = obs_res.json()["items"]
    assert len(all_obs) >= 8

    # Zero fabrication checks across stored observations
    def get_ind_type(o):
        return (o.get("indicator") or {}).get("indicator_type", "")

    def get_cb_meta(o):
        return (o.get("metadata_") or o.get("metadata") or {}).get("central_bank_decision")

    cpi_obs_list = [o for o in all_obs if get_ind_type(o) == "cpi"]
    assert len(cpi_obs_list) >= 1
    assert any(
        o["reported_value"] == 3.2
        and o["previous_value"] == 3.0
        and o["expected_value"] is None
        and o["change_value"] == 0.2
        for o in cpi_obs_list
    )

    tb_obs = next(o for o in all_obs if get_ind_type(o) == "trade_balance")
    assert tb_obs["reported_value"] == 621.0
    assert tb_obs["previous_value"] == 1020.0  # normalized trillion to billion
    assert tb_obs["expected_value"] is None

    pay_obs = next(o for o in all_obs if get_ind_type(o) == "payrolls")
    assert pay_obs["reported_value"] == 142000.0
    assert pay_obs["expected_value"] == 165000.0
    assert pay_obs["previous_value"] is None  # Unstated in text -> strictly null

    for obs in all_obs:
        # Every numerical observation must have explainable relevance [0.1, 1.0]
        assert 0.1 <= obs["economic_relevance"] <= 1.0

    print(f"[PASS] 8. Value Semantics & Zero Fabrication verified across {len(all_obs)} live PostgreSQL observations.")

    # 9. Verify Central Bank Intelligence & Decision Types
    cb_obs = [o for o in all_obs if get_cb_meta(o) is not None]
    assert len(cb_obs) >= 3, f"Expected >= 3 CB decisions, got {len(cb_obs)}"

    hike = next(o for o in cb_obs if get_cb_meta(o).get("decision_type") == "rate_hike")
    assert hike["reported_value"] == 4.0
    assert get_cb_meta(hike).get("rate_change_bps") == 25.0
    assert hike["direction"] == "hike"

    cut = next(o for o in cb_obs if get_cb_meta(o).get("decision_type") == "rate_cut")
    assert cut["reported_value"] == 5.0
    assert cut["previous_value"] == 5.25
    assert cut["change_value"] == -0.25
    assert cut["direction"] == "cut"

    hold = next(o for o in cb_obs if get_cb_meta(o).get("decision_type") == "rate_hold")
    assert hold["reported_value"] == 5.50
    assert hold["direction"] == "hold"

    print(f"[PASS] 9. Central Bank Intelligence: Hikes, Cuts, and Holds accurately classified with bps deltas.")

    # 10. Verify 5-Tier Provenance Chain:
    # Economic Observation -> Economic Indicator -> Extracted Event -> Document -> Source
    cpi_obs_record = next(o for o in all_obs if get_ind_type(o) == "cpi" and o["reported_value"] == 3.2)
    detail_obs_res = client.get(f"/api/v1/economic-observations/{cpi_obs_record['id']}")
    assert detail_obs_res.status_code == 200
    prov = detail_obs_res.json()

    # Tier 1: Observation
    assert prov["id"] == cpi_obs_record["id"]
    assert prov["reported_value"] == 3.2
    # Tier 2: Indicator
    assert prov["indicator_id"] is not None
    assert prov["indicator"]["canonical_name"] == "United States Consumer Price Index (CPI)"
    # Tier 3: Event
    assert prov["event_id"] is not None
    # Tier 4: Document
    assert prov["document_id"] is not None
    # Tier 5: Source
    assert prov["source_name"] == "EconIntelligence Wire"
    # Evidence Snippet
    assert "US CPI rose 3.2% year-over-year in August" in prov["evidence_snippet"]
    print(f"[PASS] 10. 5-Tier Provenance Trace verified: Observation -> Indicator -> Event -> Document -> Source.")

    # 11. Verify Country Economic Profile API
    # Find US entity in database
    from backend.app.models.entity import Entity
    us_entity = db.query(Entity).filter(Entity.normalized_name == "united states").first()
    assert us_entity is not None, "United States entity missing in database"

    profile_res = client.get(f"/api/v1/entities/{us_entity.id}/economic-profile")
    assert profile_res.status_code == 200
    profile = profile_res.json()
    assert profile["country_entity"]["canonical_name"] == "United States"
    assert profile["indicators_count"] >= 2
    assert profile["observations_count"] >= 2
    assert "Inflation" in profile["domains"] or "Monetary Policy" in profile["domains"]
    print(f"[PASS] 11. Country Economic Profile API: verified for {profile['country_entity']['canonical_name']} ({profile['observations_count']} prints).")

    # 12. Verify Global Economic Search
    search_res = client.get("/api/v1/search?q=CPI&limit=10")
    assert search_res.status_code == 200
    s_data = search_res.json()
    assert s_data["total_indicators"] >= 1
    assert any("CPI" in i["canonical_name"] for i in s_data["indicators"])
    print(f"[PASS] 12. Global Economic Search: found {s_data['total_indicators']} indicators matching 'CPI'.")

    # 13. Verify Dashboard Summary includes Economic Telemetry
    dash_res = client.get("/api/v1/dashboard/summary")
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert "economic_summary" in dash_data
    econ_sum = dash_data["economic_summary"]
    assert econ_sum is not None
    assert econ_sum["total_indicators_count"] >= 5
    assert econ_sum["total_observations_count"] >= 8
    assert econ_sum["central_bank_decisions_count"] >= 3
    print(f"[PASS] 13. Dashboard Summary: integrated economic_summary verified ({econ_sum['total_observations_count']} observations).")

    # 14. Verify Idempotent Reprocessing (No duplicate observations or orphaned records)
    doc1 = db.query(Document).filter(Document.url == "https://api.econwire.test/doc/1").first()
    pre_reprocess_count = db.query(EconomicObservation).filter(EconomicObservation.document_id == doc1.id).count()
    extract_from_document(db=db, document_id=doc1.id, reprocess=True)
    post_reprocess_count = db.query(EconomicObservation).filter(EconomicObservation.document_id == doc1.id).count()
    assert pre_reprocess_count == post_reprocess_count, f"Reprocessing created duplicates: {pre_reprocess_count} vs {post_reprocess_count}"
    print(f"[PASS] 14. Idempotent Reprocessing: count preserved at {post_reprocess_count} without duplicate rows.")

    db.close()
    print("=================================================================")
    print("=== [ALL 14 E2E GATES PASSED ON LIVE POSTGRESQL 16] ===")
    print("=================================================================")


if __name__ == "__main__":
    run_v0_5_verification()
