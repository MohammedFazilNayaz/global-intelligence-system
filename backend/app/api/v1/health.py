from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.config.settings import get_settings
from backend.app.db.session import get_db
from backend.app.schemas.health import HealthResponse
from backend.app.schemas.intelligence_feed import SystemFreshnessResponse
from backend.app.services.freshness_service import get_system_freshness_summary
from backend.app.utils.time import utc_now

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """System health check endpoint verifying database connectivity."""
    settings = get_settings()
    db_status = "connected"
    system_status = "healthy"

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"
        system_status = "degraded"

    return HealthResponse(
        status=system_status,
        version=settings.VERSION,
        timestamp=utc_now(),
        database=db_status,
        environment=settings.ENVIRONMENT,
    )


@router.get("/system/freshness", response_model=SystemFreshnessResponse)
def get_system_freshness(db: Session = Depends(get_db)) -> SystemFreshnessResponse:
    """Retrieve operational system freshness metrics, pipeline backlog age, and latency percentiles."""
    return get_system_freshness_summary(db)


@router.get("/system/coverage")
def get_system_coverage(db: Session = Depends(get_db)):
    """Retrieve multi-theatre operational coverage (11 regions), domain breadth, and primary source ratios."""
    from backend.app.services.coverage_service import coverage_service
    return coverage_service.get_global_coverage_summary(db)


@router.get("/system/reliability-audit")
def get_system_reliability_audit(db: Session = Depends(get_db)):
    """Retrieve empirical operational reliability and source coverage audit metrics for V0.9.5."""
    from backend.app.services.coverage_service import coverage_service
    return coverage_service.get_reliability_audit_metrics(db)


