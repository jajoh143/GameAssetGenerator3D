/**
 * Ring-cap hair geometry builder.
 * Pure Three.js BufferGeometry — no bmesh.
 */

import * as THREE from 'three';

const CAP_LEVELS = [
  [0.00, 0.97, 0.90],  // hairline
  [0.50, 0.84, 0.77],  // upper forehead
  [0.86, 0.52, 0.48],  // upper cranium
  [0.97, 0.14, 0.13],  // crown apex
];
const RING_N = 12;
const H_SCALE = 1.20;

/**
 * Build hair geometry as a THREE.BufferGeometry.
 *
 * @param {number} headY - Y position of head centre (Y-up)
 * @param {number} headR - head radius (vertical)
 * @param {string} [style='short'] - hair style name
 * @param {number|null} [headRHoriz=null] - horizontal head radius
 * @returns {THREE.BufferGeometry|null}
 */
export function buildHairGeometry(headY, headR, style = 'short', headRHoriz = null) {
  if (style === 'none') return null;
  const hr = headRHoriz ?? headR;
  const verts = [];   // flat [x,y,z,x,y,z,...]
  const faces = [];   // flat [i,j,k,i,j,k,...] triangles

  // Rings lie in XZ plane at height cy (Y-up convention)
  function ringVerts(cy, rxM, ryM) {
    const start = verts.length / 3;
    for (let i = 0; i < RING_N; i++) {
      const a = 2 * Math.PI * i / RING_N;
      verts.push(
        hr * rxM * H_SCALE * Math.sin(a),
        cy,
        -hr * ryM * H_SCALE * Math.cos(a)
      );
    }
    return start;  // index of first vertex in this ring
  }

  const rings = CAP_LEVELS.map(([yOff, rxM, ryM]) =>
    ringVerts(headY + headR * yOff, rxM, ryM)
  );

  // Bridge rings with quads (2 triangles each)
  for (let r = 0; r < rings.length - 1; r++) {
    const a = rings[r], b = rings[r + 1];
    for (let i = 0; i < RING_N; i++) {
      const j = (i + 1) % RING_N;
      faces.push(a+i, a+j, b+j,  a+i, b+j, b+i);
    }
  }

  // Close crown with triangle fan
  const topStart = rings[rings.length - 1];
  const crownIdx = verts.length / 3;
  verts.push(0, headY + headR, 0);
  for (let i = 0; i < RING_N; i++) {
    faces.push(topStart+i, topStart+(i+1)%RING_N, crownIdx);
  }

  // For 'short' or 'long' style also add a simple nape panel
  if (style === 'short' || style === 'long') {
    const napeY = headY - headR * 0.3;
    const hairlineStart = rings[0];
    const napeStart = verts.length / 3;
    for (let i = 0; i < RING_N; i++) {
      const a = 2 * Math.PI * i / RING_N;
      verts.push(
        hr * 0.97 * H_SCALE * Math.sin(a),
        napeY,
        -hr * 0.90 * H_SCALE * Math.cos(a)
      );
    }
    // Bridge back half only (indices RING_N/4 to 3*RING_N/4)
    const backStart = Math.floor(RING_N / 4);
    const backEnd = Math.floor(3 * RING_N / 4);
    for (let i = backStart; i < backEnd; i++) {
      const j = i + 1;
      faces.push(
        hairlineStart+i, hairlineStart+j, napeStart+j,
        hairlineStart+i, napeStart+j, napeStart+i
      );
    }
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
  geo.setIndex(faces);
  geo.computeVertexNormals();
  return geo;
}
