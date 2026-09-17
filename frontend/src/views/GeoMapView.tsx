/**
 * Geographic Situational Awareness View for V0.9-C.
 * Replaces the lightweight prototype with the Dual-Mode Interactive Globe Rendering Foundation.
 *
 * Enforces:
 * 1. Read-only consumption of V0.9-B GET /api/v1/geo/features
 * 2. 3D Orthographic default view with instantaneous 2D Equirectangular toggle
 * 3. Exact 2D/3D camera and state parity
 * 4. Four-state visual integrity (RESOLVED, APPROXIMATE, REGIONAL, UNRESOLVED)
 * 5. <=150 individual marker ceiling with deterministic prioritization
 * 6. Zero coordinate fabrication
 */

import React, { useState, useCallback, useMemo } from 'react';
import type { LocationState, GeoFeature } from '../types/intelligence';
import { useGlobeProjection } from '../hooks/useGlobeProjection';
import { useGeoFeatures } from '../hooks/useGeoFeatures';
import { GlobeCanvas } from '../components/geo/GlobeCanvas';
import { GlobeControls } from '../components/geo/GlobeControls';
import { GlobeTooltip } from '../components/geo/GlobeTooltip';
import { GlobeLegend } from '../components/geo/GlobeLegend';
import { GlobeStatusOverlay } from '../components/geo/GlobeStatusOverlay';
import { UnresolvedSummaryBadge } from '../components/geo/UnresolvedSummaryBadge';
import { RegionalLedger } from '../components/geo/RegionalLedger';
import { ImportanceBadge, ConfidenceBadge, EventTypeBadge } from '../components/Badges';

interface GeoMapViewProps {
  onSelectCluster?: (clusterId: string) => void;
  onSelectEvent?: (eventId: string) => void;
}

export const GeoMapView: React.FC<GeoMapViewProps> = ({
  onSelectCluster,
  onSelectEvent,
}) => {
  // Shared Camera State (Preserved across 2D <-> 3D mode toggles)
  const {
    viewMode,
    centerLon,
    centerLat,
    zoom,
    toggleViewMode,
    setCenter,
    setZoom,
    resetCamera,
  } = useGlobeProjection({ initialViewMode: '3d', initialLon: 0, initialLat: 20, initialZoom: 1.0 });

  // Filter State
  const [locationStateFilter, setLocationStateFilter] = useState<LocationState | 'ALL'>('ALL');

  // Load Geographic Features from V0.9-B Read-Only API
  const {
    loading,
    error,
    renderedFeatures,
    overflowFeatures,
    regionalFeatures,
    unresolvedCount,
    totalMatching,
    resolvedCount,
    approximateCount,
    regionalCount,
    refetch,
  } = useGeoFeatures({
    locationState: locationStateFilter === 'ALL' ? undefined : locationStateFilter,
  });

  // Interaction State
  const [selectedFeatureId, setSelectedFeatureId] = useState<string | null>(null);
  const [hoveredFeature, setHoveredFeature] = useState<GeoFeature | null>(null);
  const [hoverPosition, setHoverPosition] = useState<{ x: number; y: number } | null>(null);

  // Find currently selected feature object from all available features
  const selectedFeature = useMemo(() => {
    if (!selectedFeatureId) return null;
    return (
      renderedFeatures.find((f) => f.id === selectedFeatureId) ||
      overflowFeatures.find((f) => f.id === selectedFeatureId) ||
      regionalFeatures.find((f) => f.id === selectedFeatureId) ||
      null
    );
  }, [selectedFeatureId, renderedFeatures, overflowFeatures, regionalFeatures]);

  // Camera Rotation / Pan handlers
  const handleRotateCamera = useCallback((dLon: number, dLat: number) => {
    setCenter(centerLon + dLon, centerLat + dLat);
  }, [centerLon, centerLat, setCenter]);

  const handlePanCamera = useCallback((dLon: number, dLat: number) => {
    setCenter(centerLon + dLon, centerLat + dLat);
  }, [centerLon, centerLat, setCenter]);

  const handleZoomIn = useCallback(() => {
    setZoom((z) => z * 1.25);
  }, [setZoom]);

  const handleZoomOut = useCallback(() => {
    setZoom((z) => z * 0.8);
  }, [setZoom]);

  const handleZoomFactor = useCallback((factor: number) => {
    setZoom((z) => z * factor);
  }, [setZoom]);

  const handleHoverChange = useCallback(
    (feature: GeoFeature | null, position: { x: number; y: number } | null) => {
      setHoveredFeature(feature);
      setHoverPosition(position);
    },
    []
  );

  const handleInspectSelected = useCallback(() => {
    if (!selectedFeature) return;
    if (selectedFeature.properties.cluster_id && onSelectCluster) {
      onSelectCluster(selectedFeature.properties.cluster_id);
    } else if (onSelectEvent) {
      onSelectEvent(selectedFeature.id);
    }
  }, [selectedFeature, onSelectCluster, onSelectEvent]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%' }}>
      {/* View Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            Interactive Global Intelligence Globe (V0.9-C)
          </h2>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
            Dual-Mode Situational Awareness &middot; {viewMode === '3d' ? '3D Orthographic Sphere' : '2D Equirectangular Overview'} &middot;{' '}
            <span style={{ color: '#34d399', fontWeight: 600 }}>{resolvedCount} Resolved</span> &middot;{' '}
            <span style={{ color: '#fbbf24', fontWeight: 600 }}>{approximateCount} Approximate</span> &middot;{' '}
            <span style={{ color: '#eab308', fontWeight: 600 }}>{regionalCount} Regional</span>
          </div>
        </div>

        {/* Status badges */}
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <div
            style={{
              fontSize: '0.72rem',
              color: 'var(--text-muted)',
              background: 'var(--bg-surface)',
              padding: '0.35rem 0.65rem',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            Camera: <span style={{ fontFamily: 'monospace', color: 'var(--text-primary)' }}>{centerLat.toFixed(1)}°N, {centerLon.toFixed(1)}°E</span> &middot; Zoom {zoom.toFixed(1)}x
          </div>
        </div>
      </div>

      {/* Main Map Viewport */}
      <div
        className="section-box"
        style={{
          position: 'relative',
          padding: 0,
          overflow: 'hidden',
          minHeight: '560px',
          height: '62vh',
          display: 'flex',
          flexDirection: 'column',
          background: '#050813',
        }}
      >
        {/* Core Canvas */}
        <GlobeCanvas
          viewMode={viewMode}
          centerLon={centerLon}
          centerLat={centerLat}
          zoom={zoom}
          features={renderedFeatures}
          selectedFeatureId={selectedFeatureId}
          onSelectFeature={setSelectedFeatureId}
          onRotateCamera={handleRotateCamera}
          onPanCamera={handlePanCamera}
          onZoomCamera={handleZoomFactor}
          onHoverFeatureChange={handleHoverChange}
        />

        {/* Floating HUD Controls */}
        <GlobeControls
          viewMode={viewMode}
          onToggleViewMode={toggleViewMode}
          onZoomIn={handleZoomIn}
          onZoomOut={handleZoomOut}
          onReset={resetCamera}
          locationStateFilter={locationStateFilter}
          onChangeLocationFilter={setLocationStateFilter}
          renderedCount={renderedFeatures.length}
          totalMatching={totalMatching}
        />

        {/* Quarantined Off-Map Unresolved Counter */}
        <UnresolvedSummaryBadge unresolvedCount={unresolvedCount} />

        {/* Symbology Legend */}
        <GlobeLegend />

        {/* Non-Point Regional Ledger */}
        <RegionalLedger
          regionalFeatures={regionalFeatures}
          selectedFeatureId={selectedFeatureId}
          onSelectFeature={setSelectedFeatureId}
        />

        {/* Hover Tooltip Card */}
        {hoveredFeature && hoverPosition && (
          <GlobeTooltip feature={hoveredFeature} position={hoverPosition} />
        )}

        {/* Loading / Error / Empty Overlays */}
        <GlobeStatusOverlay
          loading={loading}
          error={error}
          empty={!loading && !error && renderedFeatures.length === 0 && regionalFeatures.length === 0}
          onRetry={refetch}
        />
      </div>

      {/* Selected Event Analytical Banner */}
      {selectedFeature && (
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-strong)',
            borderRadius: 'var(--radius-sm)',
            padding: '1rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '1rem',
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.3)',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span
                style={{
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  padding: '0.15rem 0.45rem',
                  borderRadius: '3px',
                  background:
                    selectedFeature.properties.location_state === 'RESOLVED'
                      ? 'rgba(16, 185, 129, 0.2)'
                      : selectedFeature.properties.location_state === 'APPROXIMATE'
                      ? 'rgba(245, 158, 11, 0.2)'
                      : 'rgba(234, 179, 8, 0.2)',
                  color:
                    selectedFeature.properties.location_state === 'RESOLVED'
                      ? '#34d399'
                      : selectedFeature.properties.location_state === 'APPROXIMATE'
                      ? '#fbbf24'
                      : '#eab308',
                  border: '1px solid currentColor',
                }}
              >
                {selectedFeature.properties.location_state}
              </span>
              <EventTypeBadge eventType={selectedFeature.properties.event_type} />
              <ImportanceBadge importance={selectedFeature.properties.importance} />
              <ConfidenceBadge confidence={selectedFeature.properties.confidence} />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {selectedFeature.properties.freshness_status}
              </span>
            </div>

            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              {selectedFeature.properties.title}
            </h3>

            {selectedFeature.geometry && (
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                Spatial Coordinates: Lat {selectedFeature.geometry.coordinates[1].toFixed(4)}°, Lon {selectedFeature.geometry.coordinates[0].toFixed(4)}°
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleInspectSelected}
            >
              Inspect Details &rarr;
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setSelectedFeatureId(null)}
            >
              Deselect
            </button>
          </div>
        </div>
      )}

      {/* Screen Reader Semantic Accessibility Summary */}
      <ul className="sr-only" aria-label="Geographic intelligence events currently visible on map">
        {renderedFeatures.map((f) => (
          <li key={f.id}>
            {f.properties.title} ({f.properties.location_state}, {f.properties.event_type})
          </li>
        ))}
      </ul>
    </div>
  );
};
