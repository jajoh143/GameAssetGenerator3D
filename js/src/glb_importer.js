/**
 * Load an arbitrary GLB file, normalise it to a target height, and produce
 * mesh data (positions, normals, uvs, skinIndices, skinWeights, indices)
 * compatible with builder.js / buildRiggedFromGLB().
 *
 * Two skin-weighting paths:
 *   • Existing skeleton whose bone names match our dictionary (Mixamo, glTF,
 *     Unity conventions) → remap joint indices to our 19-bone layout.
 *   • No skeleton, or skeleton with too few recognisable bones → envelope-based
 *     auto-weighting using bone-segment distance with Gaussian falloff.
 */

import { NullEngine, Scene, SceneLoader } from '@babylonjs/core';
import '@babylonjs/loaders/glTF/index.js';
import { BONE_NAMES, BONE_PARENTS, boneWorldPositions } from './skeleton.js';

// ── Bone name → our 19-bone index ────────────────────────────────────────────
// Covers Mixamo ("mixamorig_*", "mixamorig:*"), Unity humanoid, plain glTF/VRM,
// and our own convention used in skeleton.js.
const NAME_TO_BONE_IDX = {
  // 0  Hips
  Hips: 0, hips: 0, Pelvis: 0, pelvis: 0, HipsCtrl: 0,
  mixamorig_Hips: 0, 'mixamorig:Hips': 0,
  // 1  Spine
  Spine: 1, spine: 1, Spine1: 1, spine1: 1,
  mixamorig_Spine: 1, 'mixamorig:Spine': 1,
  // 2  Chest
  Chest: 2, chest: 2, Spine2: 2, spine2: 2, UpperChest: 2,
  mixamorig_Spine2: 2, 'mixamorig:Spine2': 2,
  mixamorig_Spine1: 2, 'mixamorig:Spine1': 2,
  // 3  Neck
  Neck: 3, neck: 3, mixamorig_Neck: 3, 'mixamorig:Neck': 3,
  // 4  Head
  Head: 4, head: 4, mixamorig_Head: 4, 'mixamorig:Head': 4,
  // 5  Shoulder.L
  'Shoulder.L': 5, LeftShoulder: 5, L_Shoulder: 5,
  mixamorig_LeftShoulder: 5, 'mixamorig:LeftShoulder': 5,
  // 6  UpperArm.L
  'UpperArm.L': 6, LeftArm: 6, LeftUpperArm: 6, L_UpperArm: 6,
  mixamorig_LeftArm: 6, 'mixamorig:LeftArm': 6,
  // 7  LowerArm.L
  'LowerArm.L': 7, LeftForeArm: 7, LeftForearm: 7, L_LowerArm: 7,
  mixamorig_LeftForeArm: 7, 'mixamorig:LeftForeArm': 7,
  // 8  Hand.L
  'Hand.L': 8, LeftHand: 8, L_Hand: 8,
  mixamorig_LeftHand: 8, 'mixamorig:LeftHand': 8,
  LeftHandIndex1: 8, LeftHandIndex2: 8, LeftHandIndex3: 8,
  LeftHandThumb1: 8, LeftHandThumb2: 8,
  // 9  Shoulder.R
  'Shoulder.R': 9, RightShoulder: 9, R_Shoulder: 9,
  mixamorig_RightShoulder: 9, 'mixamorig:RightShoulder': 9,
  // 10 UpperArm.R
  'UpperArm.R': 10, RightArm: 10, RightUpperArm: 10, R_UpperArm: 10,
  mixamorig_RightArm: 10, 'mixamorig:RightArm': 10,
  // 11 LowerArm.R
  'LowerArm.R': 11, RightForeArm: 11, RightForearm: 11, R_LowerArm: 11,
  mixamorig_RightForeArm: 11, 'mixamorig:RightForeArm': 11,
  // 12 Hand.R
  'Hand.R': 12, RightHand: 12, R_Hand: 12,
  mixamorig_RightHand: 12, 'mixamorig:RightHand': 12,
  RightHandIndex1: 12, RightHandIndex2: 12, RightHandIndex3: 12,
  RightHandThumb1: 12, RightHandThumb2: 12,
  // 13 UpperLeg.L
  'UpperLeg.L': 13, LeftUpLeg: 13, LeftUpperLeg: 13, L_UpperLeg: 13,
  mixamorig_LeftUpLeg: 13, 'mixamorig:LeftUpLeg': 13,
  // 14 LowerLeg.L
  'LowerLeg.L': 14, LeftLeg: 14, LeftLowerLeg: 14, L_LowerLeg: 14,
  mixamorig_LeftLeg: 14, 'mixamorig:LeftLeg': 14,
  // 15 Foot.L
  'Foot.L': 15, LeftFoot: 15, L_Foot: 15, LeftToeBase: 15, LeftToes: 15,
  mixamorig_LeftFoot: 15, 'mixamorig:LeftFoot': 15,
  // 16 UpperLeg.R
  'UpperLeg.R': 16, RightUpLeg: 16, RightUpperLeg: 16, R_UpperLeg: 16,
  mixamorig_RightUpLeg: 16, 'mixamorig:RightUpLeg': 16,
  // 17 LowerLeg.R
  'LowerLeg.R': 17, RightLeg: 17, RightLowerLeg: 17, R_LowerLeg: 17,
  mixamorig_RightLeg: 17, 'mixamorig:RightLeg': 17,
  // 18 Foot.R
  'Foot.R': 18, RightFoot: 18, R_Foot: 18, RightToeBase: 18, RightToes: 18,
  mixamorig_RightFoot: 18, 'mixamorig:RightFoot': 18,
};

// Babylon packs 4 uint8 bone indices into a single float — unpack with round().
function unpackBoneIdx(f) { return Math.round(f); }

// ── Envelope auto-weighting ───────────────────────────────────────────────────

/**
 * Squared distance from point P to line segment AB.
 * Returns 0 when A === B.
 */
function pointToSegmentDistSq(px, py, pz, ax, ay, az, bx, by, bz) {
  const dx = bx - ax, dy = by - ay, dz = bz - az;
  const lenSq = dx * dx + dy * dy + dz * dz;
  let cx, cy, cz;
  if (lenSq < 1e-12) {
    cx = ax; cy = ay; cz = az;
  } else {
    const t = Math.max(0, Math.min(1,
      ((px - ax) * dx + (py - ay) * dy + (pz - az) * dz) / lenSq));
    cx = ax + t * dx; cy = ay + t * dy; cz = az + t * dz;
  }
  const ex = px - cx, ey = py - cy, ez = pz - cz;
  return ex * ex + ey * ey + ez * ez;
}

/**
 * Generate envelope-based skin weights when no usable skeleton is present.
 * Each bone owns a capsule (its segment from parent to child joint); vertex
 * weight = Gaussian(distance_to_capsule_axis, sigma[bone]).
 * Top-4 weights are kept and normalised.
 */
function envelopeWeight(positions, H) {
  const worldPos = boneWorldPositions(H);
  const vCount   = positions.length / 3;
  const N        = BONE_NAMES.length; // 19

  // Per-bone sigma (radial falloff) proportional to limb thickness
  const sigma = [
    H * 0.10,  // 0  Hips
    H * 0.08,  // 1  Spine
    H * 0.08,  // 2  Chest
    H * 0.06,  // 3  Neck
    H * 0.10,  // 4  Head
    H * 0.06,  // 5  Shoulder.L
    H * 0.06,  // 6  UpperArm.L
    H * 0.05,  // 7  LowerArm.L
    H * 0.05,  // 8  Hand.L
    H * 0.06,  // 9  Shoulder.R
    H * 0.06,  // 10 UpperArm.R
    H * 0.05,  // 11 LowerArm.R
    H * 0.05,  // 12 Hand.R
    H * 0.09,  // 13 UpperLeg.L
    H * 0.07,  // 14 LowerLeg.L
    H * 0.06,  // 15 Foot.L
    H * 0.09,  // 16 UpperLeg.R
    H * 0.07,  // 17 LowerLeg.R
    H * 0.06,  // 18 Foot.R
  ];

  const skinIndices = new Uint16Array(vCount * 4);
  const skinWeights = new Float32Array(vCount * 4);
  const w = new Float32Array(N);

  for (let v = 0; v < vCount; v++) {
    const px = positions[v * 3], py = positions[v * 3 + 1], pz = positions[v * 3 + 2];

    for (let b = 0; b < N; b++) {
      const [bx, by, bz] = worldPos[b];
      const pi = BONE_PARENTS[b];
      let dSq;
      if (pi === -1) {
        const ex = px - bx, ey = py - by, ez = pz - bz;
        dSq = ex * ex + ey * ey + ez * ez;
      } else {
        const [ax, ay, az] = worldPos[pi];
        dSq = pointToSegmentDistSq(px, py, pz, ax, ay, az, bx, by, bz);
      }
      const s = sigma[b];
      w[b] = Math.exp(-dSq / (2 * s * s));
    }

    // Top-4 by weight
    const order = Array.from({ length: N }, (_, i) => i).sort((a, b) => w[b] - w[a]);
    let total = 0;
    for (let j = 0; j < 4; j++) total += w[order[j]];
    const inv = total > 0 ? 1 / total : 0;

    for (let j = 0; j < 4; j++) {
      skinIndices[v * 4 + j] = order[j];
      skinWeights[v * 4 + j] = w[order[j]] * inv;
    }
  }

  return { skinIndices, skinWeights };
}

// ── Skeleton remap ────────────────────────────────────────────────────────────

/**
 * Remap existing GLB skin weights to our 19-bone index space.
 * @param {number} vCount
 * @param {Float32Array} matIdxArr - Babylon packed float bone indices
 * @param {Float32Array} matWtArr  - skin weights
 * @param {number[]} origToOur    - origBoneIdx → ourBoneIdx (or -1)
 * @returns {{ skinIndices: Uint16Array, skinWeights: Float32Array }}
 */
function remapSkinWeights(vCount, matIdxArr, matWtArr, origToOur) {
  const skinIndices = new Uint16Array(vCount * 4);
  const skinWeights = new Float32Array(vCount * 4);

  for (let v = 0; v < vCount; v++) {
    const accum = new Map();
    for (let j = 0; j < 4; j++) {
      const origIdx = unpackBoneIdx(matIdxArr[v * 4 + j]);
      const wt      = matWtArr[v * 4 + j];
      if (wt <= 0) continue;
      const our = origToOur[origIdx] ?? -1;
      if (our < 0) continue;
      accum.set(our, (accum.get(our) ?? 0) + wt);
    }

    const sorted = Array.from(accum.entries()).sort((a, b) => b[1] - a[1]).slice(0, 4);
    const total  = sorted.reduce((s, [, wt]) => s + wt, 0);
    const inv    = total > 0 ? 1 / total : 0;

    for (let j = 0; j < 4; j++) {
      if (j < sorted.length) {
        skinIndices[v * 4 + j] = sorted[j][0];
        skinWeights[v * 4 + j] = sorted[j][1] * inv;
      } else {
        skinIndices[v * 4 + j] = 0;
        skinWeights[v * 4 + j] = 0;
      }
    }
  }

  return { skinIndices, skinWeights };
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Load an arbitrary GLB (Buffer or base64 data URL), normalise to targetHeight
 * (feet at Y=0), and return mesh data ready for buildRiggedFromGLB().
 *
 * @param {Buffer|string} source       - raw GLB bytes or data URL
 * @param {number}        targetHeight - desired character height in metres
 * @returns {Promise<{
 *   positions:   Float32Array,
 *   normals:     Float32Array|null,
 *   uvs:         Float32Array|null,
 *   skinIndices: Uint16Array,
 *   skinWeights: Float32Array,
 *   indices:     Uint32Array,
 *   height:      number,
 *   albedoColor: [number,number,number]|null,
 * }>}
 */
export async function loadImportedGLB(source, targetHeight = 1.75) {
  const dataUrl = typeof source === 'string'
    ? source
    : `data:model/gltf-binary;base64,${source.toString('base64')}`;

  const engine = new NullEngine();
  const scene  = new Scene(engine);

  let result;
  try {
    result = await SceneLoader.ImportMeshAsync('', '', dataUrl, scene, null, '.glb');
  } catch (err) {
    engine.dispose();
    throw new Error(`Failed to parse GLB: ${err.message}`);
  }

  // Pick the largest mesh (by vertex count) that has real geometry
  let mainMesh = null;
  for (const mesh of result.meshes) {
    if (!mesh.isEnabled()) continue;
    const vc = mesh.getTotalVertices();
    if (vc < 10) continue;
    if (!mainMesh || vc > mainMesh.getTotalVertices()) mainMesh = mesh;
  }

  if (!mainMesh) {
    engine.dispose();
    throw new Error('No usable mesh found in the GLB file.');
  }

  // ── Extract geometry ──────────────────────────────────────────────────────

  const posArr  = mainMesh.getVerticesData('position');
  const normArr = mainMesh.getVerticesData('normal');
  const uvArr   = mainMesh.getVerticesData('uv');
  const idxArr  = mainMesh.getIndices();

  if (!posArr || !idxArr) {
    engine.dispose();
    throw new Error('GLB mesh is missing position or index data.');
  }

  const positions = new Float32Array(posArr);
  const vCount    = positions.length / 3;

  // ── Normalise height ──────────────────────────────────────────────────────

  let minY = Infinity, maxY = -Infinity;
  for (let i = 0; i < vCount; i++) {
    const y = positions[i * 3 + 1];
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  }
  const origH  = maxY - minY;
  const scale  = origH > 1e-4 ? targetHeight / origH : 1;

  for (let i = 0; i < vCount; i++) {
    positions[i * 3]      *= scale;
    positions[i * 3 + 1]   = (positions[i * 3 + 1] - minY) * scale;
    positions[i * 3 + 2]  *= scale;
  }

  // ── Try to extract a base colour from the material ────────────────────────

  let albedoColor = null;
  const mat = mainMesh.material;
  if (mat) {
    const c = mat.albedoColor ?? mat.diffuseColor ?? null;
    if (c) albedoColor = [c.r, c.g, c.b];
  }

  // ── Skin weighting ────────────────────────────────────────────────────────

  let skinIndices, skinWeights;
  const skeleton = mainMesh.skeleton;

  if (skeleton) {
    const origNames  = skeleton.bones.map(b => b.name);
    const origToOur  = origNames.map(n => NAME_TO_BONE_IDX[n] ?? -1);
    const mappedCount = origToOur.filter(i => i >= 0).length;

    const matIdxArr = mainMesh.getVerticesData('matricesIndices');
    const matWtArr  = mainMesh.getVerticesData('matricesWeights');

    if (matIdxArr && matWtArr && mappedCount >= 4) {
      console.log(`[importer] Remapping ${mappedCount}/${origNames.length} bones from existing skeleton.`);
      ({ skinIndices, skinWeights } = remapSkinWeights(vCount, matIdxArr, matWtArr, origToOur));
    } else {
      console.log('[importer] Skeleton present but insufficient bone mapping — using envelope weighting.');
      ({ skinIndices, skinWeights } = envelopeWeight(positions, targetHeight));
    }
  } else {
    console.log('[importer] No skeleton found — applying envelope-based auto-weighting.');
    ({ skinIndices, skinWeights } = envelopeWeight(positions, targetHeight));
  }

  engine.dispose();

  return {
    positions,
    normals:     normArr ? new Float32Array(normArr) : null,
    uvs:         uvArr   ? new Float32Array(uvArr)   : null,
    skinIndices,
    skinWeights,
    indices:     new Uint32Array(idxArr),
    height:      targetHeight,
    albedoColor,
  };
}
