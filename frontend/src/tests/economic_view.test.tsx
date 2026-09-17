import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { EconomicView } from '../views/EconomicView';
import { api } from '../api/client';
import type {
  EconomicObservationListResponse,
  EconomicIndicatorListResponse,
  EconomicObservation,
} from '../types/intelligence';

vi.mock('../api/client', () => ({
  api: {
    getEconomicObservations: vi.fn(),
    getEconomicIndicators: vi.fn(),
  },
}));

describe('EconomicView Macro Terminal Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockObservation: EconomicObservation = {
    id: 'obs-cpi-001',
    indicator_id: 'ind-cpi-001',
    indicator_type: 'cpi',
    indicator_canonical_name: 'United States Consumer Price Index (CPI)',
    economic_domain: 'Inflation',
    country_name: 'United States',
    country_code: 'US',
    observation_period: 'August',
    observation_date: '2026-08-31T00:00:00Z',
    reported_value: 3.2,
    reported_unit: '%',
    previous_value: 3.0,
    expected_value: 3.1,
    revised_value: null,
    direction: 'increase',
    change_value: 0.2,
    change_percent: 6.67,
    calculation_method: 'derived_difference',
    economic_relevance: 0.98,
    evidence_snippet: 'US CPI rose 3.2% year-over-year in August, compared with 3.0% previously.',
    central_bank_decision: null,
    event_id: 'event-001',
    document_id: 'doc-001',
    source_name: 'Financial Bureau',
    metadata_: {
      relevance_explanation: {
        base_indicator_tier: 0.92,
        major_economic_jurisdiction: 0.05,
        final_economic_relevance: 0.98,
      },
    },
    created_at: '2026-09-10T00:00:00Z',
    updated_at: '2026-09-10T00:00:00Z',
  };

  const mockCbObservation: EconomicObservation = {
    id: 'obs-cb-002',
    indicator_id: 'ind-cb-002',
    indicator_type: 'central_bank_rate',
    indicator_canonical_name: 'Eurozone Policy / Benchmark Interest Rate',
    economic_domain: 'Monetary Policy',
    country_name: 'Eurozone',
    country_code: 'EU',
    observation_period: 'September 2026',
    observation_date: '2026-09-08T00:00:00Z',
    reported_value: 4.0,
    reported_unit: '%',
    previous_value: 3.75,
    expected_value: null,
    revised_value: null,
    direction: 'hike',
    change_value: 0.25,
    change_percent: 6.67,
    calculation_method: 'derived_difference',
    economic_relevance: 1.0,
    evidence_snippet: 'European Central Bank raised its benchmark deposit facility rate by 25 basis points to 4.00%.',
    central_bank_decision: {
      decision_type: 'rate_hike',
      rate_change_bps: 25.0,
      target_rate: 4.0,
      previous_rate: 3.75,
    },
    created_at: '2026-09-10T00:00:00Z',
    updated_at: '2026-09-10T00:00:00Z',
  };

  it('renders Economic Intelligence Desk with observations and central bank desk', async () => {
    const mockObsList: EconomicObservationListResponse = {
      items: [mockObservation, mockCbObservation],
      total: 2,
      limit: 20,
      offset: 0,
    };

    const mockIndList: EconomicIndicatorListResponse = {
      items: [],
      total: 0,
      limit: 10,
      offset: 0,
    };

    (api.getEconomicObservations as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockObsList);
    (api.getEconomicIndicators as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockIndList);

    render(<EconomicView />);

    expect(screen.getByText('Economic Intelligence Desk')).toBeDefined();

    await waitFor(() => {
      // Check Central Bank Policy strip
      expect(screen.getByText(/Central Bank Policy Actions/)).toBeDefined();
      expect(screen.getAllByText('Eurozone Policy / Benchmark Interest Rate').length).toBeGreaterThanOrEqual(1);

      // Check observation rows
      expect(screen.getByText('United States Consumer Price Index (CPI)')).toBeDefined();
      expect(screen.getAllByText('Inflation').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/3\.2/)).toBeDefined();
      expect(screen.getByText('0.98')).toBeDefined();
    });
  });

  it('opens 5-tier provenance modal upon clicking Inspect Trace', async () => {
    const mockObsList: EconomicObservationListResponse = {
      items: [mockObservation],
      total: 1,
      limit: 20,
      offset: 0,
    };

    (api.getEconomicObservations as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockObsList);
    (api.getEconomicIndicators as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 });

    render(<EconomicView />);

    await waitFor(() => {
      expect(screen.getByText('Inspect Trace')).toBeDefined();
    });

    fireEvent.click(screen.getByText('Inspect Trace'));

    await waitFor(() => {
      expect(screen.getByText(/5-Tier Provenance Trace & Audit Chain/)).toBeDefined();
      expect(screen.getByText('Economic Observation')).toBeDefined();
      expect(screen.getByText('Economic Indicator')).toBeDefined();
      expect(screen.getByText('Extracted Event')).toBeDefined();
      expect(screen.getByText('Source Document & Raw Evidence')).toBeDefined();
      expect(screen.getByText('Explainable Economic Relevance')).toBeDefined();
      expect(screen.getByText(/US CPI rose 3.2% year-over-year in August/)).toBeDefined();
    });

    // Close modal
    fireEvent.click(screen.getByText('Close Trace'));
    await waitFor(() => {
      expect(screen.queryByText(/5-Tier Provenance Trace & Audit Chain/)).toBeNull();
    });
  });

  it('displays empty state when no observations match query filters', async () => {
    (api.getEconomicObservations as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    });
    (api.getEconomicIndicators as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 });

    render(<EconomicView />);

    await waitFor(() => {
      expect(screen.getByText('No Economic Observations Found')).toBeDefined();
    });
  });
});
