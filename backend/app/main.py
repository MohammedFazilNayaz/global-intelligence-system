import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text

from backend.app.config.settings import get_settings
from backend.app.api.router import api_router
from backend.app.api.v1.health import router as health_router
from backend.app.db.session import engine
from backend.app.utils.logger import setup_logger
from backend.app.utils.time import utc_now

settings = get_settings()
logger = setup_logger("app.main", level=settings.LOG_LEVEL)


from backend.app.services.scheduler_service import scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events for startup and shutdown logging and scheduler orchestration."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    if settings.ENVIRONMENT != "testing" and not os.environ.get("UNIT_TEST_DATABASE_URL") and not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connectivity check: OK")
        except Exception as exc:
            logger.error(f"Database connectivity check failed on startup: {exc}")

        try:
            scheduler.start()
            logger.info("IngestionScheduler started on application boot.")
        except Exception as sched_err:
            logger.error(f"Failed to start IngestionScheduler on boot: {sched_err}")

    yield

    if scheduler.is_running:
        try:
            await scheduler.stop()
            logger.info("IngestionScheduler stopped cleanly on application shutdown.")
        except Exception as stop_err:
            logger.error(f"Error stopping IngestionScheduler on shutdown: {stop_err}")

    logger.info(f"Shutting down {settings.PROJECT_NAME}")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Data Foundation backend for Global Intelligence Platform.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root-level health check (in addition to /api/v1/health)
app.include_router(health_router)

# Mount API V1
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global unhandled exception handler ensuring all errors are logged and cleanly returned."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error occurred.",
            "timestamp": utc_now().isoformat(),
        },
    )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root_status():
    """Minimal, sleek system status landing page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{settings.PROJECT_NAME} — Status</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
        }}
        .card {{
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 32px;
            max-width: 460px;
            width: 100%;
            box-shadow: 0 10px 25px rgba(0,0,0,0.4);
        }}
        h1 {{ font-size: 1.25rem; margin: 0 0 8px 0; color: #38bdf8; }}
        .badge {{
            display: inline-block;
            background: #065f46;
            color: #34d399;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-bottom: 20px;
        }}
        p {{ margin: 6px 0; color: #94a3b8; font-size: 0.9rem; }}
        strong {{ color: #e2e8f0; }}
        .links {{ margin-top: 24px; display: flex; gap: 12px; }}
        .links a {{
            color: #38bdf8;
            text-decoration: none;
            font-size: 0.85rem;
            border: 1px solid #0284c7;
            padding: 6px 12px;
            border-radius: 6px;
            transition: all 0.2s;
        }}
        .links a:hover {{
            background: #0284c7;
            color: #ffffff;
        }}
    </style>
</head>
<body>
    <div class="card">
        <h1>{settings.PROJECT_NAME}</h1>
        <div class="badge">● V0.1 — Data Foundation Active</div>
        <p><strong>Environment:</strong> {settings.ENVIRONMENT}</p>
        <p><strong>Version:</strong> {settings.VERSION}</p>
        <p><strong>Server Time (UTC):</strong> {utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        <div class="links">
            <a href="/docs">API Documentation (/docs)</a>
            <a href="/health">Health Endpoint (/health)</a>
            <a href="{settings.API_V1_STR}/documents">Documents API</a>
        </div>
    </div>
</body>
</html>"""
