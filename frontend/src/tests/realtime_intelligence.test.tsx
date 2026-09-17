import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { RealTimeIntelligenceView } from '../views/RealTimeIntelligenceView';
import { SystemStatusView } from '../views/SystemStatusView';
import { api } from '../api/client';
import type {
  PaginatedLiveFeedResponse,
  SystemFreshnessResponse,
  SourceHealthSummary,
  PaginatedIngestionRuns,
  IngestionSchedulerStatus,
  PaginatedAlerts,
} from '../types/intelligence';

vi.mock('../api/client', () => ({
  api: {
    getLiveFeed: vi.fn(),
    getSystemFreshness: vi.fn(),
    getSourcesHealth: vi.fn(),
    getSources: vi.fn(),
    getIngestionRuns: vi.fn(),
    getIngestionStatus: vi.fn(),
    getAlerts: vi.fn(),
    triggerIngestion: vi.fn(),
    acknowledgeAlert: vi.fn(),
    updateSource: vi.fn(),
    getSystemHealth: vi.fn(),
    getDashboardSummary: vi.fn(),
    getAuditLog: vi.fn(),
    getSystemCoverage: vi.fn(),
    getMarketTickers: vi.fn(),
    getOperationalMetrics: vi.fn(),
    getIngestionBacklog: vi.fn(),
  },
}));

describe('RealTimeIntelligenceView Integration Suite (V0.8)', () => {
  const mockFeedResponse: PaginatedLiveFeedResponse = {
    items: [
      {
        event_id: 'evt-101',
        event_title: 'ECB Announces Interest Rate Decision',
        event_type: 'MONETARY_POLICY',
        event_time: '2026-09-11T12:00:00Z',
        age_seconds: 45.0,
        freshness_status: 'CURRENT',
        importance: 0.85,
        confidence: 0.95,
        primary_location: 'Frankfurt',
        country_code: 'DE',
        cluster_id: 'clust-201',
        cluster_title: 'European Central Bank Rate Decision Cycle',
        event_summary: 'Governing Council maintains benchmark interest rate at 3.75%.',
        provenance_url: 'https://ecb.europa.eu/press/pr/2026/09/rates.htm',
        source_name: 'ECB Press Feed',
        entities: [
          { id: 'ent-1', canonical_name: 'European Central Bank', entity_type: 'CENTRAL_BANK' },
          { id: 'ent-2', canonical_name: 'Christine Lagarde', entity_type: 'PERSON' },
        ],
        economic_context: [
          {
            indicator_name: 'Interest Rate',
            reported_value: 3.75,
            reported_unit: '%',
            direction: 'HOLD',
            economic_relevance: 0.9,
          },
        ],
        market_context: [
          {
            symbol: 'EUR/USD',
            canonical_name: 'Euro / US Dollar',
            window_size: '1h',
            return_percent: -0.12,
            neutral_observation: 'EUR/USD moved -0.12% during window',
          },
        ],
        active_alerts: [
          {
            id: 'alt-501',
            trigger_type: 'HIGH_IMPORTANCE_EVENT',
            alert_title: 'High Importance Monetary Policy Event Detected',
            importance: 0.85,
            status: 'ACTIVE',
          },
        ],
        created_at: '2026-09-11T12:00:00Z',
      },
      {
        event_id: 'evt-102',
        event_title: 'US Crude Oil Inventory Report',
        event_type: 'ENERGY_REPORT',
        event_time: '2026-09-11T10:30:00Z',
        age_seconds: 5400.0,
        freshness_status: 'CURRENT',
        importance: 0.60,
        confidence: 0.90,
        primary_location: 'Washington',
        country_code: 'US',
        cluster_id: null,
        cluster_title: null,
        event_summary: 'Commercial crude inventories decreased by 1.8 million barrels.',
        provenance_url: null,
        source_name: 'EIA Official Feed',
        entities: [
          { id: 'ent-3', canonical_name: 'Energy Information Administration', entity_type: 'AGENCY' },
        ],
        economic_context: [],
        market_context: [],
        active_alerts: [],
        created_at: '2026-09-11T10:30:00Z',
      },
    ],
    total: 2,
    page: 1,
    page_size: 15,
    freshness_summary: {
      CURRENT: 2,
      STALE: 0,
      FAILED: 0,
      UNKNOWN: 0,
    },
  };

  const mockFreshness: SystemFreshnessResponse = {
    system_status: 'HEALTHY',
    current_time_utc: '2026-09-11T12:30:00Z',
    sources_total: 5,
    sources_current: 4,
    sources_stale: 1,
    sources_failed: 0,
    sources_unknown: 0,
    pending_backlog_count: 0,
    source_health_breakdown: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.getLiveFeed as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockFeedResponse);
    (api.getSystemFreshness as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockFreshness);
  });

  it('renders live intelligence feed items and metadata', async () => {
    render(<RealTimeIntelligenceView />);

    await waitFor(() => {
      expect(screen.getByText('ECB Announces Interest Rate Decision')).toBeDefined();
      expect(screen.getByText('US Crude Oil Inventory Report')).toBeDefined();
      expect(screen.getByText(/Governing Council maintains benchmark interest rate/i)).toBeDefined();
    });
  });

  it('displays multi-domain context (entities, economic context, market context)', async () => {
    render(<RealTimeIntelligenceView />);

    await waitFor(() => {
      expect(screen.getAllByText(/European Central Bank/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Interest Rate: 3.75%/i)).toBeDefined();
      expect(screen.getByText(/EUR\/USD: -0.12%/i)).toBeDefined();
    });
  });

  it('displays active alert banner when present on live items', async () => {
    render(<RealTimeIntelligenceView />);

    await waitFor(() => {
      expect(screen.getByText(/ALERT: High Importance Monetary Policy Event Detected/i)).toBeDefined();
    });
  });

  it('displays non-causal disclaimer', async () => {
    render(<RealTimeIntelligenceView />);

    await waitFor(() => {
      expect(screen.getByText(/Non-Causal Architecture/i)).toBeDefined();
      expect(screen.getByText(/Correlation does not imply causation/i)).toBeDefined();
    });
  });

  it('handles filtering by minimum importance', async () => {
    render(<RealTimeIntelligenceView />);

    await waitFor(() => {
      expect(screen.getByText('ECB Announces Interest Rate Decision')).toBeDefined();
    });

    const select = screen.getByLabelText(/Min Importance/i);
    fireEvent.change(select, { target: { value: '0.7' } });

    await waitFor(() => {
      expect(api.getLiveFeed).toHaveBeenCalledWith(
        expect.objectContaining({ min_importance: 0.7 })
      );
    });
  });
});

describe('SystemStatusView Real-Time Telemetry Suite (V0.8)', () => {
  const mockSystemHealth = {
    status: 'healthy',
    timestamp: '2026-09-11T12:30:00Z',
    version: '0.8.0',
    db_connected: true,
  };

  const mockDashboardSummary = {
    total_events: 95,
    total_clusters: 20,
    total_entities: 110,
    active_sources: 4,
  };

  const mockSourcesHealth: SourceHealthSummary[] = [
    {
      source_id: 'src-1',
      source_name: 'Federal Reserve RSS',
      source_type: 'RSS',
      jurisdiction: 'US',
      is_enabled: true,
      polling_interval_seconds: 300,
      freshness_status: 'CURRENT',
      last_successful_fetch_at: '2026-09-11T12:00:00Z',
      last_attempted_fetch_at: '2026-09-11T12:00:00Z',
      consecutive_failures: 0,
      last_error_message: null,
      total_runs: 45,
      total_documents_ingested: 120,
    },
    {
      source_id: 'src-2',
      source_name: 'ECB Statements',
      source_type: 'RSS',
      jurisdiction: 'EU',
      is_enabled: false,
      polling_interval_seconds: 600,
      freshness_status: 'STALE',
      last_successful_fetch_at: '2026-09-10T12:00:00Z',
      last_attempted_fetch_at: '2026-09-11T11:00:00Z',
      consecutive_failures: 2,
      last_error_message: 'HTTP 503 Service Unavailable',
      total_runs: 30,
      total_documents_ingested: 85,
    },
  ];

  const mockIngestionRuns: PaginatedIngestionRuns = {
    items: [
      {
        id: 'run-901',
        source_id: 'src-1',
        source_name: 'Federal Reserve RSS',
        started_at: '2026-09-11T12:00:00Z',
        completed_at: '2026-09-11T12:00:02Z',
        status: 'SUCCESS',
        documents_discovered: 5,
        documents_inserted: 2,
        documents_duplicate: 3,
        documents_failed: 0,
        error_message: null,
        duration_ms: 2150.0,
      },
    ],
    total: 1,
  };

  const mockSchedulerStatus: IngestionSchedulerStatus = {
    status: 'RUNNING',
    is_active: true,
    active_workers: 1,
    configured_sources_count: 2,
    active_sources_count: 1,
    pending_backlog_count: 0,
    last_scheduler_run_at: '2026-09-11T12:00:00Z',
    total_runs_completed: 45,
    total_runs_failed: 1,
    uptime_seconds: 3600,
  };

  const mockAlerts: PaginatedAlerts = {
    items: [
      {
        id: 'alt-501',
        trigger_type: 'HIGH_IMPORTANCE_EVENT',
        alert_title: 'High Importance Monetary Policy Event Detected',
        importance: 0.85,
        confidence: 0.95,
        status: 'ACTIVE',
        timestamp: '2026-09-11T12:01:00Z',
        affected_entity_ids: ['ent-1'],
        affected_event_id: 'evt-101',
        evidence: 'Federal Reserve Press Statement',
        explanation: 'Event importance (0.85) exceeded trigger threshold (0.80).',
        created_at: '2026-09-11T12:01:00Z',
        updated_at: '2026-09-11T12:01:00Z',
      },
    ],
    total: 1,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.getSystemHealth as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockSystemHealth);
    (api.getDashboardSummary as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockDashboardSummary);
    (api.getSourcesHealth as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockSourcesHealth);
    (api.getSources as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockSourcesHealth);
    (api.getIngestionRuns as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockIngestionRuns);
    (api.getIngestionStatus as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockSchedulerStatus);
    (api.getSystemFreshness as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      system_status: 'DEGRADED',
      current_time_utc: '2026-09-11T12:30:00Z',
      sources_total: 2,
      sources_current: 1,
      sources_stale: 1,
      sources_failed: 0,
      sources_unknown: 0,
      pending_backlog_count: 0,
      source_health_breakdown: [],
    });
    (api.getAlerts as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockAlerts);
    (api.triggerIngestion as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      triggered_count: 1,
      run_ids: ['run-902'],
      message: 'Ingestion run completed successfully',
    });
    (api.acknowledgeAlert as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...mockAlerts.items[0],
      status: 'ACKNOWLEDGED',
    });
    (api.updateSource as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 'src-1',
      name: 'Federal Reserve RSS',
      active: false,
    });
    (api.getSystemCoverage as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      timestamp: '2026-09-12T12:00:00Z',
      regional_coverage: {
        theatres: {
          'North America': { region: 'North America', score: 0.95, rating: 'GOOD', active_sources: 4, total_sources: 4, weekly_events: 25, uptime_rate: 1.0 },
          'Europe': { region: 'Europe', score: 0.92, rating: 'GOOD', active_sources: 3, total_sources: 3, weekly_events: 18, uptime_rate: 1.0 },
          'Latin America': { region: 'Latin America', score: 0.85, rating: 'GOOD', active_sources: 2, total_sources: 2, weekly_events: 10, uptime_rate: 1.0 },
          'Middle East': { region: 'Middle East', score: 0.88, rating: 'GOOD', active_sources: 2, total_sources: 2, weekly_events: 15, uptime_rate: 1.0 },
          'North Africa': { region: 'North Africa', score: 0.82, rating: 'GOOD', active_sources: 2, total_sources: 2, weekly_events: 8, uptime_rate: 1.0 },
          'Sub-Saharan Africa': { region: 'Sub-Saharan Africa', score: 0.80, rating: 'GOOD', active_sources: 2, total_sources: 2, weekly_events: 7, uptime_rate: 1.0 },
          'South Asia': { region: 'South Asia', score: 0.84, rating: 'GOOD', active_sources: 2, total_sources: 2, weekly_events: 9, uptime_rate: 1.0 },
          'Eurasia': { region: 'Eurasia', score: 0.86, rating: 'GOOD', active_sources: 2, total_sources: 2, weekly_events: 11, uptime_rate: 1.0 },
          'East Asia': { region: 'East Asia', score: 0.89, rating: 'GOOD', active_sources: 2, total_sources: 2, weekly_events: 14, uptime_rate: 1.0 },
          'Southeast Asia': { region: 'Southeast Asia', score: 0.65, rating: 'PARTIAL', active_sources: 1, total_sources: 1, weekly_events: 3, uptime_rate: 1.0 },
          'Oceania': { region: 'Oceania', score: 0.62, rating: 'PARTIAL', active_sources: 1, total_sources: 1, weekly_events: 2, uptime_rate: 1.0 },
        },
        ratings_summary: { GOOD: 9, PARTIAL: 2, POOR: 0, NONE: 0 },
        good_or_partial_count: 11,
        none_count: 0,
        gate_03_pass: true,
      },
      domain_coverage: {
        total_domains: 35,
        covered_domains_count: 30,
        coverage_percent: 85.71,
        domains: {},
      },
      primary_source_ratios: {
        total_text_documents: 1011,
        primary_text_documents: 385,
        textual_primary_ratio_pct: 38.08,
        textual_primary_target_pct: 30.0,
        textual_primary_pass: true,
        total_telemetry_observations: 165,
        primary_telemetry_observations: 165,
        telemetry_primary_ratio_pct: 100.0,
        telemetry_primary_pass: true,
      },
      information_quality_index: 0.896,
    });
    (api.getMarketTickers as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        id: 't-1',
        symbol: 'BTC-USD',
        canonical_name: 'Bitcoin',
        asset_type: 'crypto',
        exchange_venue: 'Coinbase / Binance',
        quote_currency: 'USD',
        price: 88500.0,
        source: 'Binance',
        timestamp: '2026-09-12T12:00:00Z',
        return_24h: 1.25,
        observations_count: 48,
      },
      {
        id: 't-2',
        symbol: 'SPX',
        canonical_name: 'S&P 500 Index',
        asset_type: 'equity_index',
        exchange_venue: 'Cboe / CME',
        quote_currency: 'USD',
        price: 7656.98,
        source: 'EquityIndexFeed',
        timestamp: '2026-09-11T13:30:00Z',
        return_24h: 0.86,
        observations_count: 5,
      },
    ]);
    (api.getOperationalMetrics as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      fetch_latency: { median_seconds: 0.12, p90_seconds: 0.25, sample_size: 50 },
      processing_latency: { median_seconds: 0.38, p90_seconds: 0.65, sample_size: 50 },
      e2e_latency: { median_seconds: 0.45, p90_seconds: 0.88, sample_size: 50 },
      pipeline_health: 'OPTIMAL',
      active_sources_count: 26,
      pending_backlog_count: 0,
      calculated_at: '2026-09-12T12:00:00Z',
    });
  });

  it('renders source health matrix and operational statuses', async () => {
    render(<SystemStatusView />);

    await waitFor(() => {
      expect(screen.getAllByText('Federal Reserve RSS').length).toBeGreaterThan(0);
      expect(screen.getByText('ECB Statements')).toBeDefined();
      expect(screen.getByText('HTTP 503 Service Unavailable')).toBeDefined();
    });
  });

  it('renders ingestion runs telemetry ledger', async () => {
    render(<SystemStatusView />);

    await waitFor(() => {
      expect(screen.getByText('run-901')).toBeDefined();
      expect(screen.getByText('2150ms')).toBeDefined();
      expect(screen.getByText('SUCCESS')).toBeDefined();
    });
  });

  it('renders active alerts and allows acknowledgment', async () => {
    render(<SystemStatusView />);

    await waitFor(() => {
      expect(screen.getByText('High Importance Monetary Policy Event Detected')).toBeDefined();
      expect(screen.getByText(/Event importance \(0.85\) exceeded trigger threshold/i)).toBeDefined();
    });

    const ackButton = screen.getByRole('button', { name: /Acknowledge/i });
    fireEvent.click(ackButton);

    await waitFor(() => {
      expect(api.acknowledgeAlert).toHaveBeenCalledWith('alt-501');
    });
  });

  it('triggers on-demand ingestion run', async () => {
    render(<SystemStatusView />);

    await waitFor(() => {
      expect(screen.getAllByText('Federal Reserve RSS').length).toBeGreaterThan(0);
    });

    const triggerButtons = screen.getAllByRole('button', { name: /Run Now/i });
    expect(triggerButtons.length).toBeGreaterThan(0);
    fireEvent.click(triggerButtons[0]);

    await waitFor(() => {
      expect(api.triggerIngestion).toHaveBeenCalledWith('src-1');
    });
  });

  it('renders 11-region coverage health matrix, 16-asset tickers, and 4-stage pipeline audit', async () => {
    render(<SystemStatusView />);

    await waitFor(() => {
      // 11-region coverage matrix
      expect(screen.getByText(/Global Intelligence Coverage & Multi-Theatre Health Matrix/i)).toBeDefined();
      expect(screen.getByText('North America')).toBeDefined();
      expect(screen.getByText('Latin America')).toBeDefined();
      expect(screen.getByText('Sub-Saharan Africa')).toBeDefined();
      expect(screen.getByText('0.896')).toBeDefined(); // IQI
      expect(screen.getByText('38.08%')).toBeDefined(); // Textual primary ratio

      // 16-asset tickers
      expect(screen.getByText(/Canonical Market Telemetry Tickers/i)).toBeDefined();
      expect(screen.getByText('BTC-USD')).toBeDefined();
      expect(screen.getByText('Binance')).toBeDefined();
      expect(screen.getByText('SPX')).toBeDefined();
      expect(screen.getByText('EquityIndexFeed')).toBeDefined();

      // 4-Stage audit
      expect(screen.getByText(/4-Stage Pipeline Timestamp & Non-Synthetic Provenance Audit/i)).toBeDefined();
      expect(screen.getByText('STAGE 1 (T_pub)')).toBeDefined();
      expect(screen.getByText('STAGE 2 (T_ingest)')).toBeDefined();
      expect(screen.getByText('STAGE 3 (T_proc)')).toBeDefined();
      expect(screen.getByText('STAGE 4 (T_view)')).toBeDefined();
    });
  });
});
