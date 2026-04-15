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
 * Build a clothing shell by offsetting body mesh vertices along their surface normals.
 * Only includes triangles where ALL 3 vertices pass the zone + bone filter tests.
 * This gives a shell that perfectly conforms to the body at every point.
 *
 * @param {Float32Array}       bPos       body positions, stride 3
 * @param {Float32Array}       bNorm      body normals, stride 3 (unit, from glTF)
 * @param {Uint32Array}        bIdx       body triangle index buffer
 * @param {number}             vCount     bPos.length / 3
 * @param {number}             triCount   bIdx.length / 3
 * @param {number}             yLo        zone bottom (world Y)
 * @param {number}             yHi        zone top (world Y)
 * @param {number}             offset     outward gap in metres
 * @param {Uint16Array|null}   skinIdx    skin bone indices, stride 4
 * @param {Float32Array|null}  skinWts    skin bone weights, stride 4
 * @param {string}             boneMode   'excludeArm' | 'excludeTorso' | 'none'
 * @returns {{ positions: Float32Array, normals: Float32Array, indices: Uint32Array }|null}
 */
function buildVertexShell(bPos, bNorm, bIdx, vCount, triCount,
                          yLo, yHi, offset,
                          skinIdx, skinWts, boneMode) {

  // Bone filter
  // 'excludeArm':    include unless arm-bone total (5-12) >= 0.50  → shirt torso
  // 'excludeTorso':  include unless spine/chest total (1-4)  >= 0.50  → pants (mirrors excludeArm)
  // 'none':          include all                                        → long_sleeve
  function passFilter(i) {
    if (boneMode === 'none' || !skinIdx || !skinWts) return true;
    let armWt = 0, torsoWt = 0;
    for (let j = 0; j < 4; j++) {
      const b = skinIdx[i*4+j], w = skinWts[i*4+j];
      if (b >= 5 && b <= 12) armWt  += w;   // arm bones
      if (b >= 1 && b <= 4)  torsoWt += w;  // Spine(1), Chest(2), Neck(3), Head(4)
    }
    if (boneMode === 'excludeArm')    return armWt   < 0.50;
    if (boneMode === 'excludeTorso')  return torsoWt < 0.50;
    return true;
  }

  // Mark which body vertices are in the clothing zone
  const inZone = new Uint8Array(vCount);
  for (let i = 0; i < vCount; i++) {
    const y = bPos[i*3+1];
    if (y >= yLo && y <= yHi && passFilter(i)) inZone[i] = 1;
  }

  // Include triangles where ALL 3 verts are in-zone; offset each along its body normal
  const vertMap  = new Int32Array(vCount).fill(-1);
  const newVerts = [];
  const faces    = [];

  for (let t = 0; t < triCount; t++) {
    const ia = bIdx[t*3], ib = bIdx[t*3+1], ic = bIdx[t*3+2];
    if (!inZone[ia] || !inZone[ib] || !inZone[ic]) continue;

    for (const i of [ia, ib, ic]) {
      if (vertMap[i] !== -1) continue;
      const nx = bNorm ? bNorm[i*3]   : 0;
      const ny = bNorm ? bNorm[i*3+1] : 0;
      const nz = bNorm ? bNorm[i*3+2] : 0;
      newVerts.push(
        bPos[i*3]   + nx * offset,
        bPos[i*3+1] + ny * offset,
        bPos[i*3+2] + nz * offset,
      );
      vertMap[i] = newVerts.length / 3 - 1;
    }
    faces.push(vertMap[ia], vertMap[ib], vertMap[ic]);
  }

  if (newVerts.length === 0) return null;
  const pos = new Float32Array(newVerts);
  const idx = new Uint32Array(faces);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}

/** Merge two geometry objects into one. */
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
 * Uses skin-weight data to restrict each cross-section scan to arm/forearm vertices
 * only, preventing torso mesh from inflating the shoulder-seam ring.
 *
 * @param {Float32Array}  bPos      body positions (stride 3)
 * @param {number}        vCount
 * @param {number}        xStart    inner X (shoulder seam), absolute value
 * @param {number}        xEnd      outer X (sleeve hem), absolute value
 * @param {number}        xSign     +1 = right, -1 = left
 * @param {number}        yMin      lower Y bound for arm scan
 * @param {number}        yMax      upper Y bound for arm scan
 * @param {number}        offset    gap above body surface
 * @param {number}        maxArmR   max ring radius (cap against torso contamination)
 * @param {Uint16Array|null} skinIdx body skin bone indices (stride 4), or null
 * @param {Float32Array|null} skinWts body skin weights (stride 4), or null
 */
function buildProceduralSleeve(bPos, vCount, xStart, xEnd, xSign,
                               yMin, yMax, offset,
                               maxArmR = Infinity,
                               skinIdx = null, skinWts = null) {
  const N_RINGS = 7;
  const SEGS    = 16;
  const xSpan   = xEnd - xStart;
  const xWin    = xSpan * 0.18;  // tight window — was 0.35, heavy overlap caused blobs

  // Arm / forearm bone indices in our remapped scheme (0-18):
  //   LeftShoulder=5, LeftArm=6, LeftForeArm=7
  //   RightShoulder=9, RightArm=10, RightForeArm=11
  // xSign already constrains which X side, so we accept both left & right arm bones.
  //
  // Use weight-threshold (>= 0.20) rather than dominant-bone: shoulder-junction
  // vertices are often split 50/50 between Chest and LeftArm, so dominant-bone
  // check would exclude them and leave the inner sleeve ring empty.
  function isArmVert(i) {
    if (!skinIdx || !skinWts) return true;
    for (let j = 0; j < 4; j++) {
      const b = skinIdx[i * 4 + j];
      const w = skinWts[i * 4 + j];
      if (w >= 0.20 && ((b >= 5 && b <= 7) || (b >= 9 && b <= 11))) return true;
    }
    return false;
  }

  function scanAt(xAbs) {
    let mxY = -Infinity, mnY = Infinity, mxZ = -Infinity, mnZ = Infinity, found = false;
    for (let i = 0; i < vCount; i++) {
      const vxRaw = bPos[i*3];
      const vxAbs = Math.abs(vxRaw);
      if (Math.abs(vxAbs - xAbs) > xWin) continue;
      if ((vxRaw >= 0 ? +1 : -1) !== xSign) continue;
      const vy = bPos[i*3+1];
      if (vy < yMin || vy > yMax) continue;
      if (!isArmVert(i)) continue;  // skin-weight gate
      const vz = bPos[i*3+2];
      if (vy > mxY) mxY = vy;
      if (vy < mnY) mnY = vy;
      if (vz > mxZ) mxZ = vz;
      if (vz < mnZ) mnZ = vz;
      found = true;
    }
    if (!found) return null;
    // Cap radii so a sparse/noisy scan near the shoulder seam can't produce blobs
    const ry = Math.min((mxY - mnY) / 2 + offset, maxArmR);
    const rz = Math.min((mxZ - mnZ) / 2 + offset, maxArmR);
    return { cy: (mxY + mnY) / 2, ry, rz, cz: (mxZ + mnZ) / 2 };
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

  // Close the outer sleeve end with a disc cap.
  // Without this the tube is open and looks hollow from the side.
  {
    const lr = rings[rings.length - 1];
    const capIdx = positions.length / 3;
    positions.push(lr.x, lr.cy, lr.cz);
    for (let si = 0; si < SEGS; si++) {
      const next = (si + 1) % SEGS;
      // xSign>0: right arm cap faces +X → wind (cap, next, si) for outward normal
      // xSign<0: left arm cap faces −X → wind (cap, si, next)
      if (xSign > 0) {
        indices.push(capIdx, prevBase + next, prevBase + si);
      } else {
        indices.push(capIdx, prevBase + si, prevBase + next);
      }
    }
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
  const { positions: bPos, normals: bNorm, indices: bIdx,
          skinIndices: bSkinIdx, skinWeights: bSkinWts } = bodyData;
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
  const footTop    = minY + bodyHeight * 0.05;  // just above shoe line
  const kneeY      = minY + bodyHeight * 0.24;
  const hipY       = minY + bodyHeight * 0.45;  // natural waist (was 0.43 — too low/hip-level)
  const chestY     = minY + bodyHeight * 0.57;
  const armY       = minY + bodyHeight * 0.63;  // armpit level (used for v_neck)
  const shirtTopY  = minY + bodyHeight * 0.70;  // top of short-sleeve zone
  const shoulderY  = minY + bodyHeight * 0.73;  // shoulder top — long sleeves reach here

  const X_TORSO        = maxAbsX * 0.20;
  const X_LEGS         = maxAbsX * 0.28;
  const X_SHORT_SLEEVE = bodyHeight * 0.19;  // shoulder/sleeve cap width
  const X_NECK         = bodyHeight * 0.12;   // neckline ≈ 71% of shoulder width (target 60-80%)

  // Y zone boundaries for each clothing type (vertex shell only needs yLo/yHi)
  // Jeans top extends to 0.52*bH (above hipY=0.45) so the "all-3-in-zone" test
  // captures hip/crotch triangles whose vertices straddle the old hipY boundary.
  const jeansTopY = minY + bodyHeight * 0.52;
  const ZONES = {
    short_sleeve: [hipY,    shirtTopY],
    polo:         [hipY,    shirtTopY],
    long_sleeve:  [hipY,    shoulderY],
    v_neck:       [hipY,    chestY   ],
    jeans:        [footTop, jeansTopY],
    shorts:       [kneeY,   hipY     ],
  };

  const baseOffset    = 0.016;  // tight fit matching reference
  const SHELL_MARGIN  = bodyHeight * 0.015;  // ~2.6 cm — captures boundary triangles
  const clothingList  = Array.isArray(cfg.clothing) ? cfg.clothing : [];
  const result        = {};

  for (const ctype of clothingList) {
    if (ctype === 'none') continue;
    const zone = ZONES[ctype];
    if (!zone) continue;
    const [yLo, yHi] = zone;

    if (ctype === 'jeans' || ctype === 'shorts') {
      // Single vertex shell — both legs + hip bridge in one pass (no crotch gap)
      const geo = buildVertexShell(
        bPos, bNorm, bIdx, vCount, triCount,
        yLo - SHELL_MARGIN, yHi + SHELL_MARGIN, baseOffset,
        bSkinIdx, bSkinWts, 'excludeTorso'
      );
      if (!geo) { console.warn(`[Clothing] No verts for '${ctype}'`); continue; }
      result[ctype] = geo;
      console.log(`[Clothing] Built vertex-shell legs '${ctype}': ${geo.positions.length/3} verts`);

    } else if (ctype === 'long_sleeve') {
      // Single shell covering torso + arms — no bone filter needed for full coverage
      const geo = buildVertexShell(
        bPos, bNorm, bIdx, vCount, triCount,
        yLo - SHELL_MARGIN, yHi + SHELL_MARGIN, baseOffset,
        bSkinIdx, bSkinWts, 'none'
      );
      if (!geo) { console.warn(`[Clothing] No verts for '${ctype}'`); continue; }
      result[ctype] = geo;
      console.log(`[Clothing] Built vertex-shell long sleeve '${ctype}': ${geo.positions.length/3} verts`);

    } else if (ctype === 'v_neck') {
      // Torso shell only — arm exclusion gives clean armhole opening
      const geo = buildVertexShell(
        bPos, bNorm, bIdx, vCount, triCount,
        yLo - SHELL_MARGIN, yHi + SHELL_MARGIN, baseOffset,
        bSkinIdx, bSkinWts, 'excludeArm'
      );
      if (!geo) { console.warn(`[Clothing] No verts for '${ctype}'`); continue; }
      result[ctype] = geo;
      console.log(`[Clothing] Built vertex-shell shirt '${ctype}': ${geo.positions.length/3} verts`);

    } else {
      // short_sleeve / polo: torso shell + short sleeve tubes + shoulder seam bands
      const torso = buildVertexShell(
        bPos, bNorm, bIdx, vCount, triCount,
        yLo - SHELL_MARGIN, yHi + SHELL_MARGIN, baseOffset,
        bSkinIdx, bSkinWts, 'excludeArm'
      );
      if (!torso) { console.warn(`[Clothing] No torso verts for '${ctype}'`); continue; }
      // Shoulder seam (sleeve start) is at |x|~0.08*bH; short sleeve end ~0.19*bH
      const sleeveXStart = bodyHeight * 0.08;
      const sleeveXEnd   = bodyHeight * 0.19;
      // Arm verts sit in Y=[0.577, 0.661]*bH — scan that range (relative to minY=0)
      const sleeveYMin   = bodyHeight * 0.54;
      const sleeveYMax   = bodyHeight * 0.69;
      const maxArmR      = bodyHeight * 0.058;

      // Armhole band — a ring at the shoulder seam that bridges the shirt shell's open
      // edge to the sleeve tube's inner ring, hiding any gap between the two pieces.
      // Only arm-bone-weighted vertices are scanned so the ring fits the ARM, not the
      // wider torso shoulder.
      const buildArmholeBand = (xSign) => {
        const xWin = bodyHeight * 0.04;
        let mxY = -Infinity, mnY_ = Infinity, mxZ = -Infinity, mnZ = Infinity, nf = 0;
        for (let i = 0; i < vCount; i++) {
          const vx = bPos[i*3], vy = bPos[i*3+1], vz = bPos[i*3+2];
          if (vx * xSign <= 0) continue;                                       // correct side only
          if (Math.abs(Math.abs(vx) - sleeveXStart) > xWin) continue;         // near shoulder seam X
          if (vy < sleeveYMin - bodyHeight * 0.05 || vy > sleeveYMax) continue; // shoulder Y range
          // Only include arm-bone vertices so the ring radius matches the arm, not the torso
          if (bSkinIdx && bSkinWts) {
            let armWt = 0;
            for (let j = 0; j < 4; j++) {
              const b = bSkinIdx[i*4+j], w = bSkinWts[i*4+j];
              if (b >= 5 && b <= 12) armWt += w;
            }
            if (armWt < 0.20) continue;
          }
          if (vy > mxY) mxY = vy; if (vy < mnY_) mnY_ = vy;
          if (vz > mxZ) mxZ = vz; if (vz < mnZ) mnZ = vz;
          nf++;
        }
        if (nf < 3) return null;
        const cy = (mxY + mnY_) / 2, ry = (mxY - mnY_) / 2 + baseOffset * 1.5;
        const cz = (mxZ + mnZ)  / 2, rz = (mxZ - mnZ)  / 2 + baseOffset * 1.5;
        const bW = bodyHeight * 0.022;                // band width along X (spans the gap)
        const xA = sleeveXStart * xSign - bW * xSign; // inward edge (overlaps shirt shell)
        const xB = sleeveXStart * xSign + bW * xSign; // outward edge (overlaps sleeve tube)
        const SEGS = 16;
        const pos = [], idx = [];
        for (let si = 0; si < SEGS; si++) {
          const a = (2 * Math.PI * si) / SEGS;
          const y = cy + ry * Math.sin(a), z = cz + rz * Math.cos(a);
          pos.push(xA, y, z, xB, y, z);
        }
        for (let si = 0; si < SEGS; si++) {
          const next = (si + 1) % SEGS;
          const b0 = si*2, b1 = next*2, t0 = b0+1, t1 = b1+1;
          idx.push(b0, t0, b1, b1, t0, t1);
        }
        const p = new Float32Array(pos), ix = new Uint32Array(idx);
        return { positions: p, normals: computeVertexNormals(p, ix), indices: ix };
      };

      const rSleeve = buildProceduralSleeve(bPos, vCount, sleeveXStart, sleeveXEnd, +1,
                        sleeveYMin, sleeveYMax, baseOffset, maxArmR, bSkinIdx, bSkinWts);
      const lSleeve = buildProceduralSleeve(bPos, vCount, sleeveXStart, sleeveXEnd, -1,
                        sleeveYMin, sleeveYMax, baseOffset, maxArmR, bSkinIdx, bSkinWts);
      const rBand = buildArmholeBand(+1);
      const lBand = buildArmholeBand(-1);
      const geo = mergeTubes(torso, mergeTubes(rSleeve, mergeTubes(lSleeve, mergeTubes(rBand, lBand))));
      if (!geo) { console.warn(`[Clothing] Empty merged geo for '${ctype}'`); continue; }
      result[ctype] = geo;
      console.log(`[Clothing] Built vertex-shell shirt+sleeves '${ctype}': ${result[ctype].positions.length/3} verts`);
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
