/**
 * Flat-disc eye geometry builder — returns plain { positions, normals, indices } arrays.
 * No Three.js dependency; compatible with Babylon.js builder.
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

function createEyeDiscGeometry(eyeX, eyeY, eyeZ, rx, ry, segments = 10) {
  const positions = [];
  const indices = [];

  // Left eye
  const leftCenter = positions.length / 3;
  positions.push(-eyeX, eyeY, eyeZ);
  const leftRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    leftRing.push(positions.length / 3);
    positions.push(-eyeX + rx * Math.cos(angle), eyeY + ry * Math.sin(angle), eyeZ);
  }
  for (let i = 0; i < segments; i++) {
    indices.push(leftCenter, leftRing[i], leftRing[(i + 1) % segments]);
  }

  // Right eye
  const rightCenter = positions.length / 3;
  positions.push(eyeX, eyeY, eyeZ);
  const rightRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    rightRing.push(positions.length / 3);
    positions.push(eyeX + rx * Math.cos(angle), eyeY + ry * Math.sin(angle), eyeZ);
  }
  for (let i = 0; i < segments; i++) {
    indices.push(rightCenter, rightRing[i], rightRing[(i + 1) % segments]);
  }

  const pos = new Float32Array(positions);
  const idx = new Uint32Array(indices);
  return { positions: pos, normals: computeVertexNormals(pos, idx), indices: idx };
}

function createHighlightGeometry(eyeX, eyeY, eyeZ, highlightR, eyeRy, segments = 6) {
  const positions = [];
  const indices = [];

  const highlightY = eyeY + eyeRy * 0.45;
  const highlightZ = eyeZ + highlightR * 0.05;

  // Left eye highlight
  const leftHlCenter = positions.length / 3;
  positions.push(-eyeX + eyeX * 0.35, highlightY, highlightZ);
  const leftHlRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    leftHlRing.push(positions.length / 3);
    positions.push(
      -eyeX + eyeX * 0.35 + highlightR * Math.cos(angle),
      highlightY + highlightR * Math.sin(angle),
      highlightZ
    );
  }
  for (let i = 0; i < segments; i++) {
    indices.push(leftHlCenter, leftHlRing[i], leftHlRing[(i + 1) % segments]);
  }

  // Right eye highlight
  const rightHlCenter = positions.length / 3;
  positions.push(eyeX - eyeX * 0.35, highlightY, highlightZ);
  const rightHlRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    rightHlRing.push(positions.length / 3);
    positions.push(
      eyeX - eyeX * 0.35 + highlightR * Math.cos(angle),
      highlightY + highlightR * Math.sin(angle),
      highlightZ
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
 * Build eye geometry for the character.
 * @param {number} headRadius
 * @param {number|null} headRadiusHoriz
 * @returns {{ eyeDiscGeometry: object, highlightGeometry: object }}
 */
export function buildEyeGeometry(headRadius, headRadiusHoriz = null) {
  const hrH = headRadiusHoriz !== null ? headRadiusHoriz : headRadius;

  const eyeR = hrH * 0.12;
  const rx = eyeR * 1.25;
  const ry = eyeR * 1.05;
  const eyeX = hrH * 0.46;
  const eyeY = headRadius * 5.0;
  const eyeZ = headRadius * 0.22;
  const highlightR = eyeR * 0.18;

  return {
    eyeDiscGeometry: createEyeDiscGeometry(eyeX, eyeY, eyeZ, rx, ry, 10),
    highlightGeometry: createHighlightGeometry(eyeX, eyeY, eyeZ, highlightR, ry, 6),
  };
}

/**
 * Create material descriptors for eyes (plain objects, no Three.js).
 * @returns {{ eyeDiscMaterial: object, highlightMaterial: object }}
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
