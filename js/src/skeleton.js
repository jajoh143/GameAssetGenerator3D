/**
 * 19-bone skeleton hierarchy using THREE.Bone/Skeleton.
 * Port of generators/humanoid/gltf_pipeline/skeleton.py
 */

import * as THREE from 'three';

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
    // [x, y=height, z=depth] — Y-up convention
    // Spine/head chain
    [0.0,          H * 0.52,  0.0],          // 0  Hips
    [0.0,          H * 0.60,  0.0],          // 1  Spine
    [0.0,          H * 0.68,  0.0],          // 2  Chest
    [0.0,          H * 0.82,  0.0],          // 3  Neck
    [0.0,          H * 0.87,  0.0],          // 4  Head
    // Left arm chain
    [+H * 0.08,    H * 0.72,  0.0],          // 5  Shoulder.L
    [+H * 0.14,    H * 0.70,  0.0],          // 6  UpperArm.L
    [+H * 0.14,    H * 0.53,  0.0],          // 7  LowerArm.L
    [+H * 0.14,    H * 0.38,  0.0],          // 8  Hand.L
    // Right arm chain
    [-H * 0.08,    H * 0.72,  0.0],          // 9  Shoulder.R
    [-H * 0.14,    H * 0.70,  0.0],          // 10 UpperArm.R
    [-H * 0.14,    H * 0.53,  0.0],          // 11 LowerArm.R
    [-H * 0.14,    H * 0.38,  0.0],          // 12 Hand.R
    // Left leg chain
    [+H * 0.09,    H * 0.50,  0.0],          // 13 UpperLeg.L
    [+H * 0.09,    H * 0.27,  0.0],          // 14 LowerLeg.L
    [+H * 0.09,    H * 0.03,  H * 0.08],     // 15 Foot.L
    // Right leg chain
    [-H * 0.09,    H * 0.50,  0.0],          // 16 UpperLeg.R
    [-H * 0.09,    H * 0.27,  0.0],          // 17 LowerLeg.R
    [-H * 0.09,    H * 0.03,  H * 0.08],     // 18 Foot.R
  ];
}

/**
 * Build a THREE.Skeleton with 19 bones at rest positions proportional to H.
 * @param {number} H - character height in metres
 * @returns {THREE.Skeleton}
 */
export function buildSkeleton(H) {
  const worldPos = boneWorldPositions(H);

  // Create all bones
  const bones = BONE_NAMES.map((name, i) => {
    const bone = new THREE.Bone();
    bone.name = name;
    return bone;
  });

  // Set local positions and wire up parent/child hierarchy
  for (let i = 0; i < bones.length; i++) {
    const parentIdx = BONE_PARENTS[i];
    const [wx, wy, wz] = worldPos[i];

    if (parentIdx === -1) {
      // Root bone: local position == world position
      bones[i].position.set(wx, wy, wz);
    } else {
      // Local position = world position minus parent world position
      const [px, py, pz] = worldPos[parentIdx];
      bones[i].position.set(wx - px, wy - py, wz - pz);
      bones[parentIdx].add(bones[i]);
    }
  }

  return new THREE.Skeleton(bones);
}
