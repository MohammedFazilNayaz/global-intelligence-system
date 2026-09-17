"""Reprocess USGS documents to extract disaster events with coordinates."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.db.session import SessionLocal
from backend.app.models.source import Source
from backend.app.models.document import Document
from backend.app.services.pipeline_service import process_document_end_to_end
from sqlalchemy import select

def reprocess_usgs():
    db = SessionLocal()
    try:
        source = db.scalars(select(Source).where(Source.name == "USGS Earthquakes M4.5+")).first()
        if not source:
            print("USGS source not found")
            return
        docs = list(db.scalars(select(Document).where(Document.source_id == source.id)).all())
        print(f"Found {len(docs)} USGS documents.")
        for d in docs:
            res = process_document_end_to_end(db, d.id, reprocess=True)
            print(f"Doc {d.title}: events={res.get('events_extracted', 0)}")
    finally:
        db.close()

if __name__ == "__main__":
    reprocess_usgs()
