/**
 * Face-extrusion clothing geometry for the low-poly (realistic) body mesh.
 *
 * Same strategy as clothing_geo.js (cartoon): select body-mesh faces in a Y
 * zone, push vertices outward along surface normals.  The only difference is
 * the zone boundaries — realistic proportions use skeleton bone positions
 * (from skeleton.js boneWorldPositions) rather than cartoon chibi proportions.
 *
 * Realistic bone fractions of body height H:
 *   Foot    (15): Y = H * 0.03  — ankle
 *   LowerLeg(14): Y = H * 0.27  — knee
 *   UpperLeg(13): Y = H * 0.50  — hip joint
 *   Hips    (0):  Y = H * 0.52  — pelvis / waistband
 *   Chest   (2):  Y = H * 0.68  — chest
 *   Shoulder(5):  Y = H * 0.72  — shirt armhole
 */

// ── Vertex normals ────────────────────────────────────────────────────────────

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

// ── Main export ───────────────────────────────────────────────────────────────

/**
 * Build clothing by extruding body mesh faces outward along surface normals.
 *
 * @param {{ positions, normals, indices }} bodyData
 * @param {Object} cfg  - character config (.clothing array, .height)
 * @returns {Object} map of clothing type → { positions, normals, indices }
 */
export function buildClothingGeometry(bodyData, cfg) {
  const { positions: bPos, normals: bNorm, indices: bIdx } = bodyData;
  const vCount   = bPos.length / 3;
  const triCount = bIdx.length / 3;

  // Mesh extents
  let minY = Infinity, maxY = -Infinity, maxAbsX = 0;
  for (let i = 0; i < vCount; i++) {
    const y  = bPos[i*3 + 1];
    const ax = Math.abs(bPos[i*3]);
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
    if (ax > maxAbsX) maxAbsX = ax;
  }
  const bodyH = maxY - minY;

  // Zone boundaries for a realistic (7.5:1) body — derived from boneWorldPositions
  // fractions.  Cartoon uses 0.24/0.43/0.57/0.63; realistic proportions are higher
  // because the head is smaller so the torso takes up more of the total height.
  const footTop = minY + bodyH * 0.05;   // just above ankle  (bone: 0.03)
  const kneeY   = minY + bodyH * 0.27;   // knee              (bone: 0.27)
  const hipY    = minY + bodyH * 0.52;   // pelvis / waistband (bone: 0.52)
  const chestY  = minY + bodyH * 0.68;   // chest              (bone: 0.68)
  const armY    = minY + bodyH * 0.72;   // shoulder armhole   (bone: 0.72)

  // X caps relative to bodyH (height-based absolute values).
  // This is reliable regardless of mesh pose (T-pose, A-pose, I-pose):
  //   torso half-width  ≈ bodyH * 0.14  (shoulder bone at H*0.08, plus margin)
  //   short sleeve end  ≈ bodyH * 0.22  (upper-arm bone at H*0.14, plus margin)
  //   leg width         ≈ bodyH * 0.18  (hip-joint bone at H*0.09, plus generous margin)
  // Pants and long sleeves use Infinity — the Y zone alone is sufficient
  // (there are no arm verts in the leg Y band, no need to cap X there).
  const X_TORSO        = bodyH * 0.16;   // torso only (v-neck)
  const X_SHORT_SLEEVE = bodyH * 0.26;   // torso + upper arm (polo/short_sleeve)

  const waistGap = bodyH * 0.010;

  const ZONES = {
    short_sleeve: [hipY + waistGap, armY,   X_SHORT_SLEEVE],
    polo:         [hipY + waistGap, armY,   X_SHORT_SLEEVE],
    long_sleeve:  [hipY + waistGap, armY,   Infinity      ],
    v_neck:       [hipY + waistGap, chestY, X_TORSO       ],
    jeans:        [footTop,         hipY,   Infinity      ],
    shorts:       [kneeY,           hipY,   Infinity      ],
  };

  console.log(`[LP Clothing] bodyH=${bodyH.toFixed(3)} minY=${minY.toFixed(3)} maxAbsX=${maxAbsX.toFixed(3)} | footTop=${footTop.toFixed(3)} knee=${kneeY.toFixed(3)} hip=${hipY.toFixed(3)} chest=${chestY.toFixed(3)} arm=${armY.toFixed(3)}`);

  const baseOffset   = 0.022;
  const clothingList = Array.isArray(cfg.clothing) ? cfg.clothing : [];
  const result       = {};

  for (const ctype of clothingList) {
    if (ctype === 'none') continue;
    const zone = ZONES[ctype];
    if (!zone) continue;
    const [yLo, yHi, xCap] = zone;

    const verts    = [];
    const faces    = [];
    const vertMap  = new Map();

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
    console.log(`[LP Clothing] Built '${ctype}': ${verts.length/3} verts, ${faces.length/3} faces`);
  }

  return result;
}

// ── Collar ────────────────────────────────────────────────────────────────────

export function buildCollarGeometry(bodyData, armY, bodyHeight, baseOffset) {
  const bPos   = bodyData.positions;
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
  const positions = [], indices = [];

  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    const x = radiusX * Math.cos(angle);
    const z = centerZ + radiusZ * Math.sin(angle);
    positions.push(x, armY - collarH * 0.25, z);
    positions.push(x, armY + collarH * 0.75, z);
  }

  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments;
    const b0 = i * 2, b1 = next * 2, t0 = b0 + 1, t1 = b1 + 1;
    indices.push(b0, t0, b1, b1, t0, t1);
  }

  const pos = new Float32Array(positions), idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}

// ── Buttons ───────────────────────────────────────────────────────────────────

export function buildButtonGeometry(bodyData, yLo, yHi, numButtons = 4) {
  const bPos   = bodyData.positions;
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
  const positions = [], indices = [];

  for (let b = 0; b < numButtons; b++) {
    const by     = yStart + b * yStep;
    const center = positions.length / 3;
    positions.push(0, by, buttonZ);
    for (let i = 0; i < segs; i++) {
      const angle = (2 * Math.PI * i) / segs;
      positions.push(buttonR * Math.cos(angle), by + buttonR * Math.sin(angle), buttonZ);
    }
    for (let i = 0; i < segs; i++) {
      indices.push(center, center + 1 + i, center + 1 + ((i + 1) % segs));
    }
  }

  const pos = new Float32Array(positions), idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}
