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
 * Build clothing geometry by extruding body mesh faces outward.
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
  // Short sleeve: proportional to body height so it's immune to arm-pose ambiguity.
  // bodyHeight * 0.17 ≈ shoulder-width/2 + a short sleeve cap (~6-7 cm past shoulder
  // for a 1.5 m character). Does NOT depend on maxAbsX (= full arm span in T-pose).
  const X_SHORT_SLEEVE = bodyHeight * 0.17;

  const ZONES = {
    short_sleeve: [hipY, shirtTopY, X_SHORT_SLEEVE],
    polo:         [hipY, shirtTopY, X_SHORT_SLEEVE],
    long_sleeve:  [hipY, shoulderY, Infinity      ],
    v_neck:       [hipY, chestY,    X_TORSO       ],
    jeans:        [footTop, hipY,   X_LEGS        ],
    shorts:       [kneeY,   hipY,   X_LEGS        ],
  };

  const baseOffset = 0.026;
  const clothingList = Array.isArray(cfg.clothing) ? cfg.clothing : [];
  const result = {};

  for (const ctype of clothingList) {
    if (ctype === 'none') continue;
    const zone = ZONES[ctype];
    if (!zone) continue;
    const [yLo, yHi, xCap] = zone;

    const verts = [];
    const faces = [];
    const vertMap = new Map();

    for (let t = 0; t < triCount; t++) {
      const ia = bIdx[t*3], ib = bIdx[t*3+1], ic = bIdx[t*3+2];

      const vs = [ia, ib, ic].map(i => ({
        x: bPos[i*3],
        y: bPos[i*3+1],
        z: bPos[i*3+2],
        i,
      }));

      // Y: centroid filter on both bounds — includes edge triangles at waist and
      // shoulder without letting stray vertices poke out.
      const centY = (vs[0].y + vs[1].y + vs[2].y) / 3;
      if (centY < yLo || centY > yHi) continue;

      // X boundary: strict — skip if ANY vertex exceeds xCap (clean sleeve edge).
      if (isFinite(xCap) && vs.some(v => Math.abs(v.x) > xCap)) continue;

      const newIdxs = vs.map(v => {
        if (!vertMap.has(v.i)) {
          const nx = bNorm ? bNorm[v.i*3]   : 0;
          const ny = bNorm ? bNorm[v.i*3+1] : 0;
          const nz = bNorm ? bNorm[v.i*3+2] : 0;
          // Only clamp the bottom — no vertex can be above yHi (already excluded above).
          const cy = Math.max(v.y, yLo);
          verts.push(v.x + nx * baseOffset, cy + ny * baseOffset, v.z + nz * baseOffset);
          vertMap.set(v.i, verts.length / 3 - 1);
        }
        return vertMap.get(v.i);
      });
      faces.push(...newIdxs);
    }

    if (verts.length === 0) {
      console.warn(`[Clothing] No faces found for '${ctype}' (yLo=${yLo.toFixed(3)}, yHi=${yHi.toFixed(3)}, xCap=${isFinite(xCap) ? xCap.toFixed(3) : 'Inf'})`);
      continue;
    }

    const pos = new Float32Array(verts);
    const idx = new Uint32Array(faces);
    result[ctype] = { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };

    console.log(`[Clothing] Built '${ctype}': ${verts.length / 3} verts, ${faces.length / 3} faces`);
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
