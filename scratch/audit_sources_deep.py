import json
import logging
import sys
sys.path.insert(0, ".")
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from backend.app.db.session import SessionLocal, engine
engine.echo = False
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.models.ingestion_run import IngestionRun
from sqlalchemy import select, func

with SessionLocal() as db:
    sources = db.scalars(select(Source).order_by(Source.name.asc())).all()
    results = []
    for s in sources:
        doc_count = db.scalar(select(func.count(Document.id)).where(Document.source_id == s.id))
        runs_count = db.scalar(select(func.count(IngestionRun.id)).where(IngestionRun.source_id == s.id))
        failed_runs = db.scalar(select(func.count(IngestionRun.id)).where(IngestionRun.source_id == s.id, IngestionRun.status == 'FAILED'))
        latest_run = db.scalars(select(IngestionRun).where(IngestionRun.source_id == s.id).order_by(IngestionRun.started_at.desc()).limit(1)).first()
        
        # Get latest document publication timestamp
        latest_doc = db.scalars(select(Document).where(Document.source_id == s.id).order_by(Document.published_at.desc()).limit(1)).first()

        results.append({
            'id': str(s.id),
            'name': s.name,
            'source_type': s.source_type,
            'active': s.active,
            'is_primary': s.is_primary,
            'region': s.region,
            'domain': s.domain,
            'feed_url': s.feed_url,
            'base_url': s.base_url,
            'freshness_status': s.freshness_status,
            'health_status': s.health_status,
            'consecutive_failures': s.consecutive_failures,
            'doc_count': doc_count,
            'runs_count': runs_count,
            'failed_runs': failed_runs,
            'last_successful_fetch': str(s.last_successful_fetch_at),
            'last_attempted_fetch': str(s.last_attempted_fetch_at),
            'latest_doc_ingested': str(s.latest_document_ingested_at),
            'latest_pub_observed': str(s.latest_published_at_observed),
            'latest_doc_published': str(latest_doc.published_at) if latest_doc else None,
            'last_duration_ms': s.last_fetch_duration_ms,
            'last_error': (s.last_error_message or '')[:120],
            'latest_run_status': latest_run.status if latest_run else None,
            'latest_run_inserted': latest_run.documents_inserted if latest_run else 0,
            'latest_run_discovered': latest_run.documents_discovered if latest_run else 0,
            'latest_run_duplicates': latest_run.duplicates_skipped if latest_run else 0,
        })

with open("scratch/sources_audit_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"Audited {len(results)} sources. Wrote to scratch/sources_audit_results.json")
