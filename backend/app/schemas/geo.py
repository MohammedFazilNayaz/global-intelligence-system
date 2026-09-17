import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class LocationState(str, Enum):
    """Four canonical geographic location states for intelligence visualization."""
    RESOLVED = "RESOLVED"          # Authentic coordinates from authoritative primary sensor or verified geocoding
    APPROXIMATE = "APPROXIMATE"    # Location known to municipality/district/perimeter level (not exact event point)
    REGIONAL = "REGIONAL"          # Location known only at country, maritime, or transnational regional level
    UNRESOLVED = "UNRESOLVED"      # No reliable geographic location found or coordinates invalid


class CoordinateSourceType(str, Enum):
    """Categorization of how coordinates were acquired."""
    SENSOR = "SENSOR"                      # Primary telemetry sensor (e.g. USGS seismograph, satellite)
    OFFICIAL_SOURCE = "OFFICIAL_SOURCE"    # Sovereign ministry, central bank, or official gazette
    GEOCODED = "GEOCODED"                  # Verified point lookup from authoritative gazetteer
    MUNICIPAL = "MUNICIPAL"                # Municipal/city centroid
    COUNTRY = "COUNTRY"                    # Sovereign territorial centroid
    REGIONAL = "REGIONAL"                  # Transnational or maritime region
    UNKNOWN = "UNKNOWN"                    # Unresolved or missing


class CoordinatePrecision(str, Enum):
    """Precision tier of the spatial coordinates."""
    EXACT_SENSOR_POINT = "EXACT_SENSOR_POINT"
    MUNICIPAL_CENTROID = "MUNICIPAL_CENTROID"
    TERRITORIAL_CENTROID = "TERRITORIAL_CENTROID"
    NONE = "NONE"


class GeographicPoint(BaseModel):
    """Validated WGS-84 decimal coordinate point."""
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS-84 latitude in decimal degrees (-90.0 to 90.0)")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS-84 longitude in decimal degrees (-180.0 to 180.0)")

    model_config = ConfigDict(from_attributes=True)


class CoordinateProvenance(BaseModel):
    """Audit trail verifying the origin, precision, and validity of geographic coordinates."""
    coordinate_source: Optional[str] = None
    coordinate_source_type: CoordinateSourceType = CoordinateSourceType.UNKNOWN
    coordinate_precision: CoordinatePrecision = CoordinatePrecision.NONE
    location_state: LocationState = LocationState.UNRESOLVED
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    resolved_at: Optional[datetime] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    verification_notes: Optional[str] = None

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < -90.0 or v > 90.0):
            raise ValueError(f"Latitude {v} out of physical bounds [-90.0, 90.0]")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < -180.0 or v > 180.0):
            raise ValueError(f"Longitude {v} out of physical bounds [-180.0, 180.0]")
        return v

    model_config = ConfigDict(from_attributes=True)


class GeographicLocationItem(BaseModel):
    """Standardized representation of a single location associated with an event."""
    location_name: str
    location_state: LocationState
    entity_id: Optional[uuid.UUID] = None
    entity_type: Optional[str] = None
    country_code: Optional[str] = Field(None, max_length=8)
    point: Optional[GeographicPoint] = None
    provenance: CoordinateProvenance
    is_maritime: bool = False
    maritime_zone: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class EventGeographicContext(BaseModel):
    """Complete geographic intelligence contract for an extracted event."""
    event_id: uuid.UUID
    location_state: LocationState
    primary_location: Optional[GeographicLocationItem] = None
    additional_locations: List[GeographicLocationItem] = Field(default_factory=list)
    all_locations: List[GeographicLocationItem] = Field(default_factory=list)
    is_multi_location: bool = False
    has_coordinates: bool = False
    coordinate_provenance: Optional[CoordinateProvenance] = None

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# GeoJSON RFC 7946 Compliant Schemas
# ==============================================================================

class GeoFeatureGeometry(BaseModel):
    """RFC 7946 GeoJSON Geometry object (Point coordinates [longitude, latitude])."""
    type: Literal["Point"] = "Point"
    coordinates: List[float] = Field(..., min_length=2, max_length=2, description="[longitude, latitude] in decimal degrees")

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, coords: List[float]) -> List[float]:
        lon, lat = coords[0], coords[1]
        if lat < -90.0 or lat > 90.0:
            raise ValueError(f"Latitude {lat} out of physical bounds [-90.0, 90.0]")
        if lon < -180.0 or lon > 180.0:
            raise ValueError(f"Longitude {lon} out of physical bounds [-180.0, 180.0]")
        return coords


class GeoFeatureProperties(BaseModel):
    """Standardized map feature properties optimized for low-latency client rendering."""
    event_id: uuid.UUID
    title: str
    event_type: str
    importance: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    event_time: Optional[datetime] = None
    freshness_status: str = "CURRENT"
    location_state: LocationState
    location_name: Optional[str] = None
    country_code: Optional[str] = None
    is_primary: bool = False
    cluster_id: Optional[uuid.UUID] = None
    cluster_title: Optional[str] = None
    coordinate_source_type: CoordinateSourceType = CoordinateSourceType.UNKNOWN
    coordinate_precision: CoordinatePrecision = CoordinatePrecision.NONE
    is_multi_location: bool = False
    additional_location_count: int = 0
    is_maritime: bool = False
    associated_assets: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class GeoFeature(BaseModel):
    """RFC 7946 GeoJSON Feature representation."""
    type: Literal["Feature"] = "Feature"
    id: uuid.UUID
    geometry: Optional[GeoFeatureGeometry] = None
    properties: GeoFeatureProperties

    model_config = ConfigDict(from_attributes=True)


class GeoFeatureCollection(BaseModel):
    """RFC 7946 GeoJSON FeatureCollection with institutional metadata and pagination."""
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[GeoFeature]
    total: int
    resolved_count: int
    approximate_count: int
    regional_count: int
    unresolved_count: int
    page: int = 1
    page_size: int = 50
    total_pages: int = 1
    query_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
