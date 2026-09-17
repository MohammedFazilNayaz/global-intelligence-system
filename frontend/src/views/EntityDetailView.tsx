import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Entity, EntityRelatedEventItem, CountryEconomicProfile } from '../types/intelligence';
import { ImportanceBadge, ConfidenceBadge, EventTypeBadge } from '../components/Badges';

interface EntityDetailViewProps {
  entityId: string;
  onBack: () => void;
  onSelectCluster?: (clusterId: string) => void;
}

export const EntityDetailView: React.FC<EntityDetailViewProps> = ({
  entityId,
  onBack,
  onSelectCluster,
}) => {
  const [entity, setEntity] = useState<Entity | null>(null);
  const [events, setEvents] = useState<EntityRelatedEventItem[]>([]);
  const [econProfile, setEconProfile] = useState<CountryEconomicProfile | null>(null);
  const [relationships, setRelationships] = useState<{
    outbound: import('../types/intelligence').EntityRelationshipWithEntities[];
    inbound: import('../types/intelligence').EntityRelationshipWithEntities[];
    total: number;
  } | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    const promises: Promise<unknown>[] = [
      api.getEntityDetail(entityId),
      api.getEntityEvents(entityId),
      typeof api.getCountryEconomicProfile === 'function' ? api.getCountryEconomicProfile(entityId) : Promise.resolve(null),
      typeof api.getEntityRelationships === 'function' ? api.getEntityRelationships(entityId) : Promise.resolve({ outbound: [], inbound: [], total: 0 }),
    ];

    Promise.allSettled(promises)
      .then(([entityRes, eventsRes, econRes, relsRes]) => {
        if (!isMounted) return;

        if (entityRes.status === 'fulfilled') {
          setEntity(entityRes.value as Entity);
        } else {
          throw new Error('Failed to load entity');
        }

        if (eventsRes.status === 'fulfilled') {
          setEvents(eventsRes.value as EntityRelatedEventItem[]);
        }

        if (econRes.status === 'fulfilled' && econRes.value) {
          setEconProfile(econRes.value as CountryEconomicProfile);
        }

        if (relsRes.status === 'fulfilled' && relsRes.value) {
          setRelationships(relsRes.value as { outbound: import('../types/intelligence').EntityRelationshipWithEntities[]; inbound: import('../types/intelligence').EntityRelationshipWithEntities[]; total: number });
        }

        setLoading(false);
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load entity details');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [entityId]);

  if (loading) {
    return (
      <div className="state-loading">
        <div className="state-title">Loading Entity Dossier...</div>
        <div className="state-desc">Retrieving entity metadata and tracing linked events.</div>
      </div>
    );
  }

  if (error || !entity) {
    return (
      <div className="state-error">
        <div className="state-title" style={{ color: 'var(--accent-red)' }}>
          Entity Not Found
        </div>
        <div className="state-desc">{error}</div>
        <button className="btn btn-secondary" style={{ marginTop: '1rem' }} onClick={onBack}>
          &larr; Back to Entities
        </button>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button className="btn btn-secondary btn-sm" onClick={onBack}>
          &larr; Back to Entities
        </button>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          ENTITY ID: {entity.id}
        </span>
      </div>

      {/* Entity Profile Header */}
      <div className="detail-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
          <div>
            <h1 className="detail-title">{entity.canonical_name}</h1>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              Normalized: {entity.normalized_name}
            </div>
          </div>
          <span className="badge badge-event-type" style={{ fontSize: '0.8rem', padding: '0.25rem 0.6rem' }}>
            {entity.entity_type}
          </span>
        </div>

        {entity.description && (
          <div className="detail-summary" style={{ marginTop: '1rem' }}>
            {entity.description}
          </div>
        )}

        <div className="event-card-meta" style={{ marginTop: '0.75rem' }}>
          {entity.country_code && (
            <span className="meta-item">
              <strong style={{ color: 'var(--text-muted)' }}>Country Code:</strong>
              <span className="meta-item-mono" style={{ color: 'var(--accent-cyan)' }}>
                {entity.country_code}
              </span>
            </span>
          )}

          <span className="meta-item">
            <strong style={{ color: 'var(--text-muted)' }}>Linked Events:</strong>
            <span className="meta-item-mono" style={{ color: '#fff' }}>
              {events.length}
            </span>
          </span>

          {econProfile && (
            <span className="meta-item">
              <strong style={{ color: 'var(--text-muted)' }}>Economic Indicators:</strong>
              <span className="meta-item-mono" style={{ color: 'var(--accent-emerald)' }}>
                {econProfile.total_indicators}
              </span>
            </span>
          )}
        </div>
      </div>

      {/* V0.5 Country Economic Profile Section */}
      {econProfile && (econProfile.total_indicators > 0 || econProfile.recent_observations.length > 0) && (
        <div className="section-box" style={{ borderLeft: '3px solid var(--accent-cyan)' }}>
          <div className="section-title">
            <span>📊 {econProfile.country_name} Macroeconomic Intelligence Profile</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Evidence-backed economic telemetry (Not a predictive model)
            </span>
          </div>

          {/* Key Indicators tracked for this country */}
          {econProfile.indicators.length > 0 && (
            <div style={{ marginBottom: '1.25rem' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Cataloged Sovereign Indicators:
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                {econProfile.indicators.map((ind) => (
                  <span
                    key={ind.id}
                    className="domain-tag"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-strong)', color: 'var(--text-primary)' }}
                  >
                    <strong>{ind.canonical_name}</strong> ({ind.indicator_type})
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Central Bank Events for this jurisdiction */}
          {econProfile.central_bank_events.length > 0 && (
            <div style={{ marginBottom: '1.25rem' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--accent-amber)', marginBottom: '0.5rem' }}>
                🏛️ Monetary Policy & Policy Rate Decisions:
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '0.5rem' }}>
                {econProfile.central_bank_events.map((cb) => (
                  <div key={cb.id} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '3px', padding: '0.6rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.3rem' }}>
                      <span className="econ-badge econ-badge-up" style={{ fontSize: '0.65rem' }}>
                        {cb.central_bank_decision?.decision_type?.toUpperCase() || cb.direction?.toUpperCase() || 'RATE DECISION'}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        Relevance: {cb.economic_relevance.toFixed(2)}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.8rem', fontWeight: 600 }}>{cb.indicator_canonical_name}</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', marginTop: '0.2rem', color: 'var(--text-secondary)' }}>
                      {cb.reported_value != null && <span>Rate: <strong>{cb.reported_value}%</strong></span>}
                      {cb.central_bank_decision?.rate_change_bps != null && (
                        <span style={{ marginLeft: '0.5rem', color: 'var(--accent-amber)' }}>
                          ({cb.central_bank_decision.rate_change_bps} bps)
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent Domain Observations Table */}
          {econProfile.recent_observations.length > 0 && (
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Recent Macro Observations by Domain:
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table className="econ-table" style={{ fontSize: '0.75rem' }}>
                  <thead>
                    <tr>
                      <th>Domain</th>
                      <th>Indicator</th>
                      <th>Period</th>
                      <th>Reported Value</th>
                      <th>Previous</th>
                      <th>Direction</th>
                      <th>Relevance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {econProfile.recent_observations.map((obs) => (
                      <tr key={obs.id}>
                        <td><span className="domain-tag">{obs.economic_domain}</span></td>
                        <td><strong>{obs.indicator_canonical_name}</strong></td>
                        <td>{obs.observation_period || '-'}</td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                          {obs.reported_value != null ? `${obs.reported_value} ${obs.reported_unit || ''}` : '-'}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                          {obs.previous_value != null ? `${obs.previous_value} ${obs.reported_unit || ''}` : '-'}
                        </td>
                        <td>
                          <span className="econ-badge econ-badge-up" style={{ fontSize: '0.65rem' }}>
                            {obs.direction || 'Observed'}
                          </span>
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                          {obs.economic_relevance.toFixed(2)}
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

      {/* Verified Entity Relationships Section */}
      <div className="section-box" style={{ marginBottom: '1.5rem' }}>
        <div className="section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <span>Verified Entity Relationships</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
              ({(relationships?.outbound.length || 0) + (relationships?.inbound.length || 0)} edges)
            </span>
          </div>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => {
              window.location.hash = 'graph';
            }}
            style={{ fontSize: '0.75rem' }}
          >
            Explore in Knowledge Graph &rarr;
          </button>
        </div>

        {(!relationships || (relationships.outbound.length === 0 && relationships.inbound.length === 0)) ? (
          <div className="state-empty" style={{ padding: '1.5rem 1rem' }}>
            <div className="state-title" style={{ fontSize: '0.9rem' }}>No Direct Relationships Extracted</div>
            <div className="state-desc" style={{ fontSize: '0.8rem' }}>
              No evidence-backed relationships have been extracted yet for this entity in the active knowledge graph.
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {/* Outbound */}
            {relationships.outbound.map((rel) => (
              <div
                key={rel.id}
                style={{
                  padding: '0.75rem 1rem',
                  borderRadius: '8px',
                  background: 'rgba(30, 41, 59, 0.4)',
                  border: '1px solid rgba(255, 255, 255, 0.05)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '0.5rem',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontWeight: 600, color: '#fff' }}>{entity.canonical_name}</span>
                    <span
                      style={{
                        padding: '0.15rem 0.45rem',
                        borderRadius: '4px',
                        background: 'rgba(59, 130, 246, 0.2)',
                        color: '#93c5fd',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                      }}
                    >
                      &rarr; {rel.relationship_type} &rarr;
                    </span>
                    <span style={{ fontWeight: 600, color: '#38bdf8' }}>
                      {rel.target_entity?.canonical_name || rel.target_entity_id}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontStyle: 'italic', marginTop: '0.25rem' }}>
                    &ldquo;{rel.evidence}&rdquo;
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 700 }}>
                    {(rel.confidence * 100).toFixed(0)}% conf
                  </span>
                  <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
                    {rel.extractor_version}
                  </span>
                </div>
              </div>
            ))}

            {/* Inbound */}
            {relationships.inbound.map((rel) => (
              <div
                key={rel.id}
                style={{
                  padding: '0.75rem 1rem',
                  borderRadius: '8px',
                  background: 'rgba(30, 41, 59, 0.4)',
                  border: '1px solid rgba(255, 255, 255, 0.05)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '0.5rem',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontWeight: 600, color: '#38bdf8' }}>
                      {rel.source_entity?.canonical_name || rel.source_entity_id}
                    </span>
                    <span
                      style={{
                        padding: '0.15rem 0.45rem',
                        borderRadius: '4px',
                        background: 'rgba(168, 85, 247, 0.2)',
                        color: '#d8b4fe',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                      }}
                    >
                      &rarr; {rel.relationship_type} &rarr;
                    </span>
                    <span style={{ fontWeight: 600, color: '#fff' }}>{entity.canonical_name}</span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontStyle: 'italic', marginTop: '0.25rem' }}>
                    &ldquo;{rel.evidence}&rdquo;
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 700 }}>
                    {(rel.confidence * 100).toFixed(0)}% conf
                  </span>
                  <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
                    {rel.extractor_version}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Related Events Section */}
      <div className="section-box">
        <div className="section-title">
          <span>Related Intelligence Events</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Showing {events.length} linked events
          </span>
        </div>

        {events.length === 0 ? (
          <div className="state-empty">
            <div className="state-title">No Related Events Found</div>
            <div className="state-desc">This entity is not yet linked to any extracted events in the current corpus.</div>
          </div>
        ) : (
          <div className="event-feed">
            {events.map((item) => {
              const formattedTime = item.event_time
                ? new Date(item.event_time).toUTCString().replace('GMT', 'UTC')
                : 'Time unavailable';

              const locationText = item.location_entity?.canonical_name || 'Location unavailable';

              return (
                <div
                  key={item.id}
                  className="event-card"
                  onClick={() => {
                    // Try looking up cluster or event detail
                    onSelectCluster?.(item.id);
                  }}
                >
                  <div className="event-card-header">
                    <h4 className="event-card-title">
                      {item.event_title}
                    </h4>
                    <div className="event-card-badges">
                      <EventTypeBadge eventType={item.event_type} />
                      <ImportanceBadge importance={item.importance} />
                      <ConfidenceBadge confidence={item.confidence} />
                    </div>
                  </div>

                  {item.event_summary && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      {item.event_summary}
                    </div>
                  )}

                  <div className="event-card-meta">
                    <span className="meta-item">
                      <span style={{ color: 'var(--text-muted)' }}>Time:</span>
                      <span className="meta-item-mono">{formattedTime}</span>
                    </span>

                    <span className="meta-item">
                      <span style={{ color: 'var(--text-muted)' }}>Location:</span>
                      <span>{locationText}</span>
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
