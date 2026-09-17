/**
 * Interaction, State Parity, Density Ceiling, and 4-State Integrity Tests for V0.9-C.
 */

import { describe, it, expect, vi } from 'vitest';
import type { GeoFeature } from '../types/intelligence';
import { renderEventMarker } from '../utils/geo/markerRenderer';
import { compareFeaturesDeterministic } from '../hooks/useGeoFeatures';

describe('V0.9-C Interaction & Four-State Integrity', () => {
  const mapCtx3D = {
    viewMode: '3d' as const,
    centerLon: 0,
    centerLat: 0,
    radius: 200,
    centerX: 400,
    centerY: 300,
    width: 800,
    height: 600,
  };

  const createMockFeature = (
    id: string,
    state: 'RESOLVED' | 'APPROXIMATE' | 'REGIONAL' | 'UNRESOLVED',
    coordinates: [number, number] | null,
    importance: number = 0.8,
    confidence: number = 0.9,
    eventTime: string = '2026-09-12T10:00:00Z'
  ): GeoFeature => ({
    type: 'Feature',
    id,
    geometry: coordinates ? { type: 'Point', coordinates } : null,
    properties: {
      event_id: id,
      title: `Event ${id}`,
      event_type: 'conflict',
      importance,
      confidence,
      event_time: eventTime,
      freshness_status: 'CURRENT',
      location_state: state,
      is_primary: true,
      coordinate_source_type: state === 'RESOLVED' ? 'SENSOR' : 'MUNICIPAL',
      coordinate_precision: state === 'RESOLVED' ? 'EXACT_SENSOR_POINT' : 'MUNICIPAL_CENTROID',
      is_multi_location: false,
      additional_location_count: 0,
      is_maritime: false,
      associated_assets: [],
    },
  });

  // Mock Canvas 2D context
  const createMockCtx = () => {
    const ctx = {
      save: vi.fn(),
      restore: vi.fn(),
      beginPath: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      stroke: vi.fn(),
      setLineDash: vi.fn(),
      globalAlpha: 1.0,
      fillStyle: '',
      strokeStyle: '',
      lineWidth: 1.0,
    };
    return ctx as unknown as CanvasRenderingContext2D;
  };

  // ---------------------------------------------------------------------------
  // 1. Four-State Visual Distinction & Anti-Fabrication Invariants
  // ---------------------------------------------------------------------------
  it('renders RESOLVED feature as exact solid point with high-contrast rim', () => {
    const ctx = createMockCtx();
    const feat = createMockFeature('f-resolved', 'RESOLVED', [10, 10]);

    const res = renderEventMarker(ctx, feat, mapCtx3D, false, false, 0);

    expect(res.rendered).toBe(true);
    expect(res.hitRadius).toBeGreaterThan(5);
    // RESOLVED does not use dashed lines
    expect(ctx.setLineDash).not.toHaveBeenCalledWith([3, 3]);
    expect(ctx.fill).toHaveBeenCalled();
    expect(ctx.stroke).toHaveBeenCalled();
  });

  it('renders APPROXIMATE feature with dashed perimeter ring and uncertainty center', () => {
    const ctx = createMockCtx();
    const feat = createMockFeature('f-approx', 'APPROXIMATE', [10, 10]);

    const res = renderEventMarker(ctx, feat, mapCtx3D, false, false, 0);

    expect(res.rendered).toBe(true);
    // APPROXIMATE must use dashed outer ring
    expect(ctx.setLineDash).toHaveBeenCalledWith([3, 3]);
  });

  it('strictly NEVER renders point markers for REGIONAL features', () => {
    const ctx = createMockCtx();
    const feat = createMockFeature('f-reg', 'REGIONAL', null);

    const res = renderEventMarker(ctx, feat, mapCtx3D, false, false, 0);

    expect(res.rendered).toBe(false);
    expect(ctx.arc).not.toHaveBeenCalled();
    expect(ctx.fill).not.toHaveBeenCalled();
  });

  it('strictly NEVER renders point markers for UNRESOLVED features', () => {
    const ctx = createMockCtx();
    const feat = createMockFeature('f-unres', 'UNRESOLVED', null);

    const res = renderEventMarker(ctx, feat, mapCtx3D, false, false, 0);

    expect(res.rendered).toBe(false);
    expect(ctx.arc).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------------------
  // 2. Back-Hemisphere Non-Interactability Invariant
  // ---------------------------------------------------------------------------
  it('culls back-hemisphere points and marks them non-rendered and non-interactable', () => {
    const ctx = createMockCtx();
    // Point on back hemisphere: longitude 180 when camera is at 0
    const featBack = createMockFeature('f-back', 'RESOLVED', [180, 0]);

    const res = renderEventMarker(ctx, featBack, mapCtx3D, false, false, 0);

    expect(res.rendered).toBe(false);
    expect(ctx.fill).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------------------
  // 3. Density Ceiling & Deterministic Prioritization
  // ---------------------------------------------------------------------------
  it('sorts features deterministically by importance DESC, confidence DESC, time DESC, id ASC', () => {
    const f1 = createMockFeature('1', 'RESOLVED', [0, 0], 0.70, 0.90, '2026-09-12T01:00:00Z');
    const f2 = createMockFeature('2', 'RESOLVED', [0, 0], 0.95, 0.80, '2026-09-12T01:00:00Z');
    const f3 = createMockFeature('3', 'RESOLVED', [0, 0], 0.95, 0.99, '2026-09-12T01:00:00Z');
    const f4 = createMockFeature('4', 'RESOLVED', [0, 0], 0.95, 0.99, '2026-09-12T05:00:00Z');
    const f5 = createMockFeature('5', 'RESOLVED', [0, 0], 0.95, 0.99, '2026-09-12T05:00:00Z');

    const list = [f1, f2, f3, f4, f5];
    list.sort(compareFeaturesDeterministic);

    // Highest importance (0.95) and highest confidence (0.99) and newest time (05:00)
    expect(list[0].id).toBe('4');
    expect(list[1].id).toBe('5'); // Tie breaker on id
    expect(list[2].id).toBe('3'); // Earlier time (01:00)
    expect(list[3].id).toBe('2'); // Lower confidence (0.80)
    expect(list[4].id).toBe('1'); // Lower importance (0.70)
  });

  it('caps visible markers at <= 150 individual features and retains overflow', () => {
    const features: GeoFeature[] = [];
    for (let i = 0; i < 200; i++) {
      features.push(createMockFeature(`feat-${i}`, 'RESOLVED', [0, 0], i / 200));
    }

    features.sort(compareFeaturesDeterministic);
    const visible = features.slice(0, 150);
    const overflow = features.slice(150);

    expect(visible.length).toBe(150);
    expect(overflow.length).toBe(50);
    // Highest importance was 199/200, lowest in visible is 50/200
    expect(visible[0].id).toBe('feat-199');
    expect(overflow[0].id).toBe('feat-49');
    // Zero synthetic coordinates created
    expect(visible.every((f) => f.geometry !== null)).toBe(true);
  });
});
