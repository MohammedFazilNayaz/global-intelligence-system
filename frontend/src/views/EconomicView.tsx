import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';
import type { EconomicObservation, EconomicIndicator } from '../types/intelligence';

interface EconomicViewProps {
  onSelectEntity?: (entityId: string) => void;
  onSelectCluster?: (clusterId: string) => void;
}

const ECONOMIC_DOMAINS = [
  'All',
  'Monetary Policy',
  'Inflation',
  'Growth',
  'Employment',
  'Trade',
  'Commodities',
  'Fiscal Policy',
  'Industry',
  'Consumer',
  'Housing',
];

export const EconomicView: React.FC<EconomicViewProps> = ({ onSelectCluster }) => {
  const [selectedDomain, setSelectedDomain] = useState<string>('All');
  const [selectedCountry, setSelectedCountry] = useState<string>('');
  const [selectedDirection, setSelectedDirection] = useState<string>('');
  const [minRelevance, setMinRelevance] = useState<number>(0);
  const [observations, setObservations] = useState<EconomicObservation[]>([]);
  const [indicators, setIndicators] = useState<EconomicIndicator[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<number>(0);
  const pageSize = 20;

  // Provenance inspection modal
  const [activeProvenance, setActiveProvenance] = useState<EconomicObservation | null>(null);

  const fetchObservations = useCallback(() => {
    setLoading(true);
    setError(null);

    const domainParam = selectedDomain === 'All' ? undefined : selectedDomain;
    const countryParam = selectedCountry.trim() ? selectedCountry.trim().toUpperCase() : undefined;
    const dirParam = selectedDirection ? selectedDirection : undefined;

    Promise.all([
      api.getEconomicObservations({
        domain: domainParam,
        country_code: countryParam,
        direction: dirParam,
        min_relevance: minRelevance > 0 ? minRelevance : undefined,
        limit: pageSize,
        offset: page * pageSize,
      }),
      api.getEconomicIndicators({ limit: 10 }),
    ])
      .then(([obsRes, indRes]) => {
        setObservations(obsRes.items);
        setTotalCount(obsRes.total);
        setIndicators(indRes.items);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load economic observations');
        setLoading(false);
      });
  }, [selectedDomain, selectedCountry, selectedDirection, minRelevance, page]);

  useEffect(() => {
    fetchObservations();
  }, [fetchObservations]);

  // Central bank decisions highlights
  const cbDecisions = observations.filter((o) => o.central_bank_decision != null);

  const renderDirectionBadge = (dir?: string | null) => {
    if (!dir) return <span className="econ-badge econ-badge-neutral">-</span>;
    switch (dir.toLowerCase()) {
      case 'hike':
      case 'increase':
        return <span className="econ-badge econ-badge-up">▲ {dir.toUpperCase()}</span>;
      case 'cut':
      case 'decrease':
        return <span className="econ-badge econ-badge-down">▼ {dir.toUpperCase()}</span>;
      case 'hold':
      case 'unchanged':
        return <span className="econ-badge econ-badge-hold">■ {dir.toUpperCase()}</span>;
      default:
        return <span className="econ-badge econ-badge-neutral">{dir}</span>;
    }
  };

  return (
    <div className="economic-view-container">
      {/* Top Banner / Intelligence Header */}
      <div className="economic-header">
        <div>
          <h1 className="view-heading">Economic Intelligence Desk</h1>
          <p className="view-subheading">
            Evidence-backed macroeconomic telemetry, central bank decisions, and indicator releases.
            Strict zero-fabrication provenance trail.
          </p>
        </div>
        <div className="economic-live-badge">
          <span className="live-indicator-dot"></span>
          <span>V0.5 DETERMINISTIC TAXONOMY</span>
        </div>
      </div>

      {/* Cataloged Sovereign Indicators Quick Ribbon */}
      {indicators.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>Active Indicators:</span>
          {indicators.slice(0, 6).map((ind) => (
            <span key={ind.id} className="domain-tag" style={{ fontSize: '0.7rem' }}>
              {ind.canonical_name}
            </span>
          ))}
        </div>
      )}

      {/* Central Bank Policy Desk Strip */}
      {cbDecisions.length > 0 && (
        <div className="section-box cb-desk-section">
          <div className="section-title">
            <span>🏛️ Central Bank Policy Actions</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Deterministic rate action detection
            </span>
          </div>
          <div className="cb-cards-grid">
            {cbDecisions.map((cb) => (
              <div key={cb.id} className="cb-decision-card">
                <div className="cb-card-header">
                  <span className="cb-country-badge">{cb.country_code || 'CB'}</span>
                  <span className="cb-institution">{cb.indicator_canonical_name}</span>
                </div>
                <div className="cb-card-body">
                  <div className="cb-action-tag">
                    {renderDirectionBadge(cb.central_bank_decision?.decision_type || cb.direction)}
                  </div>
                  <div className="cb-rate-info">
                    {cb.reported_value != null && (
                      <span className="cb-target-rate">
                        Target: <strong>{cb.reported_value}%</strong>
                      </span>
                    )}
                    {cb.central_bank_decision?.rate_change_bps != null && (
                      <span className="cb-rate-delta">
                        {cb.central_bank_decision.rate_change_bps} bps
                      </span>
                    )}
                    {cb.previous_value != null && (
                      <span className="cb-prev-rate">Prev: {cb.previous_value}%</span>
                    )}
                  </div>
                </div>
                <div className="cb-card-footer">
                  <button
                    className="btn btn-secondary btn-xs"
                    onClick={() => setActiveProvenance(cb)}
                  >
                    Trace Evidence &rarr;
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Domain Navigation Tabs */}
      <div className="domain-tabs-bar">
        {ECONOMIC_DOMAINS.map((dom) => (
          <button
            key={dom}
            className={`domain-tab-btn ${selectedDomain === dom ? 'active' : ''}`}
            onClick={() => {
              setSelectedDomain(dom);
              setPage(0);
            }}
          >
            {dom}
          </button>
        ))}
      </div>

      {/* Filter and Query Bar */}
      <div className="section-box filter-controls-bar">
        <div className="filter-group">
          <label>Country Code:</label>
          <input
            type="text"
            className="filter-input-text"
            placeholder="e.g. US, EU, GB, JP, DE"
            value={selectedCountry}
            onChange={(e) => {
              setSelectedCountry(e.target.value);
              setPage(0);
            }}
            style={{ width: '120px' }}
          />
        </div>

        <div className="filter-group">
          <label>Direction:</label>
          <select
            className="filter-select"
            value={selectedDirection}
            onChange={(e) => {
              setSelectedDirection(e.target.value);
              setPage(0);
            }}
          >
            <option value="">All Directions</option>
            <option value="increase">Increase / Up</option>
            <option value="decrease">Decrease / Down</option>
            <option value="hike">Rate Hike</option>
            <option value="cut">Rate Cut</option>
            <option value="hold">Rate Hold</option>
            <option value="unchanged">Unchanged</option>
          </select>
        </div>

        <div className="filter-group">
          <label>Min Economic Relevance:</label>
          <select
            className="filter-select"
            value={minRelevance}
            onChange={(e) => {
              setMinRelevance(parseFloat(e.target.value));
              setPage(0);
            }}
          >
            <option value="0">All Scores (0.0+)</option>
            <option value="0.75">High Relevance (&ge; 0.75)</option>
            <option value="0.85">Very High (&ge; 0.85)</option>
            <option value="0.95">Tier 1 Key Indicators (&ge; 0.95)</option>
          </select>
        </div>

        <div style={{ marginLeft: 'auto', alignSelf: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
          Showing {observations.length} of {totalCount} observations
        </div>
      </div>

      {/* Main Macro Observation Feed Table */}
      <div className="section-box" style={{ padding: '0', overflow: 'hidden' }}>
        {loading ? (
          <div className="state-loading">
            <div className="state-title">Loading Macro Telemetry...</div>
            <div className="state-desc">Querying verified economic observations.</div>
          </div>
        ) : error ? (
          <div className="state-error">
            <div className="state-title" style={{ color: 'var(--accent-red)' }}>
              Operational Error
            </div>
            <div className="state-desc">{error}</div>
          </div>
        ) : observations.length === 0 ? (
          <div className="state-empty">
            <div className="state-title">No Economic Observations Found</div>
            <div className="state-desc">
              Try adjusting domain, country filter, or relevance threshold.
            </div>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="econ-table">
              <thead>
                <tr>
                  <th>Jurisdiction</th>
                  <th>Indicator / Canonical Name</th>
                  <th>Domain</th>
                  <th>Period</th>
                  <th>Reported Value</th>
                  <th>Previous</th>
                  <th>Change / Direction</th>
                  <th>Consensus Expected</th>
                  <th>Economic Relevance</th>
                  <th>Audit / Provenance</th>
                </tr>
              </thead>
              <tbody>
                {observations.map((obs) => (
                  <tr key={obs.id}>
                    <td>
                      <span className="country-chip">
                        {obs.country_code || 'GL'}
                      </span>
                    </td>
                    <td>
                      <div className="indicator-name-cell">
                        <strong>{obs.indicator_canonical_name || obs.indicator_type}</strong>
                        <span className="indicator-type-subtext">{obs.indicator_type}</span>
                      </div>
                    </td>
                    <td>
                      <span className="domain-tag">{obs.economic_domain || 'General'}</span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                      {obs.observation_period || '-'}
                    </td>
                    <td className="value-cell-primary">
                      {obs.reported_value != null ? (
                        <span>
                          {obs.reported_value} <span className="unit-label">{obs.reported_unit || ''}</span>
                        </span>
                      ) : (
                        <span className="text-muted">null</span>
                      )}
                    </td>
                    <td className="value-cell-secondary">
                      {obs.previous_value != null ? (
                        <span>
                          {obs.previous_value} <span className="unit-label">{obs.reported_unit || ''}</span>
                        </span>
                      ) : (
                        <span className="text-muted">-</span>
                      )}
                    </td>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                        {renderDirectionBadge(obs.direction)}
                        {obs.change_value != null && (
                          <span
                            className="change-delta-label"
                            style={{
                              color:
                                obs.change_value > 0
                                  ? 'var(--accent-emerald)'
                                  : obs.change_value < 0
                                  ? 'var(--accent-rose)'
                                  : 'var(--text-muted)',
                            }}
                          >
                            {obs.change_value > 0 ? `+${obs.change_value}` : obs.change_value}
                            {obs.change_percent != null && ` (${obs.change_percent}%)`}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="value-cell-expected">
                      {obs.expected_value != null ? (
                        <span className="consensus-badge">
                          {obs.expected_value} {obs.reported_unit || ''}
                        </span>
                      ) : (
                        <span className="text-muted">Unstated</span>
                      )}
                    </td>
                    <td>
                      <div className="relevance-bar-container">
                        <div
                          className="relevance-bar-fill"
                          style={{
                            width: `${Math.round(obs.economic_relevance * 100)}%`,
                            backgroundColor:
                              obs.economic_relevance >= 0.9
                                ? 'var(--accent-cyan)'
                                : obs.economic_relevance >= 0.75
                                ? 'var(--accent-blue)'
                                : 'var(--accent-amber)',
                          }}
                        ></div>
                        <span className="relevance-score-text">
                          {(obs.economic_relevance).toFixed(2)}
                        </span>
                      </div>
                    </td>
                    <td>
                      <button
                        className="btn btn-secondary btn-xs"
                        onClick={() => setActiveProvenance(obs)}
                        title="View Full Provenance Chain"
                      >
                        Inspect Trace
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination controls */}
        <div className="pagination-bar">
          <button
            className="btn btn-secondary btn-xs"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            &larr; Previous Page
          </button>
          <span className="page-indicator">
            Page {page + 1} of {Math.max(1, Math.ceil(totalCount / pageSize))}
          </span>
          <button
            className="btn btn-secondary btn-xs"
            disabled={(page + 1) * pageSize >= totalCount}
            onClick={() => setPage((p) => p + 1)}
          >
            Next Page &rarr;
          </button>
        </div>
      </div>

      {/* Provenance Audit Modal */}
      {activeProvenance && (
        <div className="modal-overlay" onClick={() => setActiveProvenance(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>5-Tier Provenance Trace & Audit Chain</h3>
              <button className="btn-close" onClick={() => setActiveProvenance(null)}>
                &times;
              </button>
            </div>
            <div className="modal-body">
              <div className="provenance-step">
                <div className="step-num">1</div>
                <div className="step-body">
                  <h4>Economic Observation</h4>
                  <div className="step-kv-grid">
                    <div><strong>Observation ID:</strong> <code>{activeProvenance.id}</code></div>
                    <div><strong>Domain:</strong> {activeProvenance.economic_domain}</div>
                    <div><strong>Reported:</strong> {activeProvenance.reported_value} {activeProvenance.reported_unit}</div>
                    <div><strong>Previous:</strong> {activeProvenance.previous_value ?? 'Unstated'}</div>
                    <div><strong>Expected / Consensus:</strong> {activeProvenance.expected_value ?? 'Unstated (Zero Fabrication)'}</div>
                    <div><strong>Revised:</strong> {activeProvenance.revised_value ?? 'None'}</div>
                    <div><strong>Calculation Method:</strong> <code>{activeProvenance.calculation_method || 'explicitly_reported'}</code></div>
                  </div>
                </div>
              </div>

              <div className="provenance-step">
                <div className="step-num">2</div>
                <div className="step-body">
                  <h4>Economic Indicator</h4>
                  <div className="step-kv-grid">
                    <div><strong>Indicator ID:</strong> <code>{activeProvenance.indicator_id}</code></div>
                    <div><strong>Canonical Name:</strong> {activeProvenance.indicator_canonical_name}</div>
                    <div><strong>Type:</strong> <code>{activeProvenance.indicator_type}</code></div>
                    <div><strong>Jurisdiction:</strong> {activeProvenance.country_name} ({activeProvenance.country_code})</div>
                  </div>
                </div>
              </div>

              <div className="provenance-step">
                <div className="step-num">3</div>
                <div className="step-body">
                  <h4>Extracted Event</h4>
                  <div className="step-kv-grid">
                    <div><strong>Event ID:</strong> <code>{activeProvenance.event_id || 'Direct Ingestion'}</code></div>
                    {activeProvenance.event_id && onSelectCluster && (
                      <button
                        className="btn btn-secondary btn-xs"
                        style={{ marginTop: '0.4rem' }}
                        onClick={() => {
                          const eid = activeProvenance.event_id;
                          setActiveProvenance(null);
                          if (eid) onSelectCluster(eid);
                        }}
                      >
                        Inspect Related Event Cluster &rarr;
                      </button>
                    )}
                  </div>
                </div>
              </div>

              <div className="provenance-step">
                <div className="step-num">4</div>
                <div className="step-body">
                  <h4>Source Document & Raw Evidence</h4>
                  <div className="step-kv-grid">
                    <div><strong>Document ID:</strong> <code>{activeProvenance.document_id || 'Direct'}</code></div>
                    <div><strong>Source Publisher:</strong> {activeProvenance.source_name || 'Verified Source'}</div>
                  </div>
                  {activeProvenance.evidence_snippet && (
                    <div className="evidence-snippet-box">
                      <div className="evidence-snippet-title">Exact Verbatim Text Snippet:</div>
                      <blockquote>&ldquo;{activeProvenance.evidence_snippet}&rdquo;</blockquote>
                    </div>
                  )}
                </div>
              </div>

              <div className="provenance-step">
                <div className="step-num">5</div>
                <div className="step-body">
                  <h4>Explainable Economic Relevance</h4>
                  <div className="step-kv-grid">
                    <div><strong>Score:</strong> <code>{activeProvenance.economic_relevance.toFixed(2)}</code> / 1.0</div>
                  </div>
                  {activeProvenance.metadata_ && (
                    <pre className="relevance-explain-json">
                      {JSON.stringify(activeProvenance.metadata_, null, 2)}
                    </pre>
                  )}
                </div>
              </div>

              <div className="evidence-guarantee-note">
                <strong>Data Quality Invariant:</strong> Every observation is deterministic and grounded in source text. No synthetic market predictions or trading signals are permitted in V0.5.
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setActiveProvenance(null)}>
                Close Trace
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
