/**
 * Floating Map HUD Controls for V0.9-C.
 * Provides 2D/3D toggle, zoom buttons, reset view, and state filters.
 */

import React from 'react';
import type { LocationState } from '../../types/intelligence';

interface GlobeControlsProps {
  viewMode: '3d' | '2d';
  onToggleViewMode: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  locationStateFilter: LocationState | 'ALL';
  onChangeLocationFilter: (filter: LocationState | 'ALL') => void;
  renderedCount: number;
  totalMatching: number;
}

export const GlobeControls: React.FC<GlobeControlsProps> = ({
  viewMode,
  onToggleViewMode,
  onZoomIn,
  onZoomOut,
  onReset,
  locationStateFilter,
  onChangeLocationFilter,
  renderedCount,
  totalMatching,
}) => {
  return (
    <div
      style={{
        position: 'absolute',
        top: '1rem',
        left: '1rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.6rem',
        zIndex: 10,
        pointerEvents: 'auto',
      }}
    >
      {/* Projection Mode Toggle */}
      <div
        style={{
          display: 'flex',
          background: 'rgba(11, 15, 25, 0.85)',
          backdropFilter: 'blur(8px)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-sm)',
          padding: '0.25rem',
          boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        }}
      >
        <button
          type="button"
          onClick={onToggleViewMode}
          className={`btn btn-sm ${viewMode === '3d' ? 'btn-primary' : 'btn-ghost'}`}
          style={{
            fontSize: '0.75rem',
            padding: '0.3rem 0.65rem',
            fontWeight: 600,
          }}
          title="Switch between 3D Orthographic Globe and 2D Equirectangular Flat Map"
        >
          {viewMode === '3d' ? '🌐 3D Globe' : '🗺️ 2D Map'}
        </button>
      </div>

      {/* Navigation Buttons */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          background: 'rgba(11, 15, 25, 0.85)',
          backdropFilter: 'blur(8px)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-sm)',
          overflow: 'hidden',
          boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
          width: '36px',
        }}
      >
        <button
          type="button"
          onClick={onZoomIn}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-primary)',
            padding: '0.5rem 0',
            cursor: 'pointer',
            fontSize: '1rem',
            fontWeight: 'bold',
            borderBottom: '1px solid var(--border-subtle)',
          }}
          title="Zoom In"
        >
          +
        </button>
        <button
          type="button"
          onClick={onZoomOut}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-primary)',
            padding: '0.5rem 0',
            cursor: 'pointer',
            fontSize: '1.1rem',
            fontWeight: 'bold',
            borderBottom: '1px solid var(--border-subtle)',
          }}
          title="Zoom Out"
        >
          &minus;
        </button>
        <button
          type="button"
          onClick={onReset}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-secondary)',
            padding: '0.45rem 0',
            cursor: 'pointer',
            fontSize: '0.85rem',
          }}
          title="Reset Camera to Prime Meridian (0°, 20°N)"
        >
          &#x21ba;
        </button>
      </div>

      {/* State Filter Pills */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '0.3rem',
          background: 'rgba(11, 15, 25, 0.85)',
          backdropFilter: 'blur(8px)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-sm)',
          padding: '0.5rem',
          boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
          fontSize: '0.72rem',
        }}
      >
        <div style={{ color: 'var(--text-muted)', fontWeight: 600, marginBottom: '0.2rem', textTransform: 'uppercase', fontSize: '0.65rem', letterSpacing: '0.05em' }}>
          Location State
        </div>
        {(['ALL', 'RESOLVED', 'APPROXIMATE', 'REGIONAL'] as const).map((st) => (
          <button
            key={st}
            type="button"
            onClick={() => onChangeLocationFilter(st)}
            style={{
              textAlign: 'left',
              background: locationStateFilter === st ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
              border: locationStateFilter === st ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid transparent',
              color: locationStateFilter === st ? '#38bdf8' : 'var(--text-secondary)',
              borderRadius: '4px',
              padding: '0.25rem 0.5rem',
              cursor: 'pointer',
              fontSize: '0.72rem',
              fontWeight: locationStateFilter === st ? 600 : 400,
            }}
          >
            {st}
          </button>
        ))}

        {/* Density Ceiling Indicator */}
        <div
          style={{
            marginTop: '0.3rem',
            paddingTop: '0.3rem',
            borderTop: '1px solid var(--border-subtle)',
            color: 'var(--text-muted)',
            fontSize: '0.68rem',
          }}
        >
          Visible: <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{renderedCount}</span>
          {totalMatching > renderedCount && ` of ${totalMatching}`}
        </div>
      </div>
    </div>
  );
};
