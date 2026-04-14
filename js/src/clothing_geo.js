/**
 * Face-extrusion clothing geometry from body mesh.
 * Returns plain { positions, normals, indices } arrays — no Three.js dependency.
 *
 * Clothing is created by selecting faces from the body mesh within a Y-height
 * range (Y=up in glTF), then offsetting their vertices along surface normals.
 * Zone boundaries are computed from actual body geometry Y range.
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

/**
 * Build a smooth tube by scanning the body's cross-section at multiple Y levels
 * and connecting fitted elliptical rings.  Floats `offset` metres above the body.
 * This avoids all face-extrusion artefacts (jagged edges, protruding flaps) because
 * we own every vertex — nothing is inherited from body triangles.
 *
 * @param {Float32Array} bPos   - body positions (stride 3)
 * @param {number}       vCount
 * @param {number}       yLo      - bottom of the tube
 * @param {number}       yHi      - top of the tube
 * @param {number}       xCap     - max |x| at the bottom of the tube
 * @param {number}       xCapTop  - max |x| at the top (narrower = armhole curve + neckline taper)
 * @param {number}       offset   - gap above body surface
 * @returns {{ positions, normals, indices }|null}
 */
function buildProceduralTube(bPos, vCount, yLo, yHi, xCap, xCapTop, offset) {
  const N_RINGS     = 14;
  const SEGS        = 24;
  const ySpan       = yHi - yLo;
  const yWin        = ySpan * 0.08;
  // Taper: full xCap up to TAPER_START, smoothstep down to xCapTop by TAPER_END,
  // then hold xCapTop for the neckline so the top rings form a clean uniform oval.
  // Keep full width for 72% of shirt height (shirt body + armhole area), then
  // transition quickly to neck width, leaving top 8% flat.
  const TAPER_START = 0.72;
  const TAPER_END   = 0.92;

  function scanAt(y, cap) {
    let mxZ = -Infinity, mnZ = Infinity, mxX = 0, found = false;
    for (let i = 0; i < vCount; i++) {
      const vy = bPos[i*3 + 1];
      if (Math.abs(vy - y) > yWin) continue;
      const vx = Math.abs(bPos[i*3]);
      if (vx > cap) continue;
      const vz = bPos[i*3 + 2];
      if (vz > mxZ) mxZ = vz;
      if (vz < mnZ) mnZ = vz;
      if (vx > mxX) mxX = vx;
      found = true;
    }
    if (!found) return null;
    return { rx: mxX + offset, rz: (mxZ - mnZ) / 2 + offset, cz: (mxZ + mnZ) / 2 };
  }

  const rings = [];
  for (let ri = 0; ri <= N_RINGS; ri++) {
    const t = ri / N_RINGS;
    const y = yLo + ySpan * t;
    // Smoothstep taper: full xCap below TAPER_START, curve to xCapTop by TAPER_END,
    // then hold xCapTop flat for the neckline.
    const raw    = Math.min(1, Math.max(0, (t - TAPER_START) / (TAPER_END - TAPER_START)));
    const smooth = raw * raw * (3 - 2 * raw);
    const cap    = xCap * (1 - smooth) + xCapTop * smooth;
    const s = scanAt(y, cap);
    if (s) rings.push({ y, ...s });
  }
  if (rings.length < 2) return null;

  const positions = [];
  const indices   = [];

  function addRing({ y, rx, rz, cz }) {
    const base = positions.length / 3;
    for (let si = 0; si < SEGS; si++) {
      const a = (2 * Math.PI * si) / SEGS;
      positions.push(rx * Math.cos(a), y, cz + rz * Math.sin(a));
    }
    return base;
  }

  let prevBase = addRing(rings[0]);
  for (let ri = 1; ri < rings.length; ri++) {
    const currBase = addRing(rings[ri]);
    for (let si = 0; si < SEGS; si++) {
      const next = (si + 1) % SEGS;
      indices.push(
        prevBase + si,   currBase + si,   prevBase + next,
        prevBase + next, currBase + si,   currBase + next,
      );
    }
    prevBase = currBase;
  }

  const pos = new Float32Array(positions);
  const idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}

/**
 * Build one leg tube by scanning one lateral half of the body (xSign=+1 right, -1 left).
 * The ring centre tracks the actual leg X position at each height level.
 */
function buildProceduralLeg(bPos, vCount, yLo, yHi, xSign, xCap, offset) {
  const N_RINGS = 10;
  const SEGS    = 20;
  const ySpan   = yHi - yLo;
  const yWin    = ySpan * 0.09;

  function scanAt(y) {
    let mxX = -Infinity, mnX = Infinity, mxZ = -Infinity, mnZ = Infinity, found = false;
    for (let i = 0; i < vCount; i++) {
      const vy = bPos[i*3+1];
      if (Math.abs(vy - y) > yWin) continue;
      const vx = bPos[i*3];
      if (vx * xSign <= 0 || Math.abs(vx) > xCap) continue;
      const vz = bPos[i*3+2];
      if (vx > mxX) mxX = vx;
      if (vx < mnX) mnX = vx;
      if (vz > mxZ) mxZ = vz;
      if (vz < mnZ) mnZ = vz;
      found = true;
    }
    if (!found) return null;
    return {
      cx: (mxX + mnX) / 2,
      rx: (mxX - mnX) / 2 + offset,
      rz: (mxZ - mnZ) / 2 + offset,
      cz: (mxZ + mnZ) / 2,
    };
  }

  const rings = [];
  for (let ri = 0; ri <= N_RINGS; ri++) {
    const y = yLo + ySpan * (ri / N_RINGS);
    const s = scanAt(y);
    if (s) rings.push({ y, ...s });
  }
  if (rings.length < 2) return null;

  const positions = [];
  const indices   = [];

  function addRing({ y, cx, rx, rz, cz }) {
    const base = positions.length / 3;
    for (let si = 0; si < SEGS; si++) {
      const a = (2 * Math.PI * si) / SEGS;
      positions.push(cx + rx * Math.cos(a), y, cz + rz * Math.sin(a));
    }
    return base;
  }

  let prevBase = addRing(rings[0]);
  for (let ri = 1; ri < rings.length; ri++) {
    const currBase = addRing(rings[ri]);
    for (let si = 0; si < SEGS; si++) {
      const next = (si + 1) % SEGS;
      indices.push(
        prevBase + si,   currBase + si,   prevBase + next,
        prevBase + next, currBase + si,   currBase + next,
      );
    }
    prevBase = currBase;
  }

  const pos = new Float32Array(positions);
  const idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}

/** Merge two geometry objects into one (used to combine left + right legs). */
function mergeTubes(a, b) {
  if (!a) return b;
  if (!b) return a;
  const offsetB    = a.positions.length / 3;
  const positions  = new Float32Array(a.positions.length + b.positions.length);
  const normals    = new Float32Array(a.normals.length   + b.normals.length);
  const indices    = new Uint32Array(a.indices.length   + b.indices.length);
  positions.set(a.positions); positions.set(b.positions, a.positions.length);
  normals.set(a.normals);     normals.set(b.normals,     a.normals.length);
  indices.set(a.indices);
  for (let i = 0; i < b.indices.length; i++) indices[a.indices.length + i] = b.indices[i] + offsetB;
  return { positions, normals, indices };
}

/**
 * Build one short sleeve tube — a horizontal cylinder running along the X axis.
 * Rings are in the Y-Z plane; the tube extends from the shoulder seam outward.
 *
 * @param {Float32Array} bPos    body positions (stride 3)
 * @param {number}       vCount
 * @param {number}       xStart  inner X (shoulder seam), absolute value
 * @param {number}       xEnd    outer X (sleeve hem), absolute value
 * @param {number}       xSign   +1 = right, -1 = left
 * @param {number}       yMin    lower Y bound for arm scan
 * @param {number}       yMax    upper Y bound for arm scan
 * @param {number}       offset  gap above body surface
 */
function buildProceduralSleeve(bPos, vCount, xStart, xEnd, xSign, yMin, yMax, offset) {
  const N_RINGS = 6;
  const SEGS    = 16;
  const xSpan   = xEnd - xStart;
  const xWin    = xSpan * 0.35;  // generous scan window at each X slice

  function scanAt(xAbs) {
    let mxY = -Infinity, mnY = Infinity, mxZ = -Infinity, mnZ = Infinity, found = false;
    for (let i = 0; i < vCount; i++) {
      const vxAbs = Math.abs(bPos[i*3]);
      if (Math.abs(vxAbs - xAbs) > xWin) continue;
      if ((bPos[i*3] >= 0 ? +1 : -1) !== xSign) continue;
      const vy = bPos[i*3+1];
      if (vy < yMin || vy > yMax) continue;
      const vz = bPos[i*3+2];
      if (vy > mxY) mxY = vy;
      if (vy < mnY) mnY = vy;
      if (vz > mxZ) mxZ = vz;
      if (vz < mnZ) mnZ = vz;
      found = true;
    }
    if (!found) return null;
    return {
      cy: (mxY + mnY) / 2,
      ry: (mxY - mnY) / 2 + offset,
      rz: (mxZ - mnZ) / 2 + offset,
      cz: (mxZ + mnZ) / 2,
    };
  }

  const rings = [];
  for (let ri = 0; ri <= N_RINGS; ri++) {
    const xAbs = xStart + xSpan * (ri / N_RINGS);
    const s = scanAt(xAbs);
    if (s) rings.push({ x: xAbs * xSign, ...s });
  }
  if (rings.length < 2) return null;

  const positions = [];
  const indices   = [];

  function addRing({ x, cy, ry, rz, cz }) {
    const base = positions.length / 3;
    for (let si = 0; si < SEGS; si++) {
      const a = (2 * Math.PI * si) / SEGS;
      // Ring perpendicular to the X axis — sleeve runs along X
      positions.push(x, cy + ry * Math.sin(a), cz + rz * Math.cos(a));
    }
    return base;
  }

  let prevBase = addRing(rings[0]);
  for (let ri = 1; ri < rings.length; ri++) {
    const currBase = addRing(rings[ri]);
    for (let si = 0; si < SEGS; si++) {
      const next = (si + 1) % SEGS;
      indices.push(
        prevBase + si,   currBase + si,   prevBase + next,
        prevBase + next, currBase + si,   currBase + next,
      );
    }
    prevBase = currBase;
  }

  const pos = new Float32Array(positions);
  const idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}

/**
 * Build clothing geometry by extruding body mesh faces outward (pants/shorts),
 * or by building a procedural tube from body cross-sections (shirts).
 *
 * @param {{ positions: Float32Array, normals: Float32Array, indices: Uint32Array }} bodyData
 * @param {Object} cfg - character config with .clothing array
 * @returns {Object} map of clothing type name → { positions, normals, indices }
 */
export function buildClothingGeometry(bodyData, cfg) {
  const { positions: bPos, normals: bNorm, indices: bIdx } = bodyData;
  const vCount = bPos.length / 3;
  const triCount = bIdx.length / 3;

  // Compute body Y range and max X extent
  let minY = Infinity, maxY = -Infinity, maxAbsX = 0;
  for (let i = 0; i < vCount; i++) {
    const y  = bPos[i*3 + 1];
    const ax = Math.abs(bPos[i*3]);
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
    if (ax > maxAbsX) maxAbsX = ax;
  }
  const bodyHeight = maxY - minY;

  // Zone boundaries tuned for cartoon character (large head ≈ 28% of total Y)
  const footTop    = minY + bodyHeight * 0.05;
  const kneeY      = minY + bodyHeight * 0.24;
  const hipY       = minY + bodyHeight * 0.43;
  const chestY     = minY + bodyHeight * 0.57;
  const armY       = minY + bodyHeight * 0.63;  // armpit level (used for v_neck)
  const shirtTopY  = minY + bodyHeight * 0.70;  // top of short-sleeve zone
  const shoulderY  = minY + bodyHeight * 0.73;  // shoulder top — long sleeves reach here

  const X_TORSO        = maxAbsX * 0.20;
  const X_LEGS         = maxAbsX * 0.28;
  const X_SHORT_SLEEVE = bodyHeight * 0.19;  // shoulder/sleeve cap width
  const X_NECK         = bodyHeight * 0.12;   // neckline ≈ 71% of shoulder width (target 60-80%)

  // [yLo, yHi, xCap (bottom), xCapTop (top)]
  // Shirt tubes taper from xCap at the waist to xCapTop at the neckline.
  const ZONES = {
    short_sleeve: [hipY,    shirtTopY, X_SHORT_SLEEVE, X_NECK              ],
    polo:         [hipY,    shirtTopY, X_SHORT_SLEEVE, X_NECK              ],
    long_sleeve:  [hipY,    shoulderY, Infinity,       null                ],
    v_neck:       [hipY,    chestY,    X_TORSO,        X_NECK * 0.85       ],
    jeans:        [footTop, hipY,      X_LEGS,         null                ],
    shorts:       [kneeY,   hipY,      X_LEGS,         null                ],
  };

  const baseOffset = 0.026;
  const clothingList = Array.isArray(cfg.clothing) ? cfg.clothing : [];
  const result = {};

  for (const ctype of clothingList) {
    if (ctype === 'none') continue;
    const zone = ZONES[ctype];
    if (!zone) continue;
    const [yLo, yHi, xCap, xCapTop] = zone;

    if (ctype === 'jeans' || ctype === 'shorts') {
      // Two leg tubes — one for each leg, merged into a single geometry
      const right = buildProceduralLeg(bPos, vCount, yLo, yHi, +1, xCap, baseOffset);
      const left  = buildProceduralLeg(bPos, vCount, yLo, yHi, -1, xCap, baseOffset);
      const geo   = mergeTubes(right, left);
      if (!geo) { console.warn(`[Clothing] Leg tube empty for '${ctype}'`); continue; }
      result[ctype] = geo;
      console.log(`[Clothing] Built procedural legs '${ctype}': ${geo.positions.length / 3} verts`);

    } else if (ctype === 'short_sleeve' || ctype === 'polo') {
      // Torso tube + two separate sleeve tubes branching at the shoulder seam
      const torso = buildProceduralTube(bPos, vCount, yLo, yHi, xCap, xCapTop, baseOffset);
      // Sleeve: shoulder seam → ~1/3 of upper arm; arm Y spans ±margin around shirt top
      const sleeveXEnd = xCap + bodyHeight * 0.11;
      const sleeveYMin = yHi - bodyHeight * 0.08;
      const sleeveYMax = yHi + bodyHeight * 0.02;
      const rSleeve = buildProceduralSleeve(bPos, vCount, xCap, sleeveXEnd, +1, sleeveYMin, sleeveYMax, baseOffset);
      const lSleeve = buildProceduralSleeve(bPos, vCount, xCap, sleeveXEnd, -1, sleeveYMin, sleeveYMax, baseOffset);
      const geo = mergeTubes(torso, mergeTubes(rSleeve, lSleeve));
      if (!geo) { console.warn(`[Clothing] Shirt tube empty for '${ctype}'`); continue; }
      result[ctype] = geo;
      console.log(`[Clothing] Built shirt+sleeves '${ctype}': ${geo.positions.length / 3} verts`);

    } else if (isFinite(xCap) && xCapTop !== null) {
      // v_neck: torso tube only, no sleeve branches
      const geo = buildProceduralTube(bPos, vCount, yLo, yHi, xCap, xCapTop, baseOffset);
      if (!geo) { console.warn(`[Clothing] Shirt tube empty for '${ctype}'`); continue; }
      result[ctype] = geo;
      console.log(`[Clothing] Built procedural shirt '${ctype}': ${geo.positions.length / 3} verts`);

    } else {
      // Face-extrusion for long_sleeve (Infinity xCap — arm coverage needs full mesh)
      const verts = [], faces = [], vertMap = new Map();
      for (let t = 0; t < triCount; t++) {
        const ia = bIdx[t*3], ib = bIdx[t*3+1], ic = bIdx[t*3+2];
        const vs = [ia, ib, ic].map(i => ({ x: bPos[i*3], y: bPos[i*3+1], z: bPos[i*3+2], i }));
        const centY = (vs[0].y + vs[1].y + vs[2].y) / 3;
        if (centY < yLo || centY > yHi) continue;
        const newIdxs = vs.map(v => {
          if (!vertMap.has(v.i)) {
            const nx = bNorm ? bNorm[v.i*3] : 0, ny = bNorm ? bNorm[v.i*3+1] : 0, nz = bNorm ? bNorm[v.i*3+2] : 0;
            verts.push(v.x + nx * baseOffset, Math.max(v.y, yLo) + ny * baseOffset, v.z + nz * baseOffset);
            vertMap.set(v.i, verts.length / 3 - 1);
          }
          return vertMap.get(v.i);
        });
        faces.push(...newIdxs);
      }
      if (verts.length === 0) { console.warn(`[Clothing] No faces for '${ctype}'`); continue; }
      const pos = new Float32Array(verts), idx = new Uint32Array(faces);
      result[ctype] = { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
      console.log(`[Clothing] Built face-extruded '${ctype}': ${verts.length / 3} verts`);
    }
  }

  return result;
}

/**
 * Build a procedural collar ring for a polo shirt.
 *
 * @param {{ positions: Float32Array }} bodyData
 * @param {number} armY - Y level of the collar
 * @param {number} bodyHeight - total Y range of body
 * @param {number} baseOffset - radial offset from body surface
 * @returns {{ positions, normals, indices }|null}
 */
export function buildCollarGeometry(bodyData, armY, bodyHeight, baseOffset) {
  const bPos = bodyData.positions;
  const vCount = bPos.length / 3;
  const yWindow  = bodyHeight * 0.04;
  const neckXCap = bodyHeight * 0.08;

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
 *
 * @param {{ positions: Float32Array }} bodyData
 * @param {number} yLo - bottom Y of shirt zone
 * @param {number} yHi - top Y of shirt zone
 * @param {number} numButtons
 * @returns {{ positions, normals, indices }|null}
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

/**
 * Procedural hem band at the shirt-waist boundary — covers the ragged bottom
 * edge that results from centroid-based face selection.
 *
 * @param {{ positions: Float32Array }} bodyData
 * @param {number} hipY   - Y level of the hip/waistline
 * @param {number} bodyHeight
 * @param {number} baseOffset
 * @returns {{ positions, normals, indices }|null}
 */
export function buildHemGeometry(bodyData, hipY, bodyHeight, baseOffset) {
  const bPos = bodyData.positions;
  const vCount = bPos.length / 3;
  const yWindow = bodyHeight * 0.05;
  const xLimit  = bodyHeight * 0.28;   // torso at hip level, excludes arms

  let maxZ = -Infinity, minZ = Infinity, maxAbsX = 0;
  for (let i = 0; i < vCount; i++) {
    const y  = bPos[i*3 + 1];
    const ax = Math.abs(bPos[i*3]);
    if (Math.abs(y - hipY) < yWindow && ax < xLimit) {
      const z = bPos[i*3 + 2];
      if (z > maxZ) maxZ = z;
      if (z < minZ) minZ = z;
      if (ax > maxAbsX) maxAbsX = ax;
    }
  }
  if (maxZ === -Infinity) return null;

  const hemH    = bodyHeight * 0.050;  // taller so it bridges any gap between shirt and jeans
  const hemOff  = baseOffset * 1.2;
  const radiusX = maxAbsX + hemOff;
  const radiusZ = (maxZ - minZ) / 2 + hemOff;
  const centerZ = (maxZ + minZ) / 2;
  const segments = 20;

  const positions = [];
  const indices   = [];

  for (let i = 0; i < segments; i++) {
    const a = (2 * Math.PI * i) / segments;
    const x = radiusX * Math.cos(a);
    const z = centerZ + radiusZ * Math.sin(a);
    positions.push(x, hipY - hemH * 0.35, z);   // bottom ring — extends below jeans top
    positions.push(x, hipY + hemH * 0.65, z);   // top ring — overlaps shirt hem
  }

  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments;
    const b0 = i * 2,    b1 = next * 2;
    const t0 = b0 + 1,   t1 = b1 + 1;
    indices.push(b0, t0, b1, b1, t0, t1);
  }

  const pos = new Float32Array(positions);
  const idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}

/**
 * Procedural belt — a slightly thicker, wider ring sitting above the waistline.
 *
 * @param {{ positions: Float32Array }} bodyData
 * @param {number} hipY
 * @param {number} bodyHeight
 * @param {number} baseOffset
 * @returns {{ positions, normals, indices }|null}
 */
export function buildBeltGeometry(bodyData, hipY, bodyHeight, baseOffset) {
  const bPos = bodyData.positions;
  const vCount = bPos.length / 3;
  const yWindow = bodyHeight * 0.04;
  const xLimit  = bodyHeight * 0.22;

  let maxZ = -Infinity, minZ = Infinity, maxAbsX = 0;
  for (let i = 0; i < vCount; i++) {
    const y  = bPos[i*3 + 1];
    const ax = Math.abs(bPos[i*3]);
    if (Math.abs(y - hipY) < yWindow && ax < xLimit) {
      const z = bPos[i*3 + 2];
      if (z > maxZ) maxZ = z;
      if (z < minZ) minZ = z;
      if (ax > maxAbsX) maxAbsX = ax;
    }
  }
  if (maxZ === -Infinity) return null;

  const beltH   = bodyHeight * 0.045;
  const beltOff = baseOffset * 1.8;   // wider than hem so it sits proud
  const radiusX = maxAbsX + beltOff;
  const radiusZ = (maxZ - minZ) / 2 + beltOff;
  const centerZ = (maxZ + minZ) / 2;
  const segments = 20;

  const positions = [];
  const indices   = [];

  for (let i = 0; i < segments; i++) {
    const a = (2 * Math.PI * i) / segments;
    const x = radiusX * Math.cos(a);
    const z = centerZ + radiusZ * Math.sin(a);
    positions.push(x, hipY + beltH * 0.05, z);   // bottom ring — just at waist
    positions.push(x, hipY + beltH * 1.05, z);   // top ring
  }

  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments;
    const b0 = i * 2,    b1 = next * 2;
    const t0 = b0 + 1,   t1 = b1 + 1;
    indices.push(b0, t0, b1, b1, t0, t1);
  }

  const pos = new Float32Array(positions);
  const idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}
