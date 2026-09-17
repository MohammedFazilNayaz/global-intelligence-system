/**
 * Floating Legend HUD for V0.9-C.
 * Explains four-state visual representation and event category colors.
 */

import React, { useState } from 'react';

export const GlobeLegend: React.FC = () => {
  const [isOpen, setIsOpen] = useState<boolean>(false);

  return (
    <div
      style={{
        position: 'absolute',
        bottom: '1rem',
        left: '1rem',
        zIndex: 10,
        pointerEvents: 'auto',
      }}
    >
      {!isOpen ? (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
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
          }}
        >
          ℹ️ Map Legend
        </button>
      ) : (
        <div
          style={{
            background: 'rgba(11, 15, 25, 0.92)',
            backdropFilter: 'blur(10px)',
            border: '1px solid var(--border-strong)',
            borderRadius: 'var(--radius-sm)',
            padding: '0.75rem',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)',
            color: 'var(--text-primary)',
            fontSize: '0.72rem',
            maxWidth: '240px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <span style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
              Symbology & States
            </span>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: '0.85rem',
              }}
            >
              &times;
            </button>
          </div>

          {/* Location States */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginBottom: '0.6rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: '10px',
                  height: '10px',
                  borderRadius: '50%',
                  background: '#ef4444',
                  border: '1.5px solid #ffffff',
                }}
              />
              <span>
                <strong>RESOLVED:</strong> Exact Sensor
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: '12px',
                  height: '12px',
                  borderRadius: '50%',
                  border: '1.5px dashed #38bdf8',
                  background: 'rgba(56, 189, 248, 0.25)',
                }}
              />
              <span>
                <strong>APPROXIMATE:</strong> Municipal
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: '14px',
                  height: '6px',
                  border: '1px dashed #eab308',
                  background: 'rgba(234, 179, 8, 0.15)',
                }}
              />
              <span>
                <strong>REGIONAL:</strong> Non-Point / Contour
              </span>
            </div>
          </div>

          {/* Categories */}
          <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '0.5rem' }}>
            <div style={{ color: 'var(--text-muted)', marginBottom: '0.35rem', fontSize: '0.68rem', fontWeight: 600 }}>
              EVENT CATEGORIES
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.25rem', fontSize: '0.68rem' }}>
              <div><span style={{ color: '#ef4444' }}>●</span> Conflict</div>
              <div><span style={{ color: '#f97316' }}>●</span> Disaster</div>
              <div><span style={{ color: '#10b981' }}>●</span> Central Bank</div>
              <div><span style={{ color: '#06b6d4' }}>●</span> Economy</div>
              <div><span style={{ color: '#f59e0b' }}>●</span> Sanctions</div>
              <div><span style={{ color: '#8b5cf6' }}>●</span> Diplomacy</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
