from typing import Dict, Type
from backend.app.collectors.base import BaseSourceCollector
from backend.app.collectors.rss import RSSCollector
from backend.app.collectors.api import APICollector
from backend.app.collectors.geojson import GeoJSONCollector

COLLECTOR_REGISTRY: Dict[str, Type[BaseSourceCollector]] = {
    "rss": RSSCollector,
    "api": APICollector,
    "official_publication": RSSCollector,  # Official feeds frequently publish via RSS/Atom
    "geojson": GeoJSONCollector,
}


def register_collector(source_type: str, collector_cls: Type[BaseSourceCollector]) -> None:
    """Register a new collector adapter class for a source type."""
    COLLECTOR_REGISTRY[source_type.lower()] = collector_cls


def get_collector_class(source_type: str) -> Type[BaseSourceCollector]:
    """Retrieve the collector adapter class for a source type."""
    normalized_type = source_type.lower()
    if normalized_type not in COLLECTOR_REGISTRY:
        raise ValueError(
            f"Unsupported source_type '{source_type}'. "
            f"Available types: {list(COLLECTOR_REGISTRY.keys())}"
        )
    return COLLECTOR_REGISTRY[normalized_type]
