/**
 * Status and Error Overlay Component for V0.9-C.
 * Handles loading, error with retry, and empty filter states without crashing the canvas.
 */

import React from 'react';

interface GlobeStatusOverlayProps {
  loading: boolean;
  error: string | null;
  empty: boolean;
  onRetry: () => void;
}

export const GlobeStatusOverlay: React.FC<GlobeStatusOverlayProps> = ({
  loading,
  error,
  empty,
  onRetry,
}) => {
  if (loading) {
    return (
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(5, 8, 19, 0.65)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 15,
          pointerEvents: 'none',
        }}
      >
        <div
          style={{
            width: '36px',
            height: '36px',
            border: '3px solid rgba(56, 189, 248, 0.2)',
            borderTop: '3px solid #38bdf8',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            marginBottom: '0.8rem',
          }}
        />
        <div style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: '0.9rem' }}>
          Projecting Geographic Intelligence...
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '0.2rem' }}>
          Computing geodesic coordinate transformations
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          position: 'absolute',
          top: '1rem',
          right: '1rem',
          background: 'rgba(239, 68, 68, 0.15)',
          backdropFilter: 'blur(8px)',
          border: '1px solid #ef4444',
          borderRadius: 'var(--radius-sm)',
          padding: '0.65rem 1rem',
          zIndex: 15,
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          color: '#fca5a5',
          fontSize: '0.78rem',
          boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
        }}
      >
        <div>
          <div style={{ fontWeight: 600, color: '#ef4444' }}>Map Update Interrupted</div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.72rem' }}>{error}</div>
        </div>
        <button
          type="button"
          onClick={onRetry}
          className="btn btn-sm"
          style={{
            background: 'rgba(239, 68, 68, 0.3)',
            color: '#fff',
            border: '1px solid #ef4444',
            fontSize: '0.72rem',
            padding: '0.25rem 0.6rem',
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  if (empty) {
    return (
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          background: 'rgba(11, 15, 25, 0.88)',
          backdropFilter: 'blur(8px)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-sm)',
          padding: '1rem 1.5rem',
          textAlign: 'center',
          zIndex: 12,
          pointerEvents: 'none',
          maxWidth: '320px',
        }}
      >
        <div style={{ fontSize: '1.2rem', marginBottom: '0.4rem' }}>🌐</div>
        <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.85rem' }}>
          No Matching Intelligence Features
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '0.25rem' }}>
          Active filters yielded 0 features. Try selecting "ALL" states or adjusting importance.
        </div>
      </div>
    );
  }

  return null;
};
