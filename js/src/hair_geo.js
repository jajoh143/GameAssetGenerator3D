/**
 * Three.js-native hair geometry builder.
 * Simple, clean implementation without Blender legacy code.
 */

import * as THREE from 'three';

/**
 * Build hair geometry with organic, multi-layered shape.
 * Designed for Three.js Y-up coordinate system.
 * Inspired by hair card and fuzzy mesh techniques from three.js community.
 *
 * @param {number} headRadius - radius of the head
 * @param {string} [style='short'] - hair style name
 * @returns {THREE.BufferGeometry|null}
 */
export function buildHairGeometry(headRadius, style = 'short') {
  if (style === 'none') return null;

  // Create a multi-layered hair geometry for more organic appearance
  const group = new THREE.Group();

  // Hair layer 1: Main body with high detail
  const layer1 = createHairLayer(
    headRadius,
    style === 'long' ? 1.8 : 1.3,  // heightScale
    style === 'short' ? 4 : 5,      // detail level
    style === 'short' ? 1.15 : 1.2  // radiusScale
  );

  // Hair layer 2: Secondary shape for volume (offset slightly)
  const layer2 = createHairLayer(
    headRadius,
    style === 'long' ? 1.5 : 1.0,
    style === 'short' ? 3 : 4,
    style === 'short' ? 0.95 : 1.0
  );
  layer2.position.y -= 0.15 * headRadius;  // Offset for layering effect
  layer2.position.z += 0.1 * headRadius;   // Slight back offset

  // Hair layer 3: Top crown for shape definition
  const layer3 = createHairLayer(
    headRadius * 0.6,
    style === 'long' ? 1.2 : 0.8,
    style === 'short' ? 3 : 4,
    style === 'short' ? 1.3 : 1.25
  );
  layer3.position.y += 0.4 * headRadius;   // Top position

  // Merge all layers into single geometry
  const mergedGeometry = new THREE.BufferGeometry();
  const geometries = [layer1, layer2, layer3];

  let vertexOffset = 0;
  const positions = [];
  const indices = [];
  const normals = [];

  for (const geo of geometries) {
    const pos = geo.attributes.position.array;
    const idx = geo.index ? geo.index.array : null;
    const norm = geo.attributes.normal.array;

    // Add positions
    for (let i = 0; i < pos.length; i += 3) {
      positions.push(pos[i], pos[i + 1], pos[i + 2]);
      normals.push(norm[i], norm[i + 1], norm[i + 2]);
    }

    // Add indices with offset
    if (idx) {
      for (let i = 0; i < idx.length; i++) {
        indices.push(idx[i] + vertexOffset);
      }
    }

    vertexOffset += pos.length / 3;
  }

  mergedGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));
  mergedGeometry.setAttribute('normal', new THREE.BufferAttribute(new Float32Array(normals), 3));
  if (indices.length > 0) {
    mergedGeometry.setIndex(new THREE.BufferAttribute(new Uint32Array(indices), 1));
  }

  return mergedGeometry;
}

/**
 * Create a single hair layer geometry with organic deformation.
 * @private
 */
function createHairLayer(headRadius, heightScale, detail, radiusScale) {
  const radius = headRadius * radiusScale;

  // Use IcosahedronGeometry for smooth, organic base
  const geometry = new THREE.IcosahedronGeometry(radius, detail);

  // Apply organic deformation to vertices
  const positions = geometry.attributes.position;
  for (let i = 0; i < positions.count; i++) {
    const x = positions.getX(i);
    const y = positions.getY(i);
    const z = positions.getZ(i);

    // Create dome shape with variable height
    if (y > 0) {
      // Top half: stretch with height scale
      positions.setY(i, y * heightScale);

      // Add subtle noise to break up geometric appearance
      const noise = Math.sin(x * 3 + z * 2) * 0.05 * radius;
      positions.setX(i, x + noise);
    } else {
      // Bottom half: create gradual tapering
      const taper = Math.max(0, (y + radius) / radius);  // 0 to 1 as we go up
      positions.setY(i, y * taper * 0.4);

      // Taper sides slightly
      const taperedX = x * (0.7 + taper * 0.3);
      const taperedZ = z * (0.7 + taper * 0.3);
      positions.setX(i, taperedX);
      positions.setZ(i, taperedZ);
    }
  }
  positions.needsUpdate = true;

  // Recalculate normals for proper lighting
  geometry.computeVertexNormals();

  return geometry;
}
