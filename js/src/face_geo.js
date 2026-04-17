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
  const noseY     = headBoneY - hr * 0.10;   // vertical centre of nose
  const tipOffset = hr * 0.18;               // how far nose sticks out
  const noseW     = hr * 0.14;               // half-width of nose base (≈1.4cm)
  const noseH     = hr * 0.22;               // height of nose shape

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
 * Build thin eyebrow quads above each eye — two arched rectangles,
 * inner end slightly raised for a natural expression.
 *
 * Returns { positions, normals, indices }
 */
export function buildEyebrowGeometry(headRadius, headBoneY, faceFrontZ) {
  const hr = headRadius;
  const fz = faceFrontZ + 0.002;  // just proud of face, behind eye discs

  const eyeY   = headBoneY + hr * 0.08;  // same height reference as eyes
  const browY  = eyeY + hr * 0.17;       // brows sit above eyes
  const browH  = hr * 0.055;             // thickness of brow strip
  const browX  = hr * 0.40;             // lateral centre of each brow
  const browW  = hr * 0.21;             // half-width of brow
  const tiltIn = browH * 0.5;           // inner end raised by this much

  // Left brow: 4 vertices (inner-top, inner-bottom, outer-top, outer-bottom)
  // Right brow: mirror (sign-flip on X)
  const positions = [];
  const normals   = [];
  const indices   = [];

  function addBrow(side) {  // side = +1 (right) or -1 (left)
    const cx = side * browX;
    const inX  = cx - side * browW * 0.4;  // inner end (toward nose)
    const outX = cx + side * browW * 0.6;  // outer end
    const inY  = browY + tiltIn;           // inner end slightly higher
    const outY = browY;
    const base = positions.length / 3;

    positions.push(
      inX,  inY + browH, fz,   // 0 inner-top
      inX,  inY,         fz,   // 1 inner-bottom
      outX, outY + browH, fz,  // 2 outer-top
      outX, outY,         fz,  // 3 outer-bottom
    );
    for (let i = 0; i < 4; i++) { normals.push(0, 0, 1); }  // all face +Z
    // CCW winding from +Z: (top-inner, bottom-inner, top-outer), (bottom-inner, bottom-outer, top-outer)
    indices.push(base+0, base+2, base+1,  base+1, base+2, base+3);
  }

  addBrow(-1);  // left
  addBrow(+1);  // right

  return {
    positions: new Float32Array(positions),
    normals:   new Float32Array(normals),
    indices:   new Uint32Array(indices),
  };
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
  const mouthW   = hr * 0.32;               // half-width (≈3.2cm for headRadius=0.10)
  const lipH     = hr * 0.12;               // height of lip strip (taller = more visible)
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
