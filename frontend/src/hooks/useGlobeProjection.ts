/**
 * React hook managing camera state and 2D/3D projection parity for V0.9-C.
 * Guarantees that toggling viewMode strictly preserves centerLon, centerLat, and zoom.
 */

import { useState, useCallback, useMemo } from 'react';
import type { MapRenderContext } from '../utils/geo/markerRenderer';
import {
  projectOrthographic,
  projectEquirectangular,
  unprojectOrthographic,
  unprojectEquirectangular,
  normalizeLongitudeDeg,
  type ProjectedPoint,
  type GeographicCoordinate,
} from '../utils/geo/projectionEngine';

export interface UseGlobeProjectionOptions {
  initialLon?: number;
  initialLat?: number;
  initialZoom?: number;
  initialViewMode?: '3d' | '2d';
}

export interface UseGlobeProjectionReturn {
  viewMode: '3d' | '2d';
  centerLon: number;
  centerLat: number;
  zoom: number;
  setViewMode: (mode: '3d' | '2d') => void;
  toggleViewMode: () => void;
  setCenter: (lon: number, lat: number) => void;
  setZoom: (zoom: number | ((prev: number) => number)) => void;
  resetCamera: () => void;
  getRenderContext: (width: number, height: number) => MapRenderContext;
  project: (lon: number, lat: number, width: number, height: number) => ProjectedPoint;
  unproject: (screenX: number, screenY: number, width: number, height: number) => GeographicCoordinate | null;
}

export function useGlobeProjection(
  options: UseGlobeProjectionOptions = {}
): UseGlobeProjectionReturn {
  const [viewMode, setViewModeState] = useState<'3d' | '2d'>(
    options.initialViewMode || '3d'
  );
  const [centerLon, setCenterLon] = useState<number>(
    options.initialLon !== undefined ? normalizeLongitudeDeg(options.initialLon) : 0.0
  );
  const [centerLat, setCenterLat] = useState<number>(
    options.initialLat !== undefined ? Math.max(-85.0, Math.min(85.0, options.initialLat)) : 20.0
  );
  const [zoom, setZoomState] = useState<number>(
    options.initialZoom !== undefined ? options.initialZoom : 1.0
  );

  // Set view mode preserving exact camera focal point and zoom
  const setViewMode = useCallback((mode: '3d' | '2d') => {
    setViewModeState(mode);
  }, []);

  const toggleViewMode = useCallback(() => {
    setViewModeState((prev) => (prev === '3d' ? '2d' : '3d'));
  }, []);

  const setCenter = useCallback((lon: number, lat: number) => {
    setCenterLon(normalizeLongitudeDeg(lon));
    setCenterLat(Math.max(-85.0, Math.min(85.0, lat)));
  }, []);

  const setZoom = useCallback((updater: number | ((prev: number) => number)) => {
    setZoomState((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      return Math.max(0.6, Math.min(5.0, next));
    });
  }, []);

  const resetCamera = useCallback(() => {
    setCenterLon(0.0);
    setCenterLat(20.0);
    setZoomState(1.0);
  }, []);

  // Compute MapRenderContext based on current canvas viewport dimensions
  const getRenderContext = useCallback(
    (width: number, height: number): MapRenderContext => {
      const minDim = Math.min(width, height);
      if (viewMode === '3d') {
        const radius = (minDim * 0.42) * zoom;
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
    },
    [viewMode, centerLon, centerLat, zoom]
  );

  const project = useCallback(
    (lon: number, lat: number, width: number, height: number): ProjectedPoint => {
      const mapCtx = getRenderContext(width, height);
      if (mapCtx.viewMode === '3d') {
        return projectOrthographic(
          lon,
          lat,
          mapCtx.centerLon,
          mapCtx.centerLat,
          mapCtx.radius,
          mapCtx.centerX,
          mapCtx.centerY
        );
      } else {
        return projectEquirectangular(
          lon,
          lat,
          mapCtx.centerLon,
          mapCtx.centerLat,
          mapCtx.zoom,
          mapCtx.width,
          mapCtx.height
        );
      }
    },
    [getRenderContext]
  );

  const unproject = useCallback(
    (
      screenX: number,
      screenY: number,
      width: number,
      height: number
    ): GeographicCoordinate | null => {
      const mapCtx = getRenderContext(width, height);
      if (mapCtx.viewMode === '3d') {
        return unprojectOrthographic(
          screenX,
          screenY,
          mapCtx.centerLon,
          mapCtx.centerLat,
          mapCtx.radius,
          mapCtx.centerX,
          mapCtx.centerY
        );
      } else {
        return unprojectEquirectangular(
          screenX,
          screenY,
          mapCtx.centerLon,
          mapCtx.centerLat,
          mapCtx.zoom,
          mapCtx.width,
          mapCtx.height
        );
      }
    },
    [getRenderContext]
  );

  return useMemo(
    () => ({
      viewMode,
      centerLon,
      centerLat,
      zoom,
      setViewMode,
      toggleViewMode,
      setCenter,
      setZoom,
      resetCamera,
      getRenderContext,
      project,
      unproject,
    }),
    [
      viewMode,
      centerLon,
      centerLat,
      zoom,
      setViewMode,
      toggleViewMode,
      setCenter,
      setZoom,
      resetCamera,
      getRenderContext,
      project,
      unproject,
    ]
  );
}
