/**
 * Three.js-native hair geometry builder.
 * Simple, clean implementation without Blender legacy code.
 */

import * as THREE from 'three';

/**
 * Build hair geometry as a simple rounded cap.
 * Designed for Three.js Y-up coordinate system.
 *
 * @param {number} headRadius - radius of the head
 * @param {string} [style='short'] - hair style name
 * @returns {THREE.BufferGeometry|null}
 */
export function buildHairGeometry(headRadius, style = 'short') {
  if (style === 'none') return null;

  // Hair is just a simple sphere or icosahedron positioned above the head
  // We'll use an IcosahedronGeometry which gives nice results
  const heightScale = style === 'long' ? 1.8 : 1.3;
  const radius = headRadius * 1.1;  // slightly larger than head
  const detail = style === 'short' ? 3 : 4;  // more detail for long hair

  // Create base hair geometry
  const geometry = new THREE.IcosahedronGeometry(radius, detail);

  // Scale it vertically to create a dome shape
  const positions = geometry.attributes.position;
  for (let i = 0; i < positions.count; i++) {
    const y = positions.getY(i);
    // Only stretch the top half of the sphere
    if (y > 0) {
      positions.setY(i, y * heightScale);
    } else {
      // Flatten the bottom
      positions.setY(i, -radius * 0.3);
    }
  }
  positions.needsUpdate = true;

  // Shift vertices so the base sits at origin (will be positioned above head)
  const offset = new THREE.Vector3(0, radius * heightScale * 0.5, 0);
  for (let i = 0; i < positions.count; i++) {
    positions.setXYZ(
      i,
      positions.getX(i),
      positions.getY(i) - offset.y,
      positions.getZ(i)
    );
  }
  positions.needsUpdate = true;

  geometry.computeVertexNormals();
  return geometry;
}
