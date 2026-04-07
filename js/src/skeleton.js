/**
 * 19-bone skeleton hierarchy using BABYLON.Bone/Skeleton.
 * Port of generators/humanoid/gltf_pipeline/skeleton.py
 */

import { Skeleton, Bone, Matrix } from '@babylonjs/core';

export const BONE_NAMES = [
  'Hips',                                              // 0  — root
  'Spine', 'Chest', 'Neck', 'Head',                   // 1-4
  'Shoulder.L', 'UpperArm.L', 'LowerArm.L', 'Hand.L', // 5-8
  'Shoulder.R', 'UpperArm.R', 'LowerArm.R', 'Hand.R', // 9-12
  'UpperLeg.L', 'LowerLeg.L', 'Foot.L',               // 13-15
  'UpperLeg.R', 'LowerLeg.R', 'Foot.R',               // 16-18
];

export const BONE_PARENTS = [-1,0,1,2,3,2,5,6,7,2,9,10,11,0,13,14,0,16,17];

/**
 * Return world positions for each bone proportional to height H.
 * @param {number} H - character height in metres
 * @returns {Array<[number,number,number]>} array of [x,y,z] per bone
 */
export function boneWorldPositions(H) {
  return [
    // Spine/head chain
    [0.0,          0.0,          H * 0.52],  // 0  Hips
    [0.0,          0.0,          H * 0.60],  // 1  Spine
    [0.0,          0.0,          H * 0.68],  // 2  Chest
    [0.0,          0.0,          H * 0.82],  // 3  Neck
    [0.0,          0.0,          H * 0.87],  // 4  Head
    // Left arm chain
    [+H * 0.08,    0.0,          H * 0.72],  // 5  Shoulder.L
    [+H * 0.14,    0.0,          H * 0.70],  // 6  UpperArm.L
    [+H * 0.14,    0.0,          H * 0.53],  // 7  LowerArm.L
    [+H * 0.14,    0.0,          H * 0.38],  // 8  Hand.L
    // Right arm chain
    [-H * 0.08,    0.0,          H * 0.72],  // 9  Shoulder.R
    [-H * 0.14,    0.0,          H * 0.70],  // 10 UpperArm.R
    [-H * 0.14,    0.0,          H * 0.53],  // 11 LowerArm.R
    [-H * 0.14,    0.0,          H * 0.38],  // 12 Hand.R
    // Left leg chain
    [+H * 0.09,    0.0,          H * 0.50],  // 13 UpperLeg.L
    [+H * 0.09,    0.0,          H * 0.27],  // 14 LowerLeg.L
    [+H * 0.09,    H * 0.08,     H * 0.03],  // 15 Foot.L
    // Right leg chain
    [-H * 0.09,    0.0,          H * 0.50],  // 16 UpperLeg.R
    [-H * 0.09,    0.0,          H * 0.27],  // 17 LowerLeg.R
    [-H * 0.09,    H * 0.08,     H * 0.03],  // 18 Foot.R
  ];
}

/**
 * Build a BABYLON.Skeleton with 19 bones at rest positions proportional to H.
 * @param {number} H - character height in metres
 * @param {BABYLON.Scene} scene - Babylon scene the skeleton belongs to
 * @returns {BABYLON.Skeleton}
 */
export function buildSkeleton(H, scene) {
  const worldPos = boneWorldPositions(H);
  const skeleton = new Skeleton('Skeleton', 'Skeleton', scene);

  // Create all bones
  const bones = BONE_NAMES.map((name, i) => {
    const parentIdx = BONE_PARENTS[i];
    const parentBone = parentIdx === -1 ? null : bones[parentIdx];
    const [wx, wy, wz] = worldPos[i];

    let lx, ly, lz;
    if (parentIdx === -1) {
      lx = wx; ly = wy; lz = wz;
    } else {
      const [px, py, pz] = worldPos[parentIdx];
      lx = wx - px; ly = wy - py; lz = wz - pz;
    }

    const localMatrix = Matrix.Translation(lx, ly, lz);
    return new Bone(name, skeleton, parentBone, localMatrix);
  });

  return skeleton;
}
