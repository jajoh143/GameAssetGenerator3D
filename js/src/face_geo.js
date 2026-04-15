/**
 * Low-poly face features: nose and mouth geometry.
 *
 * All geometry is in world-space Y-up coordinates.
 * Positions are returned as plain Float32Arrays ready for VertexData.
 *
 * @param {number} headRadius  - head sphere radius (metres)
 * @param {number} headBoneY   - world Y of the head bone (head centre)
 * @param {number} faceFrontZ  - world Z of the front face surface
 */

/**
 * Build a simple low-poly nose: a small three-sided pyramid protruding
 * from the face. One apex vertex sticks forward; three base vertices sit
 * on the face plane.
 *
 *   bridge (top)
 *     /   \
 *   L  tip  R   ← tip protrudes forward
 *     \   /
 *    base (bottom)
 *
 * Returns { positions, normals, indices }
 */
export function buildNoseGeometry(headRadius, headBoneY, faceFrontZ) {
  const hr = headRadius;
  const fz = faceFrontZ;

  // Nose sits slightly below head centre (eye level is above centre,
  // nose is below eye level)
  const noseY     = headBoneY - hr * 0.08;   // vertical centre of nose
  const tipOffset = hr * 0.16;               // how far nose sticks out
  const noseW     = hr * 0.16;               // half-width of nose base
  const noseH     = hr * 0.24;               // height of nose shape

  // Vertices
  // 0: bridge (top centre, on face surface)
  // 1: left base (left nostril, on face)
  // 2: right base (right nostril, on face)
  // 3: tip (protrudes forward)
  const positions = new Float32Array([
    0,        noseY + noseH * 0.55,  fz - hr * 0.02,   // 0 bridge
   -noseW,    noseY - noseH * 0.45,  fz,               // 1 left nostril
    noseW,    noseY - noseH * 0.45,  fz,               // 2 right nostril
    0,        noseY,                 fz + tipOffset,   // 3 tip
  ]);

  // Triangles (all front-facing, Z-positive = toward camera)
  const indices = new Uint32Array([
    0, 1, 3,   // left face
    0, 3, 2,   // right face
    1, 2, 3,   // bottom face
  ]);

  // Flat normals per face (compute from cross products)
  const normals = new Float32Array(4 * 3);
  function setNorm(vi, nx, ny, nz) {
    normals[vi*3]=nx; normals[vi*3+1]=ny; normals[vi*3+2]=nz;
  }
  // Approximate normals: tip points forward/slightly up
  const nFwd = [0, 0.1, 0.99];
  for (let i = 0; i < 4; i++) setNorm(i, nFwd[0], nFwd[1], nFwd[2]);

  return { positions, normals, indices };
}

/**
 * Build a simple low-poly mouth: a thin horizontal quad representing
 * closed lips, with a very slight cupid's-bow curve on the top edge.
 *
 *   TL──────────────TR   ← upper lip (slight curve via centre vertex)
 *   |  \          / |
 *   |    TM────TM   |   ← we just use a flat quad for simplicity
 *   |                |
 *   BL──────────────BR   ← lower lip
 *
 * Returns { positions, normals, indices }
 */
export function buildMouthGeometry(headRadius, headBoneY, faceFrontZ) {
  const hr = headRadius;
  const fz = faceFrontZ;

  const mouthY   = headBoneY - hr * 0.40;   // below nose
  const mouthW   = hr * 0.48;               // half-width of mouth
  const lipH     = hr * 0.10;               // height of lip strip
  const mouthZ   = fz + hr * 0.02;          // slightly proud of face

  // 5 vertices: top-left, top-centre, top-right, bottom-left, bottom-right
  // Top centre is slightly higher (cupid's bow)
  const positions = new Float32Array([
   -mouthW,  mouthY + lipH,          mouthZ,         // 0 TL
    0,        mouthY + lipH * 1.25,   mouthZ,         // 1 TC (cupid's bow peak)
    mouthW,  mouthY + lipH,          mouthZ,         // 2 TR
   -mouthW,  mouthY,                 mouthZ,         // 3 BL
    mouthW,  mouthY,                 mouthZ,         // 4 BR
  ]);

  const indices = new Uint32Array([
    0, 3, 1,   // left upper-lower triangle
    1, 3, 4,   // centre lower triangle
    1, 4, 2,   // right upper-lower triangle
  ]);

  const normals = new Float32Array(5 * 3);
  for (let i = 0; i < 5; i++) { normals[i*3+2] = 1.0; } // all face +Z

  return { positions, normals, indices };
}
