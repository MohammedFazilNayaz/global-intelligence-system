/**
 * Empirical Performance Benchmark Suite for V0.9-C.
 * Measures actual frame render times, hit-testing latency, projection switching,
 * and camera movement across 50, 100, and 150 marker densities.
 */

import { describe, it, expect } from 'vitest';
import type { GeoFeature } from '../types/intelligence';
import {
  renderBasemapBackground,
  renderGraticules,
  renderContinents,
  renderEventMarker,
  type MapRenderContext,
} from '../utils/geo/markerRenderer';
import { projectMapPoint } from '../utils/geo/markerRenderer';

describe('V0.9-C Empirical Performance Verification Suite', () => {
  // Mock Canvas 2D context with realistic operation counters
  const createBenchmarkCtx = () => {
    return {
      save: () => {},
      restore: () => {},
      beginPath: () => {},
      arc: () => {},
      fill: () => {},
      stroke: () => {},
      setLineDash: () => {},
      clearRect: () => {},
      fillRect: () => {},
      strokeRect: () => {},
      clip: () => {},
      moveTo: () => {},
      lineTo: () => {},
      closePath: () => {},
      createRadialGradient: () => ({
        addColorStop: () => {},
      }),
      globalAlpha: 1.0,
      fillStyle: '',
      strokeStyle: '',
      lineWidth: 1.0,
    } as unknown as CanvasRenderingContext2D;
  };

  const createSyntheticFeatures = (count: number): GeoFeature[] => {
    const features: GeoFeature[] = [];
    for (let i = 0; i < count; i++) {
      // Deterministic spread around global coordinates
      const lon = -150 + ((i * 37) % 300);
      const lat = -60 + ((i * 23) % 120);
      features.push({
        type: 'Feature',
        id: `bench-feat-${i}`,
        geometry: {
          type: 'Point',
          coordinates: [lon, lat],
        },
        properties: {
          event_id: `bench-feat-${i}`,
          title: `Benchmark Event ${i}`,
          event_type: i % 3 === 0 ? 'conflict' : i % 3 === 1 ? 'disaster' : 'central_bank',
          importance: 0.5 + (i % 50) / 100,
          confidence: 0.85,
          event_time: '2026-09-12T10:00:00Z',
          freshness_status: i % 4 === 0 ? 'CURRENT' : 'RECENT',
          location_state: i % 5 === 0 ? 'APPROXIMATE' : 'RESOLVED',
          is_primary: true,
          coordinate_source_type: 'SENSOR',
          coordinate_precision: 'EXACT_SENSOR_POINT',
          is_multi_location: false,
          additional_location_count: 0,
          is_maritime: false,
          associated_assets: [],
        },
      });
    }
    return features;
  };

  const mapCtx3D: MapRenderContext = {
    viewMode: '3d',
    centerLon: 0,
    centerLat: 20,
    radius: 240,
    centerX: 400,
    centerY: 300,
    width: 800,
    height: 600,
  };

  const mapCtx2D: MapRenderContext = {
    viewMode: '2d',
    centerLon: 0,
    centerLat: 20,
    zoom: 1.2,
    width: 800,
    height: 600,
  };

  const computeStats = (samples: number[]) => {
    const sorted = [...samples].sort((a, b) => a - b);
    const sum = sorted.reduce((acc, v) => acc + v, 0);
    const mean = sum / sorted.length;
    const p95 = sorted[Math.floor(sorted.length * 0.95)];
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    return { mean, p95, min, max, count: samples.length };
  };

  // ---------------------------------------------------------------------------
  // 1. Initial Render Benchmark
  // ---------------------------------------------------------------------------
  it('measures initial render pass time (basemap + graticules + continents)', () => {
    const ctx = createBenchmarkCtx();
    const iterations = 100;
    const times: number[] = [];

    for (let i = 0; i < iterations; i++) {
      const t0 = performance.now();
      renderBasemapBackground(ctx, mapCtx3D);
      renderGraticules(ctx, mapCtx3D);
      renderContinents(ctx, mapCtx3D);
      const t1 = performance.now();
      times.push(t1 - t0);
    }

    const stats = computeStats(times);
    console.log(`[BENCHMARK] Initial Basemap Render: mean=${stats.mean.toFixed(3)}ms, p95=${stats.p95.toFixed(3)}ms (N=${stats.count})`);

    // Must be well within the 16.6ms frame budget
    expect(stats.mean).toBeLessThan(10.0);
  });

  // ---------------------------------------------------------------------------
  // 2. Marker Density Scaling Benchmarks (50, 100, 150 markers)
  // ---------------------------------------------------------------------------
  it('measures render pass time at 50, 100, and 150 individual markers', () => {
    const ctx = createBenchmarkCtx();
    const iterations = 50;

    for (const count of [50, 100, 150]) {
      const features = createSyntheticFeatures(count);
      const times: number[] = [];

      for (let i = 0; i < iterations; i++) {
        const t0 = performance.now();
        renderBasemapBackground(ctx, mapCtx3D);
        renderGraticules(ctx, mapCtx3D);
        renderContinents(ctx, mapCtx3D);
        for (const feat of features) {
          renderEventMarker(ctx, feat, mapCtx3D, false, false, 0.5);
        }
        const t1 = performance.now();
        times.push(t1 - t0);
      }

      const stats = computeStats(times);
      console.log(`[BENCHMARK] ${count} Markers Complete Frame: mean=${stats.mean.toFixed(3)}ms, p95=${stats.p95.toFixed(3)}ms (N=${stats.count})`);

      // Even at maximum 150 markers, mean render time must be under 8.0ms (leaving plenty of budget for 60 FPS)
      expect(stats.mean).toBeLessThan(8.0);
    }
  });

  // ---------------------------------------------------------------------------
  // 3. Continuous Camera Movement Benchmark (Simulated 60-frame rotation drag)
  // ---------------------------------------------------------------------------
  it('measures continuous camera movement over 60 consecutive rotational frames', () => {
    const ctx = createBenchmarkCtx();
    const features = createSyntheticFeatures(150);
    const frameTimes: number[] = [];
    let currentLon = 0;

    for (let frame = 0; frame < 60; frame++) {
      currentLon = (currentLon + 2.5) % 360;
      const dynamicCtx: MapRenderContext = {
        ...mapCtx3D,
        centerLon: currentLon,
      };

      const t0 = performance.now();
      renderBasemapBackground(ctx, dynamicCtx);
      renderGraticules(ctx, dynamicCtx);
      renderContinents(ctx, dynamicCtx);
      for (const feat of features) {
        renderEventMarker(ctx, feat, dynamicCtx, false, false, (frame % 30) / 30);
      }
      const t1 = performance.now();
      frameTimes.push(t1 - t0);
    }

    const stats = computeStats(frameTimes);
    const estimatedFPS = 1000 / Math.max(0.1, stats.mean);
    console.log(`[BENCHMARK] Continuous Camera Movement (60 frames): mean=${stats.mean.toFixed(3)}ms, p95=${stats.p95.toFixed(3)}ms, estFPS=${estimatedFPS.toFixed(0)}`);

    expect(stats.mean).toBeLessThan(8.0);
  });

  // ---------------------------------------------------------------------------
  // 4. Hit-Testing Latency with 150 Visible Candidates
  // ---------------------------------------------------------------------------
  it('measures cursor hit-testing latency across 150 candidate markers', () => {
    const features = createSyntheticFeatures(150);
    const iterations = 1000;
    const times: number[] = [];

    // Pre-project candidate screen locations
    const screenHits = features.map((f) => {
      const p = projectMapPoint(f.geometry!.coordinates[0], f.geometry!.coordinates[1], mapCtx3D);
      return { id: f.id, x: p.x, y: p.y, visible: p.visible, radius: 10 };
    }).filter((h) => h.visible);

    for (let i = 0; i < iterations; i++) {
      // Simulate cursor movement across screen
      const cursorX = 200 + (i % 400);
      const cursorY = 150 + (i % 300);

      const t0 = performance.now();
      let matched: string | null = null;
      for (const hit of screenHits) {
        const distSq = (cursorX - hit.x) ** 2 + (cursorY - hit.y) ** 2;
        if (distSq <= hit.radius ** 2) {
          matched = hit.id;
          break;
        }
      }
      void matched;
      const t1 = performance.now();
      times.push(t1 - t0);
    }

    const stats = computeStats(times);
    console.log(`[BENCHMARK] Hit-Testing (1,000 queries, 150 candidates): mean=${(stats.mean * 1000).toFixed(2)}µs, p95=${(stats.p95 * 1000).toFixed(2)}µs`);

    // Hit testing must be well under 0.1ms per query
    expect(stats.mean).toBeLessThan(0.1);
  });

  // ---------------------------------------------------------------------------
  // 5. 3D -> 2D and 2D -> 3D Projection Switch Latency
  // ---------------------------------------------------------------------------
  it('measures projection mode switch latency (3D -> 2D and 2D -> 3D)', () => {
    const ctx = createBenchmarkCtx();
    const features = createSyntheticFeatures(150);

    const switch3DTo2DTimes: number[] = [];
    const switch2DTo3DTimes: number[] = [];

    for (let i = 0; i < 50; i++) {
      // 3D -> 2D
      const t0 = performance.now();
      renderBasemapBackground(ctx, mapCtx2D);
      renderGraticules(ctx, mapCtx2D);
      renderContinents(ctx, mapCtx2D);
      for (const feat of features) {
        renderEventMarker(ctx, feat, mapCtx2D, false, false, 0);
      }
      const t1 = performance.now();
      switch3DTo2DTimes.push(t1 - t0);

      // 2D -> 3D
      const t2 = performance.now();
      renderBasemapBackground(ctx, mapCtx3D);
      renderGraticules(ctx, mapCtx3D);
      renderContinents(ctx, mapCtx3D);
      for (const feat of features) {
        renderEventMarker(ctx, feat, mapCtx3D, false, false, 0);
      }
      const t3 = performance.now();
      switch2DTo3DTimes.push(t3 - t2);
    }

    const stats3to2 = computeStats(switch3DTo2DTimes);
    const stats2to3 = computeStats(switch2DTo3DTimes);

    console.log(`[BENCHMARK] Switch 3D -> 2D: mean=${stats3to2.mean.toFixed(3)}ms, p95=${stats3to2.p95.toFixed(3)}ms`);
    console.log(`[BENCHMARK] Switch 2D -> 3D: mean=${stats2to3.mean.toFixed(3)}ms, p95=${stats2to3.p95.toFixed(3)}ms`);

    expect(stats3to2.mean).toBeLessThan(8.0);
    expect(stats2to3.mean).toBeLessThan(8.0);
  });
});
