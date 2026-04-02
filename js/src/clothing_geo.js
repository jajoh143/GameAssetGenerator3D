/**
 * Face-extrusion clothing geometry from body mesh.
 * Port of generators/humanoid/gltf_pipeline/clothing_geo.py
 */

import * as THREE from 'three';

/**
 * Build clothing geometry by extruding body mesh faces outward.
 *
 * @param {THREE.BufferGeometry} bodyGeo - the body mesh geometry
 * @param {Object} cfg - character config with .height and .clothing
 * @returns {Object} map of clothing type name → THREE.BufferGeometry
 */
export function buildClothingGeometry(bodyGeo, cfg) {
  const H = cfg.height ?? 1.75;
  const footTop = 0.06;
  const hipY   = H * 0.50;
  const chestY = H * 0.68;
  const waistGap = 0.02;
  const BODY_X_CAP = 0.28;

  // Zone boundaries are Y heights (Y-up convention)
  const ZONES = {
    short_sleeve: [hipY + waistGap, chestY + 0.05, true],
    long_sleeve:  [hipY + waistGap, chestY + 0.05, true],
    v_neck:       [hipY + waistGap, chestY + 0.05, true],
    jeans:        [footTop - 0.02,  hipY + (chestY - hipY) * 0.10, false],
    shorts:       [footTop + (hipY - footTop) * 0.38, hipY + (chestY - hipY) * 0.10, false],
  };

  const clothingList = Array.isArray(cfg.clothing) ? cfg.clothing : [];
  const posAttr = bodyGeo.attributes.position;
  const idxAttr = bodyGeo.index;
  const result = {};

  for (const ctype of clothingList) {
    if (ctype === 'none') continue;
    const zone = ZONES[ctype];
    if (!zone) continue;
    const [yLo, yHi, includeArms] = zone;

    const verts = [];
    const faces = [];
    const vertMap = new Map(); // original vertex index → new index

    const triCount = idxAttr ? idxAttr.count / 3 : posAttr.count / 3;
    for (let t = 0; t < triCount; t++) {
      const [ia, ib, ic] = idxAttr
        ? [idxAttr.getX(t*3), idxAttr.getX(t*3+1), idxAttr.getX(t*3+2)]
        : [t*3, t*3+1, t*3+2];

      const vs = [ia, ib, ic].map(i => ({
        x: posAttr.getX(i), y: posAttr.getY(i), z: posAttr.getZ(i), i,
      }));

      // Zone test uses Y for height (Y-up convention)
      const anyInZone = vs.some(v => v.y >= yLo && v.y <= yHi);
      if (!anyInZone) continue;
      if (!includeArms && vs.some(v => Math.abs(v.x) > BODY_X_CAP)) continue;

      const newIdxs = vs.map(v => {
        if (!vertMap.has(v.i)) {
          // Extrude outward in XZ plane (perpendicular to Y-up axis), keep Y
          const len = Math.sqrt(v.x**2 + v.z**2) || 0.001;
          const off = 0.015 / len;
          verts.push(v.x + v.x * off, v.y, v.z + v.z * off);
          vertMap.set(v.i, verts.length / 3 - 1);
        }
        return vertMap.get(v.i);
      });
      faces.push(...newIdxs);
    }

    if (verts.length === 0) continue;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    geo.setIndex(faces);
    geo.computeVertexNormals();
    result[ctype] = geo;
  }

  return result;
}
