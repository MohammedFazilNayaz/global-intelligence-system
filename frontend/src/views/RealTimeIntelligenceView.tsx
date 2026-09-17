import React, { useEffect, useState, useRef } from 'react';
import { api } from '../api/client';
import type { LiveFeedItem, PaginatedLiveFeedResponse } from '../types/intelligence';

const getFreshnessBadgeClass = (status: string) => {
  switch (status) {
    case 'CURRENT':
      return 'badge-emerald';
    case 'RECENT':
      return 'badge-cyan';
    case 'STALE':
      return 'badge-amber';
    case 'HISTORICAL':
      return 'badge-purple';
    case 'SYNTHETIC_TEST':
      return 'badge-danger';
    default:
      return 'badge-secondary';
  }
};

export const RealTimeIntelligenceView: React.FC = () => {
  const [items, setItems] = useState<LiveFeedItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const pageSize = 15;
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [minImportance, setMinImportance] = useState<number>(0.0);
  const [eventType, setEventType] = useState<string>('');
  const [autoRefreshInterval, setAutoRefreshInterval] = useState<number>(15); // seconds, 0 = off
  const [freshnessSummary, setFreshnessSummary] = useState<Record<string, number>>({});
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string>('');

  const timerRef = useRef<any>(null);

  const fetchLiveFeed = (targetPage: number = page) => {
    setLoading(true);
    setError(null);
    const offset = (targetPage - 1) * pageSize;

    api.getLiveFeed({
      min_importance: minImportance > 0 ? minImportance : undefined,
      event_type: eventType.trim() ? eventType.trim() : undefined,
      limit: pageSize,
      offset,
    })
      .then((res: PaginatedLiveFeedResponse) => {
        setItems(res.items || []);
        setTotal(res.total || 0);
        setFreshnessSummary(res.freshness_summary || {});
        setLastRefreshedAt(new Date().toUTCString().replace('GMT', 'UTC'));
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load real-time intelligence feed');
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchLiveFeed(1);
    setPage(1);
  }, [minImportance, eventType]);

  useEffect(() => {
    if (autoRefreshInterval > 0) {
      timerRef.current = setInterval(() => {
        fetchLiveFeed(page);
      }, autoRefreshInterval * 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [autoRefreshInterval, page, minImportance, eventType]);

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="view-container">
      {/* Header & Observability Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', background: freshnessSummary.CURRENT ? 'var(--accent-emerald)' : 'var(--accent-amber)', boxShadow: freshnessSummary.CURRENT ? '0 0 10px var(--accent-emerald)' : '0 0 10px var(--accent-amber)' }}></span>
            <h1 style={{ fontSize: '1.4rem', fontWeight: 700, margin: 0 }}>Real-Time Intelligence Feed</h1>
            <span className={`badge ${freshnessSummary.CURRENT ? 'badge-emerald' : 'badge-secondary'}`} style={{ fontSize: '0.75rem' }}>
              {freshnessSummary.CURRENT ? 'OPERATIONAL STREAM' : 'STREAM IDLE'}
            </span>
          </div>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Multi-source evidence stream with deterministic entity & event extraction, clustering, and impact evaluation.
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
            Browser Refresh: {autoRefreshInterval > 0 ? `${autoRefreshInterval}s (Client HTTP Poll)` : 'Manual'} | Source Ingestion Cadence: 300s (Autonomous Backend Scheduler)
          </div>
        </div>

        {/* Telemetry Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <div className="badge badge-emerald" style={{ padding: '0.4rem 0.75rem' }}>
            CURRENT: {freshnessSummary.CURRENT ?? 0}
          </div>
          <div className="badge badge-amber" style={{ padding: '0.4rem 0.75rem' }}>
            STALE: {freshnessSummary.STALE ?? 0}
          </div>
          <div className="badge badge-primary" style={{ padding: '0.4rem 0.75rem' }}>
            TOTAL STREAM: {total}
          </div>
        </div>
      </div>

      {/* Non-Causal Regulatory Disclaimer Banner */}
      <div style={{
        background: 'rgba(56, 189, 248, 0.08)',
        border: '1px solid rgba(56, 189, 248, 0.25)',
        borderRadius: '6px',
        padding: '0.65rem 1rem',
        fontSize: '0.8rem',
        color: 'var(--text-secondary)',
        marginBottom: '1.25rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div>
          <strong>Non-Causal Architecture:</strong> Retrospective event-market excursions and economic contexts describe observed co-occurrences. Correlation does not imply causation. The platform strictly prohibits causal inference, autonomous execution, and forward-looking price predictions.
        </div>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', opacity: 0.8 }}>
          Refreshed: {lastRefreshedAt || 'Just now'}
        </span>
      </div>

      {/* Filter & Controls Toolbar */}
      <div className="section-box" style={{ marginBottom: '1.25rem', padding: '0.85rem 1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
            {/* Importance Slider */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <label htmlFor="min-importance-input" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Min Importance:</label>
              <input
                id="min-importance-input"
                type="range"
                min="0.0"
                max="0.9"
                step="0.05"
                value={minImportance}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  setMinImportance(val);
                  fetchLiveFeed(1);
                }}
                style={{ width: '100px' }}
              />
              <span style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)', width: '32px' }}>
                {minImportance.toFixed(2)}
              </span>
            </div>

            {/* Event Type Filter */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Domain:</label>
              <select
                className="input-select"
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
              >
                <option value="">All Domains</option>
                <option value="central_bank_decision">Central Bank Decision</option>
                <option value="economic_release">Economic Release</option>
                <option value="geopolitical_conflict">Geopolitical Conflict</option>
                <option value="sanction_imposition">Sanctions</option>
                <option value="market_event">Market Event</option>
                <option value="policy_decision">Policy Decision</option>
              </select>
            </div>
          </div>

          {/* Auto Refresh Toggle & Button */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              <span>Auto-poll:</span>
              <select
                className="input-select"
                value={autoRefreshInterval}
                onChange={(e) => setAutoRefreshInterval(parseInt(e.target.value, 10))}
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
              >
                <option value={0}>Off</option>
                <option value={10}>10s</option>
                <option value={15}>15s</option>
                <option value={30}>30s</option>
                <option value={60}>60s</option>
              </select>
            </div>

            <button
              className="btn btn-secondary btn-sm"
              onClick={() => fetchLiveFeed(page)}
              disabled={loading}
            >
              {loading ? 'Fetching...' : 'Poll Now'}
            </button>
          </div>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="state-error" style={{ marginBottom: '1rem' }}>
          <div className="state-title">Live Stream Error</div>
          <div className="state-desc">{error}</div>
        </div>
      )}

      {/* Feed Stream */}
      {loading && items.length === 0 ? (
        <div className="state-loading">
          <div className="state-title">Aggregating Live Global Intelligence...</div>
          <div className="state-desc">Synchronizing verified multi-source event feed and associated market context.</div>
        </div>
      ) : items.length === 0 ? (
        <div className="state-empty">
          <div className="state-title">No Intelligence Events Match Filters</div>
          <div className="state-desc">Adjust the minimum importance or domain filters to view earlier events.</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
          {items.map((item) => (
            <div
              key={item.event_id}
              className="card"
              style={{
                background: 'rgba(15, 23, 42, 0.65)',
                border: item.active_alerts.length > 0 ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid var(--border-color)',
                borderRadius: '8px',
                padding: '1rem 1.25rem',
                boxShadow: item.active_alerts.length > 0 ? '0 0 12px rgba(239, 68, 68, 0.1)' : 'none',
              }}
            >
              {/* Alert Badge Header if Alert Active */}
              {item.active_alerts.length > 0 && (
                <div style={{
                  background: 'rgba(239, 68, 68, 0.12)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  color: 'var(--accent-red)',
                  padding: '0.35rem 0.65rem',
                  borderRadius: '4px',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  marginBottom: '0.6rem',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}>
                  <span>ALERT: {item.active_alerts[0].alert_title}</span>
                  <span style={{ fontSize: '0.7rem', opacity: 0.9 }}>Trigger: {item.active_alerts[0].trigger_type}</span>
                </div>
              )}

              {/* Event Metadata Bar */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.4rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <span className={`badge ${getFreshnessBadgeClass(item.freshness_status)}`} style={{ fontSize: '0.7rem' }}>
                    {item.freshness_status}
                  </span>
                  <span className="badge badge-secondary" style={{ fontSize: '0.7rem' }}>
                    {item.event_type.replace(/_/g, ' ')}
                  </span>
                  {item.primary_location ? (
                    <span className="badge badge-outline" style={{ fontSize: '0.7rem' }}>
                      📍 {item.primary_location} {item.country_code ? `(${item.country_code})` : ''}
                    </span>
                  ) : (
                    <span className="badge badge-secondary" style={{ fontSize: '0.7rem', opacity: 0.65 }} title="Location could not be verified from source evidence">
                      📍 Location Unresolved
                    </span>
                  )}
                  {item.cluster_title && (
                    <a
                      href={`#cluster-${item.cluster_id}`}
                      className="badge badge-primary"
                      style={{ fontSize: '0.7rem', textDecoration: 'none' }}
                      title="View full cluster context"
                    >
                      Cluster: {item.cluster_title.length > 35 ? `${item.cluster_title.slice(0, 35)}...` : item.cluster_title}
                    </a>
                  )}
                </div>

                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                  {item.event_time ? new Date(item.event_time).toISOString().replace('T', ' ').slice(0, 19) + ' UTC' : 'Recent'}
                  {item.age_seconds !== undefined && item.age_seconds !== null && (
                    <span style={{ marginLeft: '0.4rem', opacity: 0.8 }}>
                      ({item.age_seconds < 60 ? `${Math.round(item.age_seconds)}s ago` : `${Math.round(item.age_seconds / 60)}m ago`})
                    </span>
                  )}
                </div>
              </div>

              {/* Event Title */}
              <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 0.35rem 0' }}>
                <a href={`#event-${item.event_id}`} style={{ color: 'inherit', textDecoration: 'none' }}>
                  {item.event_title}
                </a>
              </h3>

              {/* Event Summary */}
              {item.event_summary && (
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: '0 0 0.6rem 0', lineHeight: 1.45 }}>
                  {item.event_summary}
                </p>
              )}

              {/* Multi-Domain Context Grid (Entities, Economic Observations, Market Context) */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginTop: '0.5rem', fontSize: '0.78rem' }}>
                {/* Entities */}
                {item.entities.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' }}>
                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.72rem' }}>Entities:</span>
                    {item.entities.slice(0, 6).map((ent) => (
                      <a
                        key={ent.id}
                        href={`#entity-${ent.id}`}
                        className="badge badge-outline"
                        style={{ fontSize: '0.7rem', textDecoration: 'none' }}
                      >
                        {ent.canonical_name} ({ent.entity_type})
                      </a>
                    ))}
                  </div>
                )}

                {/* Economic Observations */}
                {item.economic_context.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' }}>
                    <span style={{ color: 'var(--accent-cyan)', fontSize: '0.72rem' }}>Economic Context:</span>
                    {item.economic_context.map((econ, idx) => (
                      <span key={idx} className="badge badge-secondary" style={{ fontSize: '0.7rem' }}>
                        {econ.indicator_name}: {econ.reported_value !== null ? `${econ.reported_value}${econ.reported_unit || ''}` : 'observed'}
                        {econ.direction ? ` (${econ.direction})` : ''}
                      </span>
                    ))}
                  </div>
                )}

                {/* Market Correlations (Neutral Observational) */}
                {item.market_context.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' }}>
                    <span style={{ color: 'var(--accent-purple)', fontSize: '0.72rem' }}>Market Excursion (1h):</span>
                    {item.market_context.map((mkt, idx) => (
                      <span
                        key={idx}
                        className="badge badge-purple"
                        style={{ fontSize: '0.7rem' }}
                        title={mkt.neutral_observation}
                      >
                        {mkt.symbol}: {mkt.return_percent !== null && mkt.return_percent !== undefined ? (mkt.return_percent >= 0 ? `+${mkt.return_percent.toFixed(2)}%` : `${mkt.return_percent.toFixed(2)}%`) : 'N/A'}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Provenance & Metrics Footer */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.75rem', paddingTop: '0.5rem', borderTop: '1px solid rgba(255, 255, 255, 0.05)', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                  <span>Importance: <strong>{(item.importance ?? 0).toFixed(2)}</strong></span>
                  <span>Confidence: <strong>{(item.confidence ?? 0).toFixed(2)}</strong></span>
                  {item.source_name && (
                    <span>Source: <strong style={{ color: 'var(--text-primary)' }}>{item.source_name}</strong></span>
                  )}
                  {item.published_at && (
                    <span title="Source Publication Timestamp">Pub: <strong>{new Date(item.published_at).toISOString().replace('T', ' ').slice(0, 19)} UTC</strong></span>
                  )}
                  {item.ingested_at && (
                    <span title="System Ingestion Timestamp">Ingested: <strong>{new Date(item.ingested_at).toISOString().replace('T', ' ').slice(0, 19)} UTC</strong></span>
                  )}
                  {item.processed_at && (
                    <span title="Pipeline Processing Completion Timestamp">Processed: <strong>{new Date(item.processed_at).toISOString().replace('T', ' ').slice(0, 19)} UTC</strong></span>
                  )}
                  {item.pipeline_duration_seconds !== null && item.pipeline_duration_seconds !== undefined && (
                    <span title="Extraction & Clustering Duration">Pipeline: <strong style={{ color: 'var(--accent-emerald)' }}>{item.pipeline_duration_seconds}s</strong></span>
                  )}
                  {item.e2e_latency_seconds !== null && item.e2e_latency_seconds !== undefined && (
                    <span title="Total End-to-End Latency from Publication to Usable Intelligence">E2E: <strong style={{ color: 'var(--accent-cyan)' }}>{item.e2e_latency_seconds}s</strong></span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  {item.provenance_url && (
                    <a
                      href={item.provenance_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: 'var(--accent-cyan)', textDecoration: 'none' }}
                    >
                      Source Article ↗
                    </a>
                  )}
                  <a
                    href={`#event-${item.event_id}`}
                    style={{ color: 'var(--accent-primary)', textDecoration: 'none', fontWeight: 600 }}
                  >
                    View Impact & Context →
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.25rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-color)' }}>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          Page {page} of {totalPages} ({total} events)
        </span>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            className="btn btn-secondary btn-sm"
            disabled={page <= 1 || loading}
            onClick={() => {
              const newPage = Math.max(1, page - 1);
              setPage(newPage);
              fetchLiveFeed(newPage);
            }}
          >
            ← Previous
          </button>
          <button
            className="btn btn-secondary btn-sm"
            disabled={page >= totalPages || loading}
            onClick={() => {
              const newPage = page + 1;
              setPage(newPage);
              fetchLiveFeed(newPage);
            }}
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
};
