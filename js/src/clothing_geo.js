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
