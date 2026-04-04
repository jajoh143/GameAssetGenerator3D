/**
 * Professional ring-based hair geometry builder for Three.js.
 * Based on GameAssetGenerator3D's Blender/Python hair system.
 *
 * Architecture:
 * - Ring-based parametric geometry with spherical proportions
 * - Tapered hair clumps using CGCookie "big→medium→small" technique
 * - Panel rows for nape/back coverage
 * - Modular style builders for extensibility
 * - Single unified mesh output (merged geometry)
 */

import * as THREE from 'three';

// ─── Constants ──────────────────────────────────────────────────────────────

// Shared cap elevation levels: (z_offset, rx_multiplier, ry_multiplier)
// Proportions follow spherical dome (sin/cos of elevation angle θ)
const CAP_LEVELS = [
  [0.00, 0.97, 0.90],   // 0° - hairline/brow (equatorial)
  [0.50, 0.84, 0.77],   // 30° - upper forehead
  [0.86, 0.52, 0.48],   // 60° - upper cranium
  [0.97, 0.14, 0.13],   // 80° - crown apex
];

const CAP_RING_N = 12;  // 12 vertices per ring = smooth circular silhouette

// ─── Helper Functions for Ring-Based Geometry ──────────────────────────────

/**
 * Create an n-vertex elliptical ring in the XY plane at height z.
 * Returns array of Vector3 positions.
 */
function createRing(cx, cy, cz, rx, ry, n = CAP_RING_N) {
  const verts = [];
  for (let i = 0; i < n; i++) {
    const a = (2 * Math.PI * i) / n;
    verts.push(new THREE.Vector3(
      cx + rx * Math.sin(a),
      cy - ry * Math.cos(a),
      cz
    ));
  }
  return verts;
}

/**
 * Connect two equal-length vertex rings with quad strips.
 * Adds faces to the geometry.
 */
function bridgeRings(geometry, ringA, ringB) {
  const n = ringA.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    addFace(geometry, ringA[i], ringA[j], ringB[j], ringB[i]);
  }
}

/**
 * Close a ring with a triangle fan pointing toward a center vertex.
 * Returns the center vertex.
 */
function closeRing(geometry, ring, pointUp = true) {
  const n = ring.length;
  const cx = ring.reduce((sum, v) => sum + v.x, 0) / n;
  const cy = ring.reduce((sum, v) => sum + v.y, 0) / n;
  const cz = ring.reduce((sum, v) => sum + v.z, 0) / n;
  const center = new THREE.Vector3(cx, cy, cz);

  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    if (pointUp) {
      addFace(geometry, ring[i], ring[j], center);
    } else {
      addFace(geometry, ring[j], ring[i], center);
    }
  }
  return center;
}

/**
 * Add a face (triangle or quad) to geometry.
 * Handles updating positions, normals, and faces array.
 */
function addFace(geometry, ...verts) {
  // Get or create position and index
  if (!geometry._positions) {
    geometry._positions = [];
    geometry._indices = [];
    geometry._vertexMap = new Map();
  }

  const indices = [];
  for (const v of verts) {
    const key = `${v.x.toFixed(6)},${v.y.toFixed(6)},${v.z.toFixed(6)}`;
    let idx = geometry._vertexMap.get(key);
    if (idx === undefined) {
      idx = geometry._positions.length / 3;
      geometry._positions.push(v.x, v.y, v.z);
      geometry._vertexMap.set(key, idx);
    }
    indices.push(idx);
  }

  // Add triangle or quad as triangles
  if (indices.length === 3) {
    geometry._indices.push(...indices);
  } else if (indices.length === 4) {
    // Quad as two triangles
    geometry._indices.push(indices[0], indices[1], indices[2]);
    geometry._indices.push(indices[0], indices[2], indices[3]);
  }
}

/**
 * Get vertices from a specific region of a ring.
 * Useful for accessing back, side, or front sections.
 */
function backHalfVerts(ring) {
  // Back 270° - everything except front 3 vertices
  const n = ring.length;
  return ring.slice(2, n - 1);
}

function frontVerts(ring) {
  const n = ring.length;
  return [ring[n - 1], ring[0], ring[1]];
}

function leftVerts(ring) {
  const n = ring.length;
  const c = Math.floor(n / 4);
  return [ring[c - 1], ring[c], ring[c + 1]];
}

function rightVerts(ring) {
  const n = ring.length;
  const c = Math.floor((3 * n) / 4);
  return [ring[c - 1], ring[c], ring[c + 1]];
}

/**
 * Build a tapered hair clump using the CGCookie technique.
 * Spine: array of Vector3 points (root → mid → tip)
 * Widths: array of half-widths at each spine point (last = 0 for pointed tip)
 */
function createHairClump(geometry, spine, widths) {
  const n = spine.length;

  // Create left and right edge vertices
  const left = [];
  const right = [];
  for (let i = 0; i < n - 1; i++) {
    const w = widths[i];
    left.push(new THREE.Vector3(spine[i].x - w, spine[i].y, spine[i].z));
    right.push(new THREE.Vector3(spine[i].x + w, spine[i].y, spine[i].z));
  }

  // Add quad strip segments
  for (let i = 0; i < n - 2; i++) {
    addFace(geometry, left[i], left[i + 1], right[i + 1], right[i]);
  }

  // Triangulated tip
  addFace(geometry, left[n - 2], spine[n - 1], right[n - 2]);
}

/**
 * Create fringe clumps (bangs) across the forehead.
 * clumpDefs: array of (cx, xDrift, yFwd, zMid, zTip, wRoot)
 */
function createFringeClumps(geometry, headR, hlZ, frY, clumpDefs, headRHoriz = null) {
  const hrH = headRHoriz !== null ? headRHoriz : headR;

  for (const [cx, xDrift, yFwd, zMid, zTip, wRoot] of clumpDefs) {
    const rx = cx * hrH;
    const drift = xDrift * hrH;
    const wdRoot = wRoot * hrH;
    const wdMid = wdRoot * 0.58;  // Taper to 58% at mid-point

    const spine = [
      new THREE.Vector3(rx, frY, hlZ + headR * 0.02),
      new THREE.Vector3(rx + drift * 0.5, frY - hrH * yFwd * 0.5, hlZ - headR * zMid),
      new THREE.Vector3(rx + drift, frY - hrH * yFwd, hlZ - headR * zTip),
    ];

    createHairClump(geometry, spine, [wdRoot, wdMid, 0]);
  }
}

/**
 * Extrude a strip of vertices downward in sequential quad rows.
 * rowsSpec: array of (dz, xScale, yScale) tuples
 */
function createPanelRows(geometry, topVerts, rowsSpec, headR) {
  let prev = topVerts;
  let cumulativeDz = 0;

  for (const [dz, xm, ym] of rowsSpec) {
    cumulativeDz += dz;
    const newRow = topVerts.map(
      v => new THREE.Vector3(v.x * xm, v.y * ym, v.z + cumulativeDz)
    );

    // Bridge rows
    for (let i = 0; i < prev.length - 1; i++) {
      addFace(geometry, prev[i], prev[i + 1], newRow[i + 1], newRow[i]);
    }

    prev = newRow;
  }
}

/**
 * Build the shared domed cap from hairline to crown.
 * Returns array of rings.
 */
function buildCap(geometry, headZ, headR, hScale = 1.20, capLevels = null, headRHoriz = null) {
  const hrH = headRHoriz !== null ? headRHoriz : headR;
  const levels = capLevels !== null ? capLevels : CAP_LEVELS;
  const rings = [];

  // Create rings at each elevation
  for (const [zOff, rxM, ryM] of levels) {
    const z = headZ + headR * zOff;
    rings.push(
      createRing(
        0, 0, z,
        hrH * rxM * hScale,
        hrH * ryM * hScale,
        CAP_RING_N
      )
    );
  }

  // Bridge rings with quad strips
  for (let i = 0; i < rings.length - 1; i++) {
    bridgeRings(geometry, rings[i], rings[i + 1]);
  }

  // Close crown with triangle fan
  closeRing(geometry, rings[rings.length - 1], true);

  return rings;
}

// ─── Style Builders (Modular) ───────────────────────────────────────────────

function buildBuzzed(geometry, headZ, headR, headRHoriz = null) {
  const rings = buildCap(geometry, headZ, headR, 1.15, CAP_LEVELS, headRHoriz);
  const hl = rings[0];

  // Single row around back for nape coverage
  createPanelRows(geometry, backHalfVerts(hl), [
    [-headR * 0.18, 1.0, 1.0],
  ], headR);
}

function buildShort(geometry, headZ, headR, headRHoriz = null) {
  const hrH = headRHoriz !== null ? headRHoriz : headR;

  // Custom cap levels for short style
  const shortCapLevels = [
    [0.00, 0.97, 0.90],   // hairline - equatorial
    [0.45, 0.86, 0.79],   // upper sides
    [0.78, 0.55, 0.50],   // upper cranium
    [0.92, 0.18, 0.16],   // crown apex
  ];

  const rings = buildCap(geometry, headZ, headR, 1.20, shortCapLevels, headRHoriz);
  const hl = rings[0];

  // Back-half panel (3 rows)
  createPanelRows(geometry, backHalfVerts(hl), [
    [-headR * 0.16, 0.97, 0.95],
    [-headR * 0.15, 0.93, 0.90],
    [-headR * 0.13, 0.88, 0.85],
  ], headR);

  // Fringe clumps (5 clumps across forehead)
  const hlZ = hl[0].z;
  const frY = -(hrH * 0.90 * 1.06) - 0.003;
  createFringeClumps(geometry, headR, hlZ, frY, [
    [-0.46, -0.05, 0.04, 0.04, 0.12, 0.13],   // left
    [-0.22, 0.00, 0.05, 0.04, 0.13, 0.13],
    [0.00, 0.00, 0.05, 0.04, 0.14, 0.15],     // center
    [0.22, 0.00, 0.05, 0.04, 0.13, 0.13],
    [0.46, 0.05, 0.04, 0.04, 0.12, 0.13],     // right
  ], hrH);
}

function buildLong(geometry, headZ, headR, headRHoriz = null) {
  const hrH = headRHoriz !== null ? headRHoriz : headR;

  // Custom cap for long style (lower hairline)
  const longCapLevels = [
    [-0.10, 0.99, 0.92],   // lower hairline
    [0.35, 0.87, 0.80],
    [0.72, 0.58, 0.52],
    [0.94, 0.20, 0.18],
  ];

  const rings = buildCap(geometry, headZ, headR, 1.22, longCapLevels, headRHoriz);
  const hl = rings[0];

  // Back curtain (6 rows for long hair)
  createPanelRows(geometry, backHalfVerts(hl), [
    [-headR * 0.14, 0.98, 0.96],
    [-headR * 0.18, 0.96, 0.93],
    [-headR * 0.22, 0.94, 0.90],
    [-headR * 0.26, 0.92, 0.88],
    [-headR * 0.30, 0.90, 0.86],
    [-headR * 0.32, 0.88, 0.84],
  ], headR);

  // Longer fringe
  const hlZ = hl[0].z;
  const frY = -(hrH * 0.92 * 1.06) - 0.005;
  createFringeClumps(geometry, headR, hlZ, frY, [
    [-0.50, -0.08, 0.06, 0.08, 0.20, 0.14],
    [-0.25, -0.02, 0.08, 0.08, 0.22, 0.14],
    [0.00, 0.00, 0.08, 0.08, 0.24, 0.16],
    [0.25, 0.02, 0.08, 0.08, 0.22, 0.14],
    [0.50, 0.08, 0.06, 0.08, 0.20, 0.14],
  ], hrH);
}

function buildSpiky(geometry, headZ, headR, headRHoriz = null) {
  const hrH = headRHoriz !== null ? headRHoriz : headR;

  // Spiky cap (lower, wider base for spikes)
  const spikyCapLevels = [
    [0.20, 0.98, 0.98],   // low hairline
    [0.48, 0.86, 0.79],
    [0.72, 0.60, 0.55],
    [0.88, 0.30, 0.28],   // small crown
  ];

  const rings = buildCap(geometry, headZ, headR, 1.18, spikyCapLevels, headRHoriz);
  const hl = rings[0];

  // Back panel
  createPanelRows(geometry, backHalfVerts(hl), [
    [-headR * 0.15, 0.96, 0.94],
    [-headR * 0.14, 0.92, 0.90],
  ], headR);

  // 6 spike clumps arranged in a circle
  const spikeZ = headZ + headR * 0.88;
  const spikeClumps = [
    [-0.50, -0.15, 0.00, 0.00, 0.40, 0.08],
    [-0.25, -0.10, 0.10, 0.05, 0.45, 0.09],
    [0.00, 0.00, 0.15, 0.10, 0.50, 0.10],
    [0.25, 0.10, 0.10, 0.05, 0.45, 0.09],
    [0.50, 0.15, 0.00, 0.00, 0.40, 0.08],
    [0.00, -0.15, -0.20, 0.00, 0.35, 0.07],
  ];

  createFringeClumps(geometry, headR, spikeZ, 0, spikeClumps, hrH);
}

// ─── Public API ──────────────────────────────────────────────────────────

/**
 * Build hair geometry for the given style.
 * Geometry is centered at origin - positioning/rotation handled by builder.
 *
 * @param {number} headRadius - Head radius in 3D units
 * @param {string} style - Hair style name ('short', 'long', 'spiky', 'buzzed', etc.)
 * @returns {THREE.BufferGeometry|null}
 */
export function buildHairGeometry(headRadius, style = 'short') {
  if (style === 'none') return null;

  // Build geometry centered at origin (Z=0)
  // This allows builder.js to handle all positioning/rotation
  const headZ = 0;

  // Create accumulator geometry
  const geom = new THREE.BufferGeometry();
  geom._positions = [];
  geom._indices = [];
  geom._vertexMap = new Map();

  // Route to appropriate style builder
  switch (style) {
    case 'buzzed':
      buildBuzzed(geom, headZ, headRadius);
      break;
    case 'short':
      buildShort(geom, headZ, headRadius);
      break;
    case 'long':
      buildLong(geom, headZ, headRadius);
      break;
    case 'spiky':
      buildSpiky(geom, headZ, headRadius);
      break;
    default:
      // Fallback to short if unknown style
      buildShort(geom, headZ, headRadius);
  }

  // Convert accumulated data to BufferGeometry
  if (geom._positions.length === 0) {
    return null;
  }

  const positionArray = new Float32Array(geom._positions);
  const indexArray = new Uint32Array(geom._indices);

  geom.setAttribute('position', new THREE.BufferAttribute(positionArray, 3));
  geom.setIndex(new THREE.BufferAttribute(indexArray, 1));
  geom.computeVertexNormals();

  return geom;
}
