/**
 * Canvas 2D Marker and Basemap Rendering Primitives for V0.9-C.
 * Enforces strict four-state visual discrimination and zero coordinate fabrication.
 */

import type { GeoFeature } from '../../types/intelligence';
import {
  projectOrthographic,
  projectEquirectangular,
  type ProjectedPoint,
} from './projectionEngine';
import {
  generateGraticules,
  CONTINENT_CONTOURS,
  CANONICAL_MARITIME_BOUNDARIES,
} from './basemapContours';

export interface RenderContext3D {
  viewMode: '3d';
  centerLon: number;
  centerLat: number;
  radius: number;
  centerX: number;
  centerY: number;
  width: number;
  height: number;
}

export interface RenderContext2D {
  viewMode: '2d';
  centerLon: number;
  centerLat: number;
  zoom: number;
  width: number;
  height: number;
}

export type MapRenderContext = RenderContext3D | RenderContext2D;

export const CATEGORY_COLORS: Record<string, string> = {
  conflict: '#ef4444',
  war: '#ef4444',
  coup: '#ef4444',
  attack: '#ef4444',
  security: '#ef4444',
  disaster: '#f97316',
  earthquake: '#f97316',
  central_bank: '#10b981',
  interest_rate: '#10b981',
  monetary: '#10b981',
  economic: '#06b6d4',
  macro: '#06b6d4',
  inflation: '#06b6d4',
  sanctions: '#f59e0b',
  trade: '#f59e0b',
  tariff: '#f59e0b',
  diplomatic: '#8b5cf6',
  summit: '#8b5cf6',
  energy: '#eab308',
  oil: '#eab308',
  maritime: '#eab308',
  general: '#64748b',
};

export function getCategoryColor(eventType: string): string {
  const norm = (eventType || '').toLowerCase().trim();
  for (const [key, color] of Object.entries(CATEGORY_COLORS)) {
    if (norm.includes(key)) return color;
  }
  return CATEGORY_COLORS.general;
}

export function getFreshnessOpacity(freshness: string): number {
  switch (freshness) {
    case 'CURRENT':
      return 1.0;
    case 'RECENT':
      return 0.85;
    case 'STALE':
      return 0.50;
    case 'HISTORICAL':
      return 0.30;
    default:
      return 0.40;
  }
}

/**
 * Projects a point according to the active map context.
 */
export function projectMapPoint(
  lon: number,
  lat: number,
  ctxState: MapRenderContext
): ProjectedPoint {
  if (ctxState.viewMode === '3d') {
    return projectOrthographic(
      lon,
      lat,
      ctxState.centerLon,
      ctxState.centerLat,
      ctxState.radius,
      ctxState.centerX,
      ctxState.centerY
    );
  } else {
    return projectEquirectangular(
      lon,
      lat,
      ctxState.centerLon,
      ctxState.centerLat,
      ctxState.zoom,
      ctxState.width,
      ctxState.height
    );
  }
}

/**
 * Renders the 3D Globe base (ocean, limb, atmospheric rim) or 2D background.
 */
export function renderBasemapBackground(
  ctx: CanvasRenderingContext2D,
  mapCtx: MapRenderContext
): void {
  const { width, height } = mapCtx;

  // Clear canvas
  ctx.clearRect(0, 0, width, height);

  // Outer space backdrop
  ctx.fillStyle = '#050813';
  ctx.fillRect(0, 0, width, height);

  if (mapCtx.viewMode === '3d') {
    const { centerX, centerY, radius } = mapCtx;

    // Atmospheric rim glow
    const glowGrad = ctx.createRadialGradient(
      centerX,
      centerY,
      radius * 0.95,
      centerX,
      centerY,
      radius * 1.08
    );
    glowGrad.addColorStop(0.0, 'rgba(56, 189, 248, 0.25)');
    glowGrad.addColorStop(0.5, 'rgba(30, 58, 138, 0.15)');
    glowGrad.addColorStop(1.0, 'rgba(5, 8, 19, 0)');

    ctx.beginPath();
    ctx.arc(centerX, centerY, radius * 1.08, 0, Math.PI * 2);
    ctx.fillStyle = glowGrad;
    ctx.fill();

    // Ocean sphere with subtle radial depth gradient
    const oceanGrad = ctx.createRadialGradient(
      centerX - radius * 0.25,
      centerY - radius * 0.25,
      radius * 0.1,
      centerX,
      centerY,
      radius
    );
    oceanGrad.addColorStop(0.0, '#0a1628');
    oceanGrad.addColorStop(0.7, '#07101f');
    oceanGrad.addColorStop(1.0, '#040914');

    ctx.save();
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
    ctx.fillStyle = oceanGrad;
    ctx.fill();

    // Globe limb stroke
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.restore();
  } else {
    // 2D Equirectangular map frame
    ctx.fillStyle = '#07101f';
    ctx.fillRect(0, 0, width, height);

    // Subtle map border
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1.0;
    ctx.strokeRect(0, 0, width, height);
  }
}

/**
 * Renders graticule grid lines (parallels and meridians).
 */
export function renderGraticules(
  ctx: CanvasRenderingContext2D,
  mapCtx: MapRenderContext
): void {
  const graticules = generateGraticules();

  ctx.save();
  ctx.strokeStyle = 'rgba(51, 65, 85, 0.35)';
  ctx.lineWidth = 0.6;
  ctx.setLineDash([2, 2]);

  if (mapCtx.viewMode === '3d') {
    // Clip to globe circle so graticules do not bleed into space
    ctx.beginPath();
    ctx.arc(mapCtx.centerX, mapCtx.centerY, mapCtx.radius, 0, Math.PI * 2);
    ctx.clip();
  }

  for (const g of graticules) {
    ctx.beginPath();
    let isFirst = true;
    for (const pt of g.points) {
      const p = projectMapPoint(pt[0], pt[1], mapCtx);
      if (p.visible) {
        if (isFirst) {
          ctx.moveTo(p.x, p.y);
          isFirst = false;
        } else {
          ctx.lineTo(p.x, p.y);
        }
      } else {
        isFirst = true;
      }
    }
    ctx.stroke();
  }

  ctx.restore();
}

/**
 * Renders simplified continental landmasses with high spherical fidelity.
 */
export function renderContinents(
  ctx: CanvasRenderingContext2D,
  mapCtx: MapRenderContext
): void {
  ctx.save();
  ctx.strokeStyle = '#2d3f58';
  ctx.fillStyle = 'rgba(23, 33, 50, 0.7)';
  ctx.lineWidth = 1.2;
  ctx.setLineDash([]);

  if (mapCtx.viewMode === '3d') {
    ctx.beginPath();
    ctx.arc(mapCtx.centerX, mapCtx.centerY, mapCtx.radius, 0, Math.PI * 2);
    ctx.clip();
  }

  for (const poly of CONTINENT_CONTOURS) {
    ctx.beginPath();
    let hasDrawn = false;
    for (let i = 0; i < poly.points.length; i++) {
      const pt = poly.points[i];
      const p = projectMapPoint(pt[0], pt[1], mapCtx);
      if (p.visible) {
        if (!hasDrawn) {
          ctx.moveTo(p.x, p.y);
          hasDrawn = true;
        } else {
          ctx.lineTo(p.x, p.y);
        }
      }
    }
    if (hasDrawn) {
      ctx.stroke();
      ctx.fill();
    }
  }

  ctx.restore();
}

/**
 * Renders an authoritative regional polygon contour (if available).
 * Strictly NEVER renders point coordinates.
 */
export function renderRegionalBoundary(
  ctx: CanvasRenderingContext2D,
  zoneKey: string,
  mapCtx: MapRenderContext,
  color: string = '#eab308'
): void {
  const boundary = CANONICAL_MARITIME_BOUNDARIES[zoneKey.toLowerCase()];
  if (!boundary) return;

  ctx.save();
  ctx.strokeStyle = color;
  ctx.fillStyle = color.replace(')', ', 0.15)').replace('rgb', 'rgba').replace('#', 'rgba(');
  ctx.lineWidth = 1.5;
  ctx.setLineDash([4, 2]);

  if (mapCtx.viewMode === '3d') {
    ctx.beginPath();
    ctx.arc(mapCtx.centerX, mapCtx.centerY, mapCtx.radius, 0, Math.PI * 2);
    ctx.clip();
  }

  ctx.beginPath();
  let first = true;
  for (const pt of boundary) {
    const p = projectMapPoint(pt[0], pt[1], mapCtx);
    if (p.visible) {
      if (first) {
        ctx.moveTo(p.x, p.y);
        first = false;
      } else {
        ctx.lineTo(p.x, p.y);
      }
    }
  }
  ctx.closePath();
  ctx.stroke();
  ctx.restore();
}

/**
 * Renders individual event markers adhering to the four-state model.
 *
 * Enforces:
 * - RESOLVED: Solid point + 1.5px white rim + pulse if CURRENT.
 * - APPROXIMATE: Soft disc + dashed perimeter [3, 3] + uncertainty dot.
 * - REGIONAL: ZERO point pixels drawn on canvas.
 * - UNRESOLVED: ZERO pixels drawn on canvas.
 */
export function renderEventMarker(
  ctx: CanvasRenderingContext2D,
  feature: GeoFeature,
  mapCtx: MapRenderContext,
  isSelected: boolean,
  isHovered: boolean,
  pulseAnimationPhase: number = 0 // 0.0 to 1.0
): { rendered: boolean; screenX: number; screenY: number; hitRadius: number } {
  const state = feature.properties.location_state;

  // STRICT INVARIANT: REGIONAL and UNRESOLVED events never receive point coordinates
  if (state === 'REGIONAL' || state === 'UNRESOLVED' || !feature.geometry) {
    return { rendered: false, screenX: 0, screenY: 0, hitRadius: 0 };
  }

  const [lon, lat] = feature.geometry.coordinates;
  const p = projectMapPoint(lon, lat, mapCtx);

  // Occlusion / frustum culling: back hemisphere in 3D or off-screen in 2D
  if (!p.visible) {
    return { rendered: false, screenX: p.x, screenY: p.y, hitRadius: 0 };
  }

  const baseColor = getCategoryColor(feature.properties.event_type);
  const opacity = getFreshnessOpacity(feature.properties.freshness_status);
  const importance = feature.properties.importance ?? 0.5;

  // Marker radius scaling (4px to 8px)
  const baseRadius = 4.0 + 4.0 * Math.max(0.0, Math.min(1.0, importance));
  const effectiveRadius = isHovered || isSelected ? baseRadius + 2.0 : baseRadius;

  ctx.save();
  ctx.globalAlpha = opacity;

  if (state === 'RESOLVED') {
    // -------------------------------------------------------------------------
    // RESOLVED: Authentic point (solid pin + white rim)
    // -------------------------------------------------------------------------

    // Active radar pulse beacon if CURRENT freshness
    if (feature.properties.freshness_status === 'CURRENT' && pulseAnimationPhase > 0) {
      const pulseR = effectiveRadius + pulseAnimationPhase * 10.0;
      const pulseAlpha = Math.max(0, (1.0 - pulseAnimationPhase) * 0.6);
      ctx.beginPath();
      ctx.arc(p.x, p.y, pulseR, 0, Math.PI * 2);
      ctx.strokeStyle = baseColor;
      ctx.lineWidth = 1.5;
      ctx.globalAlpha = pulseAlpha * opacity;
      ctx.stroke();
      ctx.globalAlpha = opacity;
    }

    // Selection ring
    if (isSelected) {
      ctx.beginPath();
      ctx.arc(p.x, p.y, effectiveRadius + 5.0, 0, Math.PI * 2);
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 2.0;
      ctx.stroke();
    }

    // Solid core
    ctx.beginPath();
    ctx.arc(p.x, p.y, effectiveRadius, 0, Math.PI * 2);
    ctx.fillStyle = baseColor;
    ctx.fill();

    // High-contrast rim
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = isSelected ? 2.0 : 1.5;
    ctx.stroke();

  } else if (state === 'APPROXIMATE') {
    // -------------------------------------------------------------------------
    // APPROXIMATE: Visibly distinct from RESOLVED (soft disc + dashed outer ring)
    // -------------------------------------------------------------------------
    const approxRadius = effectiveRadius + 4.0;

    // Soft semi-transparent disc
    ctx.beginPath();
    ctx.arc(p.x, p.y, approxRadius, 0, Math.PI * 2);
    ctx.fillStyle = baseColor;
    ctx.globalAlpha = opacity * 0.35;
    ctx.fill();
    ctx.globalAlpha = opacity;

    // Dashed outer perimeter ring (explicit approximate visual signature)
    ctx.beginPath();
    ctx.arc(p.x, p.y, approxRadius, 0, Math.PI * 2);
    ctx.strokeStyle = baseColor;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([3, 3]);
    ctx.stroke();
    ctx.setLineDash([]); // Reset dash

    // Inner uncertainty center dot
    ctx.beginPath();
    ctx.arc(p.x, p.y, 2.0, 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff';
    ctx.fill();

    // Selection highlight
    if (isSelected) {
      ctx.beginPath();
      ctx.arc(p.x, p.y, approxRadius + 4.0, 0, Math.PI * 2);
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 2.0;
      ctx.stroke();
    }
  }

  ctx.restore();

  return {
    rendered: true,
    screenX: p.x,
    screenY: p.y,
    hitRadius: effectiveRadius + 5.0,
  };
}
