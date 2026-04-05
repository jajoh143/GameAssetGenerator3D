/**
 * Professional flat-disc eye geometry builder for Three.js.
 * Based on GameAssetGenerator3D's Blender eye system.
 *
 * Each eye is a simple flat elliptical disc (not 3D sphere):
 * - Black matte disc for the eye itself
 * - Separate white highlight for shine/expression
 *
 * Total: ~28 faces (16 per eye + 12 highlights)
 */

import * as THREE from 'three';

/**
 * Create vertices in an elliptical ring.
 * Used for both eye disc and highlight geometry.
 */
function createEllipticalRing(centerX, centerY, centerZ, rx, ry, segments = 10) {
  const vertices = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    vertices.push(new THREE.Vector3(
      centerX + rx * Math.cos(angle),
      centerY,
      centerZ + ry * Math.sin(angle)
    ));
  }
  return vertices;
}

/**
 * Create geometry for the eye disc itself.
 * Simple flat ellipse with triangle fan.
 */
function createEyeDiscGeometry(eyeX, eyeY, eyeZ, rx, ry, segments = 10) {
  const geometry = new THREE.BufferGeometry();
  const positions = [];
  const indices = [];

  // Center vertex for left eye
  const leftCenter = positions.length / 3;
  positions.push(-eyeX, eyeY, eyeZ);

  // Ring vertices for left eye — disc in X-Y plane, normal points in +Z (toward viewer)
  const leftRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    leftRing.push(positions.length / 3);
    positions.push(
      -eyeX + rx * Math.cos(angle),
      eyeY + ry * Math.sin(angle),
      eyeZ
    );
  }

  // Triangle fan for left eye
  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments;
    indices.push(leftCenter, leftRing[i], leftRing[next]);
  }

  // Center vertex for right eye
  const rightCenter = positions.length / 3;
  positions.push(eyeX, eyeY, eyeZ);

  // Ring vertices for right eye — same X-Y plane orientation
  const rightRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    rightRing.push(positions.length / 3);
    positions.push(
      eyeX + rx * Math.cos(angle),
      eyeY + ry * Math.sin(angle),
      eyeZ
    );
  }

  // Triangle fan for right eye — same winding as left (both face +Z)
  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments;
    indices.push(rightCenter, rightRing[i], rightRing[next]);
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));
  geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(indices), 1));
  geometry.computeVertexNormals();

  return geometry;
}

/**
 * Create geometry for eye highlights (white glints).
 * Small highlights positioned in upper-right of each eye.
 */
function createHighlightGeometry(eyeX, eyeY, eyeZ, highlightR, eyeRy, segments = 6) {
  const geometry = new THREE.BufferGeometry();
  const positions = [];
  const indices = [];

  // Highlight in X-Y plane, slightly in front of eye disc (+Z), upper-inner quadrant
  const highlightY = eyeY + eyeRy * 0.45;   // Upper portion of eye (Y = up)
  const highlightZ = eyeZ + highlightR * 0.05;  // Slightly forward of eye disc

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

  // Triangle fan for left highlight
  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments;
    indices.push(leftHlCenter, leftHlRing[i], leftHlRing[next]);
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

  // Triangle fan for right highlight — same winding as left (both face +Z)
  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments;
    indices.push(rightHlCenter, rightHlRing[i], rightHlRing[next]);
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));
  geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(indices), 1));
  geometry.computeVertexNormals();

  return geometry;
}

/**
 * Build eye geometry for the character.
 * Returns { eyeDiscGeo, highlightGeo }
 *
 * @param {number} headRadius - Head radius (vertical)
 * @param {number} headRadiusHoriz - Head radius (horizontal, defaults to headRadius)
 * @returns {Object} { eyeDiscGeometry, highlightGeometry }
 */
export function buildEyeGeometry(headRadius, headRadiusHoriz = null) {
  const hrH = headRadiusHoriz !== null ? headRadiusHoriz : headRadius;

  // Eye sizing and positioning
  // Coordinate system: Y = up (height), Z = forward (toward viewer), X = left/right
  const eyeR = hrH * 0.18;        // 18% of horizontal head radius
  const rx = eyeR * 1.25;         // Slightly wider than tall
  const ry = eyeR * 1.05;         // Slightly taller
  const eyeX = hrH * 0.36;        // Lateral separation
  const eyeY = headRadius * 5.0;  // Height: in the face region (hair base ≈ headRadius*5.5)
  const eyeZ = headRadius * 0.20; // Forward: toward camera, near face surface

  // Highlight sizing
  const highlightR = eyeR * 0.18; // Small glint

  // Create geometries
  const eyeDiscGeo = createEyeDiscGeometry(eyeX, eyeY, eyeZ, rx, ry, 10);
  const highlightGeo = createHighlightGeometry(eyeX, eyeY, eyeZ, highlightR, ry, 6);

  return {
    eyeDiscGeometry: eyeDiscGeo,
    highlightGeometry: highlightGeo
  };
}

/**
 * Create materials for eyes.
 * Returns { eyeDiscMaterial, highlightMaterial }
 */
export function createEyeMaterials() {
  // Matte black material for eye disc
  const eyeDiscMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(0.01, 0.01, 0.02),
    roughness: 1.0,
    metalness: 0.0,
    emissive: new THREE.Color(0.02, 0.02, 0.03),
    emissiveIntensity: 0.5,
    side: THREE.DoubleSide,
  });

  // Bright white emissive material for highlight
  const highlightMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(1.0, 1.0, 1.0),
    roughness: 0.0,
    metalness: 0.0,
    emissive: new THREE.Color(1.0, 1.0, 1.0),
    emissiveIntensity: 2.0,
    side: THREE.DoubleSide,
  });

  return {
    eyeDiscMaterial: eyeDiscMat,
    highlightMaterial: highlightMat
  };
}
