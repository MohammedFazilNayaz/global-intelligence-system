"""PostgreSQL 16 lifecycle manager for local development."""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
import psycopg

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
PG_BIN_DIR = WORKSPACE_ROOT / ".venv" / "Lib" / "site-packages" / "pgserver" / "pginstall" / "bin"
PG_DATA_DIR = WORKSPACE_ROOT / ".pgdata"
DB_NAME = "global_intelligence"
DEFAULT_PORT = 5432


def get_pg_bin(name: str) -> Path:
    p = PG_BIN_DIR / f"{name}.exe"
    if not p.exists():
        raise FileNotFoundError(f"PostgreSQL binary not found: {p}")
    return p


def init_db_if_needed():
    if not (PG_DATA_DIR / "PG_VERSION").exists():
        print(f"[PostgreSQL] Initializing data directory at {PG_DATA_DIR}...")
        initdb = get_pg_bin("initdb")
        subprocess.run(
            [str(initdb), "-D", str(PG_DATA_DIR), "-U", "postgres", "-A", "trust", "--encoding=UTF8"],
            check=True,
        )


def start_server(port: int = DEFAULT_PORT):
    init_db_if_needed()
    postgres_bin = get_pg_bin("postgres")
    log_file = PG_DATA_DIR / "server.log"

    # Remove stale postmaster.pid if no process is running
    pid_file = PG_DATA_DIR / "postmaster.pid"
    if pid_file.exists():
        try:
            pid_line = pid_file.read_text().splitlines()[0].strip()
            pid = int(pid_line)
            # Check if process is running
            import psutil
            if not psutil.pid_exists(pid):
                print(f"[PostgreSQL] Removing stale postmaster.pid for PID {pid}")
                pid_file.unlink(missing_ok=True)
        except Exception:
            pid_file.unlink(missing_ok=True)

    print(f"[PostgreSQL] Starting server on port {port}...")
    log_fp = open(log_file, "a", encoding="utf-8")
    
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(
        [str(postgres_bin), "-D", str(PG_DATA_DIR), "-p", str(port), "-c", "listen_addresses=127.0.0.1"],
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        close_fds=True,
    )

    # Wait for ready
    pg_isready = get_pg_bin("pg_isready")
    ready = False
    for _ in range(20):
        time.sleep(0.5)
        res = subprocess.run([str(pg_isready), "-h", "127.0.0.1", "-p", str(port)], capture_output=True)
        if res.returncode == 0:
            ready = True
            break

    if not ready:
        print("[PostgreSQL] Server failed to become ready.")
        if log_file.exists():
            print(log_file.read_text(encoding="utf-8", errors="replace")[-1000:])
        sys.exit(1)

    print(f"[PostgreSQL] Server running on PID {proc.pid}")


    # Ensure database exists
    admin_conn_str = f"postgresql://postgres:@127.0.0.1:{port}/postgres"
    time.sleep(1)
    with psycopg.connect(admin_conn_str, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{DB_NAME}";')
                print(f"[PostgreSQL] Created database: {DB_NAME}")
            else:
                print(f"[PostgreSQL] Database {DB_NAME} exists.")

    app_url = f"postgresql+psycopg://postgres:@127.0.0.1:{port}/{DB_NAME}"
    print(f"[PostgreSQL] RUNNING on: {app_url}")
    return app_url


def stop_server():
    pg_ctl = get_pg_bin("pg_ctl")
    print("[PostgreSQL] Stopping server...")
    subprocess.run([str(pg_ctl), "stop", "-D", str(PG_DATA_DIR), "-m", "fast"])


def check_status(port: int = DEFAULT_PORT):
    pg_isready = get_pg_bin("pg_isready")
    res = subprocess.run([str(pg_isready), "-h", "127.0.0.1", "-p", str(port)])
    return res.returncode == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage local PostgreSQL instance.")
    parser.add_argument("action", choices=["start", "stop", "status"], default="start", nargs="?")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    if args.action == "start":
        start_server(port=args.port)
    elif args.action == "stop":
        stop_server()
    elif args.action == "status":
        ready = check_status(port=args.port)
        print("READY" if ready else "NOT READY")
        sys.exit(0 if ready else 1)
