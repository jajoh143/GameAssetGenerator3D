/**
 * Load NBM_Lowpoly_Male.glb or NBM_Lowpoly_Female.glb, remap joints to our
 * 19-bone skeleton, and normalise to targetHeight.
 *
 * Gender selection:
 *   'female'           → NBM_Lowpoly_Female.glb
 *   'male' | 'neutral' → NBM_Lowpoly_Male.glb
 */

import { NullEngine, Scene, SceneLoader } from '@babylonjs/core';
import '@babylonjs/loaders/glTF/index.js';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, '..', '..');

// GLB joint name → our bone index (0-18).
// Covers standard Mixamo naming used by the NBM exports.
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
 */
function unpackBoneIndex(packedFloat, slot) {
  const buf = new ArrayBuffer(4);
  new DataView(buf).setFloat32(0, packedFloat, true);
  return new DataView(buf).getUint8(slot);
}

/**
 * Load the appropriate low-poly GLB for the given gender, remap skin indices
 * to our 19-bone layout, shift foot to Y=0, and scale to targetHeight.
 *
 * @param {string} gender       - 'male', 'female', or 'neutral'
 * @param {number} targetHeight - desired character height in metres
 * @returns {Promise<{positions, normals, uvs, skinIndices, skinWeights, indices, height}>}
 */
export async function loadLowPolyMesh(gender = 'neutral', targetHeight = 1.75) {
  const filename = gender === 'female'
    ? 'NBM_Lowpoly_Female.glb'
    : 'NBM_Lowpoly_Male.glb';

  const glbPath = join(PROJECT_ROOT, 'assets', 'TemplateMeshes', filename);
  const buf = readFileSync(glbPath);
  const b64 = buf.toString('base64');
  const dataUrl = `data:model/gltf-binary;base64,${b64}`;

  const engine = new NullEngine();
  const scene = new Scene(engine);

  const result = await SceneLoader.ImportMeshAsync('', '', dataUrl, scene, null, '.glb');

  // Find the largest mesh with at least 30 vertices.
  // Prefer a skinned mesh (has skeleton), but fall back to any mesh if none
  // are skinned — the NBM_Lowpoly exports are static meshes without rigs.
  let bestMesh = null;
  let bestSkinned = null;
  for (const mesh of result.meshes) {
    const vCount = mesh.getTotalVertices();
    if (vCount < 30) continue;
    if (mesh.skeleton && (!bestSkinned || vCount > bestSkinned.getTotalVertices())) {
      bestSkinned = mesh;
    }
    if (!bestMesh || vCount > bestMesh.getTotalVertices()) {
      bestMesh = mesh;
    }
  }

  const targetMesh = bestSkinned ?? bestMesh;
  if (!targetMesh) {
    engine.dispose();
    throw new Error(`No usable mesh found in ${filename}`);
  }

  const isSkinned = !!targetMesh.skeleton;
  console.log(`[lowpoly_mesh_loader] ${filename}: using mesh "${targetMesh.name}" (${targetMesh.getTotalVertices()} verts, ${isSkinned ? 'skinned' : 'static — will bind to Hips'})`);

  // If the mesh has a skeleton, build joint remapping and log unmapped bones
  let origToOur = null;
  if (isSkinned) {
    const origBoneNames = targetMesh.skeleton.bones.map(b => b.name);
    origToOur = new Array(origBoneNames.length).fill(-1);
    const unmapped = [];
    for (let i = 0; i < origBoneNames.length; i++) {
      const name = origBoneNames[i];
      if (name in GLB_JOINT_TO_BONE_IDX) {
        origToOur[i] = GLB_JOINT_TO_BONE_IDX[name];
      } else {
        unmapped.push(name);
      }
    }
    if (unmapped.length > 0) {
      console.warn(`[lowpoly_mesh_loader] ${filename}: unmapped bone names (will default to Hips): ${unmapped.join(', ')}`);
    }
  }

  // Extract vertex data
  const posArr    = targetMesh.getVerticesData('position');
  const normArr   = targetMesh.getVerticesData('normal');
  const uvArr     = targetMesh.getVerticesData('uv');
  const matIdxArr = targetMesh.getVerticesData('matricesIndices');
  const matWtArr  = targetMesh.getVerticesData('matricesWeights');
  const idxArr    = targetMesh.getIndices();

  const vCount = posArr.length / 3;

  // Clone positions
  const positions = new Float32Array(posArr);

  // Find bounding box along Y (Babylon/glTF Y-up)
  let minY = Infinity, maxY = -Infinity;
  for (let i = 0; i < vCount; i++) {
    const y = positions[i * 3 + 1];
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  }

  const origHeight = maxY - minY;
  const scale = targetHeight / origHeight;

  // Scale uniformly, shift Y so feet start at 0
  for (let i = 0; i < vCount; i++) {
    positions[i * 3]      *= scale;
    positions[i * 3 + 1]   = (positions[i * 3 + 1] - minY) * scale;
    positions[i * 3 + 2]  *= scale;
  }

  // Build skin indices and weights.
  // Static mesh (no skeleton): bind every vertex 100% to bone 0 (Hips) so
  // the mesh at least moves with the root and the builder doesn't error.
  const skinIndices = new Uint16Array(vCount * 4);
  const skinWeights = new Float32Array(vCount * 4);

  if (!isSkinned || !matIdxArr || !matWtArr) {
    // No skin data — root-bind all vertices to Hips (bone 0)
    for (let v = 0; v < vCount; v++) {
      skinIndices[v * 4] = 0;
      skinWeights[v * 4] = 1.0;
    }
  } else {
    for (let v = 0; v < vCount; v++) {
      const accum = new Map(); // ourBoneIdx → accumulated weight

      for (let j = 0; j < 4; j++) {
        const origIdx = unpackBoneIndex(matIdxArr[v * 4 + j], 0);
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
  }

  const normals = normArr ? new Float32Array(normArr) : null;
  const uvs     = uvArr   ? new Float32Array(uvArr)   : null;
  const indices = new Uint32Array(idxArr);

  engine.dispose();

  return { positions, normals, uvs, skinIndices, skinWeights, indices, height: targetHeight };
}
