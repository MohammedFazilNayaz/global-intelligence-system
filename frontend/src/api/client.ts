import type {
  DashboardSummary,
  EventClusterListResponse,
  EventClusterDetail,
  EntityListResponse,
  Entity,
  EntityRelatedEventItem,
  SearchResult,
  SystemHealth,
} from '../types/intelligence';

const rawApiBase: string = (import.meta.env.VITE_API_URL as string) || '/api/v1';
const API_BASE = rawApiBase.endsWith('/') ? rawApiBase.slice(0, -1) : rawApiBase;

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let errorDetail = `HTTP ${res.status} ${res.statusText}`;
    try {
      const errJson = await res.json();
      if (errJson && errJson.detail) {
        errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(errorDetail);
  }

  return res.json() as Promise<T>;
}

export const api = {
  getDashboardSummary: async (): Promise<DashboardSummary> => {
    return request<DashboardSummary>('/dashboard/summary');
  },

  getClusters: async (params?: {
    event_type?: string;
    min_confidence?: number;
    min_importance?: number;
    location_entity_id?: string;
    entity_id?: string;
    from_time?: string;
    to_time?: string;
    search?: string;
    order_by?: string;
    limit?: number;
    offset?: number;
  }): Promise<EventClusterListResponse> => {
    const query = new URLSearchParams();
    if (params?.event_type) query.set('event_type', params.event_type);
    if (params?.min_confidence !== undefined && params.min_confidence > 0) {
      query.set('min_confidence', params.min_confidence.toString());
    }
    if (params?.min_importance !== undefined && params.min_importance > 0) {
      query.set('min_importance', params.min_importance.toString());
    }
    if (params?.location_entity_id) query.set('location_entity_id', params.location_entity_id);
    if (params?.entity_id) query.set('entity_id', params.entity_id);
    if (params?.from_time) query.set('from_time', params.from_time);
    if (params?.to_time) query.set('to_time', params.to_time);
    if (params?.search) query.set('search', params.search);
    if (params?.order_by) query.set('order_by', params.order_by);
    if (params?.limit) query.set('limit', params.limit.toString());
    if (params?.offset !== undefined) query.set('offset', params.offset.toString());

    const qs = query.toString();
    return request<EventClusterListResponse>(`/event-clusters${qs ? `?${qs}` : ''}`);
  },

  getClusterDetail: async (clusterId: string): Promise<EventClusterDetail> => {
    return request<EventClusterDetail>(`/event-clusters/${clusterId}`);
  },

  getEntities: async (params?: {
    search?: string;
    entity_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<EntityListResponse> => {
    const query = new URLSearchParams();
    if (params?.search) query.set('search', params.search);
    if (params?.entity_type) query.set('entity_type', params.entity_type);
    if (params?.limit) query.set('limit', params.limit.toString());
    if (params?.offset !== undefined) query.set('offset', params.offset.toString());

    const qs = query.toString();
    return request<EntityListResponse>(`/entities${qs ? `?${qs}` : ''}`);
  },

  getEntityDetail: async (entityId: string): Promise<Entity> => {
    return request<Entity>(`/entities/${entityId}`);
  },

  getEntityEvents: async (entityId: string): Promise<EntityRelatedEventItem[]> => {
    return request<EntityRelatedEventItem[]>(`/entities/${entityId}/events`);
  },

  getEconomicIndicators: async (params?: {
    search?: string;
    country_code?: string;
    indicator_type?: string;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.search) query.set('search', params.search);
    if (params?.country_code) query.set('country_code', params.country_code);
    if (params?.indicator_type) query.set('indicator_type', params.indicator_type);
    if (params?.limit) query.set('limit', params.limit.toString());
    if (params?.offset !== undefined) query.set('offset', params.offset.toString());
    const qs = query.toString();
    return request<import('../types/intelligence').EconomicIndicatorListResponse>(
      `/economic-indicators${qs ? `?${qs}` : ''}`
    );
  },

  getEconomicObservations: async (params?: {
    indicator_id?: string;
    domain?: string;
    country_code?: string;
    direction?: string;
    min_relevance?: number;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.indicator_id) query.set('indicator_id', params.indicator_id);
    if (params?.domain) query.set('domain', params.domain);
    if (params?.country_code) query.set('country_code', params.country_code);
    if (params?.direction) query.set('direction', params.direction);
    if (params?.min_relevance !== undefined) query.set('min_relevance', params.min_relevance.toString());
    if (params?.limit) query.set('limit', params.limit.toString());
    if (params?.offset !== undefined) query.set('offset', params.offset.toString());
    const qs = query.toString();
    return request<import('../types/intelligence').EconomicObservationListResponse>(
      `/economic-observations${qs ? `?${qs}` : ''}`
    );
  },

  getEconomicObservationDetail: async (observationId: string) => {
    return request<import('../types/intelligence').EconomicObservation>(
      `/economic-observations/${observationId}`
    );
  },

  getCountryEconomicProfile: async (entityId: string) => {
    return request<import('../types/intelligence').CountryEconomicProfile>(
      `/entities/${entityId}/economic-profile`
    );
  },

  getMarketAssets: async (params?: {
    asset_type?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.asset_type) query.set('asset_type', params.asset_type);
    if (params?.search) query.set('search', params.search);
    if (params?.page) query.set('page', params.page.toString());
    if (params?.page_size) query.set('page_size', params.page_size.toString());
    const qs = query.toString();
    return request<import('../types/intelligence').PaginatedMarketAssets>(
      `/market-assets${qs ? `?${qs}` : ''}`
    );
  },

  getMarketAssetDetail: async (assetId: string) => {
    return request<import('../types/intelligence').MarketAsset>(
      `/market-assets/${assetId}`
    );
  },

  getMarketAssetObservations: async (
    assetId: string,
    params?: { interval?: string; from_time?: string; to_time?: string; limit?: number }
  ) => {
    const query = new URLSearchParams();
    if (params?.interval) query.set('interval', params.interval);
    if (params?.from_time) query.set('from_time', params.from_time);
    if (params?.to_time) query.set('to_time', params.to_time);
    if (params?.limit) query.set('limit', params.limit.toString());
    const qs = query.toString();
    return request<import('../types/intelligence').MarketObservation[]>(
      `/market-assets/${assetId}/observations${qs ? `?${qs}` : ''}`
    );
  },

  getMarketAssetEvents: async (assetId: string, limit: number = 20) => {
    return request<Array<{
      correlation_id: string;
      event_id: string;
      cluster_id?: string | null;
      event_title: string;
      event_type: string;
      event_time?: string | null;
      importance: number;
      confidence: number;
      window_size: string;
      pre_event_price?: number | null;
      event_price?: number | null;
      post_event_price?: number | null;
      return_percent?: number | null;
      volume_change?: number | null;
      disclaimer: string;
    }>>(`/market-assets/${assetId}/events?limit=${limit}`);
  },

  getEventMarketCorrelations: async (eventId: string, windowSize?: string) => {
    const query = new URLSearchParams();
    if (windowSize) query.set('window_size', windowSize);
    const qs = query.toString();
    return request<import('../types/intelligence').EventMarketCorrelation[]>(
      `/events/${eventId}/market-correlations${qs ? `?${qs}` : ''}`
    );
  },

  computeEventCorrelations: async (
    eventId: string,
    payload: { window_sizes?: string[]; market_asset_ids?: string[] }
  ) => {
    return request<import('../types/intelligence').EventMarketCorrelation[]>(
      `/events/${eventId}/correlate`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    );
  },

  getMarketDashboardSummary: async () => {
    return request<import('../types/intelligence').MarketDashboardSummary>(
      '/market/dashboard-summary'
    );
  },

  searchGlobal: async (query: string, limit: number = 10): Promise<SearchResult> => {
    return request<SearchResult>(`/search?q=${encodeURIComponent(query)}&limit=${limit}`);
  },

  getSystemHealth: async (): Promise<SystemHealth> => {
    return request<SystemHealth>('/health');
  },

  // ==========================================
  // V0.7 RELATIONSHIPS & KNOWLEDGE GRAPH API
  // ==========================================

  getRelationships: async (params?: {
    relationship_type?: string;
    source_entity_id?: string;
    target_entity_id?: string;
    min_confidence?: number;
    page?: number;
    page_size?: number;
  }): Promise<import('../types/intelligence').PaginatedRelationships> => {
    const query = new URLSearchParams();
    if (params?.relationship_type) query.set('relationship_type', params.relationship_type);
    if (params?.source_entity_id) query.set('source_entity_id', params.source_entity_id);
    if (params?.target_entity_id) query.set('target_entity_id', params.target_entity_id);
    if (params?.min_confidence !== undefined) query.set('min_confidence', params.min_confidence.toString());
    if (params?.page) query.set('page', params.page.toString());
    if (params?.page_size) query.set('page_size', params.page_size.toString());
    const qs = query.toString();
    return request<import('../types/intelligence').PaginatedRelationships>(
      `/relationships${qs ? `?${qs}` : ''}`
    );
  },

  getRelationshipById: async (id: string): Promise<import('../types/intelligence').EntityRelationshipWithEntities> => {
    return request<import('../types/intelligence').EntityRelationshipWithEntities>(`/relationships/${id}`);
  },

  getEntityRelationships: async (
    entityId: string
  ): Promise<{
    outbound: import('../types/intelligence').EntityRelationshipWithEntities[];
    inbound: import('../types/intelligence').EntityRelationshipWithEntities[];
    total: number;
  }> => {
    return request(`/entities/${entityId}/relationships`);
  },

  getEntityGraph: async (
    entityId: string,
    depth: number = 1,
    maxDepth: number = 3,
    limit: number = 50
  ): Promise<import('../types/intelligence').KnowledgeGraphResponse> => {
    return request<import('../types/intelligence').KnowledgeGraphResponse>(
      `/entities/${entityId}/graph?depth=${depth}&max_depth=${maxDepth}&limit=${limit}`
    );
  },

  getEventRelationships: async (
    eventId: string
  ): Promise<import('../types/intelligence').EventRelationshipsResponse> => {
    return request<import('../types/intelligence').EventRelationshipsResponse>(
      `/events/${eventId}/relationships`
    );
  },

  getEventImpact: async (
    eventId: string
  ): Promise<import('../types/intelligence').EventImpactAssessmentResponse> => {
    return request<import('../types/intelligence').EventImpactAssessmentResponse>(
      `/events/${eventId}/impact`
    );
  },

  searchGraph: async (
    query: string,
    depth: number = 1,
    limit: number = 50
  ): Promise<import('../types/intelligence').KnowledgeGraphResponse> => {
    return request<import('../types/intelligence').KnowledgeGraphResponse>(
      `/search/graph?q=${encodeURIComponent(query)}&depth=${depth}&limit=${limit}`
    );
  },

  // V0.8 Real-Time Global Intelligence API methods
  getLiveFeed: async (params?: {
    since?: string;
    hours?: number;
    min_importance?: number;
    min_confidence?: number;
    event_type?: string;
    country_code?: string;
    entity_id?: string;
    source_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<import('../types/intelligence').PaginatedLiveFeedResponse> => {
    const query = new URLSearchParams();
    if (params?.since) query.set('since', params.since);
    if (params?.hours) query.set('hours', params.hours.toString());
    if (params?.min_importance !== undefined) query.set('min_importance', params.min_importance.toString());
    if (params?.min_confidence !== undefined) query.set('min_confidence', params.min_confidence.toString());
    if (params?.event_type) query.set('event_type', params.event_type);
    if (params?.country_code) query.set('country_code', params.country_code);
    if (params?.entity_id) query.set('entity_id', params.entity_id);
    if (params?.source_id) query.set('source_id', params.source_id);
    if (params?.limit) query.set('limit', params.limit.toString());
    if (params?.offset) query.set('offset', params.offset.toString());
    const qs = query.toString();
    return request<import('../types/intelligence').PaginatedLiveFeedResponse>(
      `/intelligence/live${qs ? `?${qs}` : ''}`
    );
  },

  getRecentIntelligence: async (hours: number = 24) => {
    return request<{
      window_hours: number;
      total_events_in_window: number;
      freshness_summary: Record<string, number>;
      recent_highlights: Array<{
        event_id: string;
        title: string;
        importance: number;
        confidence: number;
        event_type: string;
        location?: string | null;
        cluster_title?: string | null;
      }>;
    }>(`/intelligence/recent?hours=${hours}`);
  },

  getSourcesHealth: async (): Promise<import('../types/intelligence').SourceHealthSummary[]> => {
    return request<import('../types/intelligence').SourceHealthSummary[]>('/sources/health');
  },

  getIngestionRuns: async (params?: {
    source_id?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<import('../types/intelligence').PaginatedIngestionRuns> => {
    const query = new URLSearchParams();
    if (params?.source_id) query.set('source_id', params.source_id);
    if (params?.status) query.set('status', params.status);
    if (params?.limit) query.set('limit', params.limit.toString());
    if (params?.offset) query.set('offset', params.offset.toString());
    const qs = query.toString();
    return request<import('../types/intelligence').PaginatedIngestionRuns>(
      `/ingestion/runs${qs ? `?${qs}` : ''}`
    );
  },

  getIngestionRun: async (runId: string): Promise<import('../types/intelligence').IngestionRun> => {
    return request<import('../types/intelligence').IngestionRun>(`/ingestion/runs/${runId}`);
  },

  getIngestionStatus: async (): Promise<import('../types/intelligence').IngestionSchedulerStatus> => {
    return request<import('../types/intelligence').IngestionSchedulerStatus>('/ingestion/status');
  },

  triggerIngestion: async (sourceId?: string) => {
    return request<{
      triggered_count: number;
      run_ids: string[];
      message: string;
    }>('/ingestion/trigger', {
      method: 'POST',
      body: JSON.stringify(sourceId ? { source_id: sourceId } : {}),
    });
  },

  getSystemFreshness: async (): Promise<import('../types/intelligence').SystemFreshnessResponse> => {
    return request<import('../types/intelligence').SystemFreshnessResponse>('/system/freshness');
  },

  getAlerts: async (params?: {
    status?: string;
    trigger_type?: string;
    min_importance?: number;
    limit?: number;
    offset?: number;
  }): Promise<import('../types/intelligence').PaginatedAlerts> => {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.trigger_type) query.set('trigger_type', params.trigger_type);
    if (params?.min_importance !== undefined) query.set('min_importance', params.min_importance.toString());
    if (params?.limit) query.set('limit', params.limit.toString());
    if (params?.offset) query.set('offset', params.offset.toString());
    const qs = query.toString();
    return request<import('../types/intelligence').PaginatedAlerts>(`/alerts${qs ? `?${qs}` : ''}`);
  },

  getAlert: async (alertId: string): Promise<import('../types/intelligence').Alert> => {
    return request<import('../types/intelligence').Alert>(`/alerts/${alertId}`);
  },

  acknowledgeAlert: async (alertId: string, note?: string): Promise<import('../types/intelligence').Alert> => {
    return request<import('../types/intelligence').Alert>(`/alerts/${alertId}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify(note ? { note } : {}),
    });
  },

  getSources: async (): Promise<import('../types/intelligence').Source[]> => {
    return request<import('../types/intelligence').Source[]>('/sources');
  },

  updateSource: async (sourceId: string, updates: Partial<import('../types/intelligence').Source>): Promise<import('../types/intelligence').Source> => {
    return request<import('../types/intelligence').Source>(`/sources/${sourceId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  },

  getOperationalMetrics: async (): Promise<import('../types/intelligence').OperationalMetricsResponse> => {
    return request<import('../types/intelligence').OperationalMetricsResponse>('/intelligence/metrics');
  },

  getIngestionBacklog: async (limit: number = 5): Promise<{
    pending_count: number;
    oldest_backlog_document_age_seconds: number | null;
    breakdown_by_status: Record<string, number>;
    sample_pending: Array<{
      document_id: string;
      title: string;
      processing_status: string;
      ingested_at: string;
      source_name: string;
    }>;
  }> => {
    return request(`/ingestion/backlog?limit=${limit}`);
  },

  getSystemCoverage: async (): Promise<import('../types/intelligence').SystemCoverageResponse> => {
    return request<import('../types/intelligence').SystemCoverageResponse>('/system/coverage');
  },

  getMarketTickers: async (): Promise<import('../types/intelligence').CanonicalMarketTicker[]> => {
    return request<import('../types/intelligence').CanonicalMarketTicker[]>('/market/tickers');
  },

  // V0.9-B Geographic Intelligence Contract API methods
  getGeoFeatures: async (params?: {
    min_lon?: number;
    min_lat?: number;
    max_lon?: number;
    max_lat?: number;
    location_state?: string;
    event_type?: string;
    country_code?: string;
    min_importance?: number;
    min_confidence?: number;
    from_time?: string;
    to_time?: string;
    freshness?: string;
    include_unresolved?: boolean;
    page?: number;
    page_size?: number;
  }): Promise<import('../types/intelligence').GeoFeatureCollection> => {
    const query = new URLSearchParams();
    if (params?.min_lon !== undefined) query.set('min_lon', params.min_lon.toString());
    if (params?.min_lat !== undefined) query.set('min_lat', params.min_lat.toString());
    if (params?.max_lon !== undefined) query.set('max_lon', params.max_lon.toString());
    if (params?.max_lat !== undefined) query.set('max_lat', params.max_lat.toString());
    if (params?.location_state) query.set('location_state', params.location_state);
    if (params?.event_type) query.set('event_type', params.event_type);
    if (params?.country_code) query.set('country_code', params.country_code);
    if (params?.min_importance !== undefined) query.set('min_importance', params.min_importance.toString());
    if (params?.min_confidence !== undefined) query.set('min_confidence', params.min_confidence.toString());
    if (params?.from_time) query.set('from_time', params.from_time);
    if (params?.to_time) query.set('to_time', params.to_time);
    if (params?.freshness) query.set('freshness', params.freshness);
    if (params?.include_unresolved !== undefined) query.set('include_unresolved', params.include_unresolved.toString());
    if (params?.page) query.set('page', params.page.toString());
    if (params?.page_size) query.set('page_size', params.page_size.toString());
    const qs = query.toString();
    return request<import('../types/intelligence').GeoFeatureCollection>(`/geo/features${qs ? `?${qs}` : ''}`);
  },

  getGeoEvent: async (eventId: string): Promise<import('../types/intelligence').EventGeographicContext> => {
    return request<import('../types/intelligence').EventGeographicContext>(`/geo/events/${eventId}`);
  },

  getUnresolvedEvents: async (params?: {
    event_type?: string;
    min_importance?: number;
    page?: number;
    page_size?: number;
  }): Promise<import('../types/intelligence').PaginatedUnresolvedEvents> => {
    const query = new URLSearchParams();
    if (params?.event_type) query.set('event_type', params.event_type);
    if (params?.min_importance !== undefined) query.set('min_importance', params.min_importance.toString());
    if (params?.page) query.set('page', params.page.toString());
    if (params?.page_size) query.set('page_size', params.page_size.toString());
    const qs = query.toString();
    return request<import('../types/intelligence').PaginatedUnresolvedEvents>(`/geo/unresolved${qs ? `?${qs}` : ''}`);
  },

  getEventDossier: async (eventId: string): Promise<import('../types/intelligence').EventIntelligenceDossier> => {
    return request<import('../types/intelligence').EventIntelligenceDossier>(`/intelligence/events/${eventId}/dossier`);
  },
};


