import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { MarketAsset, MarketObservation } from '../types/intelligence';

interface MarketAssetDetailViewProps {
  assetId: string;
  onBack?: () => void;
  onNavigateToEvent?: (eventId: string) => void;
}

export const MarketAssetDetailView: React.FC<MarketAssetDetailViewProps> = ({
  assetId,
  onBack,
  onNavigateToEvent,
}) => {
  const [asset, setAsset] = useState<MarketAsset | null>(null);
  const [observations, setObservations] = useState<MarketObservation[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [selectedInterval, setSelectedInterval] = useState<string>('1m');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [assetRes, obsRes, eventsRes] = await Promise.all([
        api.getMarketAssetDetail(assetId),
        api.getMarketAssetObservations(assetId, { interval: selectedInterval, limit: 100 }),
        api.getMarketAssetEvents(assetId, 20),
      ]);
      setAsset(assetRes);
      setObservations(obsRes);
      setEvents(eventsRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load asset details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [assetId, selectedInterval]);

  const intervals = ['1m', '5m', '15m', '1h', '1d'];

  if (loading && !asset) {
    return <div className="loading-state">Loading market asset intelligence...</div>;
  }

  if (error && !asset) {
    return (
      <div className="error-banner" role="alert">
        <span>{error}</span>
        {onBack && <button onClick={onBack} className="back-btn">Back to Market Desk</button>}
      </div>
    );
  }

  const latest = asset?.latest_observation;
  const quality = asset?.data_quality;

  return (
    <div className="asset-detail-container">
      {/* Back button and breadcrumb */}
      <div className="detail-top-bar">
        {onBack && (
          <button onClick={onBack} className="back-link-btn">
            ← Back to Market Desk
          </button>
        )}
      </div>

      {/* Asset Hero Header */}
      {asset && (
        <div className="asset-hero-card">
          <div className="hero-left">
            <div className="hero-symbol-row">
              <h1 className="hero-symbol">{asset.symbol}</h1>
              <span className="hero-name">{asset.canonical_name}</span>
              <span className="hero-type-tag">{asset.asset_type.replace('_', ' ')}</span>
            </div>
            <div className="hero-venue-info">
              <span>Venue: <strong>{asset.exchange_venue || 'Interbank'}</strong></span>
              <span>Quote: <strong>{asset.quote_currency || 'USD'}</strong></span>
              {asset.base_currency && <span>Base: <strong>{asset.base_currency}</strong></span>}
            </div>
          </div>

          <div className="hero-right">
            <div className="hero-price">
              {latest ? latest.close.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '—'}
              <span className="hero-currency"> {asset.quote_currency || 'USD'}</span>
            </div>
            {asset.day_return_percent !== null && asset.day_return_percent !== undefined && (
              <div className={`hero-return ${asset.day_return_percent >= 0 ? 'ret-positive' : 'ret-negative'}`}>
                24h: {asset.day_return_percent > 0 ? '+' : ''}{asset.day_return_percent.toFixed(2)}%
              </div>
            )}
            <div className="hero-timestamp">
              Last tick: {latest ? new Date(latest.timestamp).toUTCString() : 'No observations'}
            </div>
          </div>
        </div>
      )}

      {/* Data Quality & Health Audit Card */}
      {quality && (
        <div className="quality-audit-card">
          <div className="audit-header">
            <h3>Data Quality & Feed Continuity Audit</h3>
            <span className={`quality-badge ${quality.is_healthy ? 'badge-healthy' : 'badge-gap'}`}>
              {quality.is_healthy ? '✔ Health: Normal' : '⚠ Anomalies Detected'}
            </span>
          </div>
          <div className="audit-metrics-grid">
            <div className="audit-metric">
              <span className="audit-label">Continuity Ratio</span>
              <span className="audit-val">{(quality.continuity_ratio * 100).toFixed(1)}%</span>
            </div>
            <div className="audit-metric">
              <span className="audit-label">Loaded Bars</span>
              <span className="audit-val">{quality.total_observations}</span>
            </div>
            <div className="audit-metric">
              <span className="audit-label">Missing Candles</span>
              <span className={`audit-val ${quality.missing_candles_count > 0 ? 'text-warn' : ''}`}>
                {quality.missing_candles_count}
              </span>
            </div>
            <div className="audit-metric">
              <span className="audit-label">Duplicates Filtered</span>
              <span className="audit-val">{quality.duplicate_count}</span>
            </div>
            <div className="audit-metric">
              <span className="audit-label">Out of Order</span>
              <span className="audit-val">{quality.out_of_order_count}</span>
            </div>
          </div>
        </div>
      )}

      {/* Mandatory Disclaimer */}
      <div className="market-disclaimer-banner">
        <span className="disclaimer-icon">ℹ</span>
        <div className="disclaimer-content">
          <strong>Non-Causal Market Invariant:</strong> Temporal correlations between events and price movements are descriptive and do not establish causality or predict future prices.
        </div>
      </div>

      {/* Bidirectional Navigation: Observed Events around Asset */}
      <div className="correlated-events-section">
        <h2 className="section-title">Temporally Correlated Events</h2>
        <p className="section-description">
          Global events occurring in temporal proximity to observations of {asset?.symbol}. Click any event to inspect source provenance.
        </p>

        {events.length > 0 ? (
          <div className="correlation-table-container">
            <table className="correlation-table">
              <thead>
                <tr>
                  <th>Event Title</th>
                  <th>Event Type</th>
                  <th>Event Time (UTC)</th>
                  <th>Window</th>
                  <th>Pre-Price</th>
                  <th>Post-Price</th>
                  <th>Return (%)</th>
                  <th>Volume Δ</th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr
                    key={ev.correlation_id}
                    className="correlation-row"
                    onClick={() => onNavigateToEvent && onNavigateToEvent(ev.event_id)}
                  >
                    <td className="cell-event-title">{ev.event_title}</td>
                    <td><span className="event-type-badge">{ev.event_type}</span></td>
                    <td className="cell-time">{ev.event_time ? new Date(ev.event_time).toUTCString() : '—'}</td>
                    <td><span className="window-badge">±{ev.window_size}</span></td>
                    <td className="cell-numeric">{ev.pre_event_price?.toFixed(2) ?? 'null'}</td>
                    <td className="cell-numeric">{ev.post_event_price?.toFixed(2) ?? 'null'}</td>
                    <td className="cell-numeric">
                      {ev.return_percent !== null && ev.return_percent !== undefined ? (
                        <span className={`return-badge ${ev.return_percent >= 0 ? 'ret-positive' : 'ret-negative'}`}>
                          {`${ev.return_percent > 0 ? '+' : ''}${ev.return_percent.toFixed(2)}%`}
                        </span>
                      ) : 'null'}
                    </td>
                    <td className="cell-numeric">
                      {ev.volume_change !== null && ev.volume_change !== undefined
                        ? `${ev.volume_change > 0 ? '+' : ''}${ev.volume_change.toFixed(1)}%`
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No temporal event correlations calculated for this asset yet.</div>
        )}
      </div>

      {/* Historical Bars / Timeseries Explorer */}
      <div className="timeseries-section">
        <div className="section-header-row">
          <h2 className="section-title">Historical Observations (OHLCV)</h2>
          <div className="interval-buttons">
            {intervals.map((iv) => (
              <button
                key={iv}
                className={`interval-btn ${selectedInterval === iv ? 'active' : ''}`}
                onClick={() => setSelectedInterval(iv)}
              >
                {iv}
              </button>
            ))}
          </div>
        </div>

        {observations.length > 0 ? (
          <div className="correlation-table-container">
            <table className="correlation-table">
              <thead>
                <tr>
                  <th>Timestamp (UTC)</th>
                  <th>Open</th>
                  <th>High</th>
                  <th>Low</th>
                  <th>Close</th>
                  <th>Volume</th>
                  <th>Feed Source</th>
                </tr>
              </thead>
              <tbody>
                {observations.slice(-50).reverse().map((obs) => (
                  <tr key={obs.id}>
                    <td className="cell-time">{new Date(obs.timestamp).toUTCString()}</td>
                    <td className="cell-numeric">{obs.open.toFixed(2)}</td>
                    <td className="cell-numeric">{obs.high.toFixed(2)}</td>
                    <td className="cell-numeric">{obs.low.toFixed(2)}</td>
                    <td className="cell-numeric font-bold">{obs.close.toFixed(2)}</td>
                    <td className="cell-numeric">{obs.volume !== null && obs.volume !== undefined ? obs.volume.toLocaleString() : '—'}</td>
                    <td><span className="source-tag">{obs.source}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No observations recorded for interval {selectedInterval}.</div>
        )}
      </div>
    </div>
  );
};
