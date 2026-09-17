/**
 * Core Dual-Mode Canvas Component for V0.9-C Interactive Globe.
 * Implements:
 * 1. Native HTML5 Canvas 2D render loop (RAF 60 FPS target)
 * 2. ResizeObserver and devicePixelRatio scaling
 * 3. 3D Orthographic and 2D Equirectangular rendering passes
 * 4. Four-state visual discrimination and <=150 individual marker ceiling
 * 5. Pointer drag rotation/pan, wheel zoom, and hit-testing
 */

import React, { useRef, useEffect, useState, useMemo } from 'react';
import type { GeoFeature } from '../../types/intelligence';
import type { MapRenderContext } from '../../utils/geo/markerRenderer';
import {
  renderBasemapBackground,
  renderGraticules,
  renderContinents,
  renderRegionalBoundary,
  renderEventMarker,
} from '../../utils/geo/markerRenderer';
import { useCanvasInteraction } from '../../hooks/useCanvasInteraction';

interface GlobeCanvasProps {
  viewMode: '3d' | '2d';
  centerLon: number;
  centerLat: number;
  zoom: number;
  features: GeoFeature[]; // Filtered, max 150 individual features
  selectedFeatureId: string | null;
  onSelectFeature: (featureId: string | null) => void;
  onRotateCamera: (dLon: number, dLat: number) => void;
  onPanCamera: (dLon: number, dLat: number) => void;
  onZoomCamera: (zoomFactor: number) => void;
  onHoverFeatureChange?: (feature: GeoFeature | null, position: { x: number; y: number } | null) => void;
}

export const GlobeCanvas: React.FC<GlobeCanvasProps> = ({
  viewMode,
  centerLon,
  centerLat,
  zoom,
  features,
  selectedFeatureId,
  onSelectFeature,
  onRotateCamera,
  onPanCamera,
  onZoomCamera,
  onHoverFeatureChange,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [dimensions, setDimensions] = useState<{ width: number; height: number }>({
    width: 800,
    height: 520,
  });
  const [dpr, setDpr] = useState<number>(() =>
    typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1
  );

  // ResizeObserver to handle container resizing and responsive layouts
  useEffect(() => {
    if (!containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setDimensions({
            width: Math.floor(width),
            height: Math.floor(height),
          });
        }
      }
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Monitor devicePixelRatio changes (e.g. moving window between displays)
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const updateDpr = () => {
      setDpr(window.devicePixelRatio || 1);
    };

    const mediaQuery = window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`);
    mediaQuery.addEventListener('change', updateDpr);
    return () => mediaQuery.removeEventListener('change', updateDpr);
  }, []);

  // Compute MapRenderContext based on current dimensions and camera props
  const mapCtx = useMemo((): MapRenderContext => {
    const { width, height } = dimensions;
    const minDim = Math.min(width, height);
    if (viewMode === '3d') {
      const radius = minDim * 0.42 * zoom;
      return {
        viewMode: '3d',
        centerLon,
        centerLat,
        radius,
        centerX: width / 2.0,
        centerY: height / 2.0,
        width,
        height,
      };
    } else {
      return {
        viewMode: '2d',
        centerLon,
        centerLat,
        zoom,
        width,
        height,
      };
    }
  }, [viewMode, centerLon, centerLat, zoom, dimensions]);

  // Handle pointer interactions and hit-testing
  const { hoveredFeature, hoverPosition, isDragging, pointerProps } = useCanvasInteraction({
    mapCtx,
    features,
    selectedFeatureId,
    onSelectFeature,
    onRotateCamera,
    onPanCamera,
    onZoomCamera: (factor) => {
      onZoomCamera(factor);
    },
  });

  // Notify parent of hover state changes
  useEffect(() => {
    if (onHoverFeatureChange) {
      onHoverFeatureChange(hoveredFeature, hoverPosition);
    }
  }, [hoveredFeature, hoverPosition, onHoverFeatureChange]);

  // Main Canvas 2D Render Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animFrameId: number;
    let startTime = performance.now();

    const render = () => {
      const now = performance.now();
      const elapsed = (now - startTime) / 1000.0;
      // 2-second pulse animation cycle (0.0 to 1.0)
      const pulsePhase = (elapsed % 2.0) / 2.0;

      // Set canvas backing buffer scaled by DPR for Retina sharpness
      const targetWidth = Math.floor(dimensions.width * dpr);
      const targetHeight = Math.floor(dimensions.height * dpr);

      if (canvas.width !== targetWidth || canvas.height !== targetHeight) {
        canvas.width = targetWidth;
        canvas.height = targetHeight;
      }

      ctx.save();
      // Scale by DPR so coordinates use CSS pixel units
      ctx.scale(dpr, dpr);

      // 1. Basemap Background (Space / Ocean / Atmosphere)
      renderBasemapBackground(ctx, mapCtx);

      // 2. Graticules (Parallels & Meridians)
      renderGraticules(ctx, mapCtx);

      // 3. Continents & Coastlines
      renderContinents(ctx, mapCtx);

      // 4. Authoritative Regional Boundaries (if applicable)
      renderRegionalBoundary(ctx, 'red_sea', mapCtx, '#eab308');
      renderRegionalBoundary(ctx, 'persian_gulf', mapCtx, '#eab308');

      // 5. Render Discrete Individual Event Markers (<= 150 items)
      for (const feat of features) {
        const isSelected = selectedFeatureId === feat.id;
        const isHovered = hoveredFeature?.id === feat.id;
        renderEventMarker(ctx, feat, mapCtx, isSelected, isHovered, pulsePhase);
      }

      ctx.restore();

      // Continuous RAF loop for smooth pulse animation and fluid drag response
      animFrameId = requestAnimationFrame(render);
    };

    animFrameId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animFrameId);
  }, [dimensions, dpr, mapCtx, features, selectedFeatureId, hoveredFeature]);

  return (
    <div
      ref={containerRef}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        minHeight: '520px',
        overflow: 'hidden',
        background: '#050813',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-subtle)',
        cursor: isDragging ? 'grabbing' : hoveredFeature ? 'pointer' : 'grab',
        touchAction: 'none',
        userSelect: 'none',
      }}
    >
      <canvas
        ref={canvasRef}
        style={{
          display: 'block',
          width: `${dimensions.width}px`,
          height: `${dimensions.height}px`,
        }}
        role="region"
        aria-label={`Interactive Global Intelligence Map (${viewMode === '3d' ? '3D Orthographic Globe' : '2D Flat Map'})`}
        {...pointerProps}
      />
    </div>
  );
};
