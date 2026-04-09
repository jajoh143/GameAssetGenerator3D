/**
 * Facial feature geometry builders for Three.js.
 * Generates eyebrows, nose, mouth, and ear stubs.
 *
 * All geometry is positioned relative to the Head bone origin.
 * Uses the same coordinate system as eye_geo.js:
 *   X = left/right, Y = up (height), Z = forward (toward viewer)
 */

import * as THREE from 'three';

// ── Helper ──────────────────────────────────────────────────────────────────

function buildBufferGeometry(positions, indices) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));
  geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(indices), 1));
  geometry.computeVertexNormals();
  return geometry;
}

// ── Eyebrows ────────────────────────────────────────────────────────────────

/**
 * Build eyebrow geometry — slightly angled flat quads above each eye.
 * 4 faces total (2 per eyebrow, each quad = 2 triangles).
 *
 * @param {number} headRadius
 * @param {number} headRadiusHoriz
 * @returns {THREE.BufferGeometry}
 */
export function buildEyebrowGeometry(headRadius, headRadiusHoriz = null) {
  const hrH = headRadiusHoriz !== null ? headRadiusHoriz : headRadius;

  // Match eye positioning from eye_geo.js
  const eyeR = hrH * 0.13;
  const eyeX = hrH * 0.16;
  const eyeY = headRadius * 5.05;
  const eyeZ = headRadius * 0.11;

  // Eyebrow sizing
  const browWidth = eyeR * 1.15 * 1.20;     // ~1.2x eye width
  const browThickness = eyeR * 0.95 * 0.14;  // ~14% of eye height
  const browGap = eyeR * 0.95 * 0.25;        // Gap above eye

  // Position above eyes (Z = up)
  const browZ = eyeZ + eyeR * 0.95 + browGap;
  const browY = eyeY + headRadius * 0.01;    // Same forward position as eyes

  // Slight angle: inner edge lower, outer edge higher (neutral expression)
  const innerTilt = -browThickness * 0.15;
  const outerTilt = browThickness * 0.25;

  const positions = [];
  const indices = [];

  // Build one eyebrow as a quad (4 verts)
  // Coords: X = left/right, Y = forward (face surface), Z = up (height)
  function addBrow(cx) {
    const baseIdx = positions.length / 3;
    const sign = cx > 0 ? 1 : -1;

    // Inner bottom
    positions.push(cx - sign * browWidth * 0.5, browY, browZ + innerTilt);
    // Outer bottom
    positions.push(cx + sign * browWidth * 0.5, browY, browZ + outerTilt);
    // Outer top
    positions.push(cx + sign * browWidth * 0.5, browY, browZ + outerTilt + browThickness);
    // Inner top
    positions.push(cx - sign * browWidth * 0.5, browY, browZ + innerTilt + browThickness);

    // Two triangles for quad
    indices.push(baseIdx, baseIdx + 1, baseIdx + 2);
    indices.push(baseIdx, baseIdx + 2, baseIdx + 3);
  }

  addBrow(-eyeX);  // Left eyebrow
  addBrow(eyeX);   // Right eyebrow

  return buildBufferGeometry(positions, indices);
}

// ── Nose ────────────────────────────────────────────────────────────────────

/**
 * Build a simple wedge/pyramid nose.
 * 6 faces: 2 side triangles, 2 front quads (as 4 tris), bottom cap optional.
 *
 * @param {number} headRadius
 * @param {number} headRadiusHoriz
 * @returns {THREE.BufferGeometry}
 */
export function buildNoseGeometry(headRadius, headRadiusHoriz = null) {
  const hrH = headRadiusHoriz !== null ? headRadiusHoriz : headRadius;

  // Position below eyes, above mouth
  // Coords: Y = forward (face surface), Z = up (height on face)
  const eyeY = headRadius * 5.05;    // Forward position (face surface)
  const eyeZ = headRadius * 0.11;    // Height position (eye level)

  const noseWidth = hrH * 0.04;        // Narrow, subtle wedge
  const noseHeight = headRadius * 0.06; // Vertical extent (Z direction)
  const noseDepth = headRadius * 0.04;  // How far forward it sticks (Y direction)

  const noseTopZ = eyeZ - headRadius * 0.04;   // Bridge starts below eyes (lower Z)
  const noseBotZ = noseTopZ - noseHeight;        // Tip (lowest point)
  const noseY = eyeY + headRadius * 0.01;        // At face surface (forward)

  const positions = [];
  const indices = [];

  // Wedge shape: narrow at bridge (top Z), wider at tip (bottom Z)
  // Coords: X = left/right, Y = forward, Z = up (height)
  const ridgeWidth = noseWidth * 0.3;  // Top ridge is narrower

  // 7 vertices for the wedge
  // Bridge (top of nose, high Z) — at face surface
  positions.push(-ridgeWidth, noseY, noseTopZ);           // 0: bridge-left
  positions.push(ridgeWidth, noseY, noseTopZ);            // 1: bridge-right

  // Mid-point — slightly forward (higher Y)
  const midZ = noseTopZ - noseHeight * 0.5;
  positions.push(-noseWidth * 0.5, noseY + noseDepth * 0.5, midZ);  // 2: mid-left
  positions.push(noseWidth * 0.5, noseY + noseDepth * 0.5, midZ);   // 3: mid-right

  // Bottom (tip area, low Z) — widest, most forward (highest Y)
  positions.push(-noseWidth * 0.8, noseY + noseDepth, noseBotZ);   // 4: bottom-left
  positions.push(noseWidth * 0.8, noseY + noseDepth, noseBotZ);    // 5: bottom-right

  // Tip center — most forward point
  positions.push(0, noseY + noseDepth * 1.05, noseBotZ + noseHeight * 0.05);  // 6: tip

  // Front faces (2 quads as 4 triangles)
  // Upper front: 0, 1, 3, 2
  indices.push(0, 1, 3);
  indices.push(0, 3, 2);

  // Lower front: 2, 3, 5, 4
  indices.push(2, 3, 5);
  indices.push(2, 5, 4);

  // Tip triangles
  indices.push(4, 5, 6);   // Bottom face to tip
  indices.push(4, 6, 2);   // Left side to tip
  indices.push(6, 5, 3);   // Right side to tip

  return buildBufferGeometry(positions, indices);
}

// ── Mouth ───────────────────────────────────────────────────────────────────

/**
 * Build a simple mouth — slightly curved dark strip.
 * 4 faces (2 quads as 4 triangles) forming a gentle crescent.
 *
 * @param {number} headRadius
 * @param {number} headRadiusHoriz
 * @returns {THREE.BufferGeometry}
 */
export function buildMouthGeometry(headRadius, headRadiusHoriz = null) {
  const hrH = headRadiusHoriz !== null ? headRadiusHoriz : headRadius;

  // Coords: Y = forward (face surface), Z = up (height on face)
  const eyeY = headRadius * 5.05;
  const eyeZ = headRadius * 0.11;
  const eyeX = hrH * 0.16;

  // Mouth sizing and position
  const mouthWidth = eyeX * 1.10;           // Slightly wider than eye spacing
  const mouthThickness = headRadius * 0.012; // Thin strip (Z direction)
  const mouthZ = eyeZ - headRadius * 0.12;   // Below nose (lower Z = lower on face)
  const mouthY = eyeY + headRadius * 0.01;   // At face surface (forward)

  // Slight downward curve at corners for neutral expression
  const cornerDrop = mouthThickness * 0.6;

  const positions = [];
  const indices = [];

  // 10 vertices: left corner, left-mid, center, right-mid, right corner (top + bottom)
  // Coords: X = left/right, Y = forward, Z = up
  // Top edge (higher Z)
  positions.push(-mouthWidth, mouthY, mouthZ + mouthThickness * 0.5 - cornerDrop);                  // 0: left corner top
  positions.push(-mouthWidth * 0.45, mouthY, mouthZ + mouthThickness * 0.5 + mouthThickness * 0.3); // 1: left-mid top
  positions.push(0, mouthY, mouthZ + mouthThickness * 0.5 + mouthThickness * 0.5);                  // 2: center top
  positions.push(mouthWidth * 0.45, mouthY, mouthZ + mouthThickness * 0.5 + mouthThickness * 0.3);  // 3: right-mid top
  positions.push(mouthWidth, mouthY, mouthZ + mouthThickness * 0.5 - cornerDrop);                   // 4: right corner top

  // Bottom edge (lower Z)
  positions.push(-mouthWidth, mouthY, mouthZ - mouthThickness * 0.5 - cornerDrop);                  // 5: left corner bot
  positions.push(-mouthWidth * 0.45, mouthY, mouthZ - mouthThickness * 0.7);                        // 6: left-mid bot
  positions.push(0, mouthY, mouthZ - mouthThickness * 0.5);                                         // 7: center bot
  positions.push(mouthWidth * 0.45, mouthY, mouthZ - mouthThickness * 0.7);                         // 8: right-mid bot
  positions.push(mouthWidth, mouthY, mouthZ - mouthThickness * 0.5 - cornerDrop);                   // 9: right corner bot

  // 4 quads (8 triangles): left-corner-to-leftmid, leftmid-to-center, center-to-rightmid, rightmid-to-rightcorner
  for (let i = 0; i < 4; i++) {
    const tl = i, tr = i + 1, br = i + 6, bl = i + 5;
    indices.push(tl, tr, br);
    indices.push(tl, br, bl);
  }

  return buildBufferGeometry(positions, indices);
}

// ── Ear Stubs ───────────────────────────────────────────────────────────────

/**
 * Build simple ear stubs — small triangular protrusions on each side of head.
 * 4 faces total (2 per ear).
 *
 * @param {number} headRadius
 * @param {number} headRadiusHoriz
 * @returns {THREE.BufferGeometry}
 */
export function buildEarGeometry(headRadius, headRadiusHoriz = null) {
  const hrH = headRadiusHoriz !== null ? headRadiusHoriz : headRadius;

  // Coords: Y = forward, Z = up (height)
  const eyeZ = headRadius * 0.11;

  // Ear position: at the sides of the head, roughly at eye level
  // Head width is ~0.56, so head edge X is ~0.28
  const earX = 0.26;                    // At head edge (actual head ~±0.28)
  const earY = headRadius * 4.50;       // Side of head (less forward than face front)
  const earZ = eyeZ - headRadius * 0.01;  // At eye level

  const earWidth = 0.03;               // Subtle protrusion (absolute, ~3cm)
  const earHeight = headRadius * 0.06;  // Vertical size (Z direction)
  const earDepth = headRadius * 0.02;   // Front-to-back (Y direction)

  const positions = [];
  const indices = [];

  // Coords: X = left/right, Y = forward, Z = up (height)
  function addEar(side) {
    const baseIdx = positions.length / 3;
    const sx = side * earX;
    const dir = side;  // +1 for right, -1 for left

    // 5 vertices: 4 base points on head surface + 1 outer tip
    positions.push(sx, earY + earDepth, earZ + earHeight * 0.5);   // 0: base front-top
    positions.push(sx, earY + earDepth, earZ - earHeight * 0.5);   // 1: base front-bottom
    positions.push(sx, earY - earDepth, earZ - earHeight * 0.5);   // 2: base back-bottom
    positions.push(sx, earY - earDepth, earZ + earHeight * 0.5);   // 3: base back-top

    // Outer point (ear tip, sticks outward in X)
    positions.push(sx + dir * earWidth, earY, earZ + earHeight * 0.15);  // 4: outer tip

    // Front face
    indices.push(baseIdx + 0, baseIdx + 1, baseIdx + 4);
    // Back face
    indices.push(baseIdx + 3, baseIdx + 4, baseIdx + 2);
    // Top face
    indices.push(baseIdx + 0, baseIdx + 4, baseIdx + 3);
    // Bottom face
    indices.push(baseIdx + 1, baseIdx + 2, baseIdx + 4);
  }

  addEar(-1);  // Left ear
  addEar(1);   // Right ear

  return buildBufferGeometry(positions, indices);
}
