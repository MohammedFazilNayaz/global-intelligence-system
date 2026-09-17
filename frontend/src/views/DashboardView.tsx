import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { DashboardSummary } from '../types/intelligence';
import { EventCard } from '../components/EventCard';

interface DashboardViewProps {
  onSelectCluster: (clusterId: string) => void;
  onNavigateToEvents: (eventTypeFilter?: string) => void;
  onSelectMarketAsset?: (assetId: string) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  onSelectCluster,
  onNavigateToEvents,
  onSelectMarketAsset,
}) => {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    api
      .getDashboardSummary()
      .then((data) => {
        if (isMounted) {
          setSummary(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load intelligence summary');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="state-loading">
        <div className="state-title">Loading Intelligence Overview...</div>
        <div className="state-desc">Aggregating telemetry from backend intelligence pipeline.</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="state-error">
        <div className="state-title" style={{ color: 'var(--accent-red)' }}>
          Operational Error
        </div>
        <div className="state-desc">{error}</div>
        <button
          className="btn btn-secondary"
          style={{ marginTop: '1rem' }}
          onClick={() => window.location.reload()}
        >
          Retry Connection
        </button>
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div>
      {/* Aggregate Metrics Grid */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-label">Active Clusters</div>
          <div className="metric-value">{summary.active_clusters_count}</div>
          <div className="metric-subtext">Grouped event occurrences</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Extracted Events</div>
          <div className="metric-value">{summary.total_events_count}</div>
          <div className="metric-subtext">Structured events parsed</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Ingested Documents</div>
          <div className="metric-value">{summary.total_documents_count}</div>
          <div className="metric-subtext">Normalized intelligence feeds</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Active Sources</div>
          <div className="metric-value">{summary.active_sources_count}</div>
          <div className="metric-subtext">Multi-source publishers</div>
        </div>

        <div className="metric-card" style={{ borderColor: 'rgba(239, 68, 68, 0.4)' }}>
          <div className="metric-label" style={{ color: 'var(--accent-rose)' }}>
            High Importance
          </div>
          <div className="metric-value" style={{ color: 'var(--accent-red)' }}>
            {summary.high_importance_events_count}
          </div>
          <div className="metric-subtext">Impact score &ge; 0.75</div>
        </div>
      </div>

      {/* Event Category Distribution */}
      {Object.keys(summary.event_types_breakdown).length > 0 && (
        <div className="section-box">
          <div className="section-title">
            <span>Intelligence Breakdown by Event Category</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Click category to filter feed
            </span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {Object.entries(summary.event_types_breakdown).map(([type, count]) => (
              <button
                key={type}
                className="btn btn-secondary btn-sm"
                onClick={() => onNavigateToEvents(type)}
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                <span style={{ textTransform: 'capitalize' }}>{type.replace(/_/g, ' ')}</span>:
                <strong style={{ color: 'var(--accent-cyan)', marginLeft: '0.3rem' }}>{count}</strong>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* V0.5 Economic Intelligence Overview */}
      {summary.economic_summary && (
        <div className="section-box" style={{ borderLeft: '3px solid var(--accent-cyan)' }}>
          <div className="section-title">
            <span>⚡ Economic Intelligence & Central Bank Monitor</span>
            <a
              href="#economic"
              className="btn btn-secondary btn-sm"
              style={{ color: 'var(--accent-cyan)' }}
            >
              Open Economic Desk &rarr;
            </a>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
            <div className="metric-card" style={{ padding: '0.75rem' }}>
              <div className="metric-label">Tracked Indicators</div>
              <div className="metric-value" style={{ fontSize: '1.5rem', color: 'var(--accent-cyan)' }}>
                {summary.economic_summary.total_indicators ?? (summary.economic_summary as any).total_indicators_count ?? 0}
              </div>
              <div className="metric-subtext">Controlled catalog</div>
            </div>
            <div className="metric-card" style={{ padding: '0.75rem' }}>
              <div className="metric-label">Economic Observations</div>
              <div className="metric-value" style={{ fontSize: '1.5rem', color: 'var(--accent-emerald)' }}>
                {summary.economic_summary.total_observations ?? (summary.economic_summary as any).total_observations_count ?? 0}
              </div>
              <div className="metric-subtext">Evidence-grounded prints</div>
            </div>
            <div className="metric-card" style={{ padding: '0.75rem' }}>
              <div className="metric-label">Policy Decisions</div>
              <div className="metric-value" style={{ fontSize: '1.5rem', color: 'var(--accent-amber)' }}>
                {(summary.economic_summary as any).central_bank_decisions_count ?? (summary.economic_summary.latest_central_bank_decisions || []).length}
              </div>
              <div className="metric-subtext">Central bank desk events</div>
            </div>
          </div>

          {/* Domain Breakdown Chips */}
          {Object.keys((summary.economic_summary.domain_breakdown || (summary.economic_summary as any).domains_breakdown || {})).length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '1rem' }}>
              {Object.entries((summary.economic_summary.domain_breakdown || (summary.economic_summary as any).domains_breakdown || {})).map(([dom, cnt]) => (
                <span key={dom} className="domain-tag" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}>
                  {dom}: <strong>{cnt}</strong>
                </span>
              ))}
            </div>
          )}

          {/* Central Bank Quick Monitor */}
          {(summary.economic_summary.latest_central_bank_decisions || []).length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Latest Policy Rate Decisions:
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '0.5rem' }}>
                {(summary.economic_summary.latest_central_bank_decisions || []).map((cb: any) => (
                  <div key={cb.id} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '3px', padding: '0.6rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.3rem' }}>
                      <span className="country-chip">{cb.country_code || cb.indicator?.country_entity?.country_code || 'CB'}</span>
                      <span className="econ-badge econ-badge-up" style={{ fontSize: '0.65rem' }}>
                        {cb.central_bank_decision?.decision_type?.toUpperCase() || cb.direction?.toUpperCase() || 'DECISION'}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.8rem', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {cb.indicator_canonical_name || cb.indicator?.canonical_name || 'Rate Decision'}
                    </div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', marginTop: '0.3rem', color: 'var(--text-secondary)' }}>
                      {cb.reported_value != null && <span>Rate: <strong style={{ color: 'var(--text-primary)' }}>{cb.reported_value}%</strong></span>}
                      {cb.central_bank_decision?.rate_change_bps != null && <span style={{ marginLeft: '0.5rem', color: 'var(--accent-amber)' }}>({cb.central_bank_decision.rate_change_bps} bps)</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent Major Releases */}
          {(summary.economic_summary.recent_major_releases || (summary.economic_summary as any).recent_key_releases || []).length > 0 && (
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Key Macroeconomic Releases:
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table className="econ-table" style={{ fontSize: '0.75rem' }}>
                  <thead>
                    <tr>
                      <th>Region</th>
                      <th>Indicator</th>
                      <th>Period</th>
                      <th>Reported</th>
                      <th>Previous</th>
                      <th>Direction</th>
                      <th>Relevance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(summary.economic_summary.recent_major_releases || (summary.economic_summary as any).recent_key_releases || []).slice(0, 5).map((rel: any) => (
                      <tr key={rel.id}>
                        <td><span className="country-chip">{rel.country_code || rel.indicator?.country_entity?.country_code || 'GL'}</span></td>
                        <td><strong>{rel.indicator_canonical_name || rel.indicator?.canonical_name || 'Indicator'}</strong></td>
                        <td>{rel.observation_period || '-'}</td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                          {rel.reported_value != null ? `${rel.reported_value} ${rel.reported_unit || ''}` : '-'}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                          {rel.previous_value != null ? `${rel.previous_value} ${rel.reported_unit || ''}` : '-'}
                        </td>
                        <td>
                          <span className="econ-badge econ-badge-up" style={{ fontSize: '0.65rem' }}>
                            {rel.direction || 'Release'}
                          </span>
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                          {rel.economic_relevance != null ? (rel.economic_relevance).toFixed(2) : '1.00'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* V0.6 Market Intelligence Overview */}
      {summary.market_summary && (
        <div className="section-box" style={{ borderLeft: '3px solid var(--accent-amber, #f59e0b)' }}>
          <div className="section-title">
            <span>📈 Market Intelligence & Temporal Movement Desk</span>
            <a
              href="#market"
              className="btn btn-secondary btn-sm"
              style={{ color: 'var(--accent-amber, #f59e0b)' }}
            >
              Open Market Desk &rarr;
            </a>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
            <div className="metric-card" style={{ padding: '0.75rem' }}>
              <div className="metric-label">Monitored Assets</div>
              <div className="metric-value" style={{ fontSize: '1.5rem', color: 'var(--accent-amber, #f59e0b)' }}>
                {summary.market_summary.total_assets}
              </div>
              <div className="metric-subtext">Crypto, Equities, FX, Rates, Commodities</div>
            </div>
            <div className="metric-card" style={{ padding: '0.75rem' }}>
              <div className="metric-label">Market Observations</div>
              <div className="metric-value" style={{ fontSize: '1.5rem', color: 'var(--accent-cyan)' }}>
                {summary.market_summary.total_observations}
              </div>
              <div className="metric-subtext">Clean deduplicated candles</div>
            </div>
            <div className="metric-card" style={{ padding: '0.75rem' }}>
              <div className="metric-label">Temporal Correlations</div>
              <div className="metric-value" style={{ fontSize: '1.5rem', color: 'var(--accent-emerald)' }}>
                {summary.market_summary.total_correlations}
              </div>
              <div className="metric-subtext">Event-window price observations</div>
            </div>
          </div>

          {/* Neutral Invariant Disclaimer */}
          <div
            style={{
              background: 'rgba(245, 158, 11, 0.08)',
              border: '1px solid rgba(245, 158, 11, 0.25)',
              borderRadius: '4px',
              padding: '0.5rem 0.8rem',
              fontSize: '0.75rem',
              color: 'var(--text-secondary)',
              marginBottom: '1rem',
            }}
          >
            <strong>Market Association Invariant:</strong> {summary.market_summary.disclaimer}
          </div>

          {/* Top Asset Movers */}
          {summary.market_summary.top_movers && summary.market_summary.top_movers.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Major Market Movers (24h Price Action):
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.5rem' }}>
                {summary.market_summary.top_movers.map((mover) => (
                  <div
                    key={mover.id}
                    onClick={() => {
                      if (onSelectMarketAsset) {
                        onSelectMarketAsset(mover.id);
                      } else {
                        window.location.hash = `market/${mover.id}`;
                      }
                    }}
                    style={{
                      background: 'var(--bg-surface)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: '4px',
                      padding: '0.6rem 0.8rem',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong style={{ color: 'var(--accent-cyan)' }}>{mover.symbol}</strong>
                      <span className="domain-tag" style={{ fontSize: '0.65rem' }}>{mover.asset_type}</span>
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                      {mover.canonical_name}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.4rem' }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        {mover.price != null ? mover.price.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '—'} {mover.quote_currency}
                      </span>
                      {mover.return_24h != null && (
                        <span
                          style={{
                            fontFamily: 'var(--font-mono)',
                            fontSize: '0.75rem',
                            fontWeight: 700,
                            color: mover.return_24h >= 0 ? 'var(--accent-emerald)' : 'var(--accent-red)',
                          }}
                        >
                          {mover.return_24h > 0 ? '+' : ''}{mover.return_24h.toFixed(2)}%
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent Event Correlations */}
          {summary.market_summary.recent_correlations && summary.market_summary.recent_correlations.length > 0 && (
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Observed Asset Performance Around Recent Events:
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table className="econ-table" style={{ fontSize: '0.75rem' }}>
                  <thead>
                    <tr>
                      <th>Event Title</th>
                      <th>Type</th>
                      <th>Asset</th>
                      <th>Window</th>
                      <th>Pre-Price</th>
                      <th>Post-Price</th>
                      <th>Return %</th>
                      <th>Vol Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.market_summary.recent_correlations.slice(0, 5).map((c) => (
                      <tr key={c.id}>
                        <td style={{ maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          <strong>{c.event_title || 'Global Event'}</strong>
                        </td>
                        <td>
                          <span className="badge badge-event-type" style={{ fontSize: '0.65rem' }}>
                            {c.event_type || 'event'}
                          </span>
                        </td>
                        <td>
                          <strong style={{ color: 'var(--accent-cyan)' }}>
                            {c.market_asset?.symbol || 'ASSET'}
                          </strong>
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>{c.window_size}</td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                          {c.pre_event_price != null ? c.pre_event_price.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '—'}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                          {c.post_event_price != null ? c.post_event_price.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '—'}
                        </td>
                        <td
                          style={{
                            fontFamily: 'var(--font-mono)',
                            fontWeight: 700,
                            color: c.return_percent != null && c.return_percent > 0
                              ? 'var(--accent-emerald)'
                              : c.return_percent != null && c.return_percent < 0
                              ? 'var(--accent-red)'
                              : 'var(--text-secondary)',
                          }}
                        >
                          {c.return_percent != null
                            ? `${c.return_percent > 0 ? '+' : ''}${c.return_percent.toFixed(2)}%`
                            : '—'}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                          {c.volume_change != null
                            ? `${c.volume_change > 0 ? '+' : ''}${c.volume_change.toFixed(1)}%`
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Recent Intelligence Clusters */}
      <div className="section-box">
        <div className="section-title">
          <span>Recent Intelligence Clusters</span>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => onNavigateToEvents()}
          >
            View All Feed &rarr;
          </button>
        </div>

        {summary.recent_clusters.length === 0 ? (
          <div className="state-empty">
            <div className="state-title">No Event Clusters Ingested Yet</div>
            <div className="state-desc">
              Run ingestion and event clustering to populate intelligence feeds.
            </div>
          </div>
        ) : (
          <div className="event-feed">
            {summary.recent_clusters.map((cluster) => (
              <EventCard
                key={cluster.id}
                cluster={cluster}
                onClick={() => onSelectCluster(cluster.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
