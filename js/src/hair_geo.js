/**
 * Simplified hair geometry builder for cartoon mesh.
 * Creates a hair cap that wraps around the head.
 */

import * as THREE from 'three';

/**
 * Build simple hair geometry as a THREE.BufferGeometry.
 * Creates a rounded dome/cap shape for hair.
 *
 * @param {number} headZ - Z position of head center (Z is height)
 * @param {number} headR - head radius
 * @param {string} [style='short'] - hair style name
 * @returns {THREE.BufferGeometry|null}
 */
export function buildHairGeometry(headZ, headR, style = 'short') {
  if (style === 'none') return null;

  const verts = [];
  const faces = [];

  // Create a simple dome/cap shape
  const rings = 4;      // number of vertical rings
  const segments = 12;  // segments around each ring
  const heightScale = style === 'long' ? 1.5 : 1.2;  // taller for long hair

  // Build rings from base to crown
  const ringIndices = [];
  for (let ring = 0; ring <= rings; ring++) {
    const ringIndex = [];
    const ringFraction = ring / rings;

    // Height of this ring (goes from headZ at base to above head at crown)
    const ringZ = headZ + headR * ringFraction * heightScale;

    // Radius shrinks as we go up (dome shape)
    const ringRadius = headR * (1 - ringFraction * 0.8);

    for (let seg = 0; seg < segments; seg++) {
      const angle = (seg / segments) * Math.PI * 2;
      const x = Math.cos(angle) * ringRadius;
      const y = Math.sin(angle) * ringRadius;

      verts.push(x, y, ringZ);
      ringIndex.push(verts.length / 3 - 1);
    }

    ringIndices.push(ringIndex);
  }

  // Connect rings with quads (2 triangles each)
  for (let ring = 0; ring < rings; ring++) {
    const bottomRing = ringIndices[ring];
    const topRing = ringIndices[ring + 1];

    for (let seg = 0; seg < segments; seg++) {
      const nextSeg = (seg + 1) % segments;

      const b0 = bottomRing[seg];
      const b1 = bottomRing[nextSeg];
      const t0 = topRing[seg];
      const t1 = topRing[nextSeg];

      // Two triangles per quad
      faces.push(b0, t0, t1);
      faces.push(b0, t1, b1);
    }
  }

  // Build geometry
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
  geo.setIndex(faces);
  geo.computeVertexNormals();

  return geo;
}
