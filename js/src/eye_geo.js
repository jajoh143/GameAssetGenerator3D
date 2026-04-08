/**
 * Flat-disc eye geometry builder — world-space XZ-plane discs, no Three.js.
 *
 * Discs lie in the XZ plane (normal faces +Y = toward viewer) so they can be
 * placed directly in world space without any rotation on the mesh.
 * buildEyeGeometry() takes the head bone's world Z and the face's forward Y
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
 * Build a flat disc in the XZ plane (normal faces +Y).
 * eyeX        = lateral centre (±)
 * eyeFwdY     = world Y of disc (forward distance from origin)
 * eyeHeightZ  = world Z of disc centre (height)
 */
function createEyeDiscGeometry(eyeX, eyeFwdY, eyeHeightZ, rx, ry, segments = 10) {
  const positions = [];
  const indices = [];

  // Left eye — CCW winding viewed from +Y → normal in +Y direction
  const leftCenter = positions.length / 3;
  positions.push(-eyeX, eyeFwdY, eyeHeightZ);
  const leftRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    leftRing.push(positions.length / 3);
    positions.push(-eyeX + rx * Math.cos(angle), eyeFwdY, eyeHeightZ + ry * Math.sin(angle));
  }
  for (let i = 0; i < segments; i++) {
    // Reverse winding so normal faces +Y
    indices.push(leftCenter, leftRing[(i + 1) % segments], leftRing[i]);
  }

  // Right eye
  const rightCenter = positions.length / 3;
  positions.push(eyeX, eyeFwdY, eyeHeightZ);
  const rightRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    rightRing.push(positions.length / 3);
    positions.push(eyeX + rx * Math.cos(angle), eyeFwdY, eyeHeightZ + ry * Math.sin(angle));
  }
  for (let i = 0; i < segments; i++) {
    indices.push(rightCenter, rightRing[(i + 1) % segments], rightRing[i]);
  }

  const pos = new Float32Array(positions);
  const idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}

/**
 * Small glint discs in the XZ plane, slightly forward of the eye disc.
 */
function createHighlightGeometry(eyeX, eyeFwdY, eyeHeightZ, highlightR, eyeRy, segments = 6) {
  const hlHeightZ = eyeHeightZ + eyeRy * 0.45;   // upper portion of eye
  const hlFwdY    = eyeFwdY + 0.002;              // slightly forward of eye disc

  const positions = [];
  const indices = [];

  // Left highlight
  const leftHlCenter = positions.length / 3;
  positions.push(-eyeX + eyeX * 0.35, hlFwdY, hlHeightZ);
  const leftHlRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    leftHlRing.push(positions.length / 3);
    positions.push(
      -eyeX + eyeX * 0.35 + highlightR * Math.cos(angle),
      hlFwdY,
      hlHeightZ + highlightR * Math.sin(angle)
    );
  }
  for (let i = 0; i < segments; i++) {
    indices.push(leftHlCenter, leftHlRing[(i + 1) % segments], leftHlRing[i]);
  }

  // Right highlight
  const rightHlCenter = positions.length / 3;
  positions.push(eyeX - eyeX * 0.35, hlFwdY, hlHeightZ);
  const rightHlRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    rightHlRing.push(positions.length / 3);
    positions.push(
      eyeX - eyeX * 0.35 + highlightR * Math.cos(angle),
      hlFwdY,
      hlHeightZ + highlightR * Math.sin(angle)
    );
  }
  for (let i = 0; i < segments; i++) {
    indices.push(rightHlCenter, rightHlRing[(i + 1) % segments], rightHlRing[i]);
  }

  const pos = new Float32Array(positions);
  const idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}

/**
 * Build eye geometry with vertices in absolute world space (Z-up, Y-forward).
 * No rotation or attachToBone needed on the resulting meshes.
 *
 * @param {number} headRadius  - head half-width (X extent)
 * @param {number} headBoneZ   - world Z of the Head bone (default H*0.87 for H=1.75)
 * @param {number} faceFrontY  - world Y of the face surface (forward extent of head)
 * @returns {{ eyeDiscGeometry, highlightGeometry }}
 */
export function buildEyeGeometry(headRadius, headBoneZ = 1.52, faceFrontY = 0.12) {
  const eyeX        = headRadius * 0.46;               // lateral separation
  const eyeHeightZ  = headBoneZ  + headRadius * 0.25;  // slightly above head bone centre
  const eyeFwdY     = faceFrontY + 0.003;              // just in front of face surface
  const rx          = headRadius * 0.15;               // horizontal radius of disc
  const ry          = headRadius * 0.12;               // vertical radius of disc
  const highlightR  = headRadius * 0.05;               // glint radius

  return {
    eyeDiscGeometry:   createEyeDiscGeometry(eyeX, eyeFwdY, eyeHeightZ, rx, ry, 10),
    highlightGeometry: createHighlightGeometry(eyeX, eyeFwdY, eyeHeightZ, highlightR, ry, 6),
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
