/**
 * Procedural brick wall generator.
 * Creates a wall segment with individual brick meshes and mortar gaps.
 */

import { MeshBuilder } from '@babylonjs/core/Meshes/meshBuilder.js';
import { Mesh } from '@babylonjs/core/Meshes/mesh.js';
import { Vector3 } from '@babylonjs/core/Maths/math.vector.js';
import { Color3 } from '@babylonjs/core/Maths/math.color.js';
import { createBrickMaterial, createMortarMaterial } from '../utils/materials.js';

const WALL_DEFAULTS = {
  width: 4.0,        // meters
  height: 3.0,       // meters
  depth: 0.2,        // wall thickness
  brickWidth: 0.22,
  brickHeight: 0.07,
  mortarGap: 0.01,
};

/**
 * Create a brick wall segment.
 * @param {Scene} scene
 * @param {Object} [options]
 * @returns {Mesh} root mesh
 */
export function create(scene, options = {}) {
  const cfg = { ...WALL_DEFAULTS, ...options };
  const { width, height, depth, brickWidth, brickHeight, mortarGap } = cfg;

  // Mortar backing — a single plane behind all bricks
  const mortar = MeshBuilder.CreateBox('wall_mortar', {
    width,
    height,
    depth: depth * 0.8,
  }, scene);
  mortar.position = new Vector3(0, height / 2, 0);
  mortar.material = createMortarMaterial(scene);

  // Brick material with slight color variation
  const brickMat = createBrickMaterial(scene);

  // Lay bricks row by row
  const bricks = [];
  const stepX = brickWidth + mortarGap;
  const stepY = brickHeight + mortarGap;
  const cols = Math.floor(width / stepX);
  const rows = Math.floor(height / stepY);

  for (let row = 0; row < rows; row++) {
    // Alternate rows offset by half a brick
    const offset = (row % 2 === 0) ? 0 : stepX / 2;
    const y = mortarGap + brickHeight / 2 + row * stepY;

    for (let col = 0; col < cols; col++) {
      const x = -width / 2 + stepX / 2 + col * stepX + offset;

      // Skip bricks that would extend past the wall edge
      if (x - brickWidth / 2 < -width / 2 || x + brickWidth / 2 > width / 2) continue;

      const brick = MeshBuilder.CreateBox(`brick_${row}_${col}`, {
        width: brickWidth,
        height: brickHeight,
        depth: depth,
      }, scene);
      brick.position = new Vector3(x, y, 0);

      // Slight random color variation per brick
      const variation = 0.9 + Math.random() * 0.2;
      const bMat = brickMat.clone(`brick_mat_${row}_${col}`);
      bMat.albedoColor = new Color3(
        0.55 * variation,
        0.22 * variation,
        0.15 * variation
      );
      brick.material = bMat;
      bricks.push(brick);
    }
  }

  // Merge all bricks into one mesh for performance
  const merged = Mesh.MergeMeshes(bricks, true, true, undefined, false, true);
  if (merged) {
    merged.name = 'brick_wall_bricks';
  }

  // Parent everything under a root
  const root = new Mesh('brick_wall', scene);
  mortar.parent = root;
  if (merged) merged.parent = root;

  return root;
}
