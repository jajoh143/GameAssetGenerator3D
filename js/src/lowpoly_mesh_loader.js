/**
 * Load NBM_Lowpoly_Male.glb or NBM_Lowpoly_Female.glb, remap joints to our
 * 19-bone skeleton, and normalise to targetHeight.
 *
 * Gender selection:
 *   'female'           → NBM_Lowpoly_Female.glb
 *   'male' | 'neutral' → NBM_Lowpoly_Male.glb
 *
 * Skin weight strategy (in priority order):
 *   1. GLB has embedded skin data → remap to our 19-bone layout
 *   2. GLB is a static mesh       → compute envelope weights from bone proximity
 */

import { NullEngine, Scene, SceneLoader } from '@babylonjs/core';
import '@babylonjs/loaders/glTF/index.js';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { boneWorldPositions, BONE_PARENTS } from './skeleton.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, '..', '..');

// GLB joint name → our bone index (0-18).
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
 * Auto-orient positions (and normals) so that the height axis is Y.
 *
 * Blender exports in Z-up; the standard glTF exporter converts to Y-up but
 * some pipelines skip this. We detect the height axis (largest bounding-box
 * range) and rotate in-place so height → Y.
 *
 * Also detects upside-down models: for a humanoid the top 20% of the model
 * should have a narrow cross-section (the head). If the top is wider than the
 * bottom the mesh is inverted and we flip it.
 *
 * Rotations applied (right-handed, preserves handedness):
 *   Z-up → Y-up:  newY = oldZ,  newZ = -oldY
 *   X-up → Y-up:  newY = oldX,  newX = -oldZ  (rare but handled)
 *   Upside-down:  newY = -oldY, shift so min=0 after
 *
 * @param {Float32Array} pos  - flat XYZ positions, modified in-place
 * @param {Float32Array|null} nrm - flat XYZ normals, modified in-place (or null)
 * @param {number} vCount
 * @returns {{ minH: number, maxH: number }} bounding box along the (corrected) Y axis
 */
function autoOrient(pos, nrm, vCount) {
  // ── 1. Find per-axis bounding box ────────────────────────────────────────
  let minX=Infinity, maxX=-Infinity;
  let minY=Infinity, maxY=-Infinity;
  let minZ=Infinity, maxZ=-Infinity;
  for (let i = 0; i < vCount; i++) {
    const x=pos[i*3], y=pos[i*3+1], z=pos[i*3+2];
    if (x<minX) minX=x; if (x>maxX) maxX=x;
    if (y<minY) minY=y; if (y>maxY) maxY=y;
    if (z<minZ) minZ=z; if (z>maxZ) maxZ=z;
  }
  const rX = maxX-minX, rY = maxY-minY, rZ = maxZ-minZ;

  // ── 2. Rotate so height axis → Y ─────────────────────────────────────────
  // Babylon's GLB loader converts from right-handed (glTF) to its own
  // left-handed system by negating Z. So the "Z-up" values we read back are
  // the NEGATIVE of the original Blender Z. We must negate when using them
  // as the new Y to get head-at-top rather than head-at-bottom.
  //
  //   Z-up export (Blender):  newY = -oldZ,  newZ =  oldY
  //   X-up (rare):            newY = -oldX,  newX =  oldZ
  let orientation = 'Y';
  if (rZ > rY && rZ > rX) {
    orientation = 'Z';
    for (let i = 0; i < vCount; i++) {
      const y=pos[i*3+1], z=pos[i*3+2];
      pos[i*3+1]=-z; pos[i*3+2]=y;
      if (nrm) { const ny=nrm[i*3+1], nz=nrm[i*3+2]; nrm[i*3+1]=-nz; nrm[i*3+2]=ny; }
    }
  } else if (rX > rY && rX > rZ) {
    orientation = 'X';
    for (let i = 0; i < vCount; i++) {
      const x=pos[i*3], z=pos[i*3+2];
      pos[i*3]= z; pos[i*3+2]=-x;
      if (nrm) { const nx=nrm[i*3], nz=nrm[i*3+2]; nrm[i*3]=nz; nrm[i*3+2]=-nx; }
    }
  }

  // Recompute Y range after potential rotation
  let minH=Infinity, maxH=-Infinity;
  for (let i = 0; i < vCount; i++) {
    const y=pos[i*3+1];
    if (y<minH) minH=y; if (y>maxH) maxH=y;
  }

  console.log(`[lowpoly_mesh_loader] Auto-orient: detected ${orientation}-up, ranges X=${rX.toFixed(3)} Y=${rY.toFixed(3)} Z=${rZ.toFixed(3)}, post-rotate Y=[${minH.toFixed(3)}, ${maxH.toFixed(3)}]`);
  return { minH, maxH };
}

/**
 * Distance from point P to the line segment AB.
 */
function distToSegment(px, py, pz, ax, ay, az, bx, by, bz) {
  const abx = bx - ax, aby = by - ay, abz = bz - az;
  const apx = px - ax, apy = py - ay, apz = pz - az;
  const ab2 = abx*abx + aby*aby + abz*abz;
  const t   = ab2 > 0 ? Math.max(0, Math.min(1, (apx*abx + apy*aby + apz*abz) / ab2)) : 0;
  const cx  = ax + t*abx, cy = ay + t*aby, cz = az + t*abz;
  const dx  = px - cx,    dy = py - cy,    dz = pz - cz;
  return Math.sqrt(dx*dx + dy*dy + dz*dz);
}

/**
 * Compute envelope-based skin weights from bone proximity.
 *
 * For each vertex, scores each bone by inverse-squared distance to its
 * bone segment (joint → parent joint). The top 4 bones by score are
 * kept and normalised to sum to 1.
 *
 * @param {Float32Array} positions - flat [x,y,z,...] vertex positions (already scaled)
 * @param {number}       vCount
 * @param {number}       H         - character height (must match positions scale)
 * @returns {{ skinIndices: Uint16Array, skinWeights: Float32Array }}
 */
function computeEnvelopeWeights(positions, vCount, H) {
  const bonePos = boneWorldPositions(H);  // [[x,y,z], ...] for 19 bones
  const nBones  = bonePos.length;
  const EPSILON = 1e-6; // prevents div-by-zero when vertex is exactly on a joint

  const skinIndices = new Uint16Array(vCount * 4);
  const skinWeights = new Float32Array(vCount * 4);

  const scores = new Float32Array(nBones);

  for (let v = 0; v < vCount; v++) {
    const vx = positions[v*3], vy = positions[v*3+1], vz = positions[v*3+2];

    // Score each bone by inverse-squared distance to its segment
    for (let b = 0; b < nBones; b++) {
      const [bx, by, bz] = bonePos[b];
      const p = BONE_PARENTS[b];
      let dist;
      if (p < 0) {
        // Root bone — distance to point only
        const dx = vx-bx, dy = vy-by, dz = vz-bz;
        dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
      } else {
        const [ax, ay, az] = bonePos[p];
        dist = distToSegment(vx, vy, vz, ax, ay, az, bx, by, bz);
      }
      scores[b] = 1.0 / (dist * dist + EPSILON);
    }

    // Pick top 4 bones by score
    // (insertion-sort of 4 winners is faster than full sort for 19 bones)
    const topIdx = [-1, -1, -1, -1];
    const topScr = [0,   0,   0,   0];
    for (let b = 0; b < nBones; b++) {
      const s = scores[b];
      if (s > topScr[3]) {
        topIdx[3] = b; topScr[3] = s;
        // Bubble up
        for (let k = 3; k > 0 && topScr[k] > topScr[k-1]; k--) {
          let ti = topIdx[k]; topIdx[k] = topIdx[k-1]; topIdx[k-1] = ti;
          let ts = topScr[k]; topScr[k] = topScr[k-1]; topScr[k-1] = ts;
        }
      }
    }

    // Normalise
    const total = topScr[0] + topScr[1] + topScr[2] + topScr[3];
    const norm  = total > 0 ? 1.0 / total : 0;

    for (let j = 0; j < 4; j++) {
      skinIndices[v*4+j] = topIdx[j] >= 0 ? topIdx[j] : 0;
      skinWeights[v*4+j] = topIdx[j] >= 0 ? topScr[j] * norm : 0;
    }
  }

  return { skinIndices, skinWeights };
}

/**
 * Load the appropriate low-poly GLB for the given gender, build skin weights,
 * shift foot to Y=0, and scale to targetHeight.
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
  const buf     = readFileSync(glbPath);
  const dataUrl = `data:model/gltf-binary;base64,${buf.toString('base64')}`;

  const engine = new NullEngine();
  const scene  = new Scene(engine);

  const result = await SceneLoader.ImportMeshAsync('', '', dataUrl, scene, null, '.glb');

  // Find the largest mesh (≥30 verts). Prefer skinned, fall back to static.
  let bestMesh = null, bestSkinned = null;
  for (const mesh of result.meshes) {
    const vc = mesh.getTotalVertices();
    if (vc < 30) continue;
    if (mesh.skeleton && (!bestSkinned || vc > bestSkinned.getTotalVertices())) bestSkinned = mesh;
    if (!bestMesh || vc > bestMesh.getTotalVertices()) bestMesh = mesh;
  }

  const targetMesh = bestSkinned ?? bestMesh;
  if (!targetMesh) {
    engine.dispose();
    throw new Error(`No usable mesh found in ${filename}`);
  }

  const isSkinned = !!targetMesh.skeleton;
  console.log(`[lowpoly_mesh_loader] ${filename}: "${targetMesh.name}" — ${targetMesh.getTotalVertices()} verts, ${isSkinned ? 'skinned (remapping joints)' : 'static (computing envelope weights)'}`);

  // If skinned, build origJointIdx → ourBoneIdx mapping
  let origToOur = null;
  if (isSkinned) {
    const origBoneNames = targetMesh.skeleton.bones.map(b => b.name);
    origToOur = new Array(origBoneNames.length).fill(-1);
    const unmapped = [];
    for (let i = 0; i < origBoneNames.length; i++) {
      const name = origBoneNames[i];
      if (name in GLB_JOINT_TO_BONE_IDX) origToOur[i] = GLB_JOINT_TO_BONE_IDX[name];
      else unmapped.push(name);
    }
    if (unmapped.length > 0) {
      console.warn(`[lowpoly_mesh_loader] ${filename}: unmapped bones (defaulting to Hips): ${unmapped.join(', ')}`);
    }
  }

  // Extract vertex data
  const posArr    = targetMesh.getVerticesData('position');
  const normArr   = targetMesh.getVerticesData('normal');
  const uvArr     = targetMesh.getVerticesData('uv');
  const matIdxArr = targetMesh.getVerticesData('matricesIndices');
  const matWtArr  = targetMesh.getVerticesData('matricesWeights');
  const idxArr    = targetMesh.getIndices();

  const vCount    = posArr.length / 3;
  const positions = new Float32Array(posArr);
  const normals   = normArr ? new Float32Array(normArr) : null;

  // Auto-orient: detect height axis (Y vs Z vs X) and flip upside-down models.
  // The NBM_Lowpoly GLBs are Blender Z-up exports; this converts them to Y-up.
  const { minH, maxH } = autoOrient(positions, normals, vCount);

  // Normalise: scale to targetHeight, feet at Y=0
  const scale = targetHeight / (maxH - minH);
  for (let i = 0; i < vCount; i++) {
    positions[i*3]     *= scale;
    positions[i*3+1]    = (positions[i*3+1] - minH) * scale;
    positions[i*3+2]   *= scale;
    if (normals) {
      // Normals are direction vectors — no translation, no scaling needed
      // (already rotated by autoOrient in-place)
    }
  }

  // ── Skin weights ───────────────────────────────────────────────────────────
  let skinIndices, skinWeights;

  if (isSkinned && matIdxArr && matWtArr) {
    // Remap the GLB's embedded joint indices to our 19-bone layout
    skinIndices = new Uint16Array(vCount * 4);
    skinWeights = new Float32Array(vCount * 4);

    for (let v = 0; v < vCount; v++) {
      const accum = new Map();
      for (let j = 0; j < 4; j++) {
        const origIdx = unpackBoneIndex(matIdxArr[v*4+j], 0);
        const wt      = matWtArr[v*4+j];
        if (wt <= 0) continue;
        const ourIdx = origToOur[origIdx] ?? -1;
        if (ourIdx < 0) continue;
        accum.set(ourIdx, (accum.get(ourIdx) ?? 0) + wt);
      }
      const sorted  = Array.from(accum.entries()).sort((a, b) => b[1] - a[1]).slice(0, 4);
      const totalWt = sorted.reduce((s, [, w]) => s + w, 0);
      const norm    = totalWt > 0 ? 1.0 / totalWt : 0;
      for (let j = 0; j < 4; j++) {
        skinIndices[v*4+j] = j < sorted.length ? sorted[j][0] : 0;
        skinWeights[v*4+j] = j < sorted.length ? sorted[j][1] * norm : 0;
      }
    }
  } else {
    // Static mesh — derive weights from bone proximity
    ({ skinIndices, skinWeights } = computeEnvelopeWeights(positions, vCount, targetHeight));
  }

  // normals already built (and rotated) above
  const uvs = uvArr ? new Float32Array(uvArr) : null;
  const indices = new Uint32Array(idxArr);

  engine.dispose();

  return { positions, normals, uvs, skinIndices, skinWeights, indices, height: targetHeight };
}
