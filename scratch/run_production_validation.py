import os
import sys
sys.path.insert(0, os.path.abspath("."))
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, distinct
from backend.app.db.session import SessionLocal
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.event import ExtractedEvent
from backend.app.models.cluster import EventCluster
from backend.app.services.coverage_service import coverage_service
from backend.app.utils.time import utc_now

def run_validation():
    db = SessionLocal()
    now = utc_now()
    
    # Sources audit
    sources = db.execute(select(Source)).scalars().all()
    total_sources = len(sources)
    active_sources = [s for s in sources if s.active]
    
    healthy = [s for s in sources if s.health_status == "HEALTHY"]
    degraded = [s for s in sources if s.health_status == "DEGRADED"]
    stale = [s for s in sources if s.health_status == "STALE"]
    failed = [s for s in sources if s.health_status == "FAILED"]
    disabled = [s for s in sources if s.health_status == "DISABLED"]
    auth_required = [s for s in sources if s.health_status == "AUTH_REQUIRED"]
    rate_limited = [s for s in sources if s.health_status == "RATE_LIMITED"]
    
    # Document velocity
    doc_1h = db.execute(select(func.count(Document.id)).where(Document.ingested_at >= now - timedelta(hours=1))).scalar_one()
    doc_6h = db.execute(select(func.count(Document.id)).where(Document.ingested_at >= now - timedelta(hours=6))).scalar_one()
    doc_24h = db.execute(select(func.count(Document.id)).where(Document.ingested_at >= now - timedelta(hours=24))).scalar_one()
    total_docs = db.execute(select(func.count(Document.id))).scalar_one()
    
    # Events velocity
    ev_1h = db.execute(select(func.count(ExtractedEvent.id)).where(ExtractedEvent.created_at >= now - timedelta(hours=1))).scalar_one()
    ev_6h = db.execute(select(func.count(ExtractedEvent.id)).where(ExtractedEvent.created_at >= now - timedelta(hours=6))).scalar_one()
    ev_24h = db.execute(select(func.count(ExtractedEvent.id)).where(ExtractedEvent.created_at >= now - timedelta(hours=24))).scalar_one()
    total_events = db.execute(select(func.count(ExtractedEvent.id))).scalar_one()
    
    # System coverage metrics
    metrics = coverage_service.get_reliability_audit_metrics(db)
    
    source_details = []
    for s in sorted(sources, key=lambda x: x.name):
        source_details.append({
            "name": s.name,
            "type": s.source_type,
            "feed_url": s.feed_url,
            "region": s.region or "Global",
            "domain": s.domain or "General",
            "active": s.active,
            "health_status": s.health_status,
            "freshness_status": s.freshness_status,
            "consecutive_failures": s.consecutive_failures,
            "last_checked": s.last_successful_fetch_at.isoformat() if s.last_successful_fetch_at else None,
            "last_new_content": s.last_successful_ingestion_at.isoformat() if s.last_successful_ingestion_at else None,
        })
        
    res = {
        "timestamp": now.isoformat(),
        "sources": {
            "total": total_sources,
            "active": len(active_sources),
            "healthy": len(healthy),
            "degraded": len(degraded),
            "stale": len(stale),
            "failed": len(failed),
            "disabled": len(disabled),
            "auth_required": len(auth_required),
            "rate_limited": len(rate_limited),
        },
        "documents": {
            "last_1h": doc_1h,
            "last_6h": doc_6h,
            "last_24h": doc_24h,
            "total": total_docs,
        },
        "events": {
            "last_1h": ev_1h,
            "last_6h": ev_6h,
            "last_24h": ev_24h,
            "total": total_events,
        },
        "coverage_metrics": metrics,
        "source_inventory": source_details,
    }
    
    with open("scratch/production_validation_results.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
        
    print("PRODUCTION VALIDATION COMPLETE:")
    print(f"Total Sources: {total_sources} (Active: {len(active_sources)})")
    print(f"Healthy: {len(healthy)}, Degraded: {len(degraded)}, Stale: {len(stale)}, Failed: {len(failed)}, Disabled: {len(disabled)}, Auth Req: {len(auth_required)}, Rate Limited: {len(rate_limited)}")
    print(f"Documents: 1h={doc_1h}, 6h={doc_6h}, 24h={doc_24h}, Total={total_docs}")
    print(f"Events: 1h={ev_1h}, 6h={ev_6h}, 24h={ev_24h}, Total={total_events}")
    print(f"HHI Concentration: {metrics.get('hhi_index')}")
    print(f"Top 3 Sources: {metrics.get('top_sources')}")
    db.close()

if __name__ == "__main__":
    run_validation()
