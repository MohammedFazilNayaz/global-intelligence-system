/**
 * Floating Cursor-Anchored HUD Tooltip for V0.9-C.
 * Displays title, location state, coordinates, source type, and freshness.
 */

import React from 'react';
import type { GeoFeature } from '../../types/intelligence';
import { getCategoryColor } from '../../utils/geo/markerRenderer';

interface GlobeTooltipProps {
  feature: GeoFeature;
  position: { x: number; y: number };
}

export const GlobeTooltip: React.FC<GlobeTooltipProps> = ({ feature, position }) => {
  const props = feature.properties;
  const state = props.location_state;
  const categoryColor = getCategoryColor(props.event_type);
  const coords = feature.geometry?.coordinates;

  return (
    <div
      style={{
        position: 'absolute',
        left: `${position.x + 14}px`,
        top: `${position.y - 14}px`,
        background: 'rgba(11, 15, 25, 0.92)',
        backdropFilter: 'blur(10px)',
        border: '1px solid var(--border-strong)',
        borderRadius: 'var(--radius-sm)',
        padding: '0.65rem 0.85rem',
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.6)',
        color: '#fff',
        fontSize: '0.78rem',
        maxWidth: '280px',
        pointerEvents: 'none',
        zIndex: 20,
        lineHeight: 1.35,
      }}
    >
      {/* Title */}
      <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.35rem' }}>
        {props.title}
      </div>

      {/* State & Category Badges */}
      <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center', marginBottom: '0.35rem', flexWrap: 'wrap' }}>
        <span
          style={{
            fontSize: '0.68rem',
            padding: '0.15rem 0.4rem',
            borderRadius: '3px',
            background: state === 'RESOLVED' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
            color: state === 'RESOLVED' ? '#34d399' : '#fbbf24',
            border: state === 'RESOLVED' ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(245, 158, 11, 0.4)',
            fontWeight: 600,
          }}
        >
          {state === 'RESOLVED' ? 'RESOLVED (Sensor)' : 'APPROXIMATE (Centroid)'}
        </span>

        <span
          style={{
            fontSize: '0.68rem',
            padding: '0.15rem 0.4rem',
            borderRadius: '3px',
            background: `${categoryColor}25`,
            color: categoryColor,
            border: `1px solid ${categoryColor}50`,
            textTransform: 'capitalize',
          }}
        >
          {props.event_type}
        </span>

        <span
          style={{
            fontSize: '0.68rem',
            padding: '0.15rem 0.4rem',
            borderRadius: '3px',
            background: 'rgba(51, 65, 85, 0.4)',
            color: '#94a3b8',
          }}
        >
          {props.freshness_status}
        </span>
      </div>

      {/* Spatial Telemetry */}
      {coords && (
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
          Lat: {coords[1].toFixed(2)}° | Lon: {coords[0].toFixed(2)}°
        </div>
      )}

      {props.location_name && (
        <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
          Anchor: <span style={{ fontStyle: 'italic' }}>{props.location_name}</span>
        </div>
      )}

      <div style={{ fontSize: '0.68rem', color: 'var(--accent-blue)', marginTop: '0.4rem' }}>
        Click marker to inspect event details
      </div>
    </div>
  );
};
