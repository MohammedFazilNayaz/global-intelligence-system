import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';
import type { EventCluster } from '../types/intelligence';
import { EventCard } from '../components/EventCard';

interface EventsViewProps {
  onSelectCluster: (clusterId: string) => void;
  initialEventType?: string;
  initialSearchQuery?: string;
  initialEntityId?: string;
}

function parseUrlParams() {
  const hash = window.location.hash;
  const qIndex = hash.indexOf('?');
  const params = new URLSearchParams(qIndex >= 0 ? hash.slice(qIndex + 1) : '');
  return {
    eventType: params.get('event_type') || '',
    minImportance: parseFloat(params.get('min_importance') || '0') || 0,
    minConfidence: parseFloat(params.get('min_confidence') || '0') || 0,
    search: params.get('search') || '',
    orderBy: params.get('order_by') || 'newest',
    page: parseInt(params.get('page') || '1', 10) || 1,
    timeRange: params.get('time_range') || 'all',
    entityId: params.get('entity_id') || '',
  };
}

export const EventsView: React.FC<EventsViewProps> = ({
  onSelectCluster,
  initialEventType,
  initialSearchQuery,
  initialEntityId,
}) => {
  const urlInit = parseUrlParams();

  const [clusters, setClusters] = useState<EventCluster[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filter and pagination states with URL fallback
  const [eventType, setEventType] = useState<string>(initialEventType || urlInit.eventType);
  const [minImportance, setMinImportance] = useState<number>(urlInit.minImportance);
  const [minConfidence, setMinConfidence] = useState<number>(urlInit.minConfidence);
  const [search, setSearch] = useState<string>(initialSearchQuery || urlInit.search);
  const [orderBy, setOrderBy] = useState<string>(urlInit.orderBy);
  const [page, setPage] = useState<number>(urlInit.page);
  const [timeRange, setTimeRange] = useState<string>(urlInit.timeRange);
  const [entityId, setEntityId] = useState<string>(initialEntityId || urlInit.entityId);
  const pageSize = 15;

  // Sync state to URL hash query parameters without page reload
  useEffect(() => {
    const params = new URLSearchParams();
    if (eventType) params.set('event_type', eventType);
    if (minImportance > 0) params.set('min_importance', minImportance.toString());
    if (minConfidence > 0) params.set('min_confidence', minConfidence.toString());
    if (search.trim()) params.set('search', search.trim());
    if (orderBy && orderBy !== 'newest') params.set('order_by', orderBy);
    if (page > 1) params.set('page', page.toString());
    if (timeRange && timeRange !== 'all') params.set('time_range', timeRange);
    if (entityId) params.set('entity_id', entityId);

    const qs = params.toString();
    const targetHash = qs ? `#events?${qs}` : '#events';
    if (window.location.hash !== targetHash) {
      window.history.replaceState(null, '', targetHash);
    }
  }, [eventType, minImportance, minConfidence, search, orderBy, page, timeRange, entityId]);

  const loadClusters = useCallback(async () => {
    setLoading(true);
    setError(null);

    let fromTime: string | undefined = undefined;
    const now = Date.now();
    if (timeRange === 'today') {
      fromTime = new Date(now - 24 * 60 * 60 * 1000).toISOString();
    } else if (timeRange === '7d') {
      fromTime = new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString();
    } else if (timeRange === '30d') {
      fromTime = new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString();
    }

    try {
      const res = await api.getClusters({
        event_type: eventType || undefined,
        min_importance: minImportance > 0 ? minImportance : undefined,
        min_confidence: minConfidence > 0 ? minConfidence : undefined,
        search: search.trim() || undefined,
        order_by: orderBy,
        from_time: fromTime,
        entity_id: entityId || undefined,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      setClusters(res.items);
      setTotal(res.total);
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to fetch clusters';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [eventType, minImportance, minConfidence, search, orderBy, page, timeRange, entityId]);

  useEffect(() => {
    loadClusters();
  }, [loadClusters]);

  const handleResetFilters = () => {
    setEventType('');
    setMinImportance(0);
    setMinConfidence(0);
    setSearch('');
    setOrderBy('newest');
    setTimeRange('all');
    setEntityId('');
    setPage(1);
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div>
      {/* Filtering Toolbar */}
      <div className="filter-toolbar" role="search" aria-label="Event filters">
        <div className="filter-group">
          <label className="filter-label" htmlFor="filter-event-type">Category</label>
          <select
            id="filter-event-type"
            className="filter-select"
            aria-label="Filter by event category"
            value={eventType}
            onChange={(e) => {
              setEventType(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Categories</option>
            <option value="central_bank_decision">Central Bank Decision</option>
            <option value="inflation_report">Inflation Report</option>
            <option value="regulatory_enforcement">Regulatory Enforcement</option>
            <option value="military_action">Military Action</option>
            <option value="diplomatic_meeting">Diplomatic Meeting</option>
            <option value="election">Election</option>
            <option value="cyberattack">Cyberattack</option>
            <option value="market_crash">Market Crash</option>
            <option value="terrorist_attack">Terrorist Attack</option>
          </select>
        </div>

        <div className="filter-group">
          <label className="filter-label" htmlFor="filter-importance">Min Importance</label>
          <select
            id="filter-importance"
            className="filter-select"
            aria-label="Filter by minimum importance"
            value={minImportance}
            onChange={(e) => {
              setMinImportance(parseFloat(e.target.value));
              setPage(1);
            }}
          >
            <option value="0">All Importance</option>
            <option value="0.4">&ge; 0.40 (Medium+)</option>
            <option value="0.75">&ge; 0.75 (High Only)</option>
          </select>
        </div>

        <div className="filter-group">
          <label className="filter-label" htmlFor="filter-confidence">Min Confidence</label>
          <select
            id="filter-confidence"
            className="filter-select"
            aria-label="Filter by minimum confidence"
            value={minConfidence}
            onChange={(e) => {
              setMinConfidence(parseFloat(e.target.value));
              setPage(1);
            }}
          >
            <option value="0">All Confidence</option>
            <option value="0.5">&ge; 0.50 (Moderate+)</option>
            <option value="0.8">&ge; 0.80 (High Extraction)</option>
          </select>
        </div>

        <div className="filter-group">
          <label className="filter-label" htmlFor="filter-time-range">Time Window</label>
          <select
            id="filter-time-range"
            className="filter-select"
            aria-label="Filter by time range"
            value={timeRange}
            onChange={(e) => {
              setTimeRange(e.target.value);
              setPage(1);
            }}
          >
            <option value="all">All Time</option>
            <option value="today">Past 24 Hours</option>
            <option value="7d">Past 7 Days</option>
            <option value="30d">Past 30 Days</option>
          </select>
        </div>

        <div className="filter-group">
          <label className="filter-label" htmlFor="filter-order-by">Sort By</label>
          <select
            id="filter-order-by"
            className="filter-select"
            aria-label="Sort events by"
            value={orderBy}
            onChange={(e) => {
              setOrderBy(e.target.value);
              setPage(1);
            }}
          >
            <option value="newest">Newest First</option>
            <option value="highest_importance">Highest Importance</option>
            <option value="highest_confidence">Highest Confidence</option>
            <option value="oldest">Oldest First</option>
          </select>
        </div>

        <div className="filter-group" style={{ flex: 1, minWidth: '180px' }}>
          <label className="filter-label" htmlFor="filter-search-input">Search Title/Summary</label>
          <input
            id="filter-search-input"
            type="text"
            className="filter-input"
            style={{ width: '100%' }}
            aria-label="Search event title or summary"
            placeholder="Filter title or keywords..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>

        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={handleResetFilters}
          aria-label="Reset all filters"
        >
          Reset
        </button>
      </div>

      {/* Feed Area */}
      {loading && (
        <div className="state-loading">
          <div className="state-title">Querying Intelligence Repository...</div>
          <div className="state-desc">Applying filters and pagination against database.</div>
        </div>
      )}

      {error && !loading && (
        <div className="state-error">
          <div className="state-title" style={{ color: 'var(--accent-red)' }}>
            Error Loading Feed
          </div>
          <div className="state-desc">{error}</div>
          <button className="btn btn-secondary" style={{ marginTop: '1rem' }} onClick={loadClusters}>
            Retry
          </button>
        </div>
      )}

      {!loading && !error && clusters.length === 0 && (
        <div className="state-empty">
          <div className="state-title">No Matching Intelligence Events</div>
          <div className="state-desc">
            No event clusters matched the selected filters. Try broadening the criteria or resetting filters.
          </div>
          <button
            className="btn btn-secondary"
            style={{ marginTop: '1rem' }}
            onClick={handleResetFilters}
          >
            Reset Filters
          </button>
        </div>
      )}

      {!loading && !error && clusters.length > 0 && (
        <>
          <div className="event-feed">
            {clusters.map((cluster) => (
              <EventCard
                key={cluster.id}
                cluster={cluster}
                onClick={() => onSelectCluster(cluster.id)}
              />
            ))}
          </div>

          {/* Pagination Controls */}
          <div className="pagination-bar">
            <div>
              Showing <span style={{ color: '#fff' }}>{(page - 1) * pageSize + 1}</span> to{' '}
              <span style={{ color: '#fff' }}>{Math.min(page * pageSize, total)}</span> of{' '}
              <span style={{ color: '#fff' }}>{total}</span> clusters
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <button
                className="btn btn-secondary btn-sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                &larr; Previous
              </button>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                Page {page} of {Math.max(1, totalPages)}
              </span>
              <button
                className="btn btn-secondary btn-sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next &rarr;
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
