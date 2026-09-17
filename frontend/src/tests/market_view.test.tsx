import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MarketView } from '../views/MarketView';
import { MarketAssetDetailView } from '../views/MarketAssetDetailView';
import { EventDetailView } from '../views/EventDetailView';
import { api } from '../api/client';
import type {
  MarketAsset,
  MarketDashboardSummary,
  PaginatedMarketAssets,
  EventClusterDetail,
  EventMarketCorrelation,
} from '../types/intelligence';

vi.mock('../api/client', () => ({
  api: {
    getMarketDashboardSummary: vi.fn(),
    getMarketAssets: vi.fn(),
    getMarketAssetDetail: vi.fn(),
    getMarketAssetObservations: vi.fn(),
    getMarketAssetEvents: vi.fn(),
    getClusterDetail: vi.fn(),
    getEventMarketCorrelations: vi.fn(),
    computeEventCorrelations: vi.fn(),
  },
}));

describe('V0.6 Market Intelligence Views Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockMarketSummary: MarketDashboardSummary = {
    total_assets: 16,
    asset_counts_by_type: {
      crypto: 2,
      equity_index: 5,
      forex: 4,
      commodity: 3,
      interest_rate: 2,
    },
    total_observations: 480,
    total_correlations: 24,
    top_movers: [
      {
        id: 'asset-btc-001',
        symbol: 'BTC',
        canonical_name: 'Bitcoin',
        asset_type: 'crypto',
        price: 68500.0,
        quote_currency: 'USD',
        return_24h: 2.15,
        timestamp: '2026-09-10T00:00:00Z',
      },
    ],
    recent_correlations: [],
    disclaimer: 'Market movement is temporally associated with the event and does not establish causation.',
  };

  const mockBtcAsset: MarketAsset = {
    id: 'asset-btc-001',
    symbol: 'BTC',
    canonical_name: 'Bitcoin',
    asset_type: 'crypto',
    exchange_venue: 'Binance',
    quote_currency: 'USD',
    base_currency: 'BTC',
    metadata: {},
    created_at: '2026-09-10T00:00:00Z',
    updated_at: '2026-09-10T00:00:00Z',
    latest_observation: {
      id: 'obs-001',
      market_asset_id: 'asset-btc-001',
      timestamp: '2026-09-10T00:00:00Z',
      open: 68000,
      high: 68900,
      low: 67900,
      close: 68500,
      volume: 1250.5,
      source: 'crypto_feed',
      interval: '1h',
      metadata: {},
      created_at: '2026-09-10T00:00:00Z',
      updated_at: '2026-09-10T00:00:00Z',
    },
    day_return_percent: 2.15,
    data_quality: {
      is_healthy: true,
      total_observations: 100,
      duplicate_count: 0,
      missing_candles_count: 0,
      out_of_order_count: 0,
      stale_price_count: 0,
      gap_count: 0,
      gap_details: [],
      continuity_ratio: 1.0,
    },
  };

  const mockPaginatedAssets: PaginatedMarketAssets = {
    items: [mockBtcAsset],
    total: 1,
    page: 1,
    page_size: 50,
    total_pages: 1,
  };

  it('renders MarketView with KPI cards, asset ticker grid, and neutral disclaimer', async () => {
    (api.getMarketDashboardSummary as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockMarketSummary);
    (api.getMarketAssets as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockPaginatedAssets);

    render(<MarketView />);

    expect(screen.getByText('Market Intelligence Desk')).toBeDefined();

    await waitFor(() => {
      expect(screen.getAllByText('Bitcoin').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('BTC').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/68,500/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/2\.15%/).length).toBeGreaterThanOrEqual(1);
      // Verifies neutral disclaimer invariant
      expect(screen.getByText(/Market movements are temporally observed around event timestamps and do not establish causation/)).toBeDefined();
    });
  });

  it('filters assets by category on type pill click', async () => {
    (api.getMarketDashboardSummary as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockMarketSummary);
    (api.getMarketAssets as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockPaginatedAssets);

    render(<MarketView />);

    await waitFor(() => {
      expect(screen.getAllByText('Bitcoin').length).toBeGreaterThanOrEqual(1);
    });

    const cryptoPill = screen.getByText('Crypto');
    fireEvent.click(cryptoPill);

    await waitFor(() => {
      expect(api.getMarketAssets).toHaveBeenCalledWith(
        expect.objectContaining({
          asset_type: 'crypto',
        })
      );
    });
  });

  it('renders MarketAssetDetailView with data quality audit metrics and observations', async () => {
    (api.getMarketAssetDetail as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockBtcAsset);
    (api.getMarketAssetObservations as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      mockBtcAsset.latest_observation!,
    ]);
    (api.getMarketAssetEvents as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        correlation_id: 'corr-001',
        event_id: 'event-001',
        event_title: 'Federal Reserve Rate Decision',
        event_type: 'central_bank_decision',
        window_size: '1h',
        return_percent: 1.85,
        volume_change: 12.4,
        disclaimer: 'Market movement is temporally associated with the event and does not establish causation.',
      },
    ]);

    render(<MarketAssetDetailView assetId="asset-btc-001" />);

    await waitFor(() => {
      expect(screen.getAllByText('BTC').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Bitcoin')).toBeDefined();
      expect(screen.getByText('Data Quality & Feed Continuity Audit')).toBeDefined();
      expect(screen.getByText('100.0%')).toBeDefined(); // continuity
      expect(screen.getByText('Federal Reserve Rate Decision')).toBeDefined();
      expect(screen.getByText('+1.85%')).toBeDefined();
    });
  });

  it('renders Market Context section in EventDetailView with window selector and disclaimer', async () => {
    const mockClusterDetail: EventClusterDetail = {
      id: 'cluster-cpi-001',
      canonical_title: 'US CPI Rises to 3.2% in August',
      canonical_summary: 'Consumer price index accelerates modestly.',
      event_type: 'inflation_report',
      event_time: '2026-08-31T12:30:00Z',
      location: 'Washington, DC',
      confidence: 0.96,
      importance: 0.88,
      status: 'ACTIVE',
      first_event_time: '2026-08-31T12:30:00Z',
      last_event_time: '2026-08-31T12:30:00Z',
      member_count: 2,
      unique_source_count: 2,
      metadata_: {},
      created_at: '2026-08-31T12:30:00Z',
      updated_at: '2026-08-31T12:30:00Z',
      members: [
        {
          id: 'member-001',
          cluster_id: 'cluster-cpi-001',
          extracted_event_id: 'event-cpi-001',
          document_id: 'doc-001',
          membership_score: 0.98,
          membership_method: 'location_domain_match',
          is_representative: true,
          metadata_: {},
          extracted_event: {
            id: 'event-cpi-001',
            event_type: 'inflation_report',
            title: 'US Inflation Rises',
            description: 'US Inflation Rises description',
            event_time: '2026-08-31T12:30:00Z',
            location: 'Washington, DC',
            extractor_version: 'rule_based_v0.2.1',
            confidence_score: 0.95,
            importance_score: 0.88,
            entities: [],
          },
          document: {
            id: 'doc-001',
            source_id: 'src-001',
            title: 'Bureau of Labor Statistics Ingestion',
            url: 'https://example.com/cpi',
            source_name: 'Reuters',
            published_at: '2026-08-31T12:30:00Z',
          },
        },
      ],
      entities: [],
    };

    const mockCorrelations: EventMarketCorrelation[] = [
      {
        id: 'corr-cpi-btc',
        event_id: 'event-cpi-001',
        market_asset_id: 'asset-btc-001',
        window_size: '1h',
        window_start: '2026-08-31T11:30:00Z',
        window_end: '2026-08-31T13:30:00Z',
        pre_event_price: 67200.0,
        event_price: 67500.0,
        post_event_price: 68611.2,
        return_percent: 2.1,
        absolute_change: 1411.2,
        volatility: 0.0085,
        volume_change: 15.2,
        max_excursion: 2.3,
        min_excursion: -0.4,
        calculated_at: '2026-08-31T13:35:00Z',
        methodology: 'window_close_return',
        disclaimer: 'Market movement is temporally associated with the event and does not establish causation.',
        market_asset: mockBtcAsset,
        created_at: '2026-08-31T13:35:00Z',
        updated_at: '2026-08-31T13:35:00Z',
      },
    ];

    (api.getClusterDetail as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockClusterDetail);
    (api.getEventMarketCorrelations as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockCorrelations);
    (api.computeEventCorrelations as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockCorrelations);

    render(<EventDetailView clusterId="cluster-cpi-001" onBack={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(/Market Context & Temporal Asset Alignment/)).toBeDefined();
      expect(screen.getByText(/Market movement is temporally associated with the event and does not establish causation/)).toBeDefined();
    });

    await waitFor(() => {
      expect(screen.getAllByText('BTC').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/\+2\.10%/)).toBeDefined();
      expect(screen.getByText(/67,200/)).toBeDefined();
      expect(screen.getByText(/68,611\.2/)).toBeDefined();
    });
  });
});
