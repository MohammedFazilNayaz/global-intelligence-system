/**
 * React hook for loading and managing geographic intelligence features for V0.9-C.
 * Enforces:
 * 1. Read-only consumption of GET /api/v1/geo/features
 * 2. Deterministic <=150 individual marker ceiling
 * 3. Four-state partitioning (RESOLVED, APPROXIMATE, REGIONAL, UNRESOLVED)
 * 4. Zero coordinate fabrication (overflow and regional items kept in state, not synthesized)
 * 5. Malformed data resilience (invalid features quarantined without crashing)
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { api } from '../api/client';
import type { GeoFeature, GeoFeatureCollection } from '../types/intelligence';
import { validateCoordinates } from '../utils/geo/projectionEngine';

export interface UseGeoFeaturesParams {
  locationState?: string;
  eventType?: string;
  countryCode?: string;
  minImportance?: number;
  minConfidence?: number;
  freshness?: string;
  pageSize?: number;
}

export interface UseGeoFeaturesReturn {
  loading: boolean;
  error: string | null;
  rawCollection: GeoFeatureCollection | null;
  renderedFeatures: GeoFeature[]; // At most 150 individual features
  overflowFeatures: GeoFeature[]; // Features excluded by density ceiling (kept in state)
  regionalFeatures: GeoFeature[]; // Non-point regional events
  unresolvedCount: number;        // Spatially unlocated count (quarantined)
  totalMatching: number;
  resolvedCount: number;
  approximateCount: number;
  regionalCount: number;
  refetch: () => void;
}

export const MAX_VISIBLE_MARKERS = 150;

/**
 * Deterministic sort comparator for feature prioritization:
 * 1. importance DESC
 * 2. confidence DESC
 * 3. event_time DESC
 * 4. id ASC (deterministic tie-breaker)
 */
export function compareFeaturesDeterministic(a: GeoFeature, b: GeoFeature): number {
  const impA = a.properties.importance ?? 0;
  const impB = b.properties.importance ?? 0;
  if (impA !== impB) return impB - impA;

  const confA = a.properties.confidence ?? 0;
  const confB = b.properties.confidence ?? 0;
  if (confA !== confB) return confB - confA;

  const timeA = a.properties.event_time ? new Date(a.properties.event_time).getTime() : 0;
  const timeB = b.properties.event_time ? new Date(b.properties.event_time).getTime() : 0;
  if (timeA !== timeB) return timeB - timeA;

  return a.id.localeCompare(b.id);
}

export function useGeoFeatures(params: UseGeoFeaturesParams = {}): UseGeoFeaturesReturn {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [rawCollection, setRawCollection] = useState<GeoFeatureCollection | null>(null);

  const fetchFeatures = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getGeoFeatures({
        location_state: params.locationState && params.locationState !== 'ALL' ? params.locationState : undefined,
        event_type: params.eventType && params.eventType !== 'ALL' ? params.eventType : undefined,
        country_code: params.countryCode,
        min_importance: params.minImportance,
        min_confidence: params.minConfidence,
        freshness: params.freshness && params.freshness !== 'ALL' ? params.freshness : undefined,
        include_unresolved: true, // We want unresolved counts for the off-map badge
        page_size: params.pageSize || 200,
      });
      setRawCollection(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve geographic features';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [
    params.locationState,
    params.eventType,
    params.countryCode,
    params.minImportance,
    params.minConfidence,
    params.freshness,
    params.pageSize,
  ]);

  useEffect(() => {
    fetchFeatures();
  }, [fetchFeatures]);

  // Partition and enforce the 150 individual marker ceiling
  const partitioned = useMemo(() => {
    if (!rawCollection || !rawCollection.features) {
      return {
        renderedFeatures: [],
        overflowFeatures: [],
        regionalFeatures: [],
        unresolvedCount: 0,
        resolvedCount: 0,
        approximateCount: 0,
        regionalCount: 0,
        totalMatching: 0,
      };
    }

    const spatialCandidates: GeoFeature[] = [];
    const regionalFeatures: GeoFeature[] = [];
    let unresolvedCount = 0;
    let resolvedCount = 0;
    let approximateCount = 0;
    let regionalCount = 0;

    for (const feat of rawCollection.features) {
      const state = feat.properties?.location_state;

      // Malformed feature resilience
      if (!feat.id || !feat.properties) {
        unresolvedCount++;
        continue;
      }

      if (state === 'RESOLVED' || state === 'APPROXIMATE') {
        if (
          feat.geometry &&
          feat.geometry.type === 'Point' &&
          Array.isArray(feat.geometry.coordinates) &&
          feat.geometry.coordinates.length >= 2 &&
          validateCoordinates(feat.geometry.coordinates[0], feat.geometry.coordinates[1])
        ) {
          spatialCandidates.push(feat);
          if (state === 'RESOLVED') resolvedCount++;
          if (state === 'APPROXIMATE') approximateCount++;
        } else {
          // Malformed coordinates safely quarantined to unresolved
          unresolvedCount++;
        }
      } else if (state === 'REGIONAL') {
        regionalFeatures.push(feat);
        regionalCount++;
      } else {
        // UNRESOLVED or missing state
        unresolvedCount++;
      }
    }

    // Sort spatial candidates deterministically
    spatialCandidates.sort(compareFeaturesDeterministic);

    // Enforce <= 150 individual marker ceiling
    const renderedFeatures = spatialCandidates.slice(0, MAX_VISIBLE_MARKERS);
    const overflowFeatures = spatialCandidates.slice(MAX_VISIBLE_MARKERS);

    return {
      renderedFeatures,
      overflowFeatures,
      regionalFeatures,
      unresolvedCount: rawCollection.unresolved_count ?? unresolvedCount,
      resolvedCount,
      approximateCount,
      regionalCount,
      totalMatching: rawCollection.total ?? (spatialCandidates.length + regionalFeatures.length + unresolvedCount),
    };
  }, [rawCollection]);

  return {
    loading,
    error,
    rawCollection,
    renderedFeatures: partitioned.renderedFeatures,
    overflowFeatures: partitioned.overflowFeatures,
    regionalFeatures: partitioned.regionalFeatures,
    unresolvedCount: partitioned.unresolvedCount,
    totalMatching: partitioned.totalMatching,
    resolvedCount: partitioned.resolvedCount,
    approximateCount: partitioned.approximateCount,
    regionalCount: partitioned.regionalCount,
    refetch: fetchFeatures,
  };
}
