from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.app.config.settings import get_settings

settings = get_settings()

# Engine configuration
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=20,
)

import os
import sys

def _check_production_safety(db_url: str):
    """Prevent tests or verification scripts from executing mutations against global_intelligence."""
    is_test_env = (
        bool(os.environ.get("PYTEST_CURRENT_TEST"))
        or os.environ.get("ENVIRONMENT") == "testing"
        or any("verify_" in arg or "test_" in arg for arg in sys.argv)
    )
    is_prod_db = db_url.rstrip("/").endswith("/global_intelligence")
    if is_test_env and is_prod_db and os.environ.get("ALLOW_PROD_DB_MUTATION") != "1" and os.environ.get("ALLOW_PROD_AUDIT") != "1":
        raise RuntimeError(
            "SAFETY VIOLATION: Test or verification script attempted to connect to production database 'global_intelligence'! "
            "Tests must execute against 'global_intelligence_test' or an isolated test database."
        )


class SafeSessionLocal(sessionmaker):
    def __call__(self, *args, **kwargs):
        _check_production_safety(settings.DATABASE_URL)
        return super().__call__(*args, **kwargs)


SessionLocal = SafeSessionLocal(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide a transactional database session with auto-rollback on exception."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
