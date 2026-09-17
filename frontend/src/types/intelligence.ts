export interface ExtractedEventSummary {
  id: string;
  event_type: string;
  title: string | null;
  description: string | null;
  event_time: string | null;
  location: string | null;
  confidence_score: number;
  importance_score: number;
  extractor_version: string;
  entities: string[];
}

export interface DocumentSummary {
  id: string;
  source_id: string;
  source_name: string;
  title: string;
  url: string | null;
  published_at: string | null;
}

export interface ClusterExplanationScores {
  event_type_score?: number;
  temporal_score?: number;
  location_score?: number;
  actor_overlap_score?: number;
  entity_overlap_score?: number;
  lexical_score?: number;
  final_score?: number;
  threshold?: number;
  time_diff_minutes?: number;
  [key: string]: unknown;
}

export interface EventClusterMember {
  id: string;
  cluster_id: string;
  extracted_event_id: string;
  document_id: string;
  membership_score: number;
  membership_method: string;
  is_representative: boolean;
  metadata_: {
    scores?: ClusterExplanationScores;
    clustering_version?: string;
    [key: string]: unknown;
  };
  extracted_event: ExtractedEventSummary;
  document: DocumentSummary;
}

export interface EntityInCluster {
  entity_id: string;
  canonical_name: string;
  entity_type: string;
  mention_count: number;
}

export interface EventCluster {
  id: string;
  canonical_title: string;
  canonical_summary: string | null;
  event_type: string;
  event_time: string | null;
  location: string | null;
  confidence: number;
  importance: number | null;
  status: string;
  first_event_time: string | null;
  last_event_time: string | null;
  member_count: number;
  unique_source_count: number;
  metadata_: Record<string, unknown>;
  primary_location_entity?: {
    id: string;
    canonical_name: string;
    country_code?: string | null;
  } | null;
  created_at: string;
  updated_at: string;
}

export interface EventClusterDetail extends EventCluster {
  members: EventClusterMember[];
  entities: EntityInCluster[];
}

export interface EventClusterListResponse {
  items: EventCluster[];
  total: number;
  limit: number;
  offset: number;
}

export interface Entity {
  id: string;
  canonical_name: string;
  normalized_name: string;
  entity_type: string;
  country_code: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface EntityListResponse {
  items: Entity[];
  total: number;
  limit: number;
  offset: number;
}

export interface EntityRelatedEventItem {
  id: string;
  document_id: string;
  event_type: string;
  event_title: string;
  event_summary: string | null;
  event_time: string | null;
  location_entity_id: string | null;
  confidence: number;
  importance: number;
  created_at: string;
  updated_at: string;
  location_entity?: {
    id: string;
    canonical_name: string;
    entity_type: string;
  } | null;
}

export interface EconomicSummaryStats {
  total_indicators: number;
  total_observations: number;
  domain_breakdown: Record<string, number>;
  latest_central_bank_decisions: EconomicObservation[];
  recent_major_releases: EconomicObservation[];
}

export interface DashboardSummary {
  active_clusters_count: number;
  total_events_count: number;
  total_documents_count: number;
  active_sources_count: number;
  high_importance_events_count: number;
  event_types_breakdown: Record<string, number>;
  recent_clusters: EventCluster[];
  economic_summary?: EconomicSummaryStats | null;
  market_summary?: MarketDashboardSummary | null;
}

export interface EconomicIndicator {
  id: string;
  canonical_name: string;
  normalized_name: string;
  indicator_type: string;
  country_name: string;
  country_code: string | null;
  unit: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
  total_observations?: number;
}

export interface EconomicIndicatorListResponse {
  items: EconomicIndicator[];
  total: number;
  limit: number;
  offset: number;
}

export interface CentralBankDecisionData {
  decision_type: string;
  rate_change_bps?: number | null;
  target_rate?: number | null;
  previous_rate?: number | null;
}

export interface EconomicObservation {
  id: string;
  indicator_id: string;
  indicator_type: string;
  indicator_canonical_name?: string | null;
  economic_domain?: string | null;
  country_name?: string | null;
  country_code?: string | null;
  observation_period?: string | null;
  observation_date?: string | null;
  reported_value?: number | null;
  reported_unit?: string | null;
  previous_value?: number | null;
  expected_value?: number | null;
  revised_value?: number | null;
  direction?: string | null;
  change_value?: number | null;
  change_percent?: number | null;
  calculation_method?: string | null;
  economic_relevance: number;
  evidence_snippet?: string | null;
  central_bank_decision?: CentralBankDecisionData | null;
  event_id?: string | null;
  document_id?: string | null;
  source_id?: string | null;
  source_name?: string | null;
  metadata_?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface EconomicObservationListResponse {
  items: EconomicObservation[];
  total: number;
  limit: number;
  offset: number;
}

export interface CountryEconomicProfile {
  country_name: string;
  country_code: string | null;
  entity_id: string;
  total_indicators: number;
  total_observations: number;
  indicators: EconomicIndicator[];
  observations_by_domain: Record<string, EconomicObservation[]>;
  central_bank_events: EconomicObservation[];
  recent_observations: EconomicObservation[];
}

export interface SearchResult {
  query: string;
  total_clusters: number;
  total_entities: number;
  total_indicators?: number;
  total_observations?: number;
  total_market_assets?: number;
  clusters: EventCluster[];
  entities: Entity[];
  indicators?: EconomicIndicator[];
  observations?: EconomicObservation[];
  market_assets?: MarketAsset[];
  correlations?: EventMarketCorrelation[];
}

export interface DataQualityReport {
  asset_id?: string | null;
  symbol?: string | null;
  interval?: string | null;
  is_healthy: boolean;
  total_observations: number;
  duplicate_count: number;
  missing_candles_count: number;
  out_of_order_count: number;
  stale_price_count: number;
  gap_count: number;
  gap_details: Array<{
    gap_start: string;
    gap_end: string;
    duration_seconds: number;
    missing_candles: number;
  }>;
  latest_observation_time?: string | null;
  earliest_observation_time?: string | null;
  continuity_ratio: number;
}

export interface MarketObservation {
  id: string;
  market_asset_id: string;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
  source: string;
  interval: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface MarketAsset {
  id: string;
  symbol: string;
  canonical_name: string;
  asset_type: string;
  exchange_venue?: string | null;
  quote_currency?: string | null;
  base_currency?: string | null;
  entity_id?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  latest_observation?: MarketObservation | null;
  recent_observations_count?: number;
  day_return_percent?: number | null;
  data_quality?: DataQualityReport | null;
}

export interface PaginatedMarketAssets {
  items: MarketAsset[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface EventMarketCorrelation {
  id: string;
  event_id: string;
  cluster_id?: string | null;
  market_asset_id: string;
  window_size: string;
  window_start: string;
  window_end: string;
  pre_event_price?: number | null;
  event_price?: number | null;
  post_event_price?: number | null;
  return_percent?: number | null;
  absolute_change?: number | null;
  volatility?: number | null;
  volume_change?: number | null;
  max_excursion?: number | null;
  min_excursion?: number | null;
  calculated_at: string;
  methodology: string;
  disclaimer: string;
  metadata?: Record<string, unknown>;
  market_asset?: MarketAsset | null;
  event_title?: string | null;
  event_type?: string | null;
  event_time?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MarketDashboardSummary {
  total_assets: number;
  asset_counts_by_type: Record<string, number>;
  total_observations: number;
  total_correlations: number;
  top_movers: Array<{
    id: string;
    symbol: string;
    canonical_name: string;
    asset_type: string;
    price: number;
    quote_currency: string;
    return_24h: number;
    timestamp: string;
  }>;
  recent_correlations: EventMarketCorrelation[];
  disclaimer: string;
}

export interface SystemHealth {
  status: string;
  service: string;
  version: string;
}

// ==========================================
// V0.7 RELATIONSHIPS, IMPACT & KNOWLEDGE GRAPH
// ==========================================

export type RelationshipType =
  | 'headquartered_in'
  | 'operates_in'
  | 'member_of'
  | 'owns'
  | 'produces'
  | 'exports'
  | 'governs'
  | 'allied_with'
  | 'leads'
  | 'involves'
  | 'occurs_in'
  | 'associated_with';

export interface EntityRelationship {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: RelationshipType | string;
  confidence: number;
  source_document_id?: string | null;
  source_event_id?: string | null;
  extraction_method: string;
  extractor_version: string;
  evidence: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface EntityRelationshipWithEntities extends EntityRelationship {
  source_entity?: Entity | null;
  target_entity?: Entity | null;
}

export interface PaginatedRelationships {
  items: EntityRelationshipWithEntities[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface GraphNode {
  id: string;
  canonical_name: string;
  label?: string;
  entity_type: string;
  country_code?: string | null;
  metadata?: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: RelationshipType | string;
  confidence: number;
  evidence: string;
  source_document_id?: string | null;
  source_event_id?: string | null;
}

export interface KnowledgeGraphResponse {
  center_node_id: string;
  depth: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
}

export interface EventRelationshipItem {
  target_id: string;
  target_type: 'entity' | 'indicator' | 'market_asset';
  target_name: string;
  relationship_type: string;
  confidence: number;
  evidence: string;
}

export interface EventRelationshipsResponse {
  event_id: string;
  event_title?: string | null;
  relationships: EventRelationshipItem[];
  total: number;
}

export interface EconomicImpactItem {
  indicator_id: string;
  canonical_name: string;
  indicator_type: string;
  observation_period: string;
  reported_value: number;
  reported_unit: string;
  direction?: string | null;
  economic_relevance: number;
  evidence_snippet?: string | null;
}

export interface MarketImpactItem {
  market_asset_id: string;
  symbol: string;
  canonical_name: string;
  asset_type: string;
  window_size: string;
  return_percent?: number | null;
  volatility?: number | null;
  movement_description: string;
  disclaimer: string;
}

export interface EventImpactAssessmentResponse {
  event_id: string;
  event_title?: string | null;
  event_time?: string | null;
  event_importance: number;
  economic_relevance: number;
  market_association_score: number;
  confidence: number;
  disclaimer: string;
  economic_context: EconomicImpactItem[];
  market_context: MarketImpactItem[];
  assessment_notes: string[];
}

export interface Source {
  id: string;
  name: string;
  source_type: string;
  url: string;
  active: boolean;
  polling_interval_seconds: number;
  reliability_score?: number;
  created_at?: string;
  updated_at?: string;
}

// V0.8 Real-Time Intelligence & Ingestion Telemetry Types
export interface SourceHealthSummary {
  source_id: string;
  name?: string;
  source_name?: string;
  source_type: string;
  active?: boolean;
  is_enabled?: boolean;
  feed_url?: string;
  jurisdiction?: string;
  polling_interval_seconds: number;
  reliability_score?: number;
  health_status?: 'HEALTHY' | 'DEGRADED' | 'FAILING' | 'UNKNOWN' | 'INACTIVE' | string;
  freshness_status: 'CURRENT' | 'STALE' | 'FAILED' | 'UNKNOWN' | 'INACTIVE' | string;
  last_successful_fetch_at?: string | null;
  last_attempted_fetch_at?: string | null;
  last_successful_ingestion_at?: string | null;
  latest_published_at_observed?: string | null;
  last_fetch_duration_ms?: number | null;
  last_error_message?: string | null;
  consecutive_failures: number;
  total_failures_count?: number;
  total_documents?: number;
  total_runs?: number;
  total_documents_ingested?: number;
  latest_document_at?: string | null;
  age_seconds?: number | null;
}

export interface IngestionRun {
  id: string;
  source_id: string;
  source_name?: string | null;
  status: 'RUNNING' | 'SUCCESS' | 'PARTIAL_SUCCESS' | 'FAILED' | 'CANCELLED';
  started_at: string;
  completed_at?: string | null;
  documents_discovered: number;
  documents_inserted: number;
  duplicates_skipped?: number;
  documents_duplicate?: number;
  failures_count?: number;
  documents_failed?: number;
  duration_ms?: number;
  error_message?: string | null;
  processing_stats?: Record<string, unknown>;
  duration_seconds?: number | null;
  created_at?: string;
  updated_at?: string;
}

export interface PaginatedIngestionRuns {
  total: number;
  items: IngestionRun[];
}

export interface IngestionSchedulerStatus {
  status: 'RUNNING' | 'IDLE' | 'STOPPED';
  is_active: boolean;
  active_workers: number;
  configured_sources_count: number;
  active_sources_count: number;
  pending_backlog_count: number;
  last_scheduler_run_at?: string | null;
  total_runs_completed: number;
  total_runs_failed: number;
  uptime_seconds: number;
}

export type AlertTriggerType =
  | 'HIGH_IMPORTANCE_EVENT'
  | 'MAJOR_GEOPOLITICAL_EVENT'
  | 'MAJOR_ECONOMIC_RELEASE'
  | 'SIGNIFICANT_SOURCE_UPDATE'
  | 'DATA_QUALITY_FAILURE'
  | 'STALE_SOURCE'
  | 'MARKET_ASSOCIATION';

export type AlertStatus = 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED' | 'DISMISSED';

export interface Alert {
  id: string;
  trigger_type: AlertTriggerType;
  alert_title: string;
  timestamp: string;
  importance: number;
  confidence: number;
  affected_entity_ids: string[];
  affected_event_id?: string | null;
  affected_source_id?: string | null;
  evidence: string;
  explanation: string;
  status: AlertStatus;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PaginatedAlerts {
  total: number;
  items: Alert[];
}

export interface LiveFeedEntityItem {
  id: string;
  canonical_name: string;
  entity_type: string;
  country_code?: string | null;
}

export interface LiveFeedEconomicItem {
  indicator_name: string;
  reported_value?: number | null;
  reported_unit?: string | null;
  direction?: string | null;
  economic_relevance: number;
}

export interface LiveFeedMarketItem {
  symbol: string;
  canonical_name: string;
  window_size: string;
  return_percent: number;
  neutral_observation: string;
}

export interface LiveFeedAlertItem {
  id: string;
  trigger_type: string;
  alert_title: string;
  importance: number;
  status: string;
}

export interface LiveFeedItem {
  event_id: string;
  document_id?: string | null;
  event_title: string;
  event_summary?: string | null;
  event_type: string;
  event_time?: string | null;
  published_at?: string | null;
  ingested_at?: string | null;
  processed_at?: string | null;
  pipeline_duration_seconds?: number | null;
  e2e_latency_seconds?: number | null;
  importance: number;
  confidence: number;
  cluster_id?: string | null;
  cluster_title?: string | null;
  primary_location?: string | null;
  country_code?: string | null;
  source_id?: string | null;
  source_name?: string | null;
  entities: LiveFeedEntityItem[];
  economic_context: LiveFeedEconomicItem[];
  market_context: LiveFeedMarketItem[];
  active_alerts: LiveFeedAlertItem[];
  freshness_status: 'CURRENT' | 'RECENT' | 'STALE' | 'HISTORICAL' | 'UNKNOWN' | 'SYNTHETIC_TEST' | string;
  age_seconds?: number | null;
  provenance_url?: string | null;
  created_at: string;
}

export interface PaginatedLiveFeedResponse {
  total: number;
  items: LiveFeedItem[];
  page: number;
  page_size: number;
  freshness_summary: Record<string, number>;
}

export interface SystemFreshnessResponse {
  system_status: 'HEALTHY' | 'DEGRADED' | 'STALE' | 'UNKNOWN';
  current_time_utc: string;
  sources_total: number;
  sources_current: number;
  sources_stale: number;
  sources_failed: number;
  sources_unknown: number;
  median_ingestion_latency_seconds?: number | null;
  median_processing_latency_seconds?: number | null;
  median_e2e_latency_seconds?: number | null;
  oldest_backlog_document_age_seconds?: number | null;
  pending_backlog_count: number;
  latest_event_time?: string | null;
  latest_market_observation_time?: string | null;
  source_health_breakdown: Array<{
    source_id: string;
    name: string;
    freshness: string;
    age_seconds?: number | null;
    failures: number;
  }>;
}

export interface LatencyPercentiles {
  median_seconds?: number | null;
  p90_seconds?: number | null;
  min_seconds?: number | null;
  max_seconds?: number | null;
  sample_size: number;
}

export interface OperationalMetricsResponse {
  fetch_latency: LatencyPercentiles;
  processing_latency: LatencyPercentiles;
  e2e_latency: LatencyPercentiles;
  pipeline_health: string;
  active_sources_count: number;
  pending_backlog_count: number;
  calculated_at: string;
}

export interface RegionalCoverageInfo {
  region: string;
  score: number;
  rating: 'GOOD' | 'PARTIAL' | 'POOR' | 'NONE';
  active_sources: number;
  total_sources: number;
  weekly_events: number;
  uptime_rate: number;
}

export interface SystemCoverageResponse {
  timestamp: string;
  regional_coverage: {
    theatres: Record<string, RegionalCoverageInfo>;
    ratings_summary: {
      GOOD: number;
      PARTIAL: number;
      POOR: number;
      NONE: number;
    };
    good_or_partial_count: number;
    none_count: number;
    gate_03_pass: boolean;
  };
  domain_coverage: {
    total_domains: number;
    covered_domains_count: number;
    coverage_percent: number;
    domains: Record<string, {
      covered: boolean;
      document_count: number;
    }>;
  };
  primary_source_ratios: {
    total_text_documents: number;
    primary_text_documents: number;
    textual_primary_ratio_pct: number;
    textual_primary_target_pct: number;
    textual_primary_pass: boolean;
    total_telemetry_observations: number;
    primary_telemetry_observations: number;
    telemetry_primary_ratio_pct: number;
    telemetry_primary_pass: boolean;
  };
  information_quality_index: number;
}

export interface CanonicalMarketTicker {
  id: string;
  symbol: string;
  canonical_name: string;
  asset_type: 'crypto' | 'equity_index' | 'forex' | 'commodity' | 'interest_rate' | string;
  exchange_venue: string;
  quote_currency: string;
  base_currency?: string | null;
  price?: number | null;
  source: string;
  timestamp?: string | null;
  return_24h?: number | null;
  observations_count: number;
}

// ==============================================================================
// V0.9-B Geographic Data Contract Interfaces
// ==============================================================================

export type LocationState = 'RESOLVED' | 'APPROXIMATE' | 'REGIONAL' | 'UNRESOLVED';

export type CoordinateSourceType =
  | 'SENSOR'
  | 'OFFICIAL_SOURCE'
  | 'GEOCODED'
  | 'MUNICIPAL'
  | 'COUNTRY'
  | 'REGIONAL'
  | 'UNKNOWN';

export type CoordinatePrecision =
  | 'EXACT_SENSOR_POINT'
  | 'MUNICIPAL_CENTROID'
  | 'TERRITORIAL_CENTROID'
  | 'NONE';

export interface CoordinateProvenance {
  coordinate_source?: string | null;
  coordinate_source_type: CoordinateSourceType;
  coordinate_precision: CoordinatePrecision;
  location_state: LocationState;
  latitude?: number | null;
  longitude?: number | null;
  resolved_at?: string | null;
  confidence?: number | null;
  verification_notes?: string | null;
}

export interface GeographicPoint {
  latitude: number;
  longitude: number;
}

export interface GeographicLocationItem {
  location_name: string;
  location_state: LocationState;
  entity_id?: string | null;
  entity_type?: string | null;
  country_code?: string | null;
  point?: GeographicPoint | null;
  provenance: CoordinateProvenance;
  is_maritime: boolean;
  maritime_zone?: string | null;
}

export interface EventGeographicContext {
  event_id: string;
  location_state: LocationState;
  primary_location?: GeographicLocationItem | null;
  additional_locations: GeographicLocationItem[];
  all_locations: GeographicLocationItem[];
  is_multi_location: boolean;
  has_coordinates: boolean;
  coordinate_provenance?: CoordinateProvenance | null;
}

export interface GeoFeatureGeometry {
  type: 'Point';
  coordinates: [number, number]; // [longitude, latitude]
}

export interface GeoFeatureProperties {
  event_id: string;
  title: string;
  event_type: string;
  importance: number;
  confidence: number;
  event_time?: string | null;
  freshness_status: string;
  location_state: LocationState;
  location_name?: string | null;
  country_code?: string | null;
  is_primary: boolean;
  cluster_id?: string | null;
  cluster_title?: string | null;
  coordinate_source_type: CoordinateSourceType;
  coordinate_precision: CoordinatePrecision;
  is_multi_location: boolean;
  additional_location_count: number;
  is_maritime: boolean;
  associated_assets: string[];
}

export interface GeoFeature {
  type: 'Feature';
  id: string;
  geometry: GeoFeatureGeometry | null;
  properties: GeoFeatureProperties;
}

export interface GeoFeatureCollection {
  type: 'FeatureCollection';
  features: GeoFeature[];
  total: number;
  resolved_count: number;
  approximate_count: number;
  regional_count: number;
  unresolved_count: number;
  page: number;
  page_size: number;
  total_pages: number;
  query_timestamp: string;
}

export interface PaginatedUnresolvedEvents {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: ExtractedEventSummary[];
}

export type EvidenceClass =
  | 'OBSERVED'
  | 'DIRECT'
  | 'HISTORICAL_ASSOCIATION'
  | 'ANALYTICAL_IMPLICATION'
  | 'UNKNOWN';

export interface DossierEntityRef {
  entity_id?: string | null;
  name: string;
  entity_type: string;
  role?: string | null;
  evidence_class: EvidenceClass;
  evidence_snippet?: string | null;
}

export interface DossierImpactEntity {
  entity_id?: string | null;
  name: string;
  entity_type: string;
  rationale: string;
  evidence_class: EvidenceClass;
  confidence: number;
}

export interface DossierCountryImpact {
  country_code: string;
  country_name: string;
  relationship_type: string;
  evidence_class: EvidenceClass;
}

export interface DossierCompanyImpact {
  entity_id?: string | null;
  name: string;
  sector?: string | null;
  exposure_type: string;
  evidence_class: EvidenceClass;
}

export interface DossierSectorImpact {
  sector_name: string;
  impact_direction?: string | null;
  evidence_class: EvidenceClass;
  rationale?: string | null;
}

export interface DossierMarketConnection {
  asset_symbol: string;
  asset_name: string;
  asset_type: string;
  connection_type: string;
  observation_window?: string | null;
  return_percent?: number | null;
  evidence_class: EvidenceClass;
  methodology?: string;
}

export interface DossierEconomicIndicator {
  indicator_code: string;
  indicator_name: string;
  country_code?: string | null;
  reported_value?: number | null;
  reported_unit?: string | null;
  change_percent?: number | null;
  direction?: string | null;
  evidence_class: EvidenceClass;
}

export interface DossierGeopoliticalConnection {
  source_entity: string;
  target_entity: string;
  relationship_type: string;
  evidence_class: EvidenceClass;
  description?: string | null;
}

export interface DossierRelatedEvent {
  event_id: string;
  title: string;
  event_type: string;
  event_time?: string | null;
  relationship_reason: string;
  evidence_class: EvidenceClass;
}

export interface DossierMarketObservation {
  asset_symbol: string;
  price?: number | null;
  change_percent?: number | null;
  timestamp?: string | null;
  evidence_class: EvidenceClass;
}

export interface DossierSourceEvidence {
  source_id?: string | null;
  source_name: string;
  source_domain?: string | null;
  url: string;
  published_at?: string | null;
  fetched_at?: string | null;
  content_hash?: string | null;
  snippet?: string | null;
  evidence_class: EvidenceClass;
}

export interface EventIntelligenceDossier {
  what_happened: {
    event_id: string;
    title: string;
    summary?: string | null;
    event_type: string;
    event_time?: string | null;
    location?: string | null;
    country_code?: string | null;
    [key: string]: unknown;
  };
  why_it_matters: {
    importance_score: number;
    importance_grade: string;
    significance_summary: string;
    cluster_id?: string | null;
    cluster_title?: string | null;
    cluster_status?: string | null;
    [key: string]: unknown;
  };
  directly_involved: DossierEntityRef[];
  directly_affected: DossierEntityRef[];
  potential_beneficiaries: DossierImpactEntity[];
  potential_exposures: DossierImpactEntity[];
  affected_countries: DossierCountryImpact[];
  affected_companies: DossierCompanyImpact[];
  affected_sectors: DossierSectorImpact[];
  commodity_connections: DossierMarketConnection[];
  currency_connections: DossierMarketConnection[];
  equity_connections: DossierMarketConnection[];
  rate_connections: DossierMarketConnection[];
  economic_indicators: DossierEconomicIndicator[];
  geopolitical_connections: DossierGeopoliticalConnection[];
  related_events: DossierRelatedEvent[];
  related_entities: DossierEntityRef[];
  market_observations: DossierMarketObservation[];
  source_evidence: DossierSourceEvidence[];
  confidence: number;
  last_updated: string;
  publication_time?: string | null;
  fetch_time?: string | null;
  ingestion_time?: string | null;
  extraction_time?: string | null;
  intelligence_update_time?: string | null;
}


