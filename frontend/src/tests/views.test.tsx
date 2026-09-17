import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { DashboardView } from '../views/DashboardView';
import { EventsView } from '../views/EventsView';
import { EventDetailView } from '../views/EventDetailView';
import { api } from '../api/client';
import type { DashboardSummary, EventClusterDetail, EventClusterListResponse } from '../types/intelligence';

vi.mock('../api/client', () => ({
  api: {
    getDashboardSummary: vi.fn(),
    getClusters: vi.fn(),
    getClusterDetail: vi.fn(),
    getEntities: vi.fn(),
    getEntityDetail: vi.fn(),
    getEntityEvents: vi.fn(),
    searchGlobal: vi.fn(),
    getSystemHealth: vi.fn(),
  },
}));

describe('Views Integration Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders DashboardView with real aggregate metrics and category distribution', async () => {
    const mockSummary: DashboardSummary = {
      active_clusters_count: 14,
      total_events_count: 38,
      total_documents_count: 52,
      active_sources_count: 4,
      high_importance_events_count: 6,
      event_types_breakdown: {
        central_bank_decision: 8,
        military_action: 4,
        inflation_report: 2,
      },
      recent_clusters: [],
    };

    (api.getDashboardSummary as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockSummary);

    render(
      <DashboardView
        onSelectCluster={vi.fn()}
        onNavigateToEvents={vi.fn()}
      />
    );

    expect(screen.getByText(/Loading Intelligence Overview/)).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText('Active Clusters')).toBeDefined();
      expect(screen.getByText('14')).toBeDefined();
      expect(screen.getByText('38')).toBeDefined();
      expect(screen.getByText('52')).toBeDefined();
      expect(screen.getAllByText('4').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('6')).toBeDefined();
      expect(screen.getByText(/central bank decision/)).toBeDefined();
    });
  });

  it('renders explicit error state in DashboardView when backend fails', async () => {
    (api.getDashboardSummary as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('Backend connection refused')
    );

    render(
      <DashboardView
        onSelectCluster={vi.fn()}
        onNavigateToEvents={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Operational Error')).toBeDefined();
      expect(screen.getByText('Backend connection refused')).toBeDefined();
    });
  });

  it('renders EventsView with filter toolbar, empty state, and pagination info', async () => {
    const mockList: EventClusterListResponse = {
      items: [],
      total: 0,
      limit: 15,
      offset: 0,
    };

    (api.getClusters as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockList);

    render(<EventsView onSelectCluster={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('No Matching Intelligence Events')).toBeDefined();
      expect(screen.getByText('Category')).toBeDefined();
      expect(screen.getByText('Min Importance')).toBeDefined();
      expect(screen.getByText('Min Confidence')).toBeDefined();
    });
  });

  it('renders EventDetailView with full provenance and evidence table', async () => {
    const mockDetail: EventClusterDetail = {
      id: 'cluster-999',
      canonical_title: 'ECB Raises Benchmark Rate by 25 Basis Points',
      canonical_summary: 'Governing council hikes interest rates.',
      event_type: 'central_bank_decision',
      event_time: '2026-06-01T12:00:00Z',
      location: 'Frankfurt',
      confidence: 0.96,
      importance: 0.85,
      status: 'active',
      first_event_time: '2026-06-01T12:00:00Z',
      last_event_time: '2026-06-01T12:15:00Z',
      member_count: 1,
      unique_source_count: 1,
      metadata_: {},
      created_at: '2026-06-01T12:30:00Z',
      updated_at: '2026-06-01T12:30:00Z',
      entities: [
        {
          entity_id: 'ent-1',
          canonical_name: 'European Central Bank',
          entity_type: 'central_bank',
          mention_count: 2,
        },
      ],
      members: [
        {
          id: 'mem-1',
          cluster_id: 'cluster-999',
          extracted_event_id: 'ee-1',
          document_id: 'doc-1',
          membership_score: 1.0,
          membership_method: 'exact_seed',
          is_representative: true,
          metadata_: {},
          extracted_event: {
            id: 'ee-1',
            event_type: 'central_bank_decision',
            title: 'ECB rate decision',
            description: 'Rate hike',
            event_time: '2026-06-01T12:00:00Z',
            location: 'Frankfurt',
            confidence_score: 0.96,
            importance_score: 0.85,
            extractor_version: 'v0.2.1',
            entities: ['European Central Bank'],
          },
          document: {
            id: 'doc-1',
            source_id: 'src-1',
            source_name: 'Financial Times',
            title: 'ECB tightens monetary policy',
            url: 'https://ft.com/ecb-hike',
            published_at: '2026-06-01T12:05:00Z',
          },
        },
      ],
    };

    (api.getClusterDetail as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockDetail);

    render(<EventDetailView clusterId="cluster-999" onBack={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('ECB Raises Benchmark Rate by 25 Basis Points')).toBeDefined();
      expect(screen.getByText(/Governing council hikes interest rates/)).toBeDefined();
      expect(screen.getByText('Financial Times')).toBeDefined();
      expect(screen.getByText('ECB tightens monetary policy')).toBeDefined();
      expect(screen.getByText('Source Evidence & Provenance Trace')).toBeDefined();
      expect(screen.getByText('CANONICAL SEED')).toBeDefined();
    });
  });
});
