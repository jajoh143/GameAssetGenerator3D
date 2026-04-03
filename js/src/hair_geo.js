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
    style === 'short' ? 5 : 6,      // detail level (increased for smoothness)
    style === 'short' ? 1.15 : 1.2  // radiusScale
  );

  // Hair layer 2: Secondary shape for volume (offset slightly)
  const layer2 = createHairLayer(
    headRadius,
    style === 'long' ? 1.5 : 1.0,
    style === 'short' ? 5 : 5,      // detail level (increased for smoothness)
    style === 'short' ? 0.95 : 1.0
  );

  // Hair layer 3: Top crown for shape definition
  const layer3 = createHairLayer(
    headRadius * 0.6,
    style === 'long' ? 1.2 : 0.8,
    style === 'short' ? 5 : 5,      // detail level (increased for smoothness)
    style === 'short' ? 1.3 : 1.25
  );

  // Merge all layers into single geometry with offsets
  const mergedGeometry = new THREE.BufferGeometry();
  const layerData = [
    { geo: layer1, offset: { x: 0, y: 0, z: 0 } },
    { geo: layer2, offset: { x: 0, y: -0.15 * headRadius, z: 0.1 * headRadius } },
    { geo: layer3, offset: { x: 0, y: 0.4 * headRadius, z: 0 } }
  ];

  let vertexOffset = 0;
  const positions = [];
  const indices = [];
  const normals = [];

  for (const layer of layerData) {
    const geo = layer.geo;
    const offset = layer.offset;
    const pos = geo.attributes.position.array;
    const idx = geo.index ? geo.index.array : null;
    const norm = geo.attributes.normal.array;

    // Add positions with layer offset applied
    for (let i = 0; i < pos.length; i += 3) {
      positions.push(pos[i] + offset.x, pos[i + 1] + offset.y, pos[i + 2] + offset.z);
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

  // Apply smooth organic deformation to vertices
  const positions = geometry.attributes.position;
  for (let i = 0; i < positions.count; i++) {
    const x = positions.getX(i);
    const y = positions.getY(i);
    const z = positions.getZ(i);

    // Normalize to sphere distance for smooth deformation
    const dist = Math.sqrt(x * x + y * y + z * z);
    if (dist < 0.001) continue;  // Skip center

    // Create dome shape with variable height
    if (y > 0) {
      // Top half: stretch with height scale using smooth curve
      const stretchFactor = 0.5 + 0.5 * Math.sin((y / radius + 1) * Math.PI / 2);  // Smooth curve
      positions.setY(i, y * heightScale * stretchFactor);

      // Minimal subtle variation for organic look (very reduced)
      const subtleNoise = Math.cos(x * 2) * Math.sin(z * 2) * 0.02 * radius;
      positions.setX(i, x + subtleNoise);
    } else {
      // Bottom half: smooth gradual tapering
      const normalizedY = (y + radius) / radius;  // 0 to 1
      const taper = Math.max(0, Math.pow(normalizedY, 1.5));  // Smooth power curve
      positions.setY(i, y * taper * 0.3);

      // Smooth side tapering using cosine for gradual transition
      const sideScale = 0.6 + taper * 0.4;  // 0.6 to 1.0
      positions.setX(i, x * sideScale);
      positions.setZ(i, z * sideScale);
    }
  }
  positions.needsUpdate = true;

  // Recalculate normals for proper lighting
  geometry.computeVertexNormals();

  return geometry;
}
