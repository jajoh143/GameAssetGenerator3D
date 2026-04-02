/**
 * Load Cartoon_Male.glb, remap joints to our 19-bone skeleton, and normalise
 * to targetHeight.
 */

import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, '..', '..');

// GLB joint name → our bone index (0-18)
const GLB_JOINT_TO_BONE_IDX = {
  Hips: 0, HipsCtrl: 0,
  Spine: 1, Chest: 2, UpperChest: 2,
  Neck: 3, Head: 4,
  LeftShoulder: 5, LeftArm: 6, LeftForeArm: 7,
  LeftHand: 8, LeftHandIndex1: 8, LeftHandIndex2: 8, LeftHandIndex3: 8,
  LeftHandThumb1: 8, LeftHandThumb2: 8,
  RightShoulder: 9, RightArm: 10, RightForeArm: 11,
  RightHand: 12, RightHandIndex1: 12, RightHandIndex2: 12, RightHandIndex3: 12,
  RightHandThumb1: 12, RightHandThumb2: 12,
  LeftUpLeg: 13, LeftLeg: 14, LeftFoot: 15, LeftToes: 15,
  RightUpLeg: 16, RightLeg: 17, RightFoot: 18, RightToes: 18,
};

/**
 * Load Cartoon_Male.glb, remap skin indices to our 19-bone layout,
 * shift foot to Z=0, and scale to targetHeight.
 *
 * @param {number} targetHeight - desired character height in metres
 * @returns {Promise<{geometry: THREE.BufferGeometry, height: number}>}
 */
export async function loadCartoonMale(targetHeight = 1.75) {
  const glbPath = join(PROJECT_ROOT, 'assets', 'TemplateMeshes', 'Cartoon_Male.glb');
  const buf = readFileSync(glbPath);

  const loader = new GLTFLoader();
  const gltf = await new Promise((res, rej) => loader.parse(buf.buffer, '', res, rej));

  // Find the main SkinnedMesh (skip tiny helpers < 30 verts)
  let skinnedMesh = null;
  gltf.scene.traverse(obj => {
    if (obj.isSkinnedMesh) {
      const vCount = obj.geometry.attributes.position.count;
      if (vCount >= 30) {
        if (!skinnedMesh || vCount > skinnedMesh.geometry.attributes.position.count) {
          skinnedMesh = obj;
        }
      }
    }
  });

  if (!skinnedMesh) {
    throw new Error('No SkinnedMesh found in Cartoon_Male.glb');
  }

  // Build origJointIdx → ourBoneIdx mapping
  const origBoneNames = skinnedMesh.skeleton.bones.map(b => b.name);
  const origToOur = new Array(origBoneNames.length).fill(-1);
  for (let i = 0; i < origBoneNames.length; i++) {
    const name = origBoneNames[i];
    if (name in GLB_JOINT_TO_BONE_IDX) {
      origToOur[i] = GLB_JOINT_TO_BONE_IDX[name];
    }
  }

  const srcGeo = skinnedMesh.geometry;

  // Extract attributes
  const posAttr = srcGeo.attributes.position;
  const normAttr = srcGeo.attributes.normal;
  const uvAttr = srcGeo.attributes.uv;
  const skinIdxAttr = srcGeo.attributes.skinIndex;
  const skinWtAttr = srcGeo.attributes.skinWeight;
  const idxAttr = srcGeo.index;

  const vCount = posAttr.count;

  // Clone positions to float array
  const positions = new Float32Array(vCount * 3);
  for (let i = 0; i < vCount; i++) {
    positions[i * 3]     = posAttr.getX(i);
    positions[i * 3 + 1] = posAttr.getY(i);
    positions[i * 3 + 2] = posAttr.getZ(i);
  }

  // Find bounding box along Z (input GLB is Z-up from Blender)
  let minZ = Infinity, maxZ = -Infinity;
  for (let i = 0; i < vCount; i++) {
    const z = positions[i * 3 + 2];
    if (z < minZ) minZ = z;
    if (z > maxZ) maxZ = z;
  }

  const origHeight = maxZ - minZ;
  const scale = targetHeight / origHeight;

  // Scale uniformly, shift Z to 0
  for (let i = 0; i < vCount; i++) {
    positions[i * 3]     = positions[i * 3] * scale;
    positions[i * 3 + 1] = positions[i * 3 + 1] * scale;
    positions[i * 3 + 2] = (positions[i * 3 + 2] - minZ) * scale;
  }

  // Remap skin indices and weights
  const skinIndices = new Uint16Array(vCount * 4);
  const skinWeights = new Float32Array(vCount * 4);

  for (let v = 0; v < vCount; v++) {
    // Accumulate weights per our-bone index
    const accum = new Map(); // ourBoneIdx → accumulated weight

    for (let j = 0; j < 4; j++) {
      const origIdx = skinIdxAttr.getComponent(v, j);
      const wt = skinWtAttr.getComponent(v, j);
      if (wt <= 0) continue;

      const ourIdx = origToOur[origIdx] ?? -1;
      if (ourIdx < 0) continue;

      accum.set(ourIdx, (accum.get(ourIdx) ?? 0) + wt);
    }

    // Sort by weight descending, keep top 4
    const sorted = Array.from(accum.entries()).sort((a, b) => b[1] - a[1]).slice(0, 4);

    // Normalise
    const totalWt = sorted.reduce((s, [, w]) => s + w, 0);
    const norm = totalWt > 0 ? 1.0 / totalWt : 0;

    for (let j = 0; j < 4; j++) {
      if (j < sorted.length) {
        skinIndices[v * 4 + j] = sorted[j][0];
        skinWeights[v * 4 + j] = sorted[j][1] * norm;
      } else {
        skinIndices[v * 4 + j] = 0;
        skinWeights[v * 4 + j] = 0;
      }
    }
  }

  // Build new geometry
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));

  if (normAttr) {
    const normals = new Float32Array(vCount * 3);
    for (let i = 0; i < vCount; i++) {
      normals[i * 3]     = normAttr.getX(i);
      normals[i * 3 + 1] = normAttr.getY(i);
      normals[i * 3 + 2] = normAttr.getZ(i);
    }
    geo.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
  }

  if (uvAttr) {
    const uvs = new Float32Array(vCount * 2);
    for (let i = 0; i < vCount; i++) {
      uvs[i * 2]     = uvAttr.getX(i);
      uvs[i * 2 + 1] = uvAttr.getY(i);
    }
    geo.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  }

  geo.setAttribute('skinIndex',  new THREE.Uint16BufferAttribute(skinIndices, 4));
  geo.setAttribute('skinWeight', new THREE.Float32BufferAttribute(skinWeights, 4));

  if (idxAttr) {
    geo.setIndex(Array.from(idxAttr.array));
  }

  if (!normAttr) geo.computeVertexNormals();

  return { geometry: geo, height: targetHeight };
}
