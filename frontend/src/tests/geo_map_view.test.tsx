/**
 * Integration & Component Test Suite for GeoMapView (V0.9-C).
 * Tests rendering, 2D/3D toggle, loading state, error state, empty state,
 * quarantined unresolved badge, and selection dispatch.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { GeoMapView } from '../views/GeoMapView';
import { api } from '../api/client';
import type { GeoFeatureCollection } from '../types/intelligence';

// Mock api client
vi.mock('../api/client', () => ({
  api: {
    getGeoFeatures: vi.fn(),
    getGeoEvent: vi.fn(),
    getUnresolvedEvents: vi.fn(),
  },
}));

describe('GeoMapView Component Suite (V0.9-C)', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock ResizeObserver for jsdom
    if (!window.ResizeObserver) {
      window.ResizeObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
      } as unknown as typeof ResizeObserver;
    }

    // Mock matchMedia for jsdom
    if (!window.matchMedia) {
      window.matchMedia = vi.fn().mockImplementation((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }));
    }

    // Mock HTMLCanvasElement getContext
    HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
      clearRect: vi.fn(),
      fillRect: vi.fn(),
      beginPath: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      stroke: vi.fn(),
      save: vi.fn(),
      restore: vi.fn(),
      scale: vi.fn(),
      clip: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      closePath: vi.fn(),
      strokeRect: vi.fn(),
      setLineDash: vi.fn(),
      createRadialGradient: vi.fn().mockReturnValue({
        addColorStop: vi.fn(),
      }),
      globalAlpha: 1.0,
      fillStyle: '',
      strokeStyle: '',
      lineWidth: 1.0,
    }) as unknown as typeof HTMLCanvasElement.prototype.getContext;
  });

  const mockGeoCollection: GeoFeatureCollection = {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        id: 'feat-1',
        geometry: {
          type: 'Point',
          coordinates: [139.69, 35.68], // Tokyo
        },
        properties: {
          event_id: 'feat-1',
          title: 'Tokyo Municipal Summit on Economic Resilience',
          event_type: 'diplomatic',
          importance: 0.85,
          confidence: 0.92,
          event_time: '2026-09-12T08:00:00Z',
          freshness_status: 'CURRENT',
          location_state: 'RESOLVED',
          is_primary: true,
          coordinate_source_type: 'SENSOR',
          coordinate_precision: 'EXACT_SENSOR_POINT',
          is_multi_location: false,
          additional_location_count: 0,
          is_maritime: false,
          associated_assets: ['N225', 'USD/JPY'],
        },
      },
      {
        type: 'Feature',
        id: 'feat-2',
        geometry: {
          type: 'Point',
          coordinates: [30.52, 50.45], // Kyiv
        },
        properties: {
          event_id: 'feat-2',
          title: 'Kyiv District Security Alert',
          event_type: 'conflict',
          importance: 0.78,
          confidence: 0.88,
          event_time: '2026-09-12T06:00:00Z',
          freshness_status: 'CURRENT',
          location_state: 'APPROXIMATE',
          is_primary: true,
          coordinate_source_type: 'MUNICIPAL',
          coordinate_precision: 'MUNICIPAL_CENTROID',
          is_multi_location: false,
          additional_location_count: 0,
          is_maritime: false,
          associated_assets: [],
        },
      },
      {
        type: 'Feature',
        id: 'feat-3',
        geometry: null, // Regional event (no point)
        properties: {
          event_id: 'feat-3',
          title: 'Red Sea Commercial Shipping Security Update',
          event_type: 'maritime',
          importance: 0.82,
          confidence: 0.90,
          event_time: '2026-09-12T05:00:00Z',
          freshness_status: 'RECENT',
          location_state: 'REGIONAL',
          country_code: 'RED_SEA',
          is_primary: true,
          coordinate_source_type: 'REGIONAL',
          coordinate_precision: 'NONE',
          is_multi_location: false,
          additional_location_count: 0,
          is_maritime: true,
          associated_assets: ['BRENT'],
        },
      },
      {
        type: 'Feature',
        id: 'feat-4',
        geometry: null, // Unresolved
        properties: {
          event_id: 'feat-4',
          title: 'Global Macroeconomic Trend Analysis Paper',
          event_type: 'macro',
          importance: 0.65,
          confidence: 0.80,
          event_time: '2026-09-12T04:00:00Z',
          freshness_status: 'STALE',
          location_state: 'UNRESOLVED',
          is_primary: false,
          coordinate_source_type: 'UNKNOWN',
          coordinate_precision: 'NONE',
          is_multi_location: false,
          additional_location_count: 0,
          is_maritime: false,
          associated_assets: [],
        },
      },
    ],
    total: 4,
    resolved_count: 1,
    approximate_count: 1,
    regional_count: 1,
    unresolved_count: 1,
    page: 1,
    page_size: 50,
    total_pages: 1,
    query_timestamp: '2026-09-12T10:00:00Z',
  };

  it('mounts and renders initial loading overlay, then presents the dual-mode canvas', async () => {
    (api.getGeoFeatures as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockGeoCollection);

    render(<GeoMapView />);

    // Initially loading state is rendered
    expect(screen.getByText('Projecting Geographic Intelligence...')).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText('Interactive Global Intelligence Globe (V0.9-C)')).toBeDefined();
    });

    // Verify stats in header
    expect(screen.getByText(/1 Resolved/)).toBeDefined();
    expect(screen.getByText(/1 Approximate/)).toBeDefined();
    expect(screen.getByText(/1 Regional/)).toBeDefined();

    // Verify Unresolved quarantined badge
    expect(screen.getByText('1')).toBeDefined();
    expect(screen.getByText(/Unlocated Quarantined/)).toBeDefined();

    // Verify canvas element exists
    const canvas = screen.getByRole('region', { name: /Interactive Global Intelligence Map/ });
    expect(canvas).toBeDefined();
  });

  it('toggles between 3D Orthographic and 2D Equirectangular views while preserving camera state', async () => {
    (api.getGeoFeatures as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockGeoCollection);

    render(<GeoMapView />);

    await waitFor(() => {
      expect(screen.getByText('🌐 3D Globe')).toBeDefined();
    });

    const toggleBtn = screen.getByRole('button', { name: /🌐 3D Globe/ });
    fireEvent.click(toggleBtn);

    // View toggles to 2D Map
    expect(screen.getByText('🗺️ 2D Map')).toBeDefined();

    // Camera telemetry remains preserved in header
    expect(screen.getByText(/20.0°N, 0.0°E/)).toBeDefined();

    // Click back to 3D Globe
    fireEvent.click(screen.getByRole('button', { name: /🗺️ 2D Map/ }));
    expect(screen.getByText('🌐 3D Globe')).toBeDefined();
    expect(screen.getByText(/20.0°N, 0.0°E/)).toBeDefined();
  });

  it('renders informative empty state when filters yield 0 features', async () => {
    const emptyCollection: GeoFeatureCollection = {
      ...mockGeoCollection,
      features: [],
      total: 0,
      resolved_count: 0,
      approximate_count: 0,
      regional_count: 0,
      unresolved_count: 0,
    };
    (api.getGeoFeatures as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(emptyCollection);

    render(<GeoMapView />);

    await waitFor(() => {
      expect(screen.getByText('No Matching Intelligence Features')).toBeDefined();
    });
  });

  it('renders non-fatal error banner with Retry button upon API failure', async () => {
    (api.getGeoFeatures as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('Connection timed out (504 Gateway Timeout)')
    );

    render(<GeoMapView />);

    await waitFor(() => {
      expect(screen.getByText('Map Update Interrupted')).toBeDefined();
      expect(screen.getByText(/Connection timed out/)).toBeDefined();
    });

    const retryBtn = screen.getByRole('button', { name: 'Retry' });
    expect(retryBtn).toBeDefined();

    // Mock recovery on retry
    (api.getGeoFeatures as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockGeoCollection);
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByText(/1 Resolved/)).toBeDefined();
    });
  });

  it('renders non-point Regional ledger and opens details on click', async () => {
    (api.getGeoFeatures as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(mockGeoCollection);

    render(<GeoMapView />);

    await waitFor(() => {
      expect(screen.getByText(/Regional Intelligence \(1\)/)).toBeDefined();
    });

    // Expand regional ledger
    fireEvent.click(screen.getByText(/Regional Intelligence \(1\)/));

    expect(screen.getByText('Red Sea Commercial Shipping Security Update')).toBeDefined();
    expect(screen.getByText(/Country-level and maritime events rendered off-point/)).toBeDefined();
  });
});
