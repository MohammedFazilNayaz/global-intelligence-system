"""Database migration script for V0.8.5 schema extensions."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.db.session import SessionLocal
from sqlalchemy import text
from backend.app.utils.logger import setup_logger

logger = setup_logger("scripts.migrate_v085")

STATEMENTS = [
    "ALTER TABLE sources ADD COLUMN IF NOT EXISTS is_primary BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE sources ADD COLUMN IF NOT EXISTS region VARCHAR(64) DEFAULT 'Global';",
    "ALTER TABLE sources ADD COLUMN IF NOT EXISTS country VARCHAR(8) DEFAULT 'XX';",
    "ALTER TABLE sources ADD COLUMN IF NOT EXISTS domain VARCHAR(128) DEFAULT 'General';",
    "CREATE INDEX IF NOT EXISTS ix_sources_region ON sources (region);",
    "CREATE INDEX IF NOT EXISTS ix_sources_country ON sources (country);",
    "CREATE INDEX IF NOT EXISTS ix_sources_domain ON sources (domain);",
    "ALTER TABLE economic_indicators ADD COLUMN IF NOT EXISTS symbol VARCHAR(64);",
    "CREATE INDEX IF NOT EXISTS ix_economic_indicators_symbol ON economic_indicators (symbol);",
    "ALTER TABLE economic_observations ADD COLUMN IF NOT EXISTS period_start TIMESTAMPTZ;",
    "ALTER TABLE economic_observations ADD COLUMN IF NOT EXISTS period_end TIMESTAMPTZ;",
    "ALTER TABLE economic_observations ADD COLUMN IF NOT EXISTS release_timestamp TIMESTAMPTZ;",
    "ALTER TABLE economic_observations ADD COLUMN IF NOT EXISTS is_revision BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE economic_observations ADD COLUMN IF NOT EXISTS revision_number INTEGER DEFAULT 0;",
    "ALTER TABLE economic_observations ALTER COLUMN document_id DROP NOT NULL;",
]

def run_migration() -> None:
    db = SessionLocal()
    try:
        for stmt in STATEMENTS:
            db.execute(text(stmt))
        db.commit()
        logger.info("V0.8.5 database schema migrations completed successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Migration error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
