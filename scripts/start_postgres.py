"""Manage local PostgreSQL development server using pgserver (PostgreSQL 16)."""

import os
import sys
import time
from pathlib import Path
import psycopg
import pgserver

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

PG_DATA_DIR = Path(__file__).resolve().parent.parent / ".pgdata"
DB_NAME = "global_intelligence"


def get_or_start_postgres():
    """Ensure PostgreSQL 16 is running on local data directory."""
    print(f"[PostgreSQL] Initializing/Connecting at: {PG_DATA_DIR}")
    srv = pgserver.get_server(PG_DATA_DIR, cleanup_mode=None)
    admin_uri = srv.get_uri("postgres")
    print(f"[PostgreSQL] Admin URI: {admin_uri}")

    # Ensure database exists
    with psycopg.connect(admin_uri, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{DB_NAME}";')
                print(f"[PostgreSQL] Created database: {DB_NAME}")
            else:
                print(f"[PostgreSQL] Database {DB_NAME} already exists.")

    raw_app_uri = srv.get_uri(DB_NAME)
    # Convert to SQLAlchemy psycopg3 format: postgresql+psycopg://...
    if raw_app_uri.startswith("postgresql://"):
        app_db_url = raw_app_uri.replace("postgresql://", "postgresql+psycopg://", 1)
    else:
        app_db_url = f"postgresql+psycopg://{raw_app_uri}"

    print(f"[PostgreSQL] Ready! Connection URL:\n{app_db_url}")
    return srv, app_db_url


if __name__ == "__main__":
    srv, url = get_or_start_postgres()
