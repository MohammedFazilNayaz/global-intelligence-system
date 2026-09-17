"""
Geographic Service Layer for V0.9-B.
Normalizes event locations into canonical four-state model (RESOLVED, APPROXIMATE, REGIONAL, UNRESOLVED)
with strict coordinate provenance and zero coordinate fabrication.
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, func, desc, or_
from sqlalchemy.orm import Session, joinedload

from backend.app.models.event import ExtractedEvent
from backend.app.models.entity import Entity, DocumentEntity
from backend.app.models.document import Document
from backend.app.models.source import Source
from backend.app.models.market_correlation import EventMarketCorrelation
from backend.app.schemas.geo import (
    LocationState,
    CoordinateSourceType,
    CoordinatePrecision,
    CoordinateProvenance,
    GeographicPoint,
    GeographicLocationItem,
    EventGeographicContext,
    GeoFeatureGeometry,
    GeoFeatureProperties,
    GeoFeature,
    GeoFeatureCollection,
)
from backend.app.geo.gazetteer import (
    lookup_municipal_centroid,
    is_maritime_zone,
)
from backend.app.utils.time import utc_now
from backend.app.utils.logger import setup_logger

logger = setup_logger("service.geo")


def _extract_sensor_coordinates(metadata: Dict[str, Any]) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Safely extract and validate authentic sensor coordinates from event metadata.
    Returns (latitude, longitude, error_note).
    """
    if not metadata:
        return None, None, None

    lat_raw = metadata.get("latitude")
    lon_raw = metadata.get("longitude")

    if lat_raw is None or lon_raw is None:
        return None, None, None

    try:
        lat = float(lat_raw)
        lon = float(lon_raw)
    except (ValueError, TypeError):
        return None, None, f"Non-numeric sensor coordinates: lat='{lat_raw}', lon='{lon_raw}'"

    # Strict physical boundary validation
    if lat < -90.0 or lat > 90.0:
        return None, None, f"Latitude {lat} out of physical bounds [-90.0, 90.0]"
    if lon < -180.0 or lon > 180.0:
        return None, None, f"Longitude {lon} out of physical bounds [-180.0, 180.0]"

    return lat, lon, None


def normalize_event_geography(
    event: ExtractedEvent,
    db: Optional[Session] = None,
    include_additional_locations: bool = True,
) -> EventGeographicContext:
    """
    Deterministically normalize an extracted event into the canonical four-state geographic contract.

    Semantics:
    - RESOLVED: Authentic point coordinates from sensor metadata (e.g. USGS GeoJSON)
    - APPROXIMATE: Known municipality/city with verified municipal centroid
    - REGIONAL: Country-level jurisdiction or maritime basin without point coordinates
    - UNRESOLVED: No verified spatial entity or sensor coordinates
    """
    meta = event.metadata_ or {}
    sensor_lat, sensor_lon, sensor_err = _extract_sensor_coordinates(meta)

    primary_loc: Optional[GeographicLocationItem] = None
    additional_locations: List[GeographicLocationItem] = []

    # 1. Check for authentic sensor point coordinates (USGS, telemetry sensors)
    if sensor_lat is not None and sensor_lon is not None:
        sensor_name = meta.get("sensor_source", "USGS_EARTHQUAKE_HAZARDS")
        prov = CoordinateProvenance(
            coordinate_source=sensor_name,
            coordinate_source_type=CoordinateSourceType.SENSOR,
            coordinate_precision=CoordinatePrecision.EXACT_SENSOR_POINT,
            location_state=LocationState.RESOLVED,
            latitude=sensor_lat,
            longitude=sensor_lon,
            resolved_at=event.event_time or event.created_at,
            confidence=event.confidence,
            verification_notes="Authentic sensor coordinates validated within WGS-84 bounds",
        )
        loc_name = meta.get("place") or event.location_entity.canonical_name if event.location_entity else "Seismic Epicenter"
        primary_loc = GeographicLocationItem(
            location_name=loc_name,
            location_state=LocationState.RESOLVED,
            entity_id=event.location_entity_id,
            entity_type=event.location_entity.entity_type if event.location_entity else "SENSOR_STATION",
            country_code=event.location_entity.country_code if event.location_entity else None,
            point=GeographicPoint(latitude=sensor_lat, longitude=sensor_lon),
            provenance=prov,
            is_maritime=False,
        )

    elif sensor_err is not None:
        # Invalid / out-of-bounds coordinates detected: reject and flag
        prov = CoordinateProvenance(
            coordinate_source=meta.get("sensor_source", "UNVERIFIED_SENSOR"),
            coordinate_source_type=CoordinateSourceType.UNKNOWN,
            coordinate_precision=CoordinatePrecision.NONE,
            location_state=LocationState.UNRESOLVED,
            latitude=None,
            longitude=None,
            resolved_at=event.created_at,
            confidence=0.0,
            verification_notes=sensor_err,
        )
        primary_loc = GeographicLocationItem(
            location_name="Invalid Coordinates",
            location_state=LocationState.UNRESOLVED,
            entity_id=event.location_entity_id,
            point=None,
            provenance=prov,
            is_maritime=False,
        )

    # 2. Check location entity attached to event
    elif event.location_entity:
        ent = event.location_entity
        ent_name = ent.canonical_name
        ent_type = ent.entity_type or "LOCATION"

        # 2a. Maritime zone check (e.g. Red Sea, Persian Gulf)
        if is_maritime_zone(ent_name) or is_maritime_zone(event.event_title):
            prov = CoordinateProvenance(
                coordinate_source="CANONICAL_MARITIME_GAZETTEER",
                coordinate_source_type=CoordinateSourceType.REGIONAL,
                coordinate_precision=CoordinatePrecision.NONE,
                location_state=LocationState.REGIONAL,
                latitude=None,
                longitude=None,
                resolved_at=event.created_at,
                confidence=event.confidence,
                verification_notes="Maritime region remains REGIONAL without fabricated point coordinates",
            )
            primary_loc = GeographicLocationItem(
                location_name=ent_name,
                location_state=LocationState.REGIONAL,
                entity_id=ent.id,
                entity_type="MARITIME_ZONE",
                country_code=ent.country_code,
                point=None,
                provenance=prov,
                is_maritime=True,
                maritime_zone=ent_name,
            )

        # 2b. Municipal / City entity
        elif ent_type in ("CITY", "LOCATION"):
            municipal_match = lookup_municipal_centroid(ent_name)
            if municipal_match:
                lat, lon, ccode, cname = municipal_match
                prov = CoordinateProvenance(
                    coordinate_source="CANONICAL_MUNICIPAL_GAZETTEER",
                    coordinate_source_type=CoordinateSourceType.MUNICIPAL,
                    coordinate_precision=CoordinatePrecision.MUNICIPAL_CENTROID,
                    location_state=LocationState.APPROXIMATE,
                    latitude=lat,
                    longitude=lon,
                    resolved_at=event.created_at,
                    confidence=event.confidence,
                    verification_notes="Municipal centroid assigned; indicates municipal scope, not exact incident point",
                )
                primary_loc = GeographicLocationItem(
                    location_name=cname,
                    location_state=LocationState.APPROXIMATE,
                    entity_id=ent.id,
                    entity_type="CITY",
                    country_code=ccode or ent.country_code,
                    point=GeographicPoint(latitude=lat, longitude=lon),
                    provenance=prov,
                    is_maritime=False,
                )
            else:
                # Municipal entity known by name, but unanchored in municipal catalog
                prov = CoordinateProvenance(
                    coordinate_source="UNANCHORED_MUNICIPALITY",
                    coordinate_source_type=CoordinateSourceType.MUNICIPAL,
                    coordinate_precision=CoordinatePrecision.NONE,
                    location_state=LocationState.APPROXIMATE,
                    latitude=None,
                    longitude=None,
                    resolved_at=event.created_at,
                    confidence=event.confidence,
                    verification_notes="Municipality recognized by NER but no verified centroid in gazetteer",
                )
                primary_loc = GeographicLocationItem(
                    location_name=ent_name,
                    location_state=LocationState.APPROXIMATE,
                    entity_id=ent.id,
                    entity_type="CITY",
                    country_code=ent.country_code,
                    point=None,
                    provenance=prov,
                    is_maritime=False,
                )

        # 2c. Country-level entity
        elif ent_type == "COUNTRY":
            prov = CoordinateProvenance(
                coordinate_source="CANONICAL_COUNTRY_GAZETTEER",
                coordinate_source_type=CoordinateSourceType.COUNTRY,
                coordinate_precision=CoordinatePrecision.NONE,
                location_state=LocationState.REGIONAL,
                latitude=None,
                longitude=None,
                resolved_at=event.created_at,
                confidence=event.confidence,
                verification_notes="Country jurisdiction; point coordinates strictly not fabricated for national events",
            )
            primary_loc = GeographicLocationItem(
                location_name=ent_name,
                location_state=LocationState.REGIONAL,
                entity_id=ent.id,
                entity_type="COUNTRY",
                country_code=ent.country_code,
                point=None,
                provenance=prov,
                is_maritime=False,
            )

        # 2d. Other organizational / unanchored entity
        else:
            prov = CoordinateProvenance(
                coordinate_source="NON_SPATIAL_ENTITY",
                coordinate_source_type=CoordinateSourceType.UNKNOWN,
                coordinate_precision=CoordinatePrecision.NONE,
                location_state=LocationState.UNRESOLVED,
                latitude=None,
                longitude=None,
                resolved_at=event.created_at,
                confidence=event.confidence,
                verification_notes=f"Entity type '{ent_type}' does not provide direct geographic grounding",
            )
            primary_loc = GeographicLocationItem(
                location_name=ent_name,
                location_state=LocationState.UNRESOLVED,
                entity_id=ent.id,
                entity_type=ent_type,
                point=None,
                provenance=prov,
                is_maritime=False,
            )

    # 3. Check for maritime mentions in title if no location entity attached
    elif is_maritime_zone(event.event_title) or is_maritime_zone(event.event_summary or ""):
        matched_zone = "Maritime Basin"
        for z in ["Red Sea", "Persian Gulf", "Mediterranean Sea", "Strait of Malacca", "Black Sea", "Baltic Sea"]:
            if z.lower() in event.event_title.lower() or z.lower() in (event.event_summary or "").lower():
                matched_zone = z
                break

        prov = CoordinateProvenance(
            coordinate_source="MARITIME_TEXT_GROUNDING",
            coordinate_source_type=CoordinateSourceType.REGIONAL,
            coordinate_precision=CoordinatePrecision.NONE,
            location_state=LocationState.REGIONAL,
            latitude=None,
            longitude=None,
            resolved_at=event.created_at,
            confidence=event.confidence,
            verification_notes="Maritime corridor identified from text; point coordinates strictly not fabricated",
        )
        primary_loc = GeographicLocationItem(
            location_name=matched_zone,
            location_state=LocationState.REGIONAL,
            point=None,
            provenance=prov,
            is_maritime=True,
            maritime_zone=matched_zone,
        )

    # 4. Fallback: Completely Unresolved Location
    else:
        prov = CoordinateProvenance(
            coordinate_source=None,
            coordinate_source_type=CoordinateSourceType.UNKNOWN,
            coordinate_precision=CoordinatePrecision.NONE,
            location_state=LocationState.UNRESOLVED,
            latitude=None,
            longitude=None,
            resolved_at=event.created_at,
            confidence=0.0,
            verification_notes="No location entity or sensor coordinates associated with event",
        )
        primary_loc = GeographicLocationItem(
            location_name="Location Unresolved",
            location_state=LocationState.UNRESOLVED,
            point=None,
            provenance=prov,
            is_maritime=False,
        )

    # 5. Multi-Location Discovery (Query other DocumentEntity rows for this document)
    if include_additional_locations and db and event.document_id:
        doc_entities_stmt = (
            select(DocumentEntity)
            .options(joinedload(DocumentEntity.entity))
            .where(
                DocumentEntity.document_id == event.document_id,
                DocumentEntity.entity_id != event.location_entity_id,
            )
        )
        doc_entities = db.scalars(doc_entities_stmt).all()
        seen_entity_ids = {event.location_entity_id} if event.location_entity_id else set()

        for de in doc_entities:
            if not de.entity or de.entity.id in seen_entity_ids:
                continue
            if de.entity.entity_type in ("COUNTRY", "CITY", "LOCATION"):
                seen_entity_ids.add(de.entity.id)
                e_name = de.entity.canonical_name
                e_type = de.entity.entity_type

                if e_type in ("CITY", "LOCATION"):
                    m_match = lookup_municipal_centroid(e_name)
                    if m_match:
                        lat, lon, cc, cn = m_match
                        sub_prov = CoordinateProvenance(
                            coordinate_source="CANONICAL_MUNICIPAL_GAZETTEER",
                            coordinate_source_type=CoordinateSourceType.MUNICIPAL,
                            coordinate_precision=CoordinatePrecision.MUNICIPAL_CENTROID,
                            location_state=LocationState.APPROXIMATE,
                            latitude=lat,
                            longitude=lon,
                            resolved_at=event.created_at,
                            confidence=de.confidence,
                        )
                        additional_locations.append(
                            GeographicLocationItem(
                                location_name=cn,
                                location_state=LocationState.APPROXIMATE,
                                entity_id=de.entity.id,
                                entity_type="CITY",
                                country_code=cc or de.entity.country_code,
                                point=GeographicPoint(latitude=lat, longitude=lon),
                                provenance=sub_prov,
                            )
                        )
                    else:
                        sub_prov = CoordinateProvenance(
                            coordinate_source="UNANCHORED_MUNICIPALITY",
                            coordinate_source_type=CoordinateSourceType.MUNICIPAL,
                            coordinate_precision=CoordinatePrecision.NONE,
                            location_state=LocationState.APPROXIMATE,
                            resolved_at=event.created_at,
                            confidence=de.confidence,
                        )
                        additional_locations.append(
                            GeographicLocationItem(
                                location_name=e_name,
                                location_state=LocationState.APPROXIMATE,
                                entity_id=de.entity.id,
                                entity_type="CITY",
                                country_code=de.entity.country_code,
                                point=None,
                                provenance=sub_prov,
                            )
                        )
                elif e_type == "COUNTRY":
                    sub_prov = CoordinateProvenance(
                        coordinate_source="CANONICAL_COUNTRY_GAZETTEER",
                        coordinate_source_type=CoordinateSourceType.COUNTRY,
                        coordinate_precision=CoordinatePrecision.NONE,
                        location_state=LocationState.REGIONAL,
                        resolved_at=event.created_at,
                        confidence=de.confidence,
                    )
                    additional_locations.append(
                        GeographicLocationItem(
                            location_name=e_name,
                            location_state=LocationState.REGIONAL,
                            entity_id=de.entity.id,
                            entity_type="COUNTRY",
                            country_code=de.entity.country_code,
                            point=None,
                            provenance=sub_prov,
                        )
                    )

    all_locs = ([primary_loc] if primary_loc else []) + additional_locations
    is_multi = len(all_locs) > 1

    return EventGeographicContext(
        event_id=event.id,
        location_state=primary_loc.location_state if primary_loc else LocationState.UNRESOLVED,
        primary_location=primary_loc,
        additional_locations=additional_locations,
        all_locations=all_locs,
        is_multi_location=is_multi,
        has_coordinates=bool(primary_loc and primary_loc.point is not None),
        coordinate_provenance=primary_loc.provenance if primary_loc else None,
    )


def get_geo_feature_collection(
    db: Session,
    min_lon: Optional[float] = None,
    min_lat: Optional[float] = None,
    max_lon: Optional[float] = None,
    max_lat: Optional[float] = None,
    location_state: Optional[str] = None,
    event_type: Optional[str] = None,
    country_code: Optional[str] = None,
    min_importance: Optional[float] = None,
    min_confidence: Optional[float] = None,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    freshness: Optional[str] = None,
    include_unresolved: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> GeoFeatureCollection:
    """
    Retrieve paginated RFC 7946 GeoJSON FeatureCollection of intelligence events.
    Applies multi-dimensional filtering, bounding box culling, and deterministic location state mapping.
    """
    stmt = select(ExtractedEvent).options(
        joinedload(ExtractedEvent.location_entity),
        joinedload(ExtractedEvent.document).joinedload(Document.source),
        joinedload(ExtractedEvent.market_correlations),
        joinedload(ExtractedEvent.cluster_membership),
    )

    # Filtering
    if event_type:
        stmt = stmt.where(ExtractedEvent.event_type == event_type.lower())
    if min_importance is not None:
        stmt = stmt.where(ExtractedEvent.importance >= min_importance)
    if min_confidence is not None:
        stmt = stmt.where(ExtractedEvent.confidence >= min_confidence)
    if from_time:
        stmt = stmt.where(ExtractedEvent.event_time >= from_time)
    if to_time:
        stmt = stmt.where(ExtractedEvent.event_time <= to_time)

    # Order by event time desc
    stmt = stmt.order_by(desc(ExtractedEvent.event_time).nulls_last(), desc(ExtractedEvent.created_at))

    all_events = db.scalars(stmt).unique().all()

    features: List[GeoFeature] = []
    resolved_count = 0
    approximate_count = 0
    regional_count = 0
    unresolved_count = 0

    now_utc = utc_now()

    for event in all_events:
        geo_ctx = normalize_event_geography(event, db=db, include_additional_locations=False)
        loc_item = geo_ctx.primary_location
        l_state = geo_ctx.location_state

        # Update running category counts
        if l_state == LocationState.RESOLVED:
            resolved_count += 1
        elif l_state == LocationState.APPROXIMATE:
            approximate_count += 1
        elif l_state == LocationState.REGIONAL:
            regional_count += 1
        else:
            unresolved_count += 1

        # Check location_state filter
        if location_state and l_state.value.upper() != location_state.upper():
            continue

        # Skip unresolved unless explicitly requested
        if l_state == LocationState.UNRESOLVED and not include_unresolved:
            continue

        # Check country filter
        if country_code and loc_item and loc_item.country_code:
            if loc_item.country_code.upper() != country_code.upper():
                continue

        # Check bounding box culling if point coordinates exist
        if loc_item and loc_item.point:
            lat = loc_item.point.latitude
            lon = loc_item.point.longitude
            if min_lat is not None and lat < min_lat:
                continue
            if max_lat is not None and lat > max_lat:
                continue
            if min_lon is not None and lon < min_lon:
                continue
            if max_lon is not None and lon > max_lon:
                continue
        elif min_lat is not None or min_lon is not None or max_lat is not None or max_lon is not None:
            # If bounding box filter is active and feature has no coordinates, omit
            continue

        # Determine freshness status
        freshness_status = "CURRENT"
        t_ref = event.event_time or event.created_at
        if t_ref:
            t_ref_aware = t_ref if t_ref.tzinfo is not None else t_ref.replace(tzinfo=timezone.utc)
            age_hours = (now_utc - t_ref_aware).total_seconds() / 3600.0
            if age_hours <= 24.0:
                freshness_status = "CURRENT"
            elif age_hours <= 168.0:
                freshness_status = "RECENT"
            elif age_hours <= 720.0:
                freshness_status = "STALE"
            else:
                freshness_status = "HISTORICAL"

        if freshness and freshness_status.upper() != freshness.upper():
            continue

        # Collect associated market symbols
        assets: List[str] = []
        if event.market_correlations:
            for corr in event.market_correlations:
                if corr.market_asset and corr.market_asset.symbol not in assets:
                    assets.append(corr.market_asset.symbol)

        is_primary_source = False
        if event.document and event.document.source:
            is_primary_source = bool(event.document.source.is_primary)

        # Build geometry
        geom = None
        if loc_item and loc_item.point:
            geom = GeoFeatureGeometry(
                type="Point",
                coordinates=[loc_item.point.longitude, loc_item.point.latitude],
            )

        props = GeoFeatureProperties(
            event_id=event.id,
            title=event.event_title,
            event_type=event.event_type,
            importance=event.importance,
            confidence=event.confidence,
            event_time=event.event_time,
            freshness_status=freshness_status,
            location_state=l_state,
            location_name=loc_item.location_name if loc_item else None,
            country_code=loc_item.country_code if loc_item else None,
            is_primary=is_primary_source,
            cluster_id=event.cluster_membership.event_cluster_id if event.cluster_membership else None,
            coordinate_source_type=loc_item.provenance.coordinate_source_type if loc_item else CoordinateSourceType.UNKNOWN,
            coordinate_precision=loc_item.provenance.coordinate_precision if loc_item else CoordinatePrecision.NONE,
            is_multi_location=geo_ctx.is_multi_location,
            additional_location_count=len(geo_ctx.additional_locations),
            is_maritime=bool(loc_item and loc_item.is_maritime),
            associated_assets=assets,
        )

        features.append(GeoFeature(id=event.id, geometry=geom, properties=props))

    # Pagination
    total_matching = len(features)
    total_pages = math.ceil(total_matching / page_size) if total_matching > 0 else 1
    offset = (page - 1) * page_size
    paged_features = features[offset : offset + page_size]

    return GeoFeatureCollection(
        features=paged_features,
        total=total_matching,
        resolved_count=resolved_count,
        approximate_count=approximate_count,
        regional_count=regional_count,
        unresolved_count=unresolved_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        query_timestamp=now_utc,
    )


def get_unresolved_events(
    db: Session,
    event_type: Optional[str] = None,
    min_importance: Optional[float] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[ExtractedEvent], int, int]:
    """
    Retrieve paginated extracted events that normalize into the UNRESOLVED location state.
    Cleanly separates unlocated events for the Spatially Unresolved Intelligence Tray.
    """
    stmt = select(ExtractedEvent).options(
        joinedload(ExtractedEvent.location_entity),
        joinedload(ExtractedEvent.document).joinedload(Document.source),
    )

    if event_type:
        stmt = stmt.where(ExtractedEvent.event_type == event_type.lower())
    if min_importance is not None:
        stmt = stmt.where(ExtractedEvent.importance >= min_importance)

    stmt = stmt.order_by(desc(ExtractedEvent.importance), desc(ExtractedEvent.created_at))
    all_events = db.scalars(stmt).unique().all()

    unresolved_events = []
    for ev in all_events:
        ctx = normalize_event_geography(ev, db=None, include_additional_locations=False)
        if ctx.location_state == LocationState.UNRESOLVED:
            unresolved_events.append(ev)

    total = len(unresolved_events)
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size
    paged = unresolved_events[offset : offset + page_size]

    return paged, total, total_pages
