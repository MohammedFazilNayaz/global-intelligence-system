"""
Trigger real ingestion runs for primary sensor and official sources
(USGS GeoJSON, Central Banks, Diplomatic releases).
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.db.session import SessionLocal
from backend.app.services.source_service import get_source_by_name
from backend.app.services.ingestion import ingest_from_source
from backend.app.services.pipeline_service import process_document_end_to_end
from backend.app.utils.logger import setup_logger

logger = setup_logger("scripts.ingest_primary_feeds")


def ingest_live_feed(source_name: str, process_pipeline: bool = True):
    db = SessionLocal()
    try:
        source = get_source_by_name(db, source_name)
        if not source:
            logger.error(f"Source not found: {source_name}")
            return None

        logger.info(f"Ingesting live feed for: {source_name} ({source.feed_url})")
        stats = ingest_from_source(db, source=source, trigger_pipeline=False)
        logger.info(
            f"Ingestion completed for {source_name}: "
            f"fetched={stats.total_fetched}, new={stats.new_ingested}, "
            f"duplicates={stats.duplicates_skipped}"
        )

        if process_pipeline:
            # Query documents from this source that are not yet EXTRACTED
            from backend.app.models.document import Document
            from sqlalchemy import select
            to_process = list(stats.inserted_doc_ids)
            pending = list(
                db.scalars(
                    select(Document.id)
                    .where(Document.source_id == source.id)
                    .where(Document.processing_status != "EXTRACTED")
                    .limit(20)
                ).all()
            )
            for p_id in pending:
                if p_id not in to_process:
                    to_process.append(p_id)

            if to_process:
                logger.info(f"Processing {len(to_process)} documents from {source_name} through pipeline...")
                for doc_id in to_process:
                    res = process_document_end_to_end(db, doc_id)
                    logger.info(
                        f"Pipeline processed doc {doc_id}: events={res.get('events_extracted', 0)}, "
                        f"correlations={res.get('correlations_computed', 0)}, rels={res.get('relationships_created', 0)}"
                    )

        return stats
    finally:
        db.close()


if __name__ == "__main__":
    # Ingest USGS Earthquakes (Sensor Ground Truth)
    ingest_live_feed("USGS Earthquakes M4.5+", process_pipeline=True)
    # Ingest US State Dept Press
    ingest_live_feed("US Department of State Press", process_pipeline=True)
    # Ingest US Federal Reserve Press
    ingest_live_feed("US Federal Reserve Press", process_pipeline=True)
