"""
Reprocess existing news documents using the expanded 19-type relationship extractor.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.db.session import SessionLocal
from backend.app.models.document import Document
from backend.app.models.relationship import EntityRelationship
from backend.app.services.pipeline_service import process_document_end_to_end
from sqlalchemy import select, func
from backend.app.utils.logger import setup_logger

logger = setup_logger("scripts.reprocess_relationships")


def reprocess_relationships():
    db = SessionLocal()
    try:
        total_rels_before = db.scalar(select(func.count(EntityRelationship.id))) or 0
        print(f"Total relationships before: {total_rels_before}")

        # Fetch documents with content
        docs = list(
            db.scalars(
                select(Document)
                .where(Document.content.isnot(None))
                .order_by(Document.created_at.desc())
            ).all()
        )
        print(f"Found {len(docs)} documents to process...")

        total_created = 0
        for i, doc in enumerate(docs):
            try:
                summary = process_document_end_to_end(db, doc.id, reprocess=True)
                rels_count = summary.get("relationships_created", 0)
                total_created += rels_count
                if (i + 1) % 20 == 0 or rels_count > 0:
                    print(f"Processed [{i+1}/{len(docs)}] doc {doc.title[:40]}...: +{rels_count} rels (total new: {total_created})")
            except Exception as exc:
                logger.error(f"Error processing doc {doc.id}: {exc}")

        total_rels_after = db.scalar(select(func.count(EntityRelationship.id))) or 0
        print(f"Total relationships after: {total_rels_after} (Net created: {total_rels_after - total_rels_before})")
    finally:
        db.close()


if __name__ == "__main__":
    reprocess_relationships()
