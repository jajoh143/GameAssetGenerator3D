/**
 * Flat-disc eye geometry builder — world-space XY-plane discs, no Three.js.
 *
 * Discs lie in the XY plane (normal faces +Z = toward viewer) matching
 * Babylon/glTF Y-up coordinate system.
 * buildEyeGeometry() takes the head bone's world Y and the face's forward Z
 * so the geometry has absolute world coordinates baked in.
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
 * Build a flat disc in the XY plane (normal faces +Z = toward viewer).
 * eyeX        = lateral centre (±)
 * eyeZ        = world Z of disc (forward position, face front)
 * eyeHeightY  = world Y of disc centre (height)
 */
function createEyeDiscGeometry(eyeX, eyeZ, eyeHeightY, rx, ry, segments = 10) {
  const positions = [];
  const indices = [];

  // Left eye — CCW winding viewed from +Z → normal in +Z direction
  const leftCenter = positions.length / 3;
  positions.push(-eyeX, eyeHeightY, eyeZ);
  const leftRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    leftRing.push(positions.length / 3);
    positions.push(-eyeX + rx * Math.cos(angle), eyeHeightY + ry * Math.sin(angle), eyeZ);
  }
  for (let i = 0; i < segments; i++) {
    indices.push(leftCenter, leftRing[i], leftRing[(i + 1) % segments]);
  }

  // Right eye
  const rightCenter = positions.length / 3;
  positions.push(eyeX, eyeHeightY, eyeZ);
  const rightRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    rightRing.push(positions.length / 3);
    positions.push(eyeX + rx * Math.cos(angle), eyeHeightY + ry * Math.sin(angle), eyeZ);
  }
  for (let i = 0; i < segments; i++) {
    indices.push(rightCenter, rightRing[i], rightRing[(i + 1) % segments]);
  }

  const pos = new Float32Array(positions);
  const idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}

/**
 * Small glint discs in the XY plane, slightly forward of the eye disc.
 */
function createHighlightGeometry(eyeX, eyeZ, eyeHeightY, highlightR, eyeRy, segments = 6) {
  const hlHeightY = eyeHeightY + eyeRy * 0.45;  // upper portion of eye
  const hlZ       = eyeZ + 0.002;               // slightly forward of eye disc

  const positions = [];
  const indices = [];

  // Left highlight
  const leftHlCenter = positions.length / 3;
  positions.push(-eyeX + eyeX * 0.35, hlHeightY, hlZ);
  const leftHlRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    leftHlRing.push(positions.length / 3);
    positions.push(
      -eyeX + eyeX * 0.35 + highlightR * Math.cos(angle),
      hlHeightY + highlightR * Math.sin(angle),
      hlZ
    );
  }
  for (let i = 0; i < segments; i++) {
    indices.push(leftHlCenter, leftHlRing[i], leftHlRing[(i + 1) % segments]);
  }

  // Right highlight
  const rightHlCenter = positions.length / 3;
  positions.push(eyeX - eyeX * 0.35, hlHeightY, hlZ);
  const rightHlRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    rightHlRing.push(positions.length / 3);
    positions.push(
      eyeX - eyeX * 0.35 + highlightR * Math.cos(angle),
      hlHeightY + highlightR * Math.sin(angle),
      hlZ
    );
  }
  for (let i = 0; i < segments; i++) {
    indices.push(rightHlCenter, rightHlRing[i], rightHlRing[(i + 1) % segments]);
  }

  const pos = new Float32Array(positions);
  const idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}

/**
 * Build eye geometry with vertices in absolute world space (Y-up, Z-forward).
 * No rotation or attachToBone needed on the resulting meshes.
 *
 * @param {number} headRadius  - head half-width (X extent)
 * @param {number} headBoneY   - world Y of the Head bone (height, default H*0.87 for H=1.75)
 * @param {number} faceFrontZ  - world Z of the face surface (forward extent of head)
 * @returns {{ eyeDiscGeometry, highlightGeometry }}
 */
export function buildEyeGeometry(headRadius, headBoneY = 1.52, faceFrontZ = 0.12) {
  const eyeX       = headRadius * 0.45;               // lateral separation
  const eyeHeightY = headBoneY  + headRadius * 0.05;  // eye socket height (20% up from chin)
  const eyeZ       = faceFrontZ + 0.003;              // just in front of face surface
  const rx         = headRadius * 0.10;               // horizontal radius of disc
  const ry         = headRadius * 0.08;               // vertical radius of disc
  const highlightR = headRadius * 0.035;              // glint radius

  return {
    eyeDiscGeometry:   createEyeDiscGeometry(eyeX, eyeZ, eyeHeightY, rx, ry, 10),
    highlightGeometry: createHighlightGeometry(eyeX, eyeZ, eyeHeightY, highlightR, ry, 6),
  };
}

/**
 * Material descriptors for eyes (plain objects, no Three.js).
 */
export function createEyeMaterials() {
  return {
    eyeDiscMaterial: {
      albedoColor: [0.01, 0.01, 0.02],
      roughness: 1.0,
      metallic: 0.0,
    },
    highlightMaterial: {
      albedoColor: [1.0, 1.0, 1.0],
      roughness: 0.0,
      metallic: 0.0,
      emissiveColor: [1.0, 1.0, 1.0],
      backFaceCulling: false,
    },
  };
}
