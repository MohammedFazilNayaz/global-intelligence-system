import json
import time
from datetime import datetime, timezone
from typing import List, Any, Dict, Optional

from backend.app.collectors.base import BaseSourceCollector
from backend.app.schemas.document import NormalizedDocument
from backend.app.processors.normalizer import build_normalized_document
from backend.app.utils.time import utc_now


class GeoJSONCollector(BaseSourceCollector):
    """Collector adapter for geospatial feeds (e.g. USGS Earthquakes GeoJSON)."""

    def fetch_raw(self) -> str:
        """Fetch raw GeoJSON payload using resilient HTTP client."""
        custom_headers = self.config_metadata.get("headers", {})
        response = self.http_client.get(self.feed_url, headers=custom_headers)
        return response.text

    def parse_and_normalize(self, raw_data: str) -> List[NormalizedDocument]:
        """Parse GeoJSON FeatureCollection and convert features to NormalizedDocument models."""
        try:
            payload = json.loads(raw_data)
        except Exception as exc:
            raise ValueError(f"Malformed GeoJSON in source '{self.name}': {exc}")

        features = payload.get("features", [])
        normalized_docs: List[NormalizedDocument] = []

        for feat in features:
            try:
                feat_id = feat.get("id")
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                coords = geom.get("coordinates", [0.0, 0.0, 0.0])

                lon = float(coords[0]) if len(coords) > 0 else 0.0
                lat = float(coords[1]) if len(coords) > 1 else 0.0
                depth_km = float(coords[2]) if len(coords) > 2 else 0.0

                mag = props.get("mag")
                place = props.get("place") or "Unknown location"
                time_ms = props.get("time")

                if time_ms:
                    published_at = datetime.fromtimestamp(time_ms / 1000.0, tz=timezone.utc)
                else:
                    published_at = utc_now()

                mag_str = f"M{mag:.1f}" if mag is not None else "Seismic Event"
                title = f"{mag_str} Earthquake - {place}"
                url = props.get("url") or f"https://earthquake.usgs.gov/earthquakes/eventpage/{feat_id}"
                
                content = (
                    f"A {mag_str} earthquake occurred {place}. "
                    f"Official seismic observation: magnitude {mag}, latitude {lat:.4f}, "
                    f"longitude {lon:.4f}, depth {depth_km:.1f} km."
                )

                raw_metadata = {
                    "latitude": lat,
                    "longitude": lon,
                    "depth_km": depth_km,
                    "magnitude": mag,
                    "place": place,
                    "event_type": "disaster",
                    "hazard_type": "earthquake",
                    "status": props.get("status"),
                    "tsunami": props.get("tsunami", 0),
                    "significance": props.get("sig"),
                }

                doc = build_normalized_document(
                    source_name=self.name,
                    title=title,
                    url=url,
                    published_at=published_at,
                    external_id=str(feat_id or f"usgs_{lat}_{lon}_{time_ms}"),
                    description=content,
                    content=content,
                    author="USGS Earthquake Hazards Program",
                    language="en",
                    raw_metadata=raw_metadata,
                )
                normalized_docs.append(doc)
            except Exception as item_err:
                self.logger.warning(f"Error normalizing GeoJSON feature in '{self.name}': {item_err}")
                continue

        return normalized_docs
