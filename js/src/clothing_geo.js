/**
 * Face-extrusion clothing geometry from body mesh.
 * Port of generators/humanoid/gltf_pipeline/clothing_geo.py
 *
 * Clothing is created by selecting faces from the body mesh within a
 * Z-height range, then offsetting their vertices radially outward.
 * This creates a layer that fits over the body like actual clothing.
 */

import * as THREE from 'three';

/**
 * Build clothing geometry by extruding body mesh faces outward.
 *
 * Clothing types and their Z-height ranges:
 * - short_sleeve, long_sleeve, v_neck: Cover torso (waist to chest)
 * - shorts: Cover upper legs
 * - jeans: Cover full legs (feet to below hip)
 *
 * @param {THREE.BufferGeometry} bodyGeo - the body mesh geometry
 * @param {Object} cfg - character config with .height and .clothing
 * @returns {Object} map of clothing type name → THREE.BufferGeometry
 */
export function buildClothingGeometry(bodyGeo, cfg) {
  const H = cfg.height ?? 1.75;
  const footTop = 0.06;
  const hipZ   = H * 0.50;
  const chestZ = H * 0.68;
  const waistGap = 0.02;
  const BODY_X_CAP = 0.28;  // Max X extent for torso (excludes arms)

  // Define clothing zones by Z-height ranges and arm inclusion
  // Format: [zMin, zMax, includeArms]
  const ZONES = {
    short_sleeve: [hipZ + waistGap, chestZ + 0.05, true],
    long_sleeve:  [hipZ + waistGap, chestZ + 0.05, true],
    v_neck:       [hipZ + waistGap, chestZ + 0.05, true],
    jeans:        [footTop - 0.02,  hipZ + (chestZ - hipZ) * 0.10, false],
    shorts:       [footTop + (hipZ - footTop) * 0.38, hipZ + (chestZ - hipZ) * 0.10, false],
  };

  // Radial offset from body surface (scales with character height)
  const baseOffset = 0.015 * (H / 1.75);  // 15mm base, scales with height

  const clothingList = Array.isArray(cfg.clothing) ? cfg.clothing : [];
  const posAttr = bodyGeo.attributes.position;
  const idxAttr = bodyGeo.index;
  const result = {};

  for (const ctype of clothingList) {
    if (ctype === 'none') continue;
    const zone = ZONES[ctype];
    if (!zone) continue;
    const [zLo, zHi, includeArms] = zone;

    const verts = [];
    const faces = [];
    const vertMap = new Map(); // original vertex index → new index

    // Iterate through all faces in the body mesh
    const triCount = idxAttr ? idxAttr.count / 3 : posAttr.count / 3;
    for (let t = 0; t < triCount; t++) {
      // Get face vertex indices
      const [ia, ib, ic] = idxAttr
        ? [idxAttr.getX(t*3), idxAttr.getX(t*3+1), idxAttr.getX(t*3+2)]
        : [t*3, t*3+1, t*3+2];

      // Fetch vertex positions
      const vs = [ia, ib, ic].map(i => ({
        x: posAttr.getX(i), y: posAttr.getY(i), z: posAttr.getZ(i), i,
      }));

      // Check if any vertex is in the clothing zone
      const anyInZone = vs.some(v => v.z >= zLo && v.z <= zHi);
      if (!anyInZone) continue;

      // For clothing types without arms, exclude vertices beyond torso width
      if (!includeArms && vs.some(v => Math.abs(v.x) > BODY_X_CAP)) continue;

      // Create offset vertices (radially outward from body center)
      const newIdxs = vs.map(v => {
        if (!vertMap.has(v.i)) {
          // Calculate radial distance from Y axis (body center)
          const radialDist = Math.sqrt(v.x**2 + v.y**2) || 0.001;
          // Offset proportional to distance (farther out vertices get offset proportionally)
          const offsetAmount = baseOffset / radialDist;
          verts.push(
            v.x + v.x * offsetAmount,
            v.y + v.y * offsetAmount,
            v.z
          );
          vertMap.set(v.i, verts.length / 3 - 1);
        }
        return vertMap.get(v.i);
      });
      faces.push(...newIdxs);
    }

    if (verts.length === 0) continue;

    // Create THREE.js geometry from vertices and faces
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    geo.setIndex(new THREE.BufferAttribute(new Uint32Array(faces), 1));
    geo.computeVertexNormals();
    result[ctype] = geo;
  }

  return result;
}
