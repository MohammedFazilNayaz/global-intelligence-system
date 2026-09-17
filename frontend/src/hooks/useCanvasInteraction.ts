/**
 * React hook for pointer interactions, inertia rotation, wheel zooming, and hit testing for V0.9-C.
 * Enforces:
 * 1. Back-hemisphere features in 3D are strictly NON-INTERACTABLE.
 * 2. Drag-to-rotate in 3D with polar clamping [-85, 85].
 * 3. Drag-to-pan in 2D.
 * 4. High-precision distance hit-testing with hover and selection dispatch.
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import type { GeoFeature } from '../types/intelligence';
import type { MapRenderContext } from '../utils/geo/markerRenderer';
import { projectMapPoint } from '../utils/geo/markerRenderer';

export interface RenderedMarkerHit {
  feature: GeoFeature;
  screenX: number;
  screenY: number;
  hitRadius: number;
}

export interface UseCanvasInteractionOptions {
  mapCtx: MapRenderContext;
  features: GeoFeature[];
  selectedFeatureId: string | null;
  onSelectFeature: (featureId: string | null) => void;
  onRotateCamera: (dLon: number, dLat: number) => void;
  onPanCamera?: (dLon: number, dLat: number) => void;
  onZoomCamera: (zoomDelta: number) => void;
}

export function useCanvasInteraction({
  mapCtx,
  features,
  selectedFeatureId,
  onSelectFeature,
  onRotateCamera,
  onPanCamera,
  onZoomCamera,
}: UseCanvasInteractionOptions) {
  const [hoveredFeature, setHoveredFeature] = useState<GeoFeature | null>(null);
  const [hoverPosition, setHoverPosition] = useState<{ x: number; y: number } | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);

  const lastPointerPos = useRef<{ x: number; y: number } | null>(null);
  const dragDistance = useRef<number>(0);
  const velocityRef = useRef<{ vx: number; vy: number }>({ vx: 0, vy: 0 });
  const animFrameRef = useRef<number | null>(null);

  // Compute active screen positions of visible candidate markers
  const getVisibleMarkerHits = useCallback((): RenderedMarkerHit[] => {
    const hits: RenderedMarkerHit[] = [];

    for (const feat of features) {
      const state = feat.properties.location_state;
      // Regional and Unresolved events never receive point geometry
      if (state === 'REGIONAL' || state === 'UNRESOLVED' || !feat.geometry) continue;

      const [lon, lat] = feat.geometry.coordinates;
      const p = projectMapPoint(lon, lat, mapCtx);

      // Occlusion invariant: points on the back hemisphere in 3D are NOT visible and NOT interactable
      if (!p.visible) continue;

      const baseRadius = 4.0 + 4.0 * Math.max(0.0, Math.min(1.0, feat.properties.importance ?? 0.5));
      const hitRadius = baseRadius + 6.0;

      hits.push({
        feature: feat,
        screenX: p.x,
        screenY: p.y,
        hitRadius,
      });
    }

    return hits;
  }, [features, mapCtx]);

  // Pointer Down (Mouse or Touch)
  const handlePointerDown = useCallback((e: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    setIsDragging(true);
    lastPointerPos.current = { x, y };
    dragDistance.current = 0;
    velocityRef.current = { vx: 0, vy: 0 };

    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }

    // Capture pointer
    e.currentTarget.setPointerCapture(e.pointerId);
  }, []);

  // Pointer Move (Hover Hit-Testing & Dragging)
  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLCanvasElement>) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      if (isDragging && lastPointerPos.current) {
        const dx = x - lastPointerPos.current.x;
        const dy = y - lastPointerPos.current.y;
        dragDistance.current += Math.abs(dx) + Math.abs(dy);

        velocityRef.current = { vx: dx, vy: dy };
        lastPointerPos.current = { x, y };

        if (mapCtx.viewMode === '3d') {
          // In 3D: drag rotates globe around camera focal point
          const radius = mapCtx.radius > 0 ? mapCtx.radius : 200;
          const dLon = -(dx / radius) * 120.0;
          const dLat = (dy / radius) * 120.0;
          onRotateCamera(dLon, dLat);
        } else {
          // In 2D: drag pans across longitude and latitude
          const scaleX = (mapCtx.width / 360.0) * mapCtx.zoom;
          const scaleY = (mapCtx.height / 180.0) * mapCtx.zoom;
          const dLon = -(dx / scaleX);
          const dLat = dy / scaleY;
          if (onPanCamera) {
            onPanCamera(dLon, dLat);
          } else {
            onRotateCamera(dLon, dLat);
          }
        }

        // When dragging, clear hover state
        if (hoveredFeature) {
          setHoveredFeature(null);
          setHoverPosition(null);
        }
      } else {
        // Hover detection when not dragging
        const hits = getVisibleMarkerHits();
        let closestHit: RenderedMarkerHit | null = null;
        let minDistance = Infinity;

        for (const hit of hits) {
          const distSq = (x - hit.screenX) ** 2 + (y - hit.screenY) ** 2;
          if (distSq <= hit.hitRadius ** 2) {
            if (distSq < minDistance) {
              minDistance = distSq;
              closestHit = hit;
            }
          }
        }

        if (closestHit) {
          setHoveredFeature(closestHit.feature);
          setHoverPosition({ x: closestHit.screenX, y: closestHit.screenY });
        } else {
          setHoveredFeature(null);
          setHoverPosition(null);
        }
      }
    },
    [isDragging, mapCtx, onRotateCamera, onPanCamera, hoveredFeature, getVisibleMarkerHits]
  );

  // Pointer Up
  const handlePointerUp = useCallback(
    (e: React.PointerEvent<HTMLCanvasElement>) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      setIsDragging(false);
      lastPointerPos.current = null;

      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {
        // Ignore if pointer capture already released
      }

      // If user merely clicked (minimal drag distance), evaluate hit-test selection
      if (dragDistance.current < 6.0) {
        const hits = getVisibleMarkerHits();
        let clickedHit: RenderedMarkerHit | null = null;
        let minDistance = Infinity;

        for (const hit of hits) {
          const distSq = (x - hit.screenX) ** 2 + (y - hit.screenY) ** 2;
          if (distSq <= hit.hitRadius ** 2) {
            if (distSq < minDistance) {
              minDistance = distSq;
              clickedHit = hit;
            }
          }
        }

        if (clickedHit) {
          onSelectFeature(clickedHit.feature.id);
        } else {
          // Clicking empty space deselects
          if (selectedFeatureId) {
            onSelectFeature(null);
          }
        }
      } else {
        // Apply inertia dampening decay in 3D
        if (mapCtx.viewMode === '3d') {
          let { vx, vy } = velocityRef.current;
          const radius = mapCtx.radius > 0 ? mapCtx.radius : 200;

          const stepInertia = () => {
            vx *= 0.92;
            vy *= 0.92;
            if (Math.abs(vx) > 0.1 || Math.abs(vy) > 0.1) {
              const dLon = -(vx / radius) * 120.0;
              const dLat = (vy / radius) * 120.0;
              onRotateCamera(dLon, dLat);
              animFrameRef.current = requestAnimationFrame(stepInertia);
            } else {
              animFrameRef.current = null;
            }
          };
          animFrameRef.current = requestAnimationFrame(stepInertia);
        }
      }
    },
    [getVisibleMarkerHits, onSelectFeature, selectedFeatureId, mapCtx, onRotateCamera]
  );

  // Pointer Leave
  const handlePointerLeave = useCallback(() => {
    setIsDragging(false);
    lastPointerPos.current = null;
    setHoveredFeature(null);
    setHoverPosition(null);
  }, []);

  // Wheel Zoom
  const handleWheel = useCallback(
    (e: React.WheelEvent<HTMLCanvasElement>) => {
      e.preventDefault();
      // Smooth zoom step
      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
      onZoomCamera(zoomFactor);
    },
    [onZoomCamera]
  );

  // Cleanup inertia animation frame on unmount
  useEffect(() => {
    return () => {
      if (animFrameRef.current !== null) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, []);

  return {
    hoveredFeature,
    hoverPosition,
    isDragging,
    pointerProps: {
      onPointerDown: handlePointerDown,
      onPointerMove: handlePointerMove,
      onPointerUp: handlePointerUp,
      onPointerLeave: handlePointerLeave,
      onWheel: handleWheel,
    },
  };
}
