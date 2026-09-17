import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EventsView } from '../views/EventsView';
import { EventDetailView } from '../views/EventDetailView';
import { ClusterExplanationBox } from '../components/ClusterExplanationBox';
import { api } from '../api/client';
import type { EventClusterMember } from '../types/intelligence';

vi.mock('../api/client', () => ({
  api: {
    getClusters: vi.fn(),
    getClusterDetail: vi.fn(),
    getEntities: vi.fn(),
    getEntityDetail: vi.fn(),
    getEntityEvents: vi.fn(),
    searchGlobal: vi.fn(),
  },
}));

describe('UI Resilience & State Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state when fetching clusters', async () => {
    // Return a pending promise
    (api.getClusters as any).mockReturnValue(new Promise(() => {}));

    render(<EventsView onSelectCluster={() => {}} />);

    expect(screen.getByText('Querying Intelligence Repository...')).toBeDefined();
    expect(screen.getByText(/Applying filters and pagination/i)).toBeDefined();
  });

  it('renders empty state when no events match the criteria', async () => {
    (api.getClusters as any).mockResolvedValue({
      total: 0,
      page: 1,
      page_size: 15,
      total_pages: 1,
      items: [],
    });

    render(<EventsView onSelectCluster={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('No Matching Intelligence Events')).toBeDefined();
    });
    expect(screen.getByRole('button', { name: /Reset Filters/i })).toBeDefined();
  });

  it('renders error state on API network failure and provides retry button', async () => {
    (api.getClusters as any).mockRejectedValue(new Error('Network connection timeout'));

    render(<EventsView onSelectCluster={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Error Loading Feed')).toBeDefined();
      expect(screen.getByText('Network connection timeout')).toBeDefined();
    });

    const retryBtn = screen.getByRole('button', { name: /Retry/i });
    expect(retryBtn).toBeDefined();

    // Now mock success for retry
    (api.getClusters as any).mockResolvedValue({
      total: 1,
      page: 1,
      page_size: 15,
      total_pages: 1,
      items: [
        {
          id: 'test-c1',
          canonical_title: 'Recovered Event Title',
          canonical_summary: 'Summary description',
          event_type: 'central_bank_decision',
          confidence: 0.95,
          importance: 0.85,
          status: 'ACTIVE',
          member_count: 1,
          unique_source_count: 1,
        },
      ],
    });

    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByText('Recovered Event Title')).toBeDefined();
    });
  });

  it('handles missing optional fields gracefully in EventDetailView without fabricating data', async () => {
    (api.getClusterDetail as any).mockResolvedValue({
      id: 'cluster-missing-data',
      canonical_title: 'Disruption with Ambiguous Details',
      canonical_summary: null, // missing summary
      event_type: 'market_event',
      event_time_start: null, // missing start time
      event_time_end: null, // missing end time
      event_time: null, // missing
      location: null, // missing location
      confidence: 0.7,
      importance: 0.5,
      status: 'ACTIVE',
      member_count: 1,
      unique_source_count: 1,
      members: [],
      entities: [],
    });

    render(<EventDetailView clusterId="cluster-missing-data" onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Disruption with Ambiguous Details')).toBeDefined();
    });

    // Verify it doesn't invent fake locations or timestamps
    expect(screen.getByText('Time unavailable')).toBeDefined();
    expect(screen.getByText('Location unavailable')).toBeDefined();
  });

  it('ClusterExplanationBox does not fabricate 100% scores when breakdown metrics are absent', () => {
    const rawMembers: EventClusterMember[] = [
      {
        id: 'm1',
        cluster_id: 'c1',
        extracted_event_id: 'e1',
        document_id: 'd1',
        membership_score: 0.82,
        membership_method: 'exact_seed',
        is_representative: true,
        metadata_: {},
        extracted_event: {
          id: 'e1',
          event_type: 'central_bank_decision',
          title: 'Seed Event',
          description: 'Seed event description',
          event_time: '2026-09-01T00:00:00Z',
          location: 'Tokyo',
          confidence_score: 0.9,
          importance_score: 0.8,
          extractor_version: 'v0.2',
          entities: ['Entity 1'],
        },
        document: { id: 'd1', title: 'Seed Report', source_name: 'Reuters', source_id: 's1', url: 'https://example.com/1', published_at: '2026-09-01T00:00:00Z' },
      },
      {
        id: 'm2',
        cluster_id: 'c1',
        extracted_event_id: 'e2',
        document_id: 'd2',
        membership_score: 0.82,
        membership_method: 'exact_seed',
        is_representative: false,
        metadata_: {}, // No scores breakdown in metadata
        extracted_event: {
          id: 'e2',
          event_type: 'central_bank_decision',
          title: 'Secondary Event',
          description: 'Secondary event description',
          event_time: '2026-09-01T00:00:00Z',
          location: 'Tokyo',
          confidence_score: 0.85,
          importance_score: 0.75,
          extractor_version: 'v0.2',
          entities: ['Entity 2'],
        },
        document: { id: 'd2', title: 'Secondary Report', source_name: 'Bloomberg', source_id: 's2', url: 'https://example.com/2', published_at: '2026-09-01T00:00:00Z' },
      },
    ];

    render(<ClusterExplanationBox members={rawMembers} />);

    expect(screen.getByText(/Grouped Document: "Secondary Report"/i)).toBeDefined();
    expect(screen.getByText(/\[exact_seed\]/i)).toBeDefined();

    // Verify it explicitly states N/A or not recorded, and does NOT fabricate 100%
    const naElements = screen.getAllByText('N/A');
    expect(naElements.length).toBeGreaterThanOrEqual(4);
    expect(screen.getByText('Type score not recorded')).toBeDefined();
    expect(screen.getByText('Location score not recorded')).toBeDefined();
    expect(screen.getByText('Actor score not recorded')).toBeDefined();
  });
});
