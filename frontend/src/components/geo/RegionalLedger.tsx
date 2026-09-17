/**
 * Regional Events Non-Point Representation for V0.9-C.
 * Displays regional intelligence events without point coordinates in an analytical ledger,
 * strictly upholding the zero coordinate fabrication invariant.
 */

import React, { useState } from 'react';
import type { GeoFeature } from '../../types/intelligence';
import { getCategoryColor } from '../../utils/geo/markerRenderer';

interface RegionalLedgerProps {
  regionalFeatures: GeoFeature[];
  selectedFeatureId: string | null;
  onSelectFeature: (featureId: string | null) => void;
}

export const RegionalLedger: React.FC<RegionalLedgerProps> = ({
  regionalFeatures,
  selectedFeatureId,
  onSelectFeature,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  if (!regionalFeatures || regionalFeatures.length === 0) {
    return null;
  }

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '1rem',
        right: '1rem',
        zIndex: 10,
        pointerEvents: 'auto',
        maxWidth: '320px',
      }}
    >
      {!isExpanded ? (
        <button
          type="button"
          onClick={() => setIsExpanded(true)}
          style={{
            background: 'rgba(11, 15, 25, 0.85)',
            backdropFilter: 'blur(8px)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--text-secondary)',
            padding: '0.35rem 0.65rem',
            fontSize: '0.72rem',
            fontWeight: 600,
            cursor: 'pointer',
            boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
          }}
        >
          <span style={{ color: '#eab308' }}>▣</span>
          <span>Regional Intelligence ({regionalFeatures.length})</span>
        </button>
      ) : (
        <div
          style={{
            background: 'rgba(11, 15, 25, 0.94)',
            backdropFilter: 'blur(10px)',
            border: '1px solid var(--border-strong)',
            borderRadius: 'var(--radius-sm)',
            padding: '0.75rem',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.6)',
            color: 'var(--text-primary)',
            fontSize: '0.72rem',
            maxHeight: '320px',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
            <span style={{ fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Regional Events ({regionalFeatures.length})
            </span>
            <button
              type="button"
              onClick={() => setIsExpanded(false)}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: '0.9rem',
              }}
            >
              &times;
            </button>
          </div>

          <p style={{ color: 'var(--text-muted)', fontSize: '0.68rem', margin: '0 0 0.5rem 0' }}>
            Country-level and maritime events rendered off-point to preserve spatial integrity.
          </p>

          <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.4rem', maxHeight: '240px' }}>
            {regionalFeatures.map((feat) => {
              const isSelected = selectedFeatureId === feat.id;
              const catColor = getCategoryColor(feat.properties.event_type);

              return (
                <div
                  key={feat.id}
                  onClick={() => onSelectFeature(isSelected ? null : feat.id)}
                  style={{
                    padding: '0.45rem',
                    borderRadius: '4px',
                    background: isSelected ? 'rgba(56, 189, 248, 0.15)' : 'rgba(30, 41, 59, 0.5)',
                    border: isSelected ? '1px solid #38bdf8' : '1px solid var(--border-subtle)',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.2rem' }}>
                    {feat.properties.title}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.66rem' }}>
                    <span style={{ color: catColor, textTransform: 'capitalize' }}>
                      ● {feat.properties.event_type}
                    </span>
                    <span>
                      {feat.properties.country_code ? `Region: ${feat.properties.country_code}` : 'Maritime / Regional'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
