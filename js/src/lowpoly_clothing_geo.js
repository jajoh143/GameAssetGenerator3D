/**
 * Clothing geometry for the low-poly (realistic) body mesh.
 *
 * Shirts: face-extrusion from body mesh triangles (works well for the torso).
 * Pants/Shorts: procedural tube geometry — one smooth cylinder per leg —
 *   which avoids the jagged "extruded triangle" look that face-extrusion
 *   produces on a multi-directional leg mesh.
 *
 * Zone boundaries for realistic humanoid (head ≈ 13% of total height):
 *   Cartoon:   knee 24%, hip 43%, chest 57%, arm/shoulder 63%
 *   Realistic: knee 30%, hip 53%, chest 68%, arm/shoulder 82%
 */

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

// ── Shared geometry helpers ───────────────────────────────────────────────────

/** Merge an array of { positions, normals, indices } geometries into one. */
function mergeGeometries(geos) {
  const valid = geos.filter(Boolean);
  if (valid.length === 0) return null;
  if (valid.length === 1) return valid[0];

  let totalV = 0, totalI = 0;
  for (const g of valid) { totalV += g.positions.length / 3; totalI += g.indices.length; }

  const mp = new Float32Array(totalV * 3);
  const mn = new Float32Array(totalV * 3);
  const mi = new Uint32Array(totalI);
  let vOff = 0, iOff = 0;

  for (const g of valid) {
    mp.set(g.positions, vOff * 3);
    mn.set(g.normals,   vOff * 3);
    for (let i = 0; i < g.indices.length; i++) mi[iOff + i] = g.indices[i] + vOff;
    vOff += g.positions.length / 3;
    iOff += g.indices.length;
  }
  return { positions: mp, normals: mn, indices: mi };
}

/** Build a smooth tube from a set of sampled rings. */
function tubeFromRings(rings, numSegs) {
  if (rings.length < 2) return null;
  const positions = [];
  const indices   = [];

  for (const { y, cx, cz, r } of rings) {
    for (let seg = 0; seg < numSegs; seg++) {
      const angle = (2 * Math.PI * seg) / numSegs;
      positions.push(cx + r * Math.cos(angle), y, cz + r * Math.sin(angle));
    }
  }

  // Winding (a,c,b)/(b,c,d) gives outward normals on a CCW ring
  for (let ri = 0; ri < rings.length - 1; ri++) {
    for (let seg = 0; seg < numSegs; seg++) {
      const next = (seg + 1) % numSegs;
      const a = ri       * numSegs + seg;
      const b = ri       * numSegs + next;
      const c = (ri + 1) * numSegs + seg;
      const d = (ri + 1) * numSegs + next;
      indices.push(a, c, b, b, c, d);
    }
  }

  const pos = new Float32Array(positions);
  const idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}

// ── Pants tube helper ─────────────────────────────────────────────────────────

/**
 * Build smooth pants geometry: two leg tubes + a waistband that covers the
 * open top of each tube and creates the smooth waist connection.
 *
 * @param {Float32Array} bPos       body mesh positions
 * @param {number}       yLo        bottom of pants zone (world Y)
 * @param {number}       yHi        top of pants zone / hip crease (world Y)
 * @param {number}       bodyHeight full body Y span (for waistband sizing)
 * @param {number}       baseOffset radial clearance beyond body surface
 */
function buildPantsGeometry(bPos, yLo, yHi, bodyHeight, baseOffset) {
  const vCount    = bPos.length / 3;
  const numSlices = 12;
  const legSegs   = 14;   // segments per leg ring
  const hipSegs   = 18;   // segments for the wider waistband ring

  // ── Individual leg tubes ─────────────────────────────────────────────────
  function buildLegTube(isLeft) {
    const rings = [];

    for (let si = 0; si <= numSlices; si++) {
      const y    = yLo + (yHi - yLo) * (si / numSlices);
      const yWin = (yHi - yLo) / numSlices * 0.65;

      let sumX = 0, sumZ = 0, n = 0;
      for (let i = 0; i < vCount; i++) {
        const py = bPos[i*3+1], px = bPos[i*3];
        if (py < y - yWin || py > y + yWin) continue;
        if (isLeft ? px >= 0 : px <= 0) continue;
        sumX += px; sumZ += bPos[i*3+2]; n++;
      }
      if (n < 3) continue;

      const cx = sumX / n, cz = sumZ / n;
      let maxR = 0;
      for (let i = 0; i < vCount; i++) {
        const py = bPos[i*3+1], px = bPos[i*3];
        if (py < y - yWin || py > y + yWin) continue;
        if (isLeft ? px >= 0 : px <= 0) continue;
        const dx = px - cx, dz = bPos[i*3+2] - cz;
        maxR = Math.max(maxR, Math.sqrt(dx*dx + dz*dz));
      }
      if (maxR < 0.01) maxR = 0.04;
      rings.push({ y, cx, cz, r: maxR + baseOffset });
    }

    return tubeFromRings(rings, legSegs);
  }

  // ── Waistband tube — spans full hip width, hides the leg tube openings ──
  function buildWaistband() {
    const waistH  = bodyHeight * 0.055;  // ~9 cm tall waistband for H=1.75
    const wLo     = yHi - waistH * 0.4; // start slightly below hipY
    const wHi     = yHi + waistH * 0.6; // extend above hipY
    const wSlices = 4;
    const rings   = [];

    for (let si = 0; si <= wSlices; si++) {
      const y    = wLo + (wHi - wLo) * (si / wSlices);
      const yWin = waistH / wSlices;

      // Use ALL vertices at this height (full hip width, not split by side)
      let sumX = 0, sumZ = 0, n = 0;
      for (let i = 0; i < vCount; i++) {
        const py = bPos[i*3+1];
        if (py < y - yWin || py > y + yWin) continue;
        sumX += bPos[i*3]; sumZ += bPos[i*3+2]; n++;
      }
      if (n < 3) continue;

      const cx = sumX / n, cz = sumZ / n;
      let maxR = 0;
      for (let i = 0; i < vCount; i++) {
        const py = bPos[i*3+1];
        if (py < y - yWin || py > y + yWin) continue;
        const dx = bPos[i*3] - cx, dz = bPos[i*3+2] - cz;
        maxR = Math.max(maxR, Math.sqrt(dx*dx + dz*dz));
      }
      if (maxR < 0.01) maxR = 0.08;
      // Slightly larger than body to create a visible shelf over leg tubes
      rings.push({ y, cx, cz, r: maxR + baseOffset * 1.15 });
    }

    return tubeFromRings(rings, hipSegs);
  }

  return mergeGeometries([buildLegTube(true), buildLegTube(false), buildWaistband()]);
}

// ── Main export ───────────────────────────────────────────────────────────────

/**
 * Build clothing geometry.
 * Pants (jeans/shorts) use smooth tubes; shirts use face-extrusion.
 *
 * @param {{ positions, normals, indices }} bodyData
 * @param {Object} cfg  character config with .clothing array
 * @returns {Object} map of clothing type → { positions, normals, indices }
 */
export function buildClothingGeometry(bodyData, cfg) {
  const { positions: bPos, normals: bNorm, indices: bIdx } = bodyData;
  const vCount   = bPos.length / 3;
  const triCount = bIdx.length / 3;

  // Body Y extents and widest X
  let minY = Infinity, maxY = -Infinity, maxAbsX = 0;
  for (let i = 0; i < vCount; i++) {
    const y  = bPos[i*3 + 1];
    const ax = Math.abs(bPos[i*3]);
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
    if (ax > maxAbsX) maxAbsX = ax;
  }
  const bodyHeight = maxY - minY;

  // Zone boundaries — realistic humanoid (head ≈ 13% of height)
  const footTop  = minY + bodyHeight * 0.07;
  const kneeY    = minY + bodyHeight * 0.30;
  const hipY     = minY + bodyHeight * 0.53;
  const chestY   = minY + bodyHeight * 0.68;
  const armY     = minY + bodyHeight * 0.82;  // shoulder level
  const waistGap = bodyHeight * 0.010;

  // X caps for shirt face-extrusion (wide enough to reach shoulders)
  const X_TORSO        = maxAbsX * 0.20;
  const X_SHORT_SLEEVE = maxAbsX * 0.55;

  const baseOffset  = 0.024;
  const clothingList = Array.isArray(cfg.clothing) ? cfg.clothing : [];
  const result      = {};

  for (const ctype of clothingList) {
    if (ctype === 'none') continue;

    // ── Pants/shorts: tube geometry ──────────────────────────────────────────
    if (ctype === 'jeans' || ctype === 'shorts') {
      const yLo = ctype === 'jeans' ? footTop : kneeY;
      const geo = buildPantsGeometry(bPos, yLo, hipY, bodyHeight, baseOffset);
      if (!geo) {
        console.warn(`[LP Clothing] No leg geometry found for '${ctype}'`);
        continue;
      }
      result[ctype] = geo;
      console.log(`[LP Clothing] Built '${ctype}' (tube): ${geo.positions.length / 3} verts`);
      continue;
    }

    // ── Shirts: face-extrusion ───────────────────────────────────────────────
    const SHIRT_ZONES = {
      short_sleeve: [hipY + waistGap, armY,   X_SHORT_SLEEVE],
      polo:         [hipY + waistGap, armY,   X_SHORT_SLEEVE],
      long_sleeve:  [hipY + waistGap, armY,   Infinity      ],
      v_neck:       [hipY + waistGap, chestY, X_TORSO       ],
    };

    const zone = SHIRT_ZONES[ctype];
    if (!zone) continue;
    const [yLo, yHi, xCap] = zone;

    const verts   = [];
    const faces   = [];
    const vertMap = new Map();

    for (let t = 0; t < triCount; t++) {
      const ia = bIdx[t*3], ib = bIdx[t*3+1], ic = bIdx[t*3+2];
      const vs = [ia, ib, ic].map(i => ({
        x: bPos[i*3], y: bPos[i*3+1], z: bPos[i*3+2], i,
      }));

      if (!vs.some(v => v.y >= yLo && v.y <= yHi)) continue;
      const centX = (vs[0].x + vs[1].x + vs[2].x) / 3;
      if (Math.abs(centX) > xCap) continue;

      const newIdxs = vs.map(v => {
        if (!vertMap.has(v.i)) {
          const nx = bNorm ? bNorm[v.i*3]   : 0;
          const ny = bNorm ? bNorm[v.i*3+1] : 0;
          const nz = bNorm ? bNorm[v.i*3+2] : 0;
          verts.push(v.x + nx * baseOffset, v.y + ny * baseOffset, v.z + nz * baseOffset);
          vertMap.set(v.i, verts.length / 3 - 1);
        }
        return vertMap.get(v.i);
      });
      faces.push(...newIdxs);
    }

    if (verts.length === 0) {
      console.warn(`[LP Clothing] No faces for '${ctype}' (yLo=${yLo.toFixed(3)}, yHi=${yHi.toFixed(3)}, xCap=${isFinite(xCap) ? xCap.toFixed(3) : 'Inf'})`);
      continue;
    }

    const pos = new Float32Array(verts);
    const idx = new Uint32Array(faces);
    result[ctype] = { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
    console.log(`[LP Clothing] Built '${ctype}': ${verts.length / 3} verts, ${faces.length / 3} faces`);
  }

  return result;
}

// ── Collar and buttons ────────────────────────────────────────────────────────

/**
 * Build a procedural collar ring for a polo shirt.
 */
export function buildCollarGeometry(bodyData, armY, bodyHeight, baseOffset) {
  const bPos = bodyData.positions;
  const vCount = bPos.length / 3;
  const yWindow  = bodyHeight * 0.04;
  const neckXCap = bodyHeight * 0.05;

  let maxZ = -Infinity, minZ = Infinity, maxAbsX = 0;
  for (let i = 0; i < vCount; i++) {
    const y  = bPos[i*3+1];
    const ax = Math.abs(bPos[i*3]);
    if (Math.abs(y - armY) < yWindow && ax < neckXCap) {
      const z = bPos[i*3+2];
      if (z > maxZ) maxZ = z;
      if (z < minZ) minZ = z;
      if (ax > maxAbsX) maxAbsX = ax;
    }
  }
  if (maxZ === -Infinity) return null;

  const collarH   = bodyHeight * 0.04;
  const collarOff = baseOffset * 1.8;
  const radiusX   = maxAbsX + collarOff;
  const radiusZ   = (maxZ - minZ) / 2 + collarOff;
  const centerZ   = (maxZ + minZ) / 2;
  const segments  = 16;

  const positions = [];
  const indices   = [];

  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    const x = radiusX * Math.cos(angle);
    const z = centerZ + radiusZ * Math.sin(angle);
    positions.push(x, armY - collarH * 0.25, z);
    positions.push(x, armY + collarH * 0.75, z);
  }

  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments;
    const b0 = i * 2,   b1 = next * 2;
    const t0 = b0 + 1,  t1 = b1 + 1;
    indices.push(b0, t0, b1, b1, t0, t1);
  }

  const pos = new Float32Array(positions);
  const idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}

/**
 * Place small flat disc buttons along the center-front of the shirt zone.
 */
export function buildButtonGeometry(bodyData, yLo, yHi, numButtons = 4) {
  const bPos = bodyData.positions;
  const vCount = bPos.length / 3;

  let maxZ = -Infinity;
  for (let i = 0; i < vCount; i++) {
    const y  = bPos[i*3+1];
    const ax = Math.abs(bPos[i*3]);
    const z  = bPos[i*3+2];
    if (y >= yLo && y <= yHi && ax < 0.05 && z > maxZ) maxZ = z;
  }
  if (maxZ === -Infinity) return null;

  const buttonZ = maxZ + 0.030;
  const buttonR = 0.018;
  const segs    = 8;
  const yStart  = yLo + (yHi - yLo) * 0.15;
  const yEnd    = yHi - (yHi - yLo) * 0.12;
  const yStep   = numButtons > 1 ? (yEnd - yStart) / (numButtons - 1) : 0;

  const positions = [];
  const indices   = [];

  for (let b = 0; b < numButtons; b++) {
    const by     = yStart + b * yStep;
    const center = positions.length / 3;
    positions.push(0, by, buttonZ);
    for (let i = 0; i < segs; i++) {
      const angle = (2 * Math.PI * i) / segs;
      positions.push(buttonR * Math.cos(angle), by + buttonR * Math.sin(angle), buttonZ);
    }
    for (let i = 0; i < segs; i++) {
      const next = (i + 1) % segs;
      indices.push(center, center + 1 + i, center + 1 + next);
    }
  }

  const pos = new Float32Array(positions);
  const idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}
