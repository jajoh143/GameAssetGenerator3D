/**
 * Ring-based hair geometry builder — returns plain { positions, normals, indices } arrays.
 * No Three.js dependency; compatible with Babylon.js builder.
 */

// ─── Minimal Vec3 for internal calculations ──────────────────────────────────

class Vec3 {
  constructor(x, y, z) { this.x = x; this.y = y; this.z = z; }
}

// ─── Constants ──────────────────────────────────────────────────────────────

const CAP_LEVELS = [
  [0.00, 0.97, 0.90],
  [0.50, 0.84, 0.77],
  [0.86, 0.52, 0.48],
  [0.97, 0.14, 0.13],
];

const CAP_RING_N = 12;

// ─── Normal computation ──────────────────────────────────────────────────────

function computeVertexNormals(positions, indices) {
  const nVerts = positions.length / 3;
  const normals = new Float32Array(nVerts * 3);

  for (let t = 0; t < indices.length / 3; t++) {
    const ia = indices[t*3], ib = indices[t*3+1], ic = indices[t*3+2];
    const ax = positions[ia*3], ay = positions[ia*3+1], az = positions[ia*3+2];
    const bx = positions[ib*3], by = positions[ib*3+1], bz = positions[ib*3+2];
    const cx = positions[ic*3], cy = positions[ic*3+1], cz = positions[ic*3+2];
    const ex = bx-ax, ey = by-ay, ez = bz-az;
    const fx = cx-ax, fy = cy-ay, fz = cz-az;
    const nx = ey*fz - ez*fy, ny = ez*fx - ex*fz, nz = ex*fy - ey*fx;
    for (const i of [ia, ib, ic]) {
      normals[i*3] += nx; normals[i*3+1] += ny; normals[i*3+2] += nz;
    }
  }

  for (let i = 0; i < nVerts; i++) {
    const nx = normals[i*3], ny = normals[i*3+1], nz = normals[i*3+2];
    const len = Math.sqrt(nx*nx + ny*ny + nz*nz) || 1;
    normals[i*3] /= len; normals[i*3+1] /= len; normals[i*3+2] /= len;
  }
  return normals;
}

// ─── Geometry accumulator helpers ────────────────────────────────────────────

function createRing(cx, cy, cz, rx, ry, n = CAP_RING_N) {
  const verts = [];
  for (let i = 0; i < n; i++) {
    const a = (2 * Math.PI * i) / n;
    verts.push(new Vec3(cx + rx * Math.sin(a), cy - ry * Math.cos(a), cz));
  }
  return verts;
}

function addFace(geom, ...verts) {
  const indices = [];
  for (const v of verts) {
    const key = `${v.x.toFixed(6)},${v.y.toFixed(6)},${v.z.toFixed(6)}`;
    let idx = geom._vertexMap.get(key);
    if (idx === undefined) {
      idx = geom._positions.length / 3;
      geom._positions.push(v.x, v.y, v.z);
      geom._vertexMap.set(key, idx);
    }
    indices.push(idx);
  }
  if (indices.length === 3) {
    geom._indices.push(...indices);
  } else if (indices.length === 4) {
    geom._indices.push(indices[0], indices[1], indices[2]);
    geom._indices.push(indices[0], indices[2], indices[3]);
  }
}

function bridgeRings(geom, ringA, ringB) {
  const n = ringA.length;
  for (let i = 0; i < n; i++) {
    addFace(geom, ringA[i], ringA[(i+1)%n], ringB[(i+1)%n], ringB[i]);
  }
}

function closeRing(geom, ring, pointUp = true) {
  const n = ring.length;
  const cx = ring.reduce((s, v) => s + v.x, 0) / n;
  const cy = ring.reduce((s, v) => s + v.y, 0) / n;
  const cz = ring.reduce((s, v) => s + v.z, 0) / n;
  const center = new Vec3(cx, cy, cz);
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    pointUp ? addFace(geom, ring[i], ring[j], center)
            : addFace(geom, ring[j], ring[i], center);
  }
}

function backHalfVerts(ring) { return ring.slice(2, ring.length - 1); }

function createHairClump(geom, spine, widths) {
  const n = spine.length;
  const left = [], right = [];
  for (let i = 0; i < n - 1; i++) {
    const w = widths[i];
    left.push(new Vec3(spine[i].x - w, spine[i].y, spine[i].z));
    right.push(new Vec3(spine[i].x + w, spine[i].y, spine[i].z));
  }
  for (let i = 0; i < n - 2; i++) {
    addFace(geom, left[i], left[i+1], right[i+1], right[i]);
  }
  addFace(geom, left[n-2], spine[n-1], right[n-2]);
}

function createFringeClumps(geom, headR, hlZ, frY, clumpDefs, headRHoriz = null) {
  const hrH = headRHoriz !== null ? headRHoriz : headR;
  for (const [cx, xDrift, yFwd, zMid, zTip, wRoot] of clumpDefs) {
    const rx = cx * hrH, drift = xDrift * hrH;
    const wdRoot = wRoot * hrH, wdMid = wdRoot * 0.58;
    const spine = [
      new Vec3(rx, frY, hlZ + headR * 0.02),
      new Vec3(rx + drift * 0.5, frY - hrH * yFwd * 0.5, hlZ - headR * zMid),
      new Vec3(rx + drift, frY - hrH * yFwd, hlZ - headR * zTip),
    ];
    createHairClump(geom, spine, [wdRoot, wdMid, 0]);
  }
}

function createPanelRows(geom, topVerts, rowsSpec) {
  let prev = topVerts;
  let cumDz = 0;
  for (const [dz, xm, ym] of rowsSpec) {
    cumDz += dz;
    const newRow = topVerts.map(v => new Vec3(v.x * xm, v.y * ym, v.z + cumDz));
    for (let i = 0; i < prev.length - 1; i++) {
      addFace(geom, prev[i], prev[i+1], newRow[i+1], newRow[i]);
    }
    prev = newRow;
  }
}

function buildCap(geom, headZ, headR, hScale = 1.20, capLevels = null, headRHoriz = null) {
  const hrH = headRHoriz !== null ? headRHoriz : headR;
  const levels = capLevels !== null ? capLevels : CAP_LEVELS;
  const rings = levels.map(([zOff, rxM, ryM]) =>
    createRing(0, 0, headZ + headR * zOff, hrH * rxM * hScale, hrH * ryM * hScale, CAP_RING_N)
  );
  for (let i = 0; i < rings.length - 1; i++) bridgeRings(geom, rings[i], rings[i+1]);
  closeRing(geom, rings[rings.length - 1], true);
  return rings;
}

// ─── Style builders ──────────────────────────────────────────────────────────

function buildBuzzed(geom, headZ, headR) {
  const rings = buildCap(geom, headZ, headR, 1.15);
  createPanelRows(geom, backHalfVerts(rings[0]), [[-headR * 0.18, 1.0, 1.0]]);
}

function buildShort(geom, headZ, headR, headRHoriz = null) {
  const hrH = headRHoriz !== null ? headRHoriz : headR;
  const rings = buildCap(geom, headZ, headR, 1.20, [
    [0.00, 0.97, 0.90], [0.45, 0.86, 0.79], [0.78, 0.55, 0.50], [0.92, 0.18, 0.16],
  ], headRHoriz);
  createPanelRows(geom, backHalfVerts(rings[0]), [
    [-headR * 0.16, 0.97, 0.95], [-headR * 0.15, 0.93, 0.90], [-headR * 0.13, 0.88, 0.85],
  ]);
  const hlZ = rings[0][0].z;
  const frY = -(hrH * 0.90 * 1.06) - 0.003;
  createFringeClumps(geom, headR, hlZ, frY, [
    [-0.46, -0.05, 0.04, 0.04, 0.12, 0.13], [-0.22, 0.00, 0.05, 0.04, 0.13, 0.13],
    [0.00, 0.00, 0.05, 0.04, 0.14, 0.15],   [0.22, 0.00, 0.05, 0.04, 0.13, 0.13],
    [0.46, 0.05, 0.04, 0.04, 0.12, 0.13],
  ], hrH);
}

function buildLong(geom, headZ, headR, headRHoriz = null) {
  const hrH = headRHoriz !== null ? headRHoriz : headR;
  const rings = buildCap(geom, headZ, headR, 1.22, [
    [-0.10, 0.99, 0.92], [0.35, 0.87, 0.80], [0.72, 0.58, 0.52], [0.94, 0.20, 0.18],
  ], headRHoriz);
  createPanelRows(geom, backHalfVerts(rings[0]), [
    [-headR * 0.14, 0.98, 0.96], [-headR * 0.18, 0.96, 0.93], [-headR * 0.22, 0.94, 0.90],
    [-headR * 0.26, 0.92, 0.88], [-headR * 0.30, 0.90, 0.86], [-headR * 0.32, 0.88, 0.84],
  ]);
  const hlZ = rings[0][0].z;
  const frY = -(hrH * 0.92 * 1.06) - 0.005;
  createFringeClumps(geom, headR, hlZ, frY, [
    [-0.50, -0.08, 0.06, 0.08, 0.20, 0.14], [-0.25, -0.02, 0.08, 0.08, 0.22, 0.14],
    [0.00, 0.00, 0.08, 0.08, 0.24, 0.16],   [0.25, 0.02, 0.08, 0.08, 0.22, 0.14],
    [0.50, 0.08, 0.06, 0.08, 0.20, 0.14],
  ], hrH);
}

function buildSpiky(geom, headZ, headR, headRHoriz = null) {
  const hrH = headRHoriz !== null ? headRHoriz : headR;
  const rings = buildCap(geom, headZ, headR, 1.18, [
    [0.20, 0.98, 0.98], [0.48, 0.86, 0.79], [0.72, 0.60, 0.55], [0.88, 0.30, 0.28],
  ], headRHoriz);
  createPanelRows(geom, backHalfVerts(rings[0]), [
    [-headR * 0.15, 0.96, 0.94], [-headR * 0.14, 0.92, 0.90],
  ]);
  createFringeClumps(geom, headR, headZ + headR * 0.88, 0, [
    [-0.50, -0.15, 0.00, 0.00, 0.40, 0.08], [-0.25, -0.10, 0.10, 0.05, 0.45, 0.09],
    [0.00, 0.00, 0.15, 0.10, 0.50, 0.10],   [0.25, 0.10, 0.10, 0.05, 0.45, 0.09],
    [0.50, 0.15, 0.00, 0.00, 0.40, 0.08],   [0.00, -0.15, -0.20, 0.00, 0.35, 0.07],
  ], hrH);
}

// ─── Public API ──────────────────────────────────────────────────────────────

/**
 * Build hair geometry for the given style.
 * @returns {{ positions: Float32Array, normals: Float32Array, indices: Uint32Array }|null}
 */
export function buildHairGeometry(headRadius, style = 'short') {
  if (style === 'none') return null;

  const geom = { _positions: [], _indices: [], _vertexMap: new Map() };

  switch (style) {
    case 'buzzed': buildBuzzed(geom, 0, headRadius); break;
    case 'short':  buildShort(geom, 0, headRadius);  break;
    case 'long':   buildLong(geom, 0, headRadius);   break;
    case 'spiky':  buildSpiky(geom, 0, headRadius);  break;
    default:       buildShort(geom, 0, headRadius);
  }

  if (geom._positions.length === 0) return null;

  const positions = new Float32Array(geom._positions);
  const indices   = new Uint32Array(geom._indices);
  const normals   = computeVertexNormals(positions, indices);

  return { positions, normals, indices };
}
