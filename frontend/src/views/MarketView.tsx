import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { MarketAsset, MarketDashboardSummary } from '../types/intelligence';

interface MarketViewProps {
  onNavigateToAsset?: (assetId: string) => void;
  onNavigateToEvent?: (eventId: string) => void;
}

export const MarketView: React.FC<MarketViewProps> = ({
  onNavigateToAsset,
  onNavigateToEvent,
}) => {
  const [summary, setSummary] = useState<MarketDashboardSummary | null>(null);
  const [assets, setAssets] = useState<MarketAsset[]>([]);
  const [selectedType, setSelectedType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMarketData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumRes, assetsRes] = await Promise.all([
        api.getMarketDashboardSummary(),
        api.getMarketAssets({
          asset_type: selectedType === 'all' ? undefined : selectedType,
          search: searchQuery.trim() || undefined,
          page_size: 50,
        }),
      ]);
      setSummary(sumRes);
      setAssets(assetsRes.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load market intelligence data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMarketData();
  }, [selectedType]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchMarketData();
  };

  const assetTypes = [
    { key: 'all', label: 'All Assets' },
    { key: 'crypto', label: 'Crypto' },
    { key: 'equity_index', label: 'Equity Indices' },
    { key: 'forex', label: 'Forex' },
    { key: 'commodity', label: 'Commodities' },
    { key: 'interest_rate', label: 'Sovereign Rates' },
  ];

  return (
    <div className="market-view-container">
      {/* View Header */}
      <div className="market-header">
        <div>
          <h1 className="market-title">Market Intelligence Desk</h1>
          <p className="market-subtitle">
            Temporal market data alignment and price movement observation around global intelligence events.
          </p>
        </div>
        <div className="market-header-actions">
          <button className="refresh-btn" onClick={fetchMarketData} disabled={loading}>
            {loading ? 'Syncing...' : '↻ Refresh Feeds'}
          </button>
        </div>
      </div>

      {/* Mandatory Neutral Disclaimer Banner */}
      <div className="market-disclaimer-banner" role="alert">
        <span className="disclaimer-icon">ℹ</span>
        <div className="disclaimer-content">
          <strong>Market Association Invariant:</strong> Market movements are temporally observed around event timestamps and do not establish causation. The platform does not generate trading signals, price targets, directional forecasts, or execution recommendations.
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="error-banner" role="alert">
          <span>Failed to load market feeds: {error}</span>
          <button onClick={fetchMarketData} className="retry-btn">Retry</button>
        </div>
      )}

      {/* Overview KPI Cards */}
      <div className="market-kpi-grid">
        <div className="market-kpi-card">
          <span className="kpi-label">Monitored Assets</span>
          <div className="kpi-value">{summary?.total_assets || assets.length || 16}</div>
          <div className="kpi-subtext">Across 5 asset classes</div>
        </div>

        <div className="market-kpi-card">
          <span className="kpi-label">Market Observations</span>
          <div className="kpi-value">
            {summary ? summary.total_observations.toLocaleString() : '—'}
          </div>
          <div className="kpi-subtext">Historical OHLCV bars</div>
        </div>

        <div className="market-kpi-card">
          <span className="kpi-label">Event Correlations</span>
          <div className="kpi-value">
            {summary ? summary.total_correlations.toLocaleString() : '—'}
          </div>
          <div className="kpi-subtext">Calculated temporal windows</div>
        </div>

        <div className="market-kpi-card">
          <span className="kpi-label">Top 24h Mover</span>
          <div className="kpi-value">
            {summary && summary.top_movers.length > 0 ? (
              <span className={summary.top_movers[0].return_24h >= 0 ? 'text-positive' : 'text-negative'}>
                {summary.top_movers[0].symbol}{' '}
                {summary.top_movers[0].return_24h > 0 ? '+' : ''}
                {summary.top_movers[0].return_24h}%
              </span>
            ) : (
              '—'
            )}
          </div>
          <div className="kpi-subtext">
            {summary && summary.top_movers.length > 0 ? summary.top_movers[0].canonical_name : 'No quote delta'}
          </div>
        </div>
      </div>

      {/* Asset Universe Section */}
      <div className="market-universe-section">
        <div className="section-toolbar">
          <div className="type-chips">
            {assetTypes.map((t) => (
              <button
                key={t.key}
                className={`type-chip ${selectedType === t.key ? 'active' : ''}`}
                onClick={() => setSelectedType(t.key)}
              >
                {t.label}
              </button>
            ))}
          </div>

          <form onSubmit={handleSearchSubmit} className="search-form">
            <input
              type="text"
              placeholder="Search symbol (e.g. BTC, SPX, BRENT)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="market-search-input"
            />
            <button type="submit" className="market-search-btn">Search</button>
          </form>
        </div>

        {loading && assets.length === 0 ? (
          <div className="loading-state">Loading canonical market universe...</div>
        ) : assets.length === 0 ? (
          <div className="empty-state">No market assets match your search or filter.</div>
        ) : (
          <div className="market-asset-grid">
            {assets.map((asset) => {
              const latest = asset.latest_observation;
              const ret = asset.day_return_percent;
              const isHealthy = asset.data_quality?.is_healthy ?? true;

              return (
                <div
                  key={asset.id}
                  className="market-asset-card"
                  onClick={() => onNavigateToAsset && onNavigateToAsset(asset.id)}
                  role="button"
                  tabIndex={0}
                >
                  <div className="asset-card-header">
                    <div>
                      <span className="asset-symbol">{asset.symbol}</span>
                      <span className="asset-name">{asset.canonical_name}</span>
                    </div>
                    <span className={`quality-badge ${isHealthy ? 'badge-healthy' : 'badge-gap'}`}>
                      {isHealthy ? '● Verified' : '⚠ Gaps'}
                    </span>
                  </div>

                  <div className="asset-card-price-row">
                    <div className="asset-price">
                      {latest ? latest.close.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '—'}
                      <span className="asset-currency"> {asset.quote_currency || 'USD'}</span>
                    </div>
                    {ret !== null && ret !== undefined && (
                      <div className={`asset-return ${ret >= 0 ? 'ret-positive' : 'ret-negative'}`}>
                        {ret > 0 ? '+' : ''}{ret.toFixed(2)}%
                      </div>
                    )}
                  </div>

                  <div className="asset-card-footer">
                    <span className="asset-type-tag">{asset.asset_type.replace('_', ' ')}</span>
                    <span className="asset-venue">{asset.exchange_venue || 'Interbank'}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Observed Market Movement Around Events Ledger */}
      <div className="market-events-section">
        <h2 className="section-title">Recent Events with Observed Market Context</h2>
        <p className="section-description">
          Deterministic price and volume changes recorded within defined windows before and after event occurrences.
        </p>

        {summary?.recent_correlations && summary.recent_correlations.length > 0 ? (
          <div className="correlation-table-container">
            <table className="correlation-table">
              <thead>
                <tr>
                  <th>Event Description</th>
                  <th>Event Type</th>
                  <th>Market Asset</th>
                  <th>Window</th>
                  <th>Pre-Event</th>
                  <th>Post-Event</th>
                  <th>Return (%)</th>
                  <th>Volume Change</th>
                  <th>Methodology</th>
                </tr>
              </thead>
              <tbody>
                {summary.recent_correlations.map((corr) => {
                  const ret = corr.return_percent;
                  const vol = corr.volume_change;

                  return (
                    <tr
                      key={corr.id}
                      className="correlation-row"
                      onClick={() => onNavigateToEvent && onNavigateToEvent(corr.event_id)}
                    >
                      <td className="cell-event-title">
                        {corr.event_title || 'Intelligence Event'}
                      </td>
                      <td>
                        <span className="event-type-badge">
                          {corr.event_type || 'macro_event'}
                        </span>
                      </td>
                      <td className="cell-asset-name">
                        <strong>{corr.market_asset?.symbol || 'Asset'}</strong>
                        <span className="asset-canonical-sub"> ({corr.market_asset?.canonical_name})</span>
                      </td>
                      <td>
                        <span className="window-badge">±{corr.window_size}</span>
                      </td>
                      <td className="cell-numeric">
                        {corr.pre_event_price !== null && corr.pre_event_price !== undefined
                          ? corr.pre_event_price.toLocaleString(undefined, { minimumFractionDigits: 2 })
                          : 'null'}
                      </td>
                      <td className="cell-numeric">
                        {corr.post_event_price !== null && corr.post_event_price !== undefined
                          ? corr.post_event_price.toLocaleString(undefined, { minimumFractionDigits: 2 })
                          : 'null'}
                      </td>
                      <td className="cell-numeric">
                        {ret !== null && ret !== undefined ? (
                          <span className={`return-badge ${ret >= 0 ? 'ret-positive' : 'ret-negative'}`}>
                            {ret > 0 ? '+' : ''}{ret.toFixed(2)}%
                          </span>
                        ) : (
                          <span className="text-muted">null</span>
                        )}
                      </td>
                      <td className="cell-numeric">
                        {vol !== null && vol !== undefined ? (
                          <span>{vol > 0 ? '+' : ''}{vol.toFixed(1)}%</span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                      <td className="cell-methodology">
                        <code>{corr.methodology}</code>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No event-market temporal correlations recorded yet.</div>
        )}
      </div>
    </div>
  );
};
