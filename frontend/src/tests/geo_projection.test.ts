/**
 * Mathematical Projection Unit Tests for V0.9-C.
 * Verifies 3D Orthographic, 2D Equirectangular, inverse transforms,
 * occlusion culling, numerical tolerances, antimeridian wrapping, and date-line adjacency.
 */

import { describe, it, expect } from 'vitest';
import {
  projectOrthographic,
  unprojectOrthographic,
  projectEquirectangular,
  unprojectEquirectangular,
  normalizeLongitudeDeg,
  angularLongitudeDifferenceDeg,
  validateCoordinates,
} from '../utils/geo/projectionEngine';

describe('V0.9-C Mathematical Projection Engine', () => {
  const width = 800;
  const height = 600;
  const centerX = width / 2; // 400
  const centerY = height / 2; // 300
  const radius = 240; // Globe radius in pixels

  // ---------------------------------------------------------------------------
  // 1. Validation & Date-Line Adjacency Tests
  // ---------------------------------------------------------------------------
  it('validates coordinate bounds correctly', () => {
    expect(validateCoordinates(0, 0)).toBe(true);
    expect(validateCoordinates(180, 90)).toBe(true);
    expect(validateCoordinates(-180, -90)).toBe(true);
    expect(validateCoordinates(180.1, 0)).toBe(false);
    expect(validateCoordinates(0, 90.1)).toBe(false);
    expect(validateCoordinates(NaN, 0)).toBe(false);
    expect(validateCoordinates(0, NaN)).toBe(false);
  });

  it('verifies antimeridian date-line adjacency between +179.5 and -179.5', () => {
    const diff = angularLongitudeDifferenceDeg(179.5, -179.5);
    // Across the date-line, +179.5 and -179.5 are 1.0 degree apart, not 359.0 degrees
    expect(diff).toBeCloseTo(1.0, 5);
  });

  it('normalizes longitude across +/-180 bounds continuously', () => {
    expect(normalizeLongitudeDeg(180)).toBe(180);
    expect(normalizeLongitudeDeg(-180)).toBe(-180);
    expect(normalizeLongitudeDeg(181)).toBeCloseTo(-179, 5);
    expect(normalizeLongitudeDeg(-181)).toBeCloseTo(179, 5);
    expect(normalizeLongitudeDeg(540)).toBe(180);
  });

  // ---------------------------------------------------------------------------
  // 2. 3D Orthographic Forward Projection Tests
  // ---------------------------------------------------------------------------
  it('projects camera center to exact canvas center', () => {
    // When camera is at (0, 0), point (0, 0) must project exactly to (centerX, centerY)
    const p = projectOrthographic(0, 0, 0, 0, radius, centerX, centerY);
    expect(p.visible).toBe(true);
    expect(p.x).toBeCloseTo(centerX, 5);
    expect(p.y).toBeCloseTo(centerY, 5);
    expect(p.depth).toBeCloseTo(1.0, 5); // cos(c) = 1 at center
  });

  it('projects North and South poles without numerical singularities', () => {
    // North pole (0, 90) with camera at (0, 0)
    const np = projectOrthographic(0, 90, 0, 0, radius, centerX, centerY);
    expect(np.visible).toBe(true);
    expect(np.x).toBeCloseTo(centerX, 5);
    expect(np.y).toBeCloseTo(centerY - radius, 5); // Directly on top limb
    expect(np.depth).toBeCloseTo(0.0, 5);

    // South pole (0, -90) with camera at (0, 0)
    const sp = projectOrthographic(0, -90, 0, 0, radius, centerX, centerY);
    expect(sp.visible).toBe(true);
    expect(sp.x).toBeCloseTo(centerX, 5);
    expect(sp.y).toBeCloseTo(centerY + radius, 5); // Directly on bottom limb
    expect(sp.depth).toBeCloseTo(0.0, 5);
  });

  it('verifies points on the globe limb (c = 90 deg) project to the disk perimeter', () => {
    // Point 90 degrees East of camera along equator: (90, 0) with camera (0, 0)
    const pEast = projectOrthographic(90, 0, 0, 0, radius, centerX, centerY);
    expect(pEast.visible).toBe(true);
    expect(pEast.x).toBeCloseTo(centerX + radius, 5);
    expect(pEast.y).toBeCloseTo(centerY, 5);
    expect(pEast.depth).toBeCloseTo(0.0, 5); // On horizon limb

    // Point 90 degrees West of camera along equator: (-90, 0) with camera (0, 0)
    const pWest = projectOrthographic(-90, 0, 0, 0, radius, centerX, centerY);
    expect(pWest.visible).toBe(true);
    expect(pWest.x).toBeCloseTo(centerX - radius, 5);
    expect(pWest.y).toBeCloseTo(centerY, 5);
    expect(pWest.depth).toBeCloseTo(0.0, 5);
  });

  it('strictly culls points on the occluded back hemisphere (cos c < 0)', () => {
    // Point on exact opposite side of Earth: (180, 0) with camera (0, 0)
    const pBack = projectOrthographic(180, 0, 0, 0, radius, centerX, centerY);
    expect(pBack.visible).toBe(false);
    expect(pBack.depth).toBeLessThan(0); // cos(c) = -1
    expect(pBack.depth).toBeCloseTo(-1.0, 5);

    // Point at 100 degrees longitude (just past limb) with camera (0, 0)
    const pJustPastLimb = projectOrthographic(100, 0, 0, 0, radius, centerX, centerY);
    expect(pJustPastLimb.visible).toBe(false);
    expect(pJustPastLimb.depth).toBeLessThan(0);
  });

  it('verifies continuous rotation across +/-180 antimeridian in 3D', () => {
    // Camera focused at 180 degrees longitude
    const pPos = projectOrthographic(179.5, 0, 180, 0, radius, centerX, centerY);
    const pNeg = projectOrthographic(-179.5, 0, 180, 0, radius, centerX, centerY);

    expect(pPos.visible).toBe(true);
    expect(pNeg.visible).toBe(true);

    // Distance on screen between +179.5 and -179.5 should be small and centered around centerX
    expect(pPos.x).toBeLessThan(centerX);
    expect(pNeg.x).toBeGreaterThan(centerX);
    const screenDist = Math.abs(pNeg.x - pPos.x);
    // At R=240, 1 degree subtends roughly 240 * sin(1 deg) = 4.18 pixels
    expect(screenDist).toBeCloseTo(radius * Math.sin(1.0 * (Math.PI / 180)), 1);
  });

  // ---------------------------------------------------------------------------
  // 3. 3D Orthographic Inverse Projection & Round-Trip Tests
  // ---------------------------------------------------------------------------
  it('inverses center screen coordinates back to focal coordinates accurately', () => {
    const coords = unprojectOrthographic(centerX, centerY, 45, 30, radius, centerX, centerY);
    expect(coords).not.toBeNull();
    expect(coords!.longitude).toBeCloseTo(45, 5);
    expect(coords!.latitude).toBeCloseTo(30, 5);
  });

  it('returns null for screen points outside the globe limb (rho > radius)', () => {
    const coords = unprojectOrthographic(centerX + radius + 10, centerY, 0, 0, radius, centerX, centerY);
    expect(coords).toBeNull();
  });

  it('satisfies round-trip numerical tolerance for visible terrestrial points', () => {
    const testPoints: [number, number][] = [
      [0, 0],
      [20, 35],
      [-45, -20],
      [10, -60],
      [-30, 45],
      [75, 15],
    ];

    const centerLon = 15;
    const centerLat = 10;

    for (const [lon, lat] of testPoints) {
      const proj = projectOrthographic(lon, lat, centerLon, centerLat, radius, centerX, centerY);
      expect(proj.visible).toBe(true);

      const unproj = unprojectOrthographic(proj.x, proj.y, centerLon, centerLat, radius, centerX, centerY);
      expect(unproj).not.toBeNull();
      // Tolerance <= 0.0001 degrees
      expect(unproj!.longitude).toBeCloseTo(lon, 4);
      expect(unproj!.latitude).toBeCloseTo(lat, 4);
    }
  });

  // ---------------------------------------------------------------------------
  // 4. 2D Equirectangular Forward & Inverse Projection Tests
  // ---------------------------------------------------------------------------
  it('projects 2D equirectangular center and boundaries correctly', () => {
    const center = projectEquirectangular(0, 0, 0, 0, 1.0, width, height);
    expect(center.visible).toBe(true);
    expect(center.x).toBeCloseTo(width / 2, 5);
    expect(center.y).toBeCloseTo(height / 2, 5);

    // Top-left corner: (-180, 90) with camera at (0, 0)
    const topLeft = projectEquirectangular(-180, 90, 0, 0, 1.0, width, height);
    expect(topLeft.x).toBeCloseTo(0, 5);
    expect(topLeft.y).toBeCloseTo(0, 5);

    // Bottom-right corner: (180, -90) with camera at (0, 0)
    const bottomRight = projectEquirectangular(180, -90, 0, 0, 1.0, width, height);
    expect(bottomRight.x).toBeCloseTo(width, 5);
    expect(bottomRight.y).toBeCloseTo(height, 5);
  });

  it('satisfies 2D equirectangular round-trip accuracy within numerical tolerances', () => {
    const testPoints: [number, number][] = [
      [0, 0],
      [139.69, 35.68], // Tokyo
      [-77.04, 38.91], // Washington DC
      [30.52, 50.45],  // Kyiv
      [-179.5, -45.0],
      [179.5, 45.0],
    ];

    const centerLon = 10;
    const centerLat = 20;
    const zoom = 1.5;

    for (const [lon, lat] of testPoints) {
      const proj = projectEquirectangular(lon, lat, centerLon, centerLat, zoom, width, height);
      const unproj = unprojectEquirectangular(proj.x, proj.y, centerLon, centerLat, zoom, width, height);

      // Tolerance <= 0.0001 degrees
      expect(unproj.longitude).toBeCloseTo(lon, 4);
      expect(unproj.latitude).toBeCloseTo(lat, 4);
    }
  });
});
