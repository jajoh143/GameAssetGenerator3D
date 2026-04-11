/**
 * 19-bone skeleton hierarchy using BABYLON.Bone/Skeleton.
 * Port of generators/humanoid/gltf_pipeline/skeleton.py
 */

import { Skeleton, Bone, Matrix, TransformNode } from '@babylonjs/core';

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
  // [x, y, z] — Y = height (up), Z = forward depth, X = lateral
  return [
    // Spine/head chain
    [0.0,          H * 0.52, 0.0        ],  // 0  Hips
    [0.0,          H * 0.60, 0.0        ],  // 1  Spine
    [0.0,          H * 0.68, 0.0        ],  // 2  Chest
    [0.0,          H * 0.82, 0.0        ],  // 3  Neck
    [0.0,          H * 0.87, 0.0        ],  // 4  Head
    // Left arm chain
    [+H * 0.08,    H * 0.72, 0.0        ],  // 5  Shoulder.L
    [+H * 0.14,    H * 0.70, 0.0        ],  // 6  UpperArm.L
    [+H * 0.14,    H * 0.53, 0.0        ],  // 7  LowerArm.L
    [+H * 0.14,    H * 0.38, 0.0        ],  // 8  Hand.L
    // Right arm chain
    [-H * 0.08,    H * 0.72, 0.0        ],  // 9  Shoulder.R
    [-H * 0.14,    H * 0.70, 0.0        ],  // 10 UpperArm.R
    [-H * 0.14,    H * 0.53, 0.0        ],  // 11 LowerArm.R
    [-H * 0.14,    H * 0.38, 0.0        ],  // 12 Hand.R
    // Left leg chain
    [+H * 0.09,    H * 0.50, 0.0        ],  // 13 UpperLeg.L
    [+H * 0.09,    H * 0.27, 0.0        ],  // 14 LowerLeg.L
    [+H * 0.09,    H * 0.03, H * 0.08  ],  // 15 Foot.L (Z = toe forward)
    // Right leg chain
    [-H * 0.09,    H * 0.50, 0.0        ],  // 16 UpperLeg.R
    [-H * 0.09,    H * 0.27, 0.0        ],  // 17 LowerLeg.R
    [-H * 0.09,    H * 0.03, H * 0.08  ],  // 18 Foot.R (Z = toe forward)
  ];
}

/**
 * Build a BABYLON.Skeleton with 19 bones at rest positions proportional to H.
 * @param {number} H - character height in metres
 * @param {BABYLON.Scene} scene - Babylon scene the skeleton belongs to
 * @returns {BABYLON.Skeleton}
 */
/**
 * Build a BABYLON.Skeleton with 19 bones at rest positions proportional to H.
 * Each bone is linked to a TransformNode so the GLTF exporter can resolve the
 * bone's local transform and export animation tracks correctly.
 *
 * @param {number} H - character height in metres
 * @param {BABYLON.Scene} scene
 * @returns {{ skeleton: BABYLON.Skeleton, boneNodes: Map<string, BABYLON.TransformNode> }}
 */
export function buildSkeleton(H, scene) {
  const worldPos = boneWorldPositions(H);
  const skeleton  = new Skeleton('Skeleton', 'Skeleton', scene);

  const bones = [];
  const nodes = [];                // parallel array: TransformNode per bone
  const boneNodes = new Map();     // boneName → TransformNode

  for (let i = 0; i < BONE_NAMES.length; i++) {
    const name      = BONE_NAMES[i];
    const parentIdx = BONE_PARENTS[i];
    const parentBone = parentIdx === -1 ? null : bones[parentIdx];
    const [wx, wy, wz] = worldPos[i];

    // Local offset from parent (or world pos for root)
    let lx, ly, lz;
    if (parentIdx === -1) {
      lx = wx; ly = wy; lz = wz;
    } else {
      const [px, py, pz] = worldPos[parentIdx];
      lx = wx - px; ly = wy - py; lz = wz - pz;
    }

    // Bone with rest-pose matrix
    const localMatrix = Matrix.Translation(lx, ly, lz);
    const bone = new Bone(name, skeleton, parentBone, localMatrix);
    bones.push(bone);

    // TransformNode linked to this bone — required for GLTF export
    const tn = new TransformNode(name, scene);
    if (parentIdx !== -1) tn.parent = nodes[parentIdx];
    tn.position.set(lx, ly, lz);
    bone.linkTransformNode(tn);

    nodes.push(tn);
    boneNodes.set(name, tn);
  }

  return { skeleton, boneNodes };
}
