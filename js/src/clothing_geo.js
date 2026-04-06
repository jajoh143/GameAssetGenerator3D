/**
 * Face-extrusion clothing geometry from body mesh.
 * Port of generators/humanoid/gltf_pipeline/clothing_geo.py
 *
 * Clothing is created by selecting faces from the body mesh within a
 * Y-height range (Y=up in glTF/Three.js), then offsetting their vertices
 * radially outward in the X-Z plane (keeping Y unchanged).
 *
 * Zone boundaries are computed from the actual body geometry's Y range,
 * so they work correctly regardless of character height/scale.
 *
 * T-pose note: arms are horizontal at ~72% body height with large X extent.
 * Per-type X caps exclude arm vertices for torso-only clothing.
 */

import * as THREE from 'three';

/**
 * Build clothing geometry by extruding body mesh faces outward.
 *
 * @param {THREE.BufferGeometry} bodyGeo - the body mesh geometry
 * @param {Object} cfg - character config with .clothing array
 * @returns {Object} map of clothing type name → THREE.BufferGeometry
 */
export function buildClothingGeometry(bodyGeo, cfg) {
  const posAttr  = bodyGeo.attributes.position;
  const normAttr = bodyGeo.attributes.normal;
  const idxAttr  = bodyGeo.index;

  // Compute body Y (height) range and max X extent from actual geometry
  let minY = Infinity, maxY = -Infinity, maxAbsX = 0;
  for (let i = 0; i < posAttr.count; i++) {
    const y = posAttr.getY(i);
    const ax = Math.abs(posAttr.getX(i));
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
    if (ax > maxAbsX) maxAbsX = ax;
  }
  const bodyHeight = maxY - minY;

  // Zone boundaries as fractions of body height.
  // The cartoon character has a large head (~28% of total Y), so body landmarks
  // sit lower than realistic proportions. Fractions tuned for Cartoon_Male.glb.
  const footTop  = minY + bodyHeight * 0.05;   // just above floor level
  const kneeY    = minY + bodyHeight * 0.24;   // knee height
  const hipY     = minY + bodyHeight * 0.43;   // hip/waist height
  const chestY   = minY + bodyHeight * 0.57;   // lower chest height
  const armY     = minY + bodyHeight * 0.63;   // shoulder / shirt collar height
  const waistGap = bodyHeight * 0.010;

  // Per-type X caps to exclude arm geometry in T-pose.
  // Arms are horizontal: maxAbsX ≈ full arm span. Use centroid-based X test
  // so one wide vertex doesn't discard the whole face.
  const X_TORSO        = maxAbsX * 0.20;   // torso body only
  const X_LEGS         = maxAbsX * 0.28;   // hip + legs (legs splay slightly)
  const X_SHORT_SLEEVE = maxAbsX * 0.34;   // shoulder + short sleeve stub
  // kneeY already defined above

  // Define clothing zones: [yMin, yMax, xCap]
  // xCap applied to face centroid |x| so partial-boundary faces aren't dropped.
  const ZONES = {
    short_sleeve: [hipY + waistGap, armY,                 X_SHORT_SLEEVE],
    polo:         [hipY + waistGap, armY,                 X_SHORT_SLEEVE],
    long_sleeve:  [hipY + waistGap, armY,                 Infinity      ],
    v_neck:       [hipY + waistGap, chestY,               X_TORSO       ],
    jeans:        [footTop,         hipY,                  X_LEGS       ],
    shorts:       [kneeY,           hipY,                  X_LEGS       ],
  };

  // Offset from body surface along vertex normals (clothing thickness).
  // 2cm gives enough separation to prevent z-fighting without looking puffy.
  const baseOffset = 0.020;

  const clothingList = Array.isArray(cfg.clothing) ? cfg.clothing : [];
  const result = {};

  for (const ctype of clothingList) {
    if (ctype === 'none') continue;
    const zone = ZONES[ctype];
    if (!zone) continue;
    const [yLo, yHi, xCap] = zone;

    const verts = [];
    const faces = [];
    const vertMap = new Map(); // original vertex index → new index

    const triCount = idxAttr ? idxAttr.count / 3 : posAttr.count / 3;
    for (let t = 0; t < triCount; t++) {
      const [ia, ib, ic] = idxAttr
        ? [idxAttr.getX(t*3), idxAttr.getX(t*3+1), idxAttr.getX(t*3+2)]
        : [t*3, t*3+1, t*3+2];

      const vs = [ia, ib, ic].map(i => ({
        x: posAttr.getX(i),
        y: posAttr.getY(i),
        z: posAttr.getZ(i),
        i,
      }));

      // Face must have at least one vertex in the Y zone
      const anyInZone = vs.some(v => v.y >= yLo && v.y <= yHi);
      if (!anyInZone) continue;

      // Exclude faces whose centroid X exceeds the cap (arm filtering).
      // Centroid-based avoids discarding faces that merely touch the boundary.
      const centX = (vs[0].x + vs[1].x + vs[2].x) / 3;
      if (Math.abs(centX) > xCap) continue;

      const newIdxs = vs.map(v => {
        if (!vertMap.has(v.i)) {
          // Offset along body surface normal for a uniform-thickness clothing layer
          const nx = normAttr ? normAttr.getX(v.i) : 0;
          const ny = normAttr ? normAttr.getY(v.i) : 0;
          const nz = normAttr ? normAttr.getZ(v.i) : 0;
          verts.push(
            v.x + nx * baseOffset,
            v.y + ny * baseOffset,
            v.z + nz * baseOffset
          );
          vertMap.set(v.i, verts.length / 3 - 1);
        }
        return vertMap.get(v.i);
      });
      faces.push(...newIdxs);
    }

    if (verts.length === 0) {
      console.warn(`[Clothing] No faces found for '${ctype}' (yLo=${yLo.toFixed(3)}, yHi=${yHi.toFixed(3)}, xCap=${xCap.toFixed(3)})`);
      continue;
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    geo.setIndex(new THREE.BufferAttribute(new Uint32Array(faces), 1));
    geo.computeVertexNormals();
    result[ctype] = geo;

    console.log(`[Clothing] Built '${ctype}': ${verts.length / 3} verts, ${faces.length / 3} faces`);
  }

  return result;
}

/**
 * Build a procedural collar ring for a polo shirt.
 * Samples the neck cross-section from the body geometry and builds a cylinder band.
 *
 * @param {THREE.BufferGeometry} bodyGeo
 * @param {number} armY - Y position of the collar level (top of shirt zone)
 * @param {number} bodyHeight - total Y range of the body mesh
 * @param {number} baseOffset - radial offset from body surface
 * @returns {THREE.BufferGeometry|null}
 */
export function buildCollarGeometry(bodyGeo, armY, bodyHeight, baseOffset) {
  const posAttr = bodyGeo.attributes.position;
  const yWindow = bodyHeight * 0.04;

  let maxZ = -Infinity, minZ = Infinity, maxAbsX = 0;
  for (let i = 0; i < posAttr.count; i++) {
    const y = posAttr.getY(i);
    if (Math.abs(y - armY) < yWindow) {
      const z  = posAttr.getZ(i);
      const ax = Math.abs(posAttr.getX(i));
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
    positions.push(x, armY - collarH * 0.25, z);  // bottom of collar band
    positions.push(x, armY + collarH * 0.75, z);  // top of collar band
  }

  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments;
    const b0 = i * 2, b1 = next * 2;
    const t0 = b0 + 1,  t1 = b1 + 1;
    indices.push(b0, t0, b1, b1, t0, t1);
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(positions), 3));
  geo.setIndex(new THREE.BufferAttribute(new Uint32Array(indices), 1));
  geo.computeVertexNormals();
  return geo;
}

/**
 * Place small flat disc buttons along the center-front of the shirt zone.
 *
 * @param {THREE.BufferGeometry} bodyGeo
 * @param {number} yLo - bottom Y of the shirt zone
 * @param {number} yHi - top Y of the shirt zone
 * @param {number} numButtons
 * @returns {THREE.BufferGeometry|null}
 */
export function buildButtonGeometry(bodyGeo, yLo, yHi, numButtons = 4) {
  const posAttr = bodyGeo.attributes.position;

  let maxZ = -Infinity;
  for (let i = 0; i < posAttr.count; i++) {
    const y  = posAttr.getY(i);
    const ax = Math.abs(posAttr.getX(i));
    const z  = posAttr.getZ(i);
    if (y >= yLo && y <= yHi && ax < 0.05) {
      if (z > maxZ) maxZ = z;
    }
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

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(positions), 3));
  geo.setIndex(new THREE.BufferAttribute(new Uint32Array(indices), 1));
  geo.computeVertexNormals();
  return geo;
}
