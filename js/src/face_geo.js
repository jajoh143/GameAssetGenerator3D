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
  const eyeR = hrH * 0.14;
  const eyeX = hrH * 0.44;
  const eyeY = headRadius * 4.80;
  const eyeZ = headRadius * 0.28;

  // Eyebrow sizing
  const browWidth = eyeR * 1.20 * 1.20;     // ~1.2x eye width
  const browThickness = eyeR * 1.0 * 0.15;   // ~15% of eye height
  const browGap = eyeR * 1.0 * 0.30;         // Gap above eye

  // Position above eyes
  const browY = eyeY + eyeR * 1.0 + browGap;
  const browZ = eyeZ + headRadius * 0.02;    // Slightly forward of eyes

  // Slight angle: inner edge lower, outer edge higher (neutral expression)
  const innerTilt = -browThickness * 0.15;
  const outerTilt = browThickness * 0.25;

  const positions = [];
  const indices = [];

  // Build one eyebrow as a quad (4 verts)
  function addBrow(cx) {
    const baseIdx = positions.length / 3;
    const sign = cx > 0 ? 1 : -1;

    // Inner bottom
    positions.push(cx - sign * browWidth * 0.5, browY + innerTilt, browZ);
    // Outer bottom
    positions.push(cx + sign * browWidth * 0.5, browY + outerTilt, browZ);
    // Outer top
    positions.push(cx + sign * browWidth * 0.5, browY + outerTilt + browThickness, browZ);
    // Inner top
    positions.push(cx - sign * browWidth * 0.5, browY + innerTilt + browThickness, browZ);

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
  const eyeY = headRadius * 4.80;
  const eyeZ = headRadius * 0.28;

  const noseWidth = hrH * 0.05;        // Narrow, subtle wedge
  const noseHeight = headRadius * 0.15; // Shorter vertical extent
  const noseDepth = headRadius * 0.05;  // Subtle protrusion

  const noseTopY = eyeY - headRadius * 0.22;   // Bridge starts below eyes
  const noseBotY = noseTopY - noseHeight;        // Tip
  const noseZ = eyeZ + headRadius * 0.02;        // At face surface

  const positions = [];
  const indices = [];

  // Wedge shape: wide at base (noseBotY), narrow ridge at top
  const ridgeWidth = noseWidth * 0.3;  // Top ridge is narrower

  // 6 vertices for the wedge
  // Top left, top right (narrow ridge, at face surface)
  positions.push(-ridgeWidth, noseTopY, noseZ);           // 0: top-left
  positions.push(ridgeWidth, noseTopY, noseZ);            // 1: top-right

  // Mid-point (bridge) — slightly forward
  const midY = noseTopY - noseHeight * 0.5;
  positions.push(-noseWidth * 0.5, midY, noseZ + noseDepth * 0.5);  // 2: mid-left
  positions.push(noseWidth * 0.5, midY, noseZ + noseDepth * 0.5);   // 3: mid-right

  // Bottom (tip area) — slightly wider, most forward
  positions.push(-noseWidth * 0.8, noseBotY, noseZ + noseDepth);   // 4: bottom-left
  positions.push(noseWidth * 0.8, noseBotY, noseZ + noseDepth);    // 5: bottom-right

  // Tip center — forward point
  positions.push(0, noseBotY + noseHeight * 0.05, noseZ + noseDepth * 1.05);  // 6: tip

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

  const eyeY = headRadius * 4.80;
  const eyeZ = headRadius * 0.28;
  const eyeX = hrH * 0.44;

  // Mouth sizing and position
  const mouthWidth = eyeX * 0.70;           // Subtle width
  const mouthThickness = headRadius * 0.018; // Thin strip
  const mouthY = eyeY - headRadius * 0.60;   // Below nose
  const mouthZ = eyeZ + headRadius * 0.03;   // At face surface

  // Slight downward curve at corners for neutral expression
  const cornerDrop = mouthThickness * 0.6;

  const positions = [];
  const indices = [];

  // 6 vertices: left corner, left-mid, center (top/bottom), right-mid, right corner
  // Top edge
  positions.push(-mouthWidth, mouthY - cornerDrop, mouthZ);                  // 0: left corner top
  positions.push(-mouthWidth * 0.45, mouthY + mouthThickness * 0.3, mouthZ); // 1: left-mid top
  positions.push(0, mouthY + mouthThickness * 0.5, mouthZ);                  // 2: center top
  positions.push(mouthWidth * 0.45, mouthY + mouthThickness * 0.3, mouthZ);  // 3: right-mid top
  positions.push(mouthWidth, mouthY - cornerDrop, mouthZ);                   // 4: right corner top

  // Bottom edge
  positions.push(-mouthWidth, mouthY - cornerDrop - mouthThickness, mouthZ);                  // 5: left corner bot
  positions.push(-mouthWidth * 0.45, mouthY - mouthThickness * 0.7, mouthZ);                  // 6: left-mid bot
  positions.push(0, mouthY - mouthThickness * 0.5, mouthZ);                                   // 7: center bot
  positions.push(mouthWidth * 0.45, mouthY - mouthThickness * 0.7, mouthZ);                   // 8: right-mid bot
  positions.push(mouthWidth, mouthY - cornerDrop - mouthThickness, mouthZ);                   // 9: right corner bot

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

  const eyeY = headRadius * 4.80;

  // Ear position: at the sides of the head, roughly at eye level
  const earX = hrH * 0.75;             // At head edge
  const earY = eyeY - headRadius * 0.08;  // Slightly below eye line
  const earZ = headRadius * 0.01;      // Near face center

  const earWidth = hrH * 0.05;         // Subtle protrusion
  const earHeight = headRadius * 0.14;  // Vertical size
  const earDepth = headRadius * 0.025;  // Front-to-back thickness

  const positions = [];
  const indices = [];

  function addEar(side) {
    const baseIdx = positions.length / 3;
    const sx = side * earX;
    const dir = side;  // +1 for right, -1 for left

    // 4 vertices: base top, base bottom, outer top, outer bottom
    positions.push(sx, earY + earHeight * 0.5, earZ + earDepth);   // 0: base top-front
    positions.push(sx, earY - earHeight * 0.5, earZ + earDepth);   // 1: base bottom-front
    positions.push(sx, earY - earHeight * 0.5, earZ - earDepth);   // 2: base bottom-back
    positions.push(sx, earY + earHeight * 0.5, earZ - earDepth);   // 3: base top-back

    // Outer point (ear tip, sticks outward)
    positions.push(sx + dir * earWidth, earY + earHeight * 0.15, earZ);  // 4: outer tip

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
