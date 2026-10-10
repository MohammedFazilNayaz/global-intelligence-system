#!/usr/bin/env bash
set -e

echo "=== [Global Intelligence Platform] Backend Startup ==="

# 1. Wait for PostgreSQL to be ready
echo "[1/3] Waiting for PostgreSQL database to be reachable..."
python - << 'EOF'
import sys
import time
import os
from urllib.parse import urlparse
import psycopg

db_url = os.environ.get("DATABASE_URL", "")
if not db_url:
    print("[Error] DATABASE_URL environment variable is not set!", file=sys.stderr)
    sys.exit(1)

# Normalise SQLAlchemy postgresql+psycopg:// to postgresql://
parsed_url = db_url.replace("postgresql+psycopg://", "postgresql://")

max_retries = 30
for attempt in range(1, max_retries + 1):
    try:
        with psycopg.connect(parsed_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        print(f"  [OK] Connected to database successfully (attempt {attempt}).")
        sys.exit(0)
    except Exception as exc:
        if attempt == max_retries:
            print(f"  [FAIL] Database unavailable after {max_retries} attempts: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(1)
EOF

# 2. Run Database Migrations
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[2/3] Applying Alembic database migrations..."
    alembic upgrade head
    echo "  [OK] Database migrations applied successfully."
else
    echo "[2/3] Skipping database migrations (RUN_MIGRATIONS=false)."
fi

# 3. Optional Database Seeding
if [ "${SEED_ON_STARTUP:-false}" = "true" ]; then
    echo "[Optional] Seeding verified global sources..."
    python scripts/seed_sources.py || echo "[Warning] Source seeding encountered an issue, proceeding."
fi

echo "[3/3] Launching application command: $@"
exec "$@"
