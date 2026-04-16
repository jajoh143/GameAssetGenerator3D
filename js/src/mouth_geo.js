/**
 * Flat-strip mouth geometry builder — world-space XY-plane strip, no Three.js.
 *
 * Builds a horizontal band representing the mouth, placed on the face surface.
 * buildMouthGeometry() takes the head bone's world Y and face forward Z so the
 * geometry has absolute world coordinates baked in, matching eye_geo.js convention.
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
 * Build mouth geometry as a flat horizontal strip in absolute world space (Y-up, Z-forward).
 *
 * @param {number} headRadius  - head half-width (X extent)
 * @param {number} headBoneY   - world Y of the Head bone
 * @param {number} faceFrontZ  - world Z of the face surface
 * @param {object} tweaks      - optional overrides: { mouthY }
 *   mouthY: vertical offset multiplier relative to headBoneY (default -0.10,
 *            i.e. slightly below the head bone / chin area)
 * @returns {{ positions: Float32Array, normals: Float32Array, indices: Uint32Array }}
 */
export function buildMouthGeometry(headRadius, headBoneY = 1.52, faceFrontZ = 0.12, tweaks = {}) {
  const mouthCenterY = headBoneY + headRadius * ((tweaks.mouthY ?? -0.10) - 0.7);
  const mouthZ       = faceFrontZ + 0.003;          // just in front of face surface
  const halfWidth    = headRadius * 0.28;            // mouth half-width
  const thickness    = headRadius * 0.045;           // strip height
  const segments     = 10;                           // horizontal segments

  const positions = [];
  const indices   = [];

  // Build a flat horizontal strip: two rows of vertices (top edge, bottom edge)
  for (let i = 0; i <= segments; i++) {
    const t = (i / segments) * 2 - 1;  // -1 (left) to +1 (right)
    const x = t * halfWidth;
    positions.push(x, mouthCenterY,             mouthZ);  // top edge vertex
    positions.push(x, mouthCenterY - thickness, mouthZ);  // bottom edge vertex
  }

  // Quad faces between consecutive column pairs (CCW from +Z = correct normal)
  for (let i = 0; i < segments; i++) {
    const tl = i * 2,      tr = (i + 1) * 2;
    const bl = tl + 1,     br = tr + 1;
    indices.push(tl, tr, bl);
    indices.push(tr, br, bl);
  }

  const pos = new Float32Array(positions);
  const idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}

/**
 * Material descriptor for the mouth strip.
 */
export function createMouthMaterial() {
  return {
    albedoColor: [0.12, 0.04, 0.04],  // dark reddish-brown
    roughness: 0.9,
    metallic: 0.0,
  };
}
