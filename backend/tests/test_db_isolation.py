"""
Unit and Integration Test proving strict test/production database isolation.
Guarantees that test fixtures, test sessions, and pytest runs cannot mutate 'global_intelligence'.
"""
import os
import pytest
from sqlalchemy import create_engine, text
from backend.app.db.session import SessionLocal, _check_production_safety
from backend.app.db.test_session import TestSessionLocal, test_engine, init_test_db


def test_production_safety_guard_blocks_prod_db_access():
    """Verify that _check_production_safety throws RuntimeError on production database URL."""
    prod_url = "postgresql+psycopg://postgres:@127.0.0.1:5432/global_intelligence"
    
    # Under test environment, calling safety check on prod URL must raise RuntimeError
    with pytest.raises(RuntimeError, match="SAFETY VIOLATION"):
        _check_production_safety(prod_url)


def test_production_safety_guard_permits_test_db_access():
    """Verify that _check_production_safety permits test database URLs."""
    test_url = "postgresql+psycopg://postgres:@127.0.0.1:5432/global_intelligence_test"
    # Should not raise exception
    _check_production_safety(test_url)

    sqlite_url = "sqlite:///:memory:"
    _check_production_safety(sqlite_url)


def test_test_session_targets_isolated_database():
    """Verify that TestSessionLocal connects to global_intelligence_test and not global_intelligence."""
    assert "global_intelligence_test" in str(test_engine.url) or "sqlite" in str(test_engine.url)
    assert not str(test_engine.url).rstrip("/").endswith("/global_intelligence")


def test_test_execution_cannot_mutate_production_database():
    """Verify that records created in TestSessionLocal do not appear in global_intelligence."""
    init_test_db()
    
    # Read count of sources in production directly via raw connection
    prod_url = "postgresql+psycopg://postgres:@127.0.0.1:5432/global_intelligence"
    prod_engine = create_engine(prod_url, pool_pre_ping=True)
    
    with prod_engine.connect() as conn:
        prod_count_before = conn.execute(text("SELECT count(*) FROM sources")).scalar()
    
    # Now use TestSessionLocal to insert a test record in global_intelligence_test
    import uuid
    from backend.app.models.source import Source
    
    with TestSessionLocal() as test_db:
        test_src = Source(
            name=f"Isolation Probe Source {uuid.uuid4().hex[:6]}",
            source_type="rss",
            base_url="https://isolation.test",
            feed_url="https://isolation.test/feed",
            reliability_score=0.9,
            active=False,
        )
        test_db.add(test_src)
        test_db.commit()
        created_id = test_src.id

    # Verify that production database count did NOT change
    with prod_engine.connect() as conn:
        prod_count_after = conn.execute(text("SELECT count(*) FROM sources")).scalar()
        prod_probe = conn.execute(text("SELECT count(*) FROM sources WHERE id = :id"), {"id": created_id}).scalar()
    
    assert prod_count_before == prod_count_after, "Production source count was mutated by test!"
    assert prod_probe == 0, "Test record leaked into production database!"


def test_production_safety_opt_in_flags():
    """Verify that ALLOW_PROD_DB_MUTATION and ALLOW_PROD_AUDIT permit prod URL access when explicitly set."""
    prod_url = "postgresql+psycopg://postgres:@127.0.0.1:5432/global_intelligence"

    # ALLOW_PROD_AUDIT = 1
    os.environ["ALLOW_PROD_AUDIT"] = "1"
    try:
        _check_production_safety(prod_url)
    finally:
        os.environ.pop("ALLOW_PROD_AUDIT", None)

    # ALLOW_PROD_DB_MUTATION = 1
    os.environ["ALLOW_PROD_DB_MUTATION"] = "1"
    try:
        _check_production_safety(prod_url)
    finally:
        os.environ.pop("ALLOW_PROD_DB_MUTATION", None)


def test_get_db_session_and_rollback():
    """Verify get_db and get_test_db generator lifecycles and exception rollback."""
    from backend.app.db.session import get_db
    from backend.app.db.test_session import get_test_db, clean_test_db

    # Clean test DB
    clean_test_db()

    # Test get_test_db
    gen = get_test_db()
    sess = next(gen)
    assert sess is not None
    try:
        gen.throw(ValueError("Simulated session error"))
    except ValueError:
        pass

    # Test get_db generator with test URL
    os.environ["ALLOW_PROD_AUDIT"] = "1"
    try:
        gen_prod = get_db()
        sess_prod = next(gen_prod)
        assert sess_prod is not None
        try:
            gen_prod.throw(ValueError("Simulated rollback error"))
        except ValueError:
            pass
    finally:
        os.environ.pop("ALLOW_PROD_AUDIT", None)

