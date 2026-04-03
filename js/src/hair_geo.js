/**
 * Three.js-native hair geometry builder.
 * Simple, clean implementation without Blender legacy code.
 */

import * as THREE from 'three';

/**
 * Build hair geometry with distinct stylized sections.
 * Designed for Three.js Y-up coordinate system.
 * Based on low-poly character hair techniques from game development.
 *
 * @param {number} headRadius - radius of the head
 * @param {string} [style='short'] - hair style name
 * @returns {THREE.BufferGeometry|null}
 */
export function buildHairGeometry(headRadius, style = 'short') {
  if (style === 'none') return null;

  // Create distinct hair sections for stylized low-poly look
  const sections = [];

  // Top section (crown)
  sections.push(createHairSection(
    headRadius,
    'top',
    style === 'long' ? 1.6 : 1.2,
    { y: 0.3, z: -0.05 }
  ));

  // Front section (bangs/fringe area)
  sections.push(createHairSection(
    headRadius,
    'front',
    style === 'long' ? 1.4 : 1.0,
    { y: 0.1, z: -0.25 }
  ));

  // Back section (back of head)
  sections.push(createHairSection(
    headRadius,
    'back',
    style === 'long' ? 1.8 : 1.1,
    { y: -0.1, z: 0.15 }
  ));

  // Side sections (left and right)
  if (style === 'short') {
    sections.push(createHairSection(
      headRadius * 0.8,
      'side',
      1.0,
      { y: 0, z: -0.1, x: 0.35 }
    ));
    sections.push(createHairSection(
      headRadius * 0.8,
      'side',
      1.0,
      { y: 0, z: -0.1, x: -0.35 }
    ));
  }

  // Merge all sections into single geometry
  const mergedGeometry = new THREE.BufferGeometry();
  let vertexOffset = 0;
  const positions = [];
  const indices = [];
  const normals = [];

  for (const section of sections) {
    const pos = section.attributes.position.array;
    const idx = section.index ? section.index.array : null;
    const norm = section.attributes.normal.array;

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
 * Create a single hair section with defined shape and position offset.
 * @private
 */
function createHairSection(headRadius, sectionType, heightScale, positionOffset) {
  let radius, geometry;

  if (sectionType === 'top') {
    // Top crown: rounded cap
    radius = headRadius * 1.25;
    geometry = new THREE.IcosahedronGeometry(radius, 4);
  } else if (sectionType === 'front') {
    // Front bangs: smaller, more angular
    radius = headRadius * 0.9;
    geometry = new THREE.ConeGeometry(radius, radius * heightScale, 6, 4);
    // Rotate cone to point down
    geometry.rotateZ(Math.PI);
  } else if (sectionType === 'back') {
    // Back of head: bulbous shape
    radius = headRadius * 1.1;
    geometry = new THREE.IcosahedronGeometry(radius, 4);
  } else if (sectionType === 'side') {
    // Side pieces: small pods
    radius = headRadius * 0.7;
    geometry = new THREE.IcosahedronGeometry(radius, 3);
  }

  // Apply section-specific deformation
  const positions = geometry.attributes.position;
  for (let i = 0; i < positions.count; i++) {
    const x = positions.getX(i);
    const y = positions.getY(i);
    const z = positions.getZ(i);

    // Scale height based on section
    if (sectionType === 'top' || sectionType === 'back') {
      if (y > 0) {
        positions.setY(i, y * heightScale);
      }
    } else if (sectionType === 'front') {
      // Front section tapers
      positions.setY(i, y * heightScale * 1.2);
      positions.setX(i, x * 0.85);
      positions.setZ(i, z * 0.85);
    }
  }
  positions.needsUpdate = true;

  // Apply position offset
  const offsetX = positionOffset.x || 0;
  const offsetY = positionOffset.y || 0;
  const offsetZ = positionOffset.z || 0;

  for (let i = 0; i < positions.count; i++) {
    positions.setXYZ(
      i,
      positions.getX(i) + offsetX * headRadius,
      positions.getY(i) + offsetY * headRadius,
      positions.getZ(i) + offsetZ * headRadius
    );
  }
  positions.needsUpdate = true;

  geometry.computeVertexNormals();
  return geometry;
}
