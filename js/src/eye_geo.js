/**
 * Improved eye geometry builder for Three.js.
 *
 * Each eye is a multi-layer system:
 * - White sclera (slightly convex dome)
 * - Colored iris ring
 * - Black pupil disc
 * - White highlight for shine/expression
 *
 * Designed for cartoony low-poly characters with expressive, readable eyes.
 */

import * as THREE from 'three';

// ── Eye color palette ───────────────────────────────────────────────────────

export const EYE_COLORS = {
  brown:  [0.35, 0.20, 0.10],
  blue:   [0.20, 0.45, 0.75],
  green:  [0.22, 0.50, 0.28],
  hazel:  [0.50, 0.38, 0.18],
  grey:   [0.45, 0.48, 0.50],
};

// ── Geometry helpers ────────────────────────────────────────────────────────

/**
 * Create a shallow dome (convex disc) with triangle fan.
 * center bulges forward in +Z by `depth`.
 */
function createDomeGeometry(centerX, centerY, centerZ, rx, ry, depth, segments) {
  const positions = [];
  const indices = [];

  // Center vertex — pushed forward
  const cIdx = 0;
  positions.push(centerX, centerY, centerZ + depth);

  // Ring vertices — at base depth
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    positions.push(
      centerX + rx * Math.cos(angle),
      centerY + ry * Math.sin(angle),
      centerZ
    );
  }

  // Triangle fan
  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments;
    indices.push(cIdx, 1 + i, 1 + next);
  }

  return { positions, indices };
}

/**
 * Create an annular ring (iris) between inner and outer radius.
 */
function createRingGeometry(centerX, centerY, centerZ, innerRx, innerRy, outerRx, outerRy, segments) {
  const positions = [];
  const indices = [];

  // Inner ring vertices
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    positions.push(
      centerX + innerRx * Math.cos(angle),
      centerY + innerRy * Math.sin(angle),
      centerZ
    );
  }

  // Outer ring vertices
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    positions.push(
      centerX + outerRx * Math.cos(angle),
      centerY + outerRy * Math.sin(angle),
      centerZ
    );
  }

  // Quad strip between inner and outer rings
  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments;
    const inner0 = i;
    const inner1 = next;
    const outer0 = segments + i;
    const outer1 = segments + next;
    indices.push(inner0, outer0, outer1);
    indices.push(inner0, outer1, inner1);
  }

  return { positions, indices };
}

/**
 * Merge two eye geometries (left + right) into one BufferGeometry.
 */
function mergeEyePair(buildFn, eyeX, eyeY, eyeZ, ...args) {
  const left = buildFn(-eyeX, eyeY, eyeZ, ...args);
  const right = buildFn(eyeX, eyeY, eyeZ, ...args);

  // Offset right indices
  const leftVertCount = left.positions.length / 3;
  const mergedPositions = [...left.positions, ...right.positions];
  const mergedIndices = [...left.indices, ...right.indices.map(i => i + leftVertCount)];

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(mergedPositions), 3));
  geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(mergedIndices), 1));
  geometry.computeVertexNormals();
  return geometry;
}

/**
 * Build all eye geometry layers for the character.
 *
 * @param {number} headRadius - Head radius (vertical)
 * @param {number} headRadiusHoriz - Head radius (horizontal, defaults to headRadius)
 * @returns {Object} { scleraGeometry, irisGeometry, pupilGeometry, highlightGeometry }
 */
export function buildEyeGeometry(headRadius, headRadiusHoriz = null) {
  const hrH = headRadiusHoriz !== null ? headRadiusHoriz : headRadius;

  // ── Sizing — moderately larger for cartoony appeal ──
  const eyeR = hrH * 0.13;          // 13% of horizontal head radius (moderate increase from 12%)
  const scleraRx = eyeR * 1.15;     // Slightly wider than tall
  const scleraRy = eyeR * 0.95;

  // ── Positioning ──
  // Y = forward (toward face), Z = up (height on face), X = left/right
  // eyeY=5.0 is proven to place features on the face surface (from original working code)
  const eyeX = hrH * 0.16;          // Lateral — within head width
  const eyeY = headRadius * 5.0;    // Forward — on face surface (proven value)
  const eyeZ = headRadius * 0.14;   // Height — mid-face (0.22 was forehead in original)

  // ── Sclera (white dome) ──
  const scleraDomeDepth = eyeR * 0.10;  // Very slight convexity
  const scleraSegments = 10;
  const scleraGeometry = mergeEyePair(
    createDomeGeometry,
    eyeX, eyeY, eyeZ,
    scleraRx, scleraRy, scleraDomeDepth, scleraSegments
  );

  // ── Iris (colored ring) ──
  const irisInnerRx = scleraRx * 0.40;  // Pupil hole
  const irisInnerRy = scleraRy * 0.40;
  const irisOuterRx = scleraRx * 0.70;  // Iris outer edge
  const irisOuterRy = scleraRy * 0.70;
  const irisZ = eyeZ + scleraDomeDepth * 0.5;  // Sits on top of sclera dome
  const irisSegments = 10;
  const irisGeometry = mergeEyePair(
    createRingGeometry,
    eyeX, eyeY, irisZ,
    irisInnerRx, irisInnerRy, irisOuterRx, irisOuterRy, irisSegments
  );

  // ── Pupil (black center disc) ──
  const pupilRx = irisInnerRx;
  const pupilRy = irisInnerRy;
  const pupilZ = irisZ + 0.001;  // Tiny offset to prevent z-fighting
  const pupilDepth = 0;
  const pupilSegments = 8;
  const pupilGeometry = mergeEyePair(
    createDomeGeometry,
    eyeX, eyeY, pupilZ,
    pupilRx, pupilRy, pupilDepth, pupilSegments
  );

  // ── Highlight (white glint) ──
  const highlightR = eyeR * 0.22;   // Visible but not overpowering
  const highlightOffsetX = scleraRx * 0.25;   // Upper-inner quadrant
  const highlightOffsetY = scleraRy * 0.28;
  const highlightZ = irisZ + 0.003;

  // Build highlights manually (different position per eye)
  const hlSegments = 6;
  const leftHl = createDomeGeometry(
    -eyeX + highlightOffsetX, eyeY + highlightOffsetY, highlightZ,
    highlightR, highlightR, 0, hlSegments
  );
  const rightHl = createDomeGeometry(
    eyeX - highlightOffsetX, eyeY + highlightOffsetY, highlightZ,
    highlightR, highlightR, 0, hlSegments
  );

  const hlLeftCount = leftHl.positions.length / 3;
  const highlightGeometry = new THREE.BufferGeometry();
  highlightGeometry.setAttribute('position', new THREE.BufferAttribute(
    new Float32Array([...leftHl.positions, ...rightHl.positions]), 3
  ));
  highlightGeometry.setIndex(new THREE.BufferAttribute(
    new Uint32Array([...leftHl.indices, ...rightHl.indices.map(i => i + hlLeftCount)]), 1
  ));
  highlightGeometry.computeVertexNormals();

  return {
    scleraGeometry,
    irisGeometry,
    pupilGeometry,
    highlightGeometry,
  };
}

/**
 * Create materials for the multi-layer eye system.
 * @param {string|number[]} eyeColor - Named color or [r,g,b] array
 * @returns {Object} { scleraMaterial, irisMaterial, pupilMaterial, highlightMaterial }
 */
export function createEyeMaterials(eyeColor = 'brown') {
  // Resolve iris color
  let irisRgb;
  if (Array.isArray(eyeColor)) {
    irisRgb = eyeColor;
  } else {
    irisRgb = EYE_COLORS[eyeColor] ?? EYE_COLORS.brown;
  }

  // White sclera
  const scleraMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(0.95, 0.95, 0.95),
    roughness: 0.3,
    metalness: 0.0,
    side: THREE.DoubleSide,
  });

  // Colored iris
  const irisMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(irisRgb[0], irisRgb[1], irisRgb[2]),
    roughness: 0.4,
    metalness: 0.0,
    emissive: new THREE.Color(irisRgb[0] * 0.15, irisRgb[1] * 0.15, irisRgb[2] * 0.15),
    emissiveIntensity: 0.5,
    side: THREE.DoubleSide,
  });

  // Black pupil
  const pupilMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(0.02, 0.02, 0.03),
    roughness: 0.8,
    metalness: 0.0,
    emissive: new THREE.Color(0.01, 0.01, 0.02),
    emissiveIntensity: 0.3,
    side: THREE.DoubleSide,
  });

  // Bright white highlight
  const highlightMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(1.0, 1.0, 1.0),
    roughness: 0.0,
    metalness: 0.0,
    emissive: new THREE.Color(1.0, 1.0, 1.0),
    emissiveIntensity: 2.0,
    side: THREE.DoubleSide,
  });

  return {
    scleraMaterial: scleraMat,
    irisMaterial: irisMat,
    pupilMaterial: pupilMat,
    highlightMaterial: highlightMat,
  };
}
