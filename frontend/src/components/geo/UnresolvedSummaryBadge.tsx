/**
 * Unresolved / Off-Map Quarantine Indicator for V0.9-C.
 * Displays the count of spatially unlocated events that remain strictly off-canvas.
 */

import React from 'react';

interface UnresolvedSummaryBadgeProps {
  unresolvedCount: number;
}

export const UnresolvedSummaryBadge: React.FC<UnresolvedSummaryBadgeProps> = ({
  unresolvedCount,
}) => {
  return (
    <div
      style={{
        position: 'absolute',
        top: '1rem',
        right: '1rem',
        background: 'rgba(11, 15, 25, 0.85)',
        backdropFilter: 'blur(8px)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-sm)',
        padding: '0.45rem 0.75rem',
        zIndex: 10,
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        fontSize: '0.72rem',
        color: 'var(--text-secondary)',
        boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        pointerEvents: 'auto',
      }}
      title="Events lacking verified coordinates are strictly quarantined off-canvas (Zero Fabrication Policy)"
    >
      <span
        style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: unresolvedCount > 0 ? '#eab308' : '#10b981',
          display: 'inline-block',
        }}
      />
      <span>
        <strong>{unresolvedCount}</strong> Unlocated Quarantined
      </span>
      <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}>
        (Off-Map)
      </span>
    </div>
  );
};
