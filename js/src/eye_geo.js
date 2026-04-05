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

  // Ring vertices for left eye
  const leftRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    leftRing.push(positions.length / 3);
    positions.push(
      -eyeX + rx * Math.cos(angle),
      eyeY,
      eyeZ + ry * Math.sin(angle)
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

  // Ring vertices for right eye
  const rightRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    rightRing.push(positions.length / 3);
    positions.push(
      eyeX + rx * Math.cos(angle),
      eyeY,
      eyeZ + ry * Math.sin(angle)
    );
  }

  // Triangle fan for right eye (reversed winding for correct normals)
  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments;
    indices.push(rightCenter, rightRing[next], rightRing[i]);
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

  // Highlight positioned in upper-right corner, forward of eye disc
  const highlightZ = eyeZ + eyeRy * 0.45;  // High in the eye
  const highlightYOffset = highlightR * 0.8;  // Well in front

  // Left eye highlight
  const leftHlCenter = positions.length / 3;
  positions.push(-eyeX + eyeX * 0.35, eyeY - highlightYOffset, highlightZ);

  const leftHlRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    leftHlRing.push(positions.length / 3);
    positions.push(
      -eyeX + eyeX * 0.35 + highlightR * Math.cos(angle),
      eyeY - highlightYOffset,
      highlightZ + highlightR * Math.sin(angle)
    );
  }

  // Triangle fan for left highlight
  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments;
    indices.push(leftHlCenter, leftHlRing[i], leftHlRing[next]);
  }

  // Right eye highlight
  const rightHlCenter = positions.length / 3;
  positions.push(eyeX - eyeX * 0.35, eyeY - highlightYOffset, highlightZ);

  const rightHlRing = [];
  for (let i = 0; i < segments; i++) {
    const angle = (2 * Math.PI * i) / segments;
    rightHlRing.push(positions.length / 3);
    positions.push(
      eyeX - eyeX * 0.35 + highlightR * Math.cos(angle),
      eyeY - highlightYOffset,
      highlightZ + highlightR * Math.sin(angle)
    );
  }

  // Triangle fan for right highlight (reversed winding)
  for (let i = 0; i < segments; i++) {
    const next = (i + 1) % segments;
    indices.push(rightHlCenter, rightHlRing[next], rightHlRing[i]);
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
  const eyeR = hrH * 0.18;        // 18% of horizontal head radius
  const rx = eyeR * 1.25;         // Slightly wider
  const ry = eyeR * 1.05;         // Slightly taller
  const eyeX = hrH * 0.36;        // Wide lateral separation
  const eyeZ = headRadius * 0.15; // Above head center (chibi style)

  // Fallback Y positioning if face_y isn't available
  const eyeY = -(hrH * 0.62);     // Spherical approximation

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
  });

  // Bright white emissive material for highlight
  const highlightMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(1.0, 1.0, 1.0),
    roughness: 0.0,
    metalness: 0.0,
    emissive: new THREE.Color(1.0, 1.0, 1.0),
    emissiveIntensity: 2.0,
  });

  return {
    eyeDiscMaterial: eyeDiscMat,
    highlightMaterial: highlightMat
  };
}
