import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { SearchResult } from '../types/intelligence';
import { EventCard } from '../components/EventCard';

interface SearchResultsViewProps {
  query: string;
  onSelectCluster: (clusterId: string) => void;
  onSelectEntity: (entityId: string) => void;
  onSelectMarketAsset?: (assetId: string) => void;
}

export const SearchResultsView: React.FC<SearchResultsViewProps> = ({
  query,
  onSelectCluster,
  onSelectEntity,
  onSelectMarketAsset,
}) => {
  const [result, setResult] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query.trim()) {
      setResult(null);
      setLoading(false);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    api
      .searchGlobal(query.trim(), 25)
      .then((data) => {
        if (isMounted) {
          setResult(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Global search failed');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [query]);

  if (loading) {
    return (
      <div className="state-loading">
        <div className="state-title">Searching Intelligence Database...</div>
        <div className="state-desc">Scanning event clusters and canonical entities for "{query}".</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="state-error">
        <div className="state-title" style={{ color: 'var(--accent-red)' }}>
          Search Query Error
        </div>
        <div className="state-desc">{error}</div>
      </div>
    );
  }

  const hasResults =
    result &&
    (result.total_clusters > 0 ||
      result.total_entities > 0 ||
      (result.market_assets && result.market_assets.length > 0) ||
      (result.indicators && result.indicators.length > 0) ||
      (result.observations && result.observations.length > 0));

  if (!hasResults || !result) {
    return (
      <div className="state-empty">
        <div className="state-title">No Search Results Found</div>
        <div className="state-desc">
          No clusters, canonical entities, or market assets matched query: "{query}".
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: '1.25rem' }}>
        <h2 style={{ fontSize: '1.15rem', fontWeight: 600, color: 'var(--text-primary)' }}>
          Search Results for "{query}"
        </h2>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          Found <strong style={{ color: '#fff' }}>{result.total_clusters}</strong> event clusters,{' '}
          <strong style={{ color: '#fff' }}>{result.total_entities}</strong> entities, and{' '}
          <strong style={{ color: '#fff' }}>{result.market_assets ? result.market_assets.length : 0}</strong> market assets
        </div>
      </div>

      {/* Matched Market Assets */}
      {result.market_assets && result.market_assets.length > 0 && (
        <div className="section-box" style={{ borderLeft: '3px solid var(--accent-amber, #f59e0b)' }}>
          <div className="section-title">
            <span>Matched Market Assets ({result.market_assets.length})</span>
            <a href="#market" style={{ fontSize: '0.75rem', color: 'var(--accent-amber, #f59e0b)' }}>
              Open Market Desk &rarr;
            </a>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.75rem' }}>
            {result.market_assets.map((asset) => (
              <div
                key={asset.id}
                className="event-card"
                onClick={() => {
                  if (onSelectMarketAsset) {
                    onSelectMarketAsset(asset.id);
                  } else {
                    window.location.hash = `market/${asset.id}`;
                  }
                }}
                style={{ padding: '0.75rem 1rem', cursor: 'pointer' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <strong style={{ color: 'var(--accent-cyan)', fontSize: '0.95rem' }}>{asset.symbol}</strong>
                  <span className="domain-tag" style={{ fontSize: '0.65rem' }}>{asset.asset_type}</span>
                </div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', marginTop: '0.25rem', fontWeight: 600 }}>
                  {asset.canonical_name}
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                  Venue: {asset.exchange_venue || 'Interbank'} | Quote: {asset.quote_currency || 'USD'}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Matched Entities */}
      {result.entities.length > 0 && (
        <div className="section-box">
          <div className="section-title">
            <span>Matched Entities ({result.entities.length})</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '0.75rem' }}>
            {result.entities.map((entity) => (
              <div
                key={entity.id}
                className="event-card"
                onClick={() => onSelectEntity(entity.id)}
                style={{ padding: '0.75rem 1rem' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <strong style={{ color: 'var(--text-primary)', fontSize: '0.9rem' }}>{entity.canonical_name}</strong>
                  <span className="badge badge-event-type" style={{ fontSize: '0.65rem' }}>{entity.entity_type}</span>
                </div>
                {entity.description && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
                    {entity.description}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Matched Clusters */}
      {result.clusters.length > 0 && (
        <div className="section-box">
          <div className="section-title">
            <span>Matched Event Clusters ({result.clusters.length})</span>
          </div>
          <div className="event-feed">
            {result.clusters.map((cluster) => (
              <EventCard
                key={cluster.id}
                cluster={cluster}
                onClick={() => onSelectCluster(cluster.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Matched Economic Indicators */}
      {result.indicators && result.indicators.length > 0 && (
        <div className="section-box">
          <div className="section-title">
            <span>Matched Economic Indicators ({result.indicators.length})</span>
            <a href="#economic" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
              Open Economic Desk &rarr;
            </a>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.75rem' }}>
            {result.indicators.map((ind) => (
              <div key={ind.id} className="event-card" style={{ padding: '0.75rem 1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="country-chip">{ind.country_code || 'GL'}</span>
                  <span className="domain-tag">{ind.indicator_type}</span>
                </div>
                <strong style={{ display: 'block', marginTop: '0.4rem', color: 'var(--text-primary)', fontSize: '0.85rem' }}>
                  {ind.canonical_name}
                </strong>
                {ind.description && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                    {ind.description}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Matched Economic Observations */}
      {result.observations && result.observations.length > 0 && (
        <div className="section-box">
          <div className="section-title">
            <span>Matched Macroeconomic Observations ({result.observations.length})</span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="econ-table" style={{ fontSize: '0.8rem' }}>
              <thead>
                <tr>
                  <th>Region</th>
                  <th>Indicator</th>
                  <th>Domain</th>
                  <th>Period</th>
                  <th>Reported Value</th>
                  <th>Previous</th>
                  <th>Direction</th>
                  <th>Relevance</th>
                </tr>
              </thead>
              <tbody>
                {result.observations.map((obs) => (
                  <tr key={obs.id}>
                    <td><span className="country-chip">{obs.country_code || 'GL'}</span></td>
                    <td><strong>{obs.indicator_canonical_name}</strong></td>
                    <td><span className="domain-tag">{obs.economic_domain}</span></td>
                    <td>{obs.observation_period || '-'}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                      {obs.reported_value != null ? `${obs.reported_value} ${obs.reported_unit || ''}` : '-'}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                      {obs.previous_value != null ? `${obs.previous_value} ${obs.reported_unit || ''}` : '-'}
                    </td>
                    <td>
                      <span className="econ-badge econ-badge-up" style={{ fontSize: '0.65rem' }}>
                        {obs.direction || 'Release'}
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
  );
};
