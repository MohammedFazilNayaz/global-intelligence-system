from fastapi import APIRouter
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.sources import router as sources_router
from backend.app.api.v1.documents import router as documents_router
from backend.app.api.v1.entities import router as entities_router
from backend.app.api.v1.events import router as events_router
from backend.app.api.v1.clusters import router as clusters_router
from backend.app.api.v1.dashboard import router as dashboard_router
from backend.app.api.v1.search import router as search_router
from backend.app.api.v1.indicators import router as indicators_router
from backend.app.api.v1.observations import router as observations_router
from backend.app.api.v1.market import router as market_router
from backend.app.api.v1.relationships import router as relationships_router
from backend.app.api.v1.intelligence import router as intelligence_router
from backend.app.api.v1.ingestion import router as ingestion_router
from backend.app.api.v1.alerts import router as alerts_router
from backend.app.api.v1.geo import router as geo_router

api_router = APIRouter()

# Register v1 routes
api_router.include_router(health_router)
api_router.include_router(sources_router)
api_router.include_router(documents_router)
api_router.include_router(entities_router)
api_router.include_router(events_router)
api_router.include_router(clusters_router)
api_router.include_router(dashboard_router)
api_router.include_router(search_router)
api_router.include_router(indicators_router)
api_router.include_router(observations_router)
api_router.include_router(market_router)
api_router.include_router(relationships_router)
api_router.include_router(intelligence_router)
api_router.include_router(ingestion_router)
api_router.include_router(alerts_router)
api_router.include_router(geo_router)



