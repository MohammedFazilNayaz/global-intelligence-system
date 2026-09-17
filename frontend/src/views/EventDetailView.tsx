import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type {
  EventClusterDetail,
  EventMarketCorrelation,
  EventImpactAssessmentResponse,
  EventRelationshipsResponse,
  EventIntelligenceDossier,
} from '../types/intelligence';
import { ImportanceBadge, ConfidenceBadge, EventTypeBadge } from '../components/Badges';
import { ClusterExplanationBox } from '../components/ClusterExplanationBox';
import { EventDossierCard } from '../components/EventDossierCard';

interface EventDetailViewProps {
  clusterId: string;
  onBack: () => void;
  onSelectEntity?: (entityId: string) => void;
  onSelectMarketAsset?: (assetId: string) => void;
}

export const EventDetailView: React.FC<EventDetailViewProps> = ({
  clusterId,
  onBack,
  onSelectEntity,
  onSelectMarketAsset,
}) => {
  const [cluster, setCluster] = useState<EventClusterDetail | null>(null);
  const [correlations, setCorrelations] = useState<EventMarketCorrelation[]>([]);
  const [impact, setImpact] = useState<EventImpactAssessmentResponse | null>(null);
  const [eventRelationships, setEventRelationships] = useState<EventRelationshipsResponse | null>(null);
  const [dossier, setDossier] = useState<EventIntelligenceDossier | null>(null);
  const [selectedWindow, setSelectedWindow] = useState<string>('1h');
  const [loadingCorrelations, setLoadingCorrelations] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);
    setDossier(null);

    api
      .getClusterDetail(clusterId)
      .then((data) => {
        if (isMounted) {
          setCluster(data);
          setLoading(false);

          // Find representative or first extracted event ID
          const repEvent = data.members.find((m) => m.is_representative)?.extracted_event || data.members[0]?.extracted_event;
          if (repEvent?.id) {
            fetchCorrelations(repEvent.id, selectedWindow);
            if (typeof api.getEventDossier === 'function') {
              api.getEventDossier(repEvent.id).then((d) => isMounted && setDossier(d)).catch(() => {});
            }
            if (typeof api.getEventImpact === 'function') {
              api.getEventImpact(repEvent.id).then((imp) => isMounted && setImpact(imp)).catch(() => {});
            }
            if (typeof api.getEventRelationships === 'function') {
              api.getEventRelationships(repEvent.id).then((rel) => isMounted && setEventRelationships(rel)).catch(() => {});
            }
          }
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load event cluster detail');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [clusterId]);

  const fetchCorrelations = async (eventId: string, windowSize: string) => {
    setLoadingCorrelations(true);
    try {
      let res = await api.getEventMarketCorrelations(eventId, windowSize === 'all' ? undefined : windowSize);
      if (res.length === 0) {
        // Auto compute if not yet pre-computed
        res = await api.computeEventCorrelations(eventId, {
          window_sizes: ['5m', '15m', '1h', '4h', '1d'],
        });
        if (windowSize !== 'all') {
          res = res.filter((c) => c.window_size === windowSize);
        }
      }
      setCorrelations(res);
    } catch {
      // Graceful fallback for market context
      setCorrelations([]);
    } finally {
      setLoadingCorrelations(false);
    }
  };

  const handleWindowChange = (win: string) => {
    setSelectedWindow(win);
    const repEvent = cluster?.members.find((m) => m.is_representative)?.extracted_event || cluster?.members[0]?.extracted_event;
    if (repEvent?.id) {
      fetchCorrelations(repEvent.id, win);
    }
  };

  if (loading) {
    return (
      <div className="state-loading">
        <div className="state-title">Retrieving Cluster Intelligence & Evidence...</div>
        <div className="state-desc">Traversing Cluster &rarr; Extracted Event &rarr; Document &rarr; Source provenance graph.</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="state-error">
        <div className="state-title" style={{ color: 'var(--accent-red)' }}>
          Cluster Not Found or Inaccessible
        </div>
        <div className="state-desc">{error}</div>
        <button className="btn btn-secondary" style={{ marginTop: '1rem' }} onClick={onBack}>
          &larr; Back to Event Feed
        </button>
      </div>
    );
  }

  if (!cluster) return null;

  const formattedEventTime = cluster.event_time
    ? new Date(cluster.event_time).toUTCString().replace('GMT', 'UTC')
    : 'Time unavailable';

  const formattedLocation = cluster.location || 'Location unavailable';

  return (
    <div>
      {/* Back button & Action bar */}
      <div style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button className="btn btn-secondary btn-sm" onClick={onBack}>
          &larr; Back to Event Feed
        </button>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          CLUSTER ID: {cluster.id}
        </span>
      </div>

      {/* V0.9.5 Event Intelligence Dossier */}
      {dossier && (
        <div style={{ marginBottom: '1.5rem' }}>
          <EventDossierCard dossier={dossier} />
        </div>
      )}

      {/* Cluster Master Header */}
      <div className="detail-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', marginBottom: '0.75rem' }}>
          <h1 className="detail-title">{cluster.canonical_title}</h1>
          <div style={{ display: 'flex', gap: '0.5rem', flexShrink: 0 }}>
            <EventTypeBadge eventType={cluster.event_type} />
            <ImportanceBadge importance={cluster.importance} />
            <ConfidenceBadge confidence={cluster.confidence} />
          </div>
        </div>

        {cluster.canonical_summary && (
          <div className="detail-summary">
            <strong>Canonical Summary:</strong> {cluster.canonical_summary}
          </div>
        )}

        <div className="event-card-meta" style={{ marginTop: '0.5rem' }}>
          <span className="meta-item">
            <strong style={{ color: 'var(--text-muted)' }}>Event Time:</strong>
            <span className="meta-item-mono">{formattedEventTime}</span>
          </span>

          <span className="meta-item">
            <strong style={{ color: 'var(--text-muted)' }}>Location:</strong>
            <span>{formattedLocation}</span>
          </span>

          <span className="meta-item">
            <strong style={{ color: 'var(--text-muted)' }}>Status:</strong>
            <span style={{ textTransform: 'uppercase', color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)' }}>
              {cluster.status}
            </span>
          </span>

          <span className="meta-item">
            <strong style={{ color: 'var(--text-muted)' }}>Evidence Base:</strong>
            <span className="meta-item-mono">
              {cluster.member_count} reports from {cluster.unique_source_count} unique sources
            </span>
          </span>
        </div>

        {/* Entities involved */}
        {cluster.entities && cluster.entities.length > 0 && (
          <div style={{ marginTop: '1rem' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.4rem', fontWeight: 600 }}>
              Recognized Entities
            </div>
            <div className="event-entities-list">
              {cluster.entities.map((ent) => (
                <button
                  key={ent.entity_id}
                  className="entity-pill"
                  onClick={() => onSelectEntity?.(ent.entity_id)}
                  style={{ cursor: 'pointer', border: '1px solid var(--border-strong)' }}
                  title={`${ent.entity_type} - Mentioned ${ent.mention_count} times. Click to view profile.`}
                >
                  <strong>{ent.canonical_name}</strong>
                  <span style={{ color: 'var(--accent-cyan)', marginLeft: '0.35rem', fontSize: '0.68rem' }}>
                    ({ent.entity_type})
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Cluster Explanation Evidence Section */}
      <ClusterExplanationBox members={cluster.members} />

      {/* V0.6 Market Context Section */}
      <div className="section-box" style={{ borderLeft: '3px solid var(--accent-amber, #f59e0b)' }}>
        <div className="section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <span>📊 Market Context & Temporal Asset Alignment</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
              Observed price action around event window
            </span>
          </div>
          <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Window:</span>
            {['5m', '15m', '1h', '4h', '1d', 'all'].map((win) => (
              <button
                key={win}
                className={`btn btn-sm ${selectedWindow === win ? 'btn-primary' : 'btn-secondary'}`}
                style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
                onClick={() => handleWindowChange(win)}
              >
                {win}
              </button>
            ))}
          </div>
        </div>

        {/* Mandatory Neutral Disclaimer */}
        <div
          className="market-disclaimer-box"
          style={{
            background: 'rgba(245, 158, 11, 0.08)',
            border: '1px solid rgba(245, 158, 11, 0.25)',
            borderRadius: '4px',
            padding: '0.6rem 0.85rem',
            margin: '0.75rem 0',
            fontSize: '0.75rem',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <span style={{ color: 'var(--accent-amber)', fontWeight: 700 }}>⚠ DISCLAIMER:</span>
          <span>
            Market movement is temporally associated with the event and does not establish causation.
            The system reports historical observations and does not produce predictive metrics or trading signals.
          </span>
        </div>

        {loadingCorrelations ? (
          <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
            Aligning market observations across temporal event window...
          </div>
        ) : correlations.length === 0 ? (
          <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
            No relevant market assets or observations registered for this event window.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="evidence-table" style={{ fontSize: '0.75rem' }}>
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Type</th>
                  <th>Window</th>
                  <th>Pre-Event</th>
                  <th>Event Price</th>
                  <th>Post-Event</th>
                  <th>Return %</th>
                  <th>Vol Change</th>
                  <th>Volatility</th>
                  <th>Excursions (Max / Min)</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {correlations.map((c) => {
                  const asset = c.market_asset;
                  const ret = c.return_percent;
                  const isPositive = ret != null && ret > 0;
                  const isNegative = ret != null && ret < 0;
                  return (
                    <tr key={c.id}>
                      <td>
                        <button
                          onClick={() => onSelectMarketAsset?.(c.market_asset_id)}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: 'var(--accent-cyan)',
                            fontWeight: 700,
                            cursor: 'pointer',
                            textAlign: 'left',
                            padding: 0,
                          }}
                        >
                          {asset?.symbol || 'ASSET'}
                        </button>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                          {asset?.canonical_name}
                        </div>
                      </td>
                      <td>
                        <span className="domain-tag" style={{ fontSize: '0.65rem' }}>
                          {asset?.asset_type || 'asset'}
                        </span>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{c.window_size}</td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        {c.pre_event_price != null ? c.pre_event_price.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '—'}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        {c.event_price != null ? c.event_price.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '—'}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        {c.post_event_price != null ? c.post_event_price.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '—'}
                      </td>
                      <td
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontWeight: 700,
                          color: isPositive ? 'var(--accent-emerald)' : isNegative ? 'var(--accent-red)' : 'var(--text-secondary)',
                        }}
                      >
                        {ret != null ? `${isPositive ? '+' : ''}${ret.toFixed(2)}%` : '—'}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        {c.volume_change != null ? `${c.volume_change > 0 ? '+' : ''}${c.volume_change.toFixed(1)}%` : '—'}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                        {c.volatility != null ? c.volatility.toFixed(4) : '—'}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        {c.max_excursion != null || c.min_excursion != null
                          ? `${c.max_excursion != null ? `+${c.max_excursion.toFixed(2)}%` : '—'} / ${c.min_excursion != null ? `${c.min_excursion.toFixed(2)}%` : '—'}`
                          : '—'}
                      </td>
                      <td style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        <div>{c.methodology || 'observed_ohlcv'}</div>
                        <div style={{ fontFamily: 'var(--font-mono)' }}>
                          {new Date(c.calculated_at).toISOString().substring(11, 19)} UTC
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* V0.7 Impact Assessment & Cross-Domain Relationships */}
      <div className="section-box" style={{ marginBottom: '1.5rem', borderLeft: '4px solid #8b5cf6' }}>
        <div className="section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <span>Impact Assessment & Relational Intelligence</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
              (Observational Cross-Domain Foundation)
            </span>
          </div>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => {
              window.location.hash = 'graph';
            }}
            style={{ fontSize: '0.75rem' }}
          >
            Open Knowledge Graph &rarr;
          </button>
        </div>

        {/* Mandatory Non-Causal Retrospective Disclaimer */}
        <div
          style={{
            padding: '0.75rem 1rem',
            background: 'rgba(139, 92, 246, 0.1)',
            border: '1px solid rgba(139, 92, 246, 0.3)',
            borderRadius: '6px',
            fontSize: '0.8rem',
            color: '#c4b5fd',
            marginBottom: '1rem',
            lineHeight: 1.4,
          }}
        >
          <strong>NON-CAUSAL RETROSPECTIVE DISCLAIMER:</strong>{' '}
          {impact?.disclaimer ||
            'Impact assessments represent retrospective, observational associations within historical observation windows. They do not assert or imply causality, trade recommendations, or future price forecasts.'}
        </div>

        {/* Isolated Metric Quad */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '1rem',
            marginBottom: '1.25rem',
          }}
        >
          <div style={{ padding: '0.75rem 1rem', background: 'rgba(30, 41, 59, 0.5)', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase' }}>Event Importance</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f59e0b', marginTop: '0.25rem' }}>
              {impact?.event_importance != null ? (impact.event_importance * 100).toFixed(0) + '%' : `${((cluster.importance || 0.5) * 100).toFixed(0)}%`}
            </div>
            <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '2px' }}>Structural occurrence weight</div>
          </div>

          <div style={{ padding: '0.75rem 1rem', background: 'rgba(30, 41, 59, 0.5)', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase' }}>Economic Relevance</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#10b981', marginTop: '0.25rem' }}>
              {impact?.economic_relevance != null ? (impact.economic_relevance * 100).toFixed(0) + '%' : '0%'}
            </div>
            <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '2px' }}>Macro indicator alignment</div>
          </div>

          <div style={{ padding: '0.75rem 1rem', background: 'rgba(30, 41, 59, 0.5)', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase' }}>Market Association</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#38bdf8', marginTop: '0.25rem' }}>
              {impact?.market_association_score != null ? (impact.market_association_score * 100).toFixed(0) + '%' : correlations.length > 0 ? '70%' : '0%'}
            </div>
            <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '2px' }}>Asset temporal correlation</div>
          </div>

          <div style={{ padding: '0.75rem 1rem', background: 'rgba(30, 41, 59, 0.5)', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase' }}>Extraction Confidence</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#a78bfa', marginTop: '0.25rem' }}>
              {impact?.confidence != null ? (impact.confidence * 100).toFixed(0) + '%' : `${((cluster.confidence || 0.85) * 100).toFixed(0)}%`}
            </div>
            <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '2px' }}>Deterministic rule provenance</div>
          </div>
        </div>

        {/* Assessment Notes */}
        {impact?.assessment_notes && impact.assessment_notes.length > 0 && (
          <div style={{ marginBottom: '1.25rem' }}>
            <h4 style={{ fontSize: '0.8rem', color: '#94a3b8', textTransform: 'uppercase', margin: '0 0 0.5rem 0' }}>
              Observational Intelligence Notes
            </h4>
            <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.8rem', color: '#cbd5e1', lineHeight: 1.5 }}>
              {impact.assessment_notes.map((note, idx) => (
                <li key={idx}>{note}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Connected Cross-Domain Entities & Assets */}
        {eventRelationships?.relationships && eventRelationships.relationships.length > 0 && (
          <div>
            <h4 style={{ fontSize: '0.8rem', color: '#94a3b8', textTransform: 'uppercase', margin: '0 0 0.5rem 0' }}>
              Cross-Domain Relationship Graph Edges
            </h4>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              {eventRelationships.relationships.map((r, i) => (
                <div
                  key={i}
                  style={{
                    padding: '0.4rem 0.75rem',
                    borderRadius: '6px',
                    background: 'rgba(30, 41, 59, 0.7)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    fontSize: '0.8rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                  }}
                >
                  <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}>{r.relationship_type}:</span>
                  <span style={{ color: '#fff', fontWeight: 600 }}>{r.target_name}</span>
                  <span style={{ color: '#64748b', fontSize: '0.7rem' }}>[{r.target_type}]</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Provenance and Evidence Table */}
      <div className="section-box">
        <div className="section-title">
          <span>Source Evidence & Provenance Trace</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Cluster &rarr; Extracted Event &rarr; Document &rarr; Source
          </span>
        </div>

        <table className="evidence-table">
          <thead>
            <tr>
              <th style={{ width: '15%' }}>Source</th>
              <th style={{ width: '35%' }}>Document Evidence</th>
              <th style={{ width: '25%' }}>Extracted Event & Confidence</th>
              <th style={{ width: '15%' }}>Clustering Link</th>
              <th style={{ width: '10%' }}>Original</th>
            </tr>
          </thead>
          <tbody>
            {cluster.members.map((member) => {
              const doc = member.document;
              const evt = member.extracted_event;
              const pubTime = doc?.published_at
                ? new Date(doc.published_at).toUTCString().replace('GMT', 'UTC')
                : 'Date unavailable';

              return (
                <tr key={member.id}>
                  {/* Source */}
                  <td>
                    <strong style={{ color: 'var(--text-primary)' }}>
                      {doc?.source_name || 'Unknown Source'}
                    </strong>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      ID: {doc?.source_id ? doc.source_id.substring(0, 8) + '...' : 'N/A'}
                    </div>
                  </td>

                  {/* Document Title & Pub Time */}
                  <td>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.2rem' }}>
                      {doc?.title || 'Untitled Document'}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                      Published: <span className="meta-item-mono">{pubTime}</span>
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '0.2rem' }}>
                      Doc ID: {doc?.id}
                    </div>
                  </td>

                  {/* Extracted Event Metadata */}
                  <td>
                    <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.3rem' }}>
                      <span className="badge badge-event-type" style={{ fontSize: '0.65rem' }}>
                        {evt?.event_type || 'event'}
                      </span>
                      <ConfidenceBadge confidence={evt?.confidence_score} />
                      <ImportanceBadge importance={evt?.importance_score} />
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {evt?.title || evt?.description || 'Extracted occurrence'}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '0.2rem' }}>
                      Extractor: {evt?.extractor_version || 'rule_based_v0.2.1'}
                    </div>
                  </td>

                  {/* Membership Score & Method */}
                  <td>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                      {(member.membership_score * 100).toFixed(1)}% Match
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      {member.membership_method}
                    </div>
                    {member.is_representative && (
                      <span
                        className="badge"
                        style={{
                          background: 'rgba(56, 189, 248, 0.15)',
                          border: '1px solid var(--accent-cyan)',
                          color: 'var(--accent-cyan)',
                          marginTop: '0.25rem',
                        }}
                      >
                        CANONICAL SEED
                      </span>
                    )}
                  </td>

                  {/* Original Link */}
                  <td>
                    {doc?.url ? (
                      <a
                        href={doc.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-secondary btn-sm"
                        style={{ fontSize: '0.7rem' }}
                      >
                        Source Link &nearr;
                      </a>
                    ) : (
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>No URL</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
