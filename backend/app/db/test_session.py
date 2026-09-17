"""
Dedicated isolated database session for testing and verification scripts.
Enforces strict isolation from the production database 'global_intelligence'.
"""
import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.app.db.base import Base

# Target test database in PostgreSQL 16 or fallback to in-memory SQLite if specified
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:@127.0.0.1:5432/global_intelligence_test",
)

connect_args = {}
if TEST_DB_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

test_engine = create_engine(
    TEST_DB_URL,
    echo=False,
    connect_args=connect_args,
    pool_pre_ping=True,
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    expire_on_commit=False,
)


def init_test_db() -> None:
    """Initialize all relational tables in the test database."""
    # Ensure all models are imported and registered on Base.metadata
    import backend.app.models.source  # noqa: F401
    import backend.app.models.document  # noqa: F401
    import backend.app.models.entity  # noqa: F401
    import backend.app.models.event  # noqa: F401
    import backend.app.models.cluster  # noqa: F401
    import backend.app.models.relationship  # noqa: F401
    import backend.app.models.indicator  # noqa: F401
    import backend.app.models.observation  # noqa: F401
    import backend.app.models.market_asset  # noqa: F401
    import backend.app.models.market_observation  # noqa: F401
    import backend.app.models.market_correlation  # noqa: F401
    import backend.app.models.ingestion_run  # noqa: F401
    import backend.app.models.alert  # noqa: F401

    Base.metadata.create_all(bind=test_engine)


def clean_test_db() -> None:
    """Safely truncate all tables in the isolated test database."""
    init_test_db()
    from sqlalchemy import text
    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE;'))


def get_test_db() -> Generator[Session, None, None]:
    """Provide a transactional test database session."""
    db = TestSessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
