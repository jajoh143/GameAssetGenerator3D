/**
 * Load Cartoon_Male.glb, remap joints to our 19-bone skeleton, and normalise
 * to targetHeight.
 */

import { NullEngine, Scene, SceneLoader } from '@babylonjs/core';
import '@babylonjs/loaders/glTF';
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
 * Unpack one of the 4 Babylon-packed bone indices from a single Float32.
 * Babylon stores 4 uint8 joint indices packed into one float via DataView.
 */
function unpackBoneIndex(packedFloat, slot) {
  const buf = new ArrayBuffer(4);
  new DataView(buf).setFloat32(0, packedFloat, true);
  return new DataView(buf).getUint8(slot);
}

/**
 * Load Cartoon_Male.glb, remap skin indices to our 19-bone layout,
 * shift foot to Z=0, and scale to targetHeight.
 *
 * @param {number} targetHeight - desired character height in metres
 * @returns {Promise<{positions, normals, uvs, skinIndices, skinWeights, indices, height}>}
 */
export async function loadCartoonMale(targetHeight = 1.75) {
  const glbPath = join(PROJECT_ROOT, 'assets', 'TemplateMeshes', 'Cartoon_Male.glb');
  const buf = readFileSync(glbPath);
  const b64 = buf.toString('base64');
  const dataUrl = `data:model/gltf-binary;base64,${b64}`;

  const engine = new NullEngine();
  const scene = new Scene(engine);

  const result = await SceneLoader.ImportMeshAsync('', '', dataUrl, scene, null, '.glb');

  // Find the main skinned mesh (skip tiny helpers < 30 verts)
  let skinnedMesh = null;
  for (const mesh of result.meshes) {
    if (!mesh.skeleton) continue;
    const vCount = mesh.getTotalVertices();
    if (vCount < 30) continue;
    if (!skinnedMesh || vCount > skinnedMesh.getTotalVertices()) {
      skinnedMesh = mesh;
    }
  }

  if (!skinnedMesh) {
    engine.dispose();
    throw new Error('No SkinnedMesh found in Cartoon_Male.glb');
  }

  // Build origJointIdx → ourBoneIdx mapping
  const skeleton = skinnedMesh.skeleton;
  const origBoneNames = skeleton.bones.map(b => b.name);
  const origToOur = new Array(origBoneNames.length).fill(-1);
  for (let i = 0; i < origBoneNames.length; i++) {
    const name = origBoneNames[i];
    if (name in GLB_JOINT_TO_BONE_IDX) {
      origToOur[i] = GLB_JOINT_TO_BONE_IDX[name];
    }
  }

  // Extract vertex data
  const posArr  = skinnedMesh.getVerticesData('position');   // Float32Array, stride 3
  const normArr = skinnedMesh.getVerticesData('normal');     // Float32Array, stride 3
  const uvArr   = skinnedMesh.getVerticesData('uv');         // Float32Array, stride 2
  // Babylon packs 4 uint8 bone indices into 1 float — stride 4 floats = 4 packed indices
  const matIdxArr = skinnedMesh.getVerticesData('matricesIndices');  // Float32Array, stride 4
  const matWtArr  = skinnedMesh.getVerticesData('matricesWeights');  // Float32Array, stride 4
  const idxArr    = skinnedMesh.getIndices();

  const vCount = posArr.length / 3;

  // Clone positions
  const positions = new Float32Array(posArr);

  // Find bounding box along Z (Blender Z-up)
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
    positions[i * 3]     *= scale;
    positions[i * 3 + 1] *= scale;
    positions[i * 3 + 2]  = (positions[i * 3 + 2] - minZ) * scale;
  }

  // Remap skin indices and weights
  const skinIndices = new Uint16Array(vCount * 4);
  const skinWeights = new Float32Array(vCount * 4);

  for (let v = 0; v < vCount; v++) {
    const accum = new Map(); // ourBoneIdx → accumulated weight

    for (let j = 0; j < 4; j++) {
      const origIdx = unpackBoneIndex(matIdxArr[v * 4 + j], 0); // packed into slot 0
      const wt = matWtArr[v * 4 + j];
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

  // Build normals (scaled normals stay unit — scaling is uniform)
  const normals = normArr ? new Float32Array(normArr) : null;

  // Build UVs
  const uvs = uvArr ? new Float32Array(uvArr) : null;

  // Indices
  const indices = new Uint32Array(idxArr);

  engine.dispose();

  return { positions, normals, uvs, skinIndices, skinWeights, indices, height: targetHeight };
}
