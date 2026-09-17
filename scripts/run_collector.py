"""CLI script to manually trigger source ingestion."""

import argparse
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.db.session import SessionLocal
from backend.app.services.source_service import get_source_by_name, list_sources
from backend.app.services.ingestion import ingest_from_source, ingest_all_active_sources
from backend.app.utils.logger import setup_logger

logger = setup_logger("scripts.run_collector")


def main():
    parser = argparse.ArgumentParser(description="Run Global Intelligence Platform collectors.")
    parser.add_argument(
        "--source-name",
        type=str,
        help="Run ingestion for a single source by name",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run ingestion for all active sources",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.source_name:
            source = get_source_by_name(db, name=args.source_name)
            if not source:
                logger.error(f"Source with name '{args.source_name}' not found.")
                sys.exit(1)
            stats = ingest_from_source(db, source=source)
            logger.info(f"Ingestion result: {stats.model_dump()}")
        else:
            results = ingest_all_active_sources(db)
            logger.info(f"Processed {len(results)} sources.")
            for r in results:
                logger.info(f"  - {r.source_name}: {r.new_ingested} new, {r.duplicates_skipped} duplicates")
    finally:
        db.close()


if __name__ == "__main__":
    main()
