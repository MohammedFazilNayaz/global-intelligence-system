from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.sources import router as sources_router
from backend.app.api.v1.documents import router as documents_router

__all__ = ["health_router", "sources_router", "documents_router"]
