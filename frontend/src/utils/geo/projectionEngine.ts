/**
 * Mathematical Projection Engine for V0.9-C Dual-Mode Interactive Globe.
 * Pure TypeScript functions with zero UI dependencies.
 *
 * Implements:
 * 1. 3D Orthographic Projection (Spherical forward/inverse, occlusion culling, limb attenuation)
 * 2. 2D Equirectangular Projection (Cylindrical forward/inverse, antimeridian date-line wrapping)
 * 3. Topological boundary handling (poles, date-line +/-180, adjacency at +/-179.5)
 */

export interface ProjectedPoint {
  x: number;
  y: number;
  visible: boolean;
  depth: number; // cos(c) for 3D (1.0 = center, 0.0 = limb, <0 = back hemisphere)
  angularDistance: number; // c in radians
}

export interface GeographicCoordinate {
  longitude: number; // degrees [-180, 180]
  latitude: number;  // degrees [-90, 90]
}

const DEG_TO_RAD = Math.PI / 180.0;
const RAD_TO_DEG = 180.0 / Math.PI;

/**
 * Validates whether coordinates fall within valid physical geographic bounds.
 */
export function validateCoordinates(lon: number, lat: number): boolean {
  if (typeof lon !== 'number' || typeof lat !== 'number') return false;
  if (isNaN(lon) || isNaN(lat)) return false;
  if (lat < -90.0 || lat > 90.0) return false;
  if (lon < -180.0 || lon > 180.0) return false;
  return true;
}

/**
 * Normalizes an angle in degrees to [-180, 180].
 */
export function normalizeLongitudeDeg(lon: number): number {
  if (lon === 180.0) return 180.0;
  if (lon === -180.0) return -180.0;
  let l = ((lon + 180.0) % 360.0);
  if (l < 0) l += 360.0;
  const res = l - 180.0;
  if (res === -180.0 && lon > 0) return 180.0;
  return res;
}

/**
 * Normalizes an angle difference in radians to [-PI, PI].
 */
export function normalizeLongitudeRad(rad: number): number {
  let r = (rad + Math.PI) % (2.0 * Math.PI);
  if (r < 0) r += 2.0 * Math.PI;
  return r - Math.PI;
}

/**
 * Calculates shortest angular distance in degrees across the sphere / antimeridian.
 * For example: distance between +179.5 and -179.5 is 1.0 degree.
 */
export function angularLongitudeDifferenceDeg(lon1: number, lon2: number): number {
  const diff = Math.abs(lon1 - lon2) % 360.0;
  return diff > 180.0 ? 360.0 - diff : diff;
}

/**
 * Calculates central angular distance c (in radians) between two points on a sphere.
 */
export function angularDistanceRad(
  lon1Rad: number,
  lat1Rad: number,
  lon2Rad: number,
  lat2Rad: number
): number {
  const sinLat1 = Math.sin(lat1Rad);
  const cosLat1 = Math.cos(lat1Rad);
  const sinLat2 = Math.sin(lat2Rad);
  const cosLat2 = Math.cos(lat2Rad);
  const dLon = lon1Rad - lon2Rad;

  const cosC = sinLat1 * sinLat2 + cosLat1 * cosLat2 * Math.cos(dLon);
  // Clamp to [-1, 1] to prevent floating point domain errors in acos
  const clampedCosC = Math.max(-1.0, Math.min(1.0, cosC));
  return Math.acos(clampedCosC);
}

// =============================================================================
// 3D ORTHOGRAPHIC PROJECTION
// =============================================================================

/**
 * Forward 3D Orthographic Projection:
 * Maps (lon, lat) in degrees onto a 2D screen coordinate [x, y] for an orthographic sphere.
 *
 * @param lon - Target longitude in degrees [-180, 180]
 * @param lat - Target latitude in degrees [-90, 90]
 * @param centerLon - Camera focal longitude in degrees
 * @param centerLat - Camera focal latitude in degrees
 * @param radius - Globe radius in pixels
 * @param centerX - Canvas X center coordinate
 * @param centerY - Canvas Y center coordinate
 */
export function projectOrthographic(
  lon: number,
  lat: number,
  centerLon: number,
  centerLat: number,
  radius: number,
  centerX: number,
  centerY: number
): ProjectedPoint {
  if (!validateCoordinates(lon, lat)) {
    return { x: centerX, y: centerY, visible: false, depth: -1.0, angularDistance: Math.PI };
  }

  const lambda = lon * DEG_TO_RAD;
  const phi = lat * DEG_TO_RAD;
  const lambda0 = centerLon * DEG_TO_RAD;
  const phi0 = centerLat * DEG_TO_RAD;

  const deltaLambda = normalizeLongitudeRad(lambda - lambda0);

  const sinPhi = Math.sin(phi);
  const cosPhi = Math.cos(phi);
  const sinPhi0 = Math.sin(phi0);
  const cosPhi0 = Math.cos(phi0);
  const cosDeltaLambda = Math.cos(deltaLambda);
  const sinDeltaLambda = Math.sin(deltaLambda);

  // Angular distance cosine: cos(c) = sin(phi0)*sin(phi) + cos(phi0)*cos(phi)*cos(deltaLambda)
  const cosC = sinPhi0 * sinPhi + cosPhi0 * cosPhi * cosDeltaLambda;
  const clampedCosC = Math.max(-1.0, Math.min(1.0, cosC));
  const c = Math.acos(clampedCosC);

  // Back-hemisphere occlusion invariant: if cos(c) < 0, the point is on the far hemisphere
  const visible = cosC >= 0;

  // Cartesian forward projection:
  // x = centerX + R * cos(phi) * sin(deltaLambda)
  // y = centerY - R * (cos(phi0) * sin(phi) - sin(phi0) * cos(phi) * cos(deltaLambda))
  const x = centerX + radius * cosPhi * sinDeltaLambda;
  const y = centerY - radius * (cosPhi0 * sinPhi - sinPhi0 * cosPhi * cosDeltaLambda);

  return {
    x,
    y,
    visible,
    depth: cosC,
    angularDistance: c,
  };
}

/**
 * Inverse 3D Orthographic Projection:
 * Maps screen coordinate [x, y] back to (lon, lat) on the sphere.
 * Returns null if the screen point falls outside the globe limb (rho > radius).
 *
 * @param screenX - Screen X position
 * @param screenY - Screen Y position
 * @param centerLon - Camera focal longitude in degrees
 * @param centerLat - Camera focal latitude in degrees
 * @param radius - Globe radius in pixels
 * @param centerX - Canvas X center coordinate
 * @param centerY - Canvas Y center coordinate
 */
export function unprojectOrthographic(
  screenX: number,
  screenY: number,
  centerLon: number,
  centerLat: number,
  radius: number,
  centerX: number,
  centerY: number
): GeographicCoordinate | null {
  if (radius <= 0) return null;

  const dx = screenX - centerX;
  const dy = centerY - screenY; // Invert Y for mathematical Cartesian coordinate system
  const rho = Math.sqrt(dx * dx + dy * dy);

  // Point is outside the globe disk
  if (rho > radius) {
    return null;
  }

  // Handle center point singularity
  if (rho === 0) {
    return {
      longitude: normalizeLongitudeDeg(centerLon),
      latitude: Math.max(-90.0, Math.min(90.0, centerLat)),
    };
  }

  const phi0 = centerLat * DEG_TO_RAD;
  const lambda0 = centerLon * DEG_TO_RAD;

  // c = arcsin(rho / R)
  const sinC = Math.min(1.0, rho / radius);
  const c = Math.asin(sinC);
  const cosC = Math.cos(c);

  const sinPhi0 = Math.sin(phi0);
  const cosPhi0 = Math.cos(phi0);

  // phi = arcsin(cos(c)*sin(phi0) + (dy * sin(c) * cos(phi0) / rho))
  const sinPhi = cosC * sinPhi0 + (dy * sinC * cosPhi0) / rho;
  const clampedSinPhi = Math.max(-1.0, Math.min(1.0, sinPhi));
  const phi = Math.asin(clampedSinPhi);

  // lambda = lambda0 + atan2(dx * sin(c), rho * cos(phi0) * cos(c) - dy * sin(phi0) * sin(c))
  const numerator = dx * sinC;
  const denominator = rho * cosPhi0 * cosC - dy * sinPhi0 * sinC;

  let lambda: number;
  if (Math.abs(denominator) < 1e-15 && Math.abs(numerator) < 1e-15) {
    lambda = lambda0;
  } else {
    lambda = lambda0 + Math.atan2(numerator, denominator);
  }

  const latDeg = Math.max(-90.0, Math.min(90.0, phi * RAD_TO_DEG));
  const lonDeg = normalizeLongitudeDeg(lambda * RAD_TO_DEG);

  return {
    longitude: lonDeg,
    latitude: latDeg,
  };
}

// =============================================================================
// 2D EQUIRECTANGULAR PROJECTION
// =============================================================================

/**
 * Forward 2D Equirectangular Projection:
 * Maps (lon, lat) onto an equirectangular flat map.
 * Supports antimeridian centering and zoom.
 *
 * @param lon - Target longitude in degrees
 * @param lat - Target latitude in degrees
 * @param centerLon - Center focal longitude
 * @param centerLat - Center focal latitude
 * @param zoom - Zoom scale multiplier (1.0 = world fit)
 * @param width - Map viewport width in pixels
 * @param height - Map viewport height in pixels
 */
export function projectEquirectangular(
  lon: number,
  lat: number,
  centerLon: number,
  centerLat: number,
  zoom: number,
  width: number,
  height: number
): ProjectedPoint {
  if (!validateCoordinates(lon, lat)) {
    return { x: width / 2, y: height / 2, visible: false, depth: 0, angularDistance: 0 };
  }

  // Relative longitude offset normalized across antimeridian
  const deltaLon = normalizeLongitudeDeg(lon - centerLon);
  const deltaLat = lat - centerLat;

  // Scale factors: at zoom=1.0, 360 degrees covers width, 180 degrees covers height
  const scaleX = (width / 360.0) * zoom;
  const scaleY = (height / 180.0) * zoom;

  const x = width / 2.0 + deltaLon * scaleX;
  const y = height / 2.0 - deltaLat * scaleY;

  // Viewport culling with a 50px margin
  const visible = x >= -50 && x <= width + 50 && y >= -50 && y <= height + 50;

  return {
    x,
    y,
    visible,
    depth: 1.0,
    angularDistance: Math.abs(deltaLon) * DEG_TO_RAD,
  };
}

/**
 * Inverse 2D Equirectangular Projection:
 * Maps screen coordinate [x, y] back to (lon, lat).
 */
export function unprojectEquirectangular(
  screenX: number,
  screenY: number,
  centerLon: number,
  centerLat: number,
  zoom: number,
  width: number,
  height: number
): GeographicCoordinate {
  const scaleX = (width / 360.0) * zoom;
  const scaleY = (height / 180.0) * zoom;

  const deltaLon = (screenX - width / 2.0) / scaleX;
  const deltaLat = (height / 2.0 - screenY) / scaleY;

  const lon = normalizeLongitudeDeg(centerLon + deltaLon);
  const lat = Math.max(-90.0, Math.min(90.0, centerLat + deltaLat));

  return {
    longitude: lon,
    latitude: lat,
  };
}
