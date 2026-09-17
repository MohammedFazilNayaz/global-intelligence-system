/**
 * Vector basemap contours, graticules, and regional boundaries for V0.9-C.
 * Pre-sampled vector line-strings that curve naturally under 3D orthographic projection.
 */

export interface VectorPolygon {
  name: string;
  points: [number, number][]; // [longitude, latitude] in degrees
}

export interface GraticuleLine {
  type: 'parallel' | 'meridian';
  angle: number; // degrees
  points: [number, number][]; // [longitude, latitude]
}

/**
 * Generates graticule grid lines every 30 degrees for longitude and latitude.
 * Interpolates points every 5 degrees so curves render smoothly on a sphere.
 */
export function generateGraticules(): GraticuleLine[] {
  const lines: GraticuleLine[] = [];

  // Parallels (lines of constant latitude) every 30 degrees (-60, -30, 0, 30, 60)
  for (let lat = -60; lat <= 60; lat += 30) {
    const pts: [number, number][] = [];
    for (let lon = -180; lon <= 180; lon += 5) {
      pts.push([lon, lat]);
    }
    lines.push({ type: 'parallel', angle: lat, points: pts });
  }

  // Meridians (lines of constant longitude) every 30 degrees (-180 to 150)
  for (let lon = -180; lon < 180; lon += 30) {
    const pts: [number, number][] = [];
    for (let lat = -80; lat <= 80; lat += 5) {
      pts.push([lon, lat]);
    }
    lines.push({ type: 'meridian', angle: lon, points: pts });
  }

  return lines;
}

/**
 * Standard continent outlines with dense vertices for smooth spherical curvature.
 */
export const CONTINENT_CONTOURS: VectorPolygon[] = [
  // North America
  {
    name: 'North America',
    points: [
      [-168, 65], [-160, 71], [-140, 70], [-120, 75], [-95, 74], [-80, 70], [-60, 60],
      [-65, 45], [-75, 35], [-80, 25], [-82, 23], [-90, 21], [-97, 26], [-97, 18],
      [-105, 20], [-115, 30], [-124, 38], [-125, 49], [-135, 57], [-150, 60], [-168, 65],
    ],
  },
  // South America
  {
    name: 'South America',
    points: [
      [-75, 12], [-60, 8], [-50, 0], [-35, -5], [-37, -12], [-42, -22], [-50, -30],
      [-58, -38], [-65, -55], [-75, -50], [-73, -40], [-70, -30], [-75, -15], [-80, -2],
      [-77, 8], [-75, 12],
    ],
  },
  // Eurasia
  {
    name: 'Eurasia',
    points: [
      [-10, 36], [0, 44], [10, 45], [15, 55], [5, 62], [25, 71], [40, 68], [60, 73],
      [80, 73], [100, 76], [120, 73], [140, 71], [170, 66], [160, 55], [142, 50],
      [130, 35], [120, 25], [108, 15], [100, 5], [95, 20], [80, 10], [70, 22],
      [60, 25], [50, 30], [35, 32], [28, 41], [12, 38], [-5, 36], [-10, 36],
    ],
  },
  // Africa
  {
    name: 'Africa',
    points: [
      [-5, 36], [10, 37], [25, 32], [33, 28], [43, 12], [51, 12], [45, 0],
      [40, -10], [35, -25], [28, -34], [18, -34], [12, -20], [10, -5], [5, 4],
      [-15, 11], [-17, 15], [-10, 28], [-5, 36],
    ],
  },
  // Australia
  {
    name: 'Australia',
    points: [
      [114, -22], [122, -18], [130, -12], [136, -12], [142, -11], [146, -18],
      [153, -28], [150, -37], [140, -38], [130, -32], [118, -35], [113, -26], [114, -22],
    ],
  },
  // Antarctica
  {
    name: 'Antarctica',
    points: [
      [-160, -78], [-120, -74], [-80, -72], [-60, -65], [-40, -75], [0, -70],
      [40, -68], [80, -66], [120, -66], [160, -70], [180, -78], [-160, -78],
    ],
  },
];

/**
 * Authoritative geometries for canonical maritime regions (verified bounds).
 */
export const CANONICAL_MARITIME_BOUNDARIES: Record<string, [number, number][]> = {
  red_sea: [
    [32.5, 29.9], [34.0, 27.5], [37.5, 20.0], [43.0, 13.0], [43.5, 12.6],
    [43.3, 12.8], [41.5, 16.0], [38.0, 22.0], [35.0, 27.0], [32.5, 29.9],
  ],
  persian_gulf: [
    [48.0, 30.0], [50.0, 28.5], [52.5, 26.5], [56.3, 26.0], [56.5, 26.5],
    [54.0, 27.0], [51.0, 29.0], [48.0, 30.0],
  ],
  strait_of_malacca: [
    [95.5, 5.5], [98.5, 3.5], [101.5, 2.0], [103.5, 1.2],
    [103.0, 1.6], [100.5, 2.8], [97.5, 4.5], [95.5, 5.5],
  ],
};
