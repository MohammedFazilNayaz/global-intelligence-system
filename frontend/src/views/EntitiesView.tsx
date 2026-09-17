import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';
import type { Entity } from '../types/intelligence';

interface EntitiesViewProps {
  onSelectEntity: (entityId: string) => void;
  initialSearch?: string;
}

function parseEntityUrlParams() {
  const hash = window.location.hash;
  const qIndex = hash.indexOf('?');
  const params = new URLSearchParams(qIndex >= 0 ? hash.slice(qIndex + 1) : '');
  return {
    search: params.get('search') || '',
    entityType: params.get('entity_type') || '',
    page: parseInt(params.get('page') || '1', 10) || 1,
  };
}

export const EntitiesView: React.FC<EntitiesViewProps> = ({
  onSelectEntity,
  initialSearch,
}) => {
  const urlInit = parseEntityUrlParams();

  const [entities, setEntities] = useState<Entity[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState<string>(initialSearch || urlInit.search);
  const [entityType, setEntityType] = useState<string>(urlInit.entityType);
  const [page, setPage] = useState<number>(urlInit.page);
  const pageSize = 20;

  // Sync state to URL hash query parameters without page reload
  useEffect(() => {
    const params = new URLSearchParams();
    if (search.trim()) params.set('search', search.trim());
    if (entityType) params.set('entity_type', entityType);
    if (page > 1) params.set('page', page.toString());

    const qs = params.toString();
    const targetHash = qs ? `#entities?${qs}` : '#entities';
    if (window.location.hash !== targetHash) {
      window.history.replaceState(null, '', targetHash);
    }
  }, [search, entityType, page]);

  const loadEntities = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getEntities({
        search: search.trim() || undefined,
        entity_type: entityType || undefined,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      setEntities(res.items);
      setTotal(res.total);
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to fetch entities';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [search, entityType, page]);

  useEffect(() => {
    loadEntities();
  }, [loadEntities]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div>
      {/* Filtering Toolbar */}
      <div className="filter-toolbar">
        <div className="filter-group" style={{ flex: 1, minWidth: '220px' }}>
          <label className="filter-label" htmlFor="entity-search-input">Search Entities</label>
          <input
            id="entity-search-input"
            type="text"
            className="filter-input"
            style={{ width: '100%' }}
            placeholder="Search by canonical or normalized name..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>

        <div className="filter-group">
          <label className="filter-label" htmlFor="filter-entity-type">Entity Type</label>
          <select
            id="filter-entity-type"
            className="filter-select"
            value={entityType}
            onChange={(e) => {
              setEntityType(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Types</option>
            <option value="central_bank">Central Bank</option>
            <option value="regulator">Regulator</option>
            <option value="government_agency">Government Agency</option>
            <option value="organization">Organization</option>
            <option value="person">Person</option>
            <option value="location">Location</option>
          </select>
        </div>

        <button
          className="btn btn-secondary btn-sm"
          onClick={() => {
            setSearch('');
            setEntityType('');
            setPage(1);
          }}
        >
          Reset
        </button>
      </div>

      {loading && (
        <div className="state-loading">
          <div className="state-title">Loading Canonical Entities...</div>
          <div className="state-desc">Querying normalized intelligence entity repository.</div>
        </div>
      )}

      {error && !loading && (
        <div className="state-error">
          <div className="state-title" style={{ color: 'var(--accent-red)' }}>
            Error Loading Entities
          </div>
          <div className="state-desc">{error}</div>
          <button className="btn btn-secondary" style={{ marginTop: '1rem' }} onClick={loadEntities}>
            Retry
          </button>
        </div>
      )}

      {!loading && !error && entities.length === 0 && (
        <div className="state-empty">
          <div className="state-title">No Entities Found</div>
          <div className="state-desc">
            No canonical entities matched "{search || entityType}".
          </div>
        </div>
      )}

      {!loading && !error && entities.length > 0 && (
        <>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
              gap: '0.75rem',
            }}
          >
            {entities.map((entity) => (
              <div
                key={entity.id}
                className="event-card"
                onClick={() => onSelectEntity(entity.id)}
                style={{ padding: '0.85rem 1rem' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {entity.canonical_name}
                  </h4>
                  <span className="badge badge-event-type" style={{ fontSize: '0.65rem' }}>
                    {entity.entity_type}
                  </span>
                </div>

                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  Normalized: {entity.normalized_name}
                </div>

                {entity.country_code && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    Country: <strong style={{ color: 'var(--text-primary)' }}>{entity.country_code}</strong>
                  </div>
                )}

                {entity.description && (
                  <div
                    style={{
                      fontSize: '0.75rem',
                      color: 'var(--text-secondary)',
                      marginTop: '0.2rem',
                      lineHeight: 1.4,
                    }}
                  >
                    {entity.description}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="pagination-bar">
            <div>
              Showing <span style={{ color: '#fff' }}>{(page - 1) * pageSize + 1}</span> to{' '}
              <span style={{ color: '#fff' }}>{Math.min(page * pageSize, total)}</span> of{' '}
              <span style={{ color: '#fff' }}>{total}</span> entities
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
