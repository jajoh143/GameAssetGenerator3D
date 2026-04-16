/**
 * Procedural cup/glass generator.
 * Variants: pint_glass, shot_glass, coffee_mug, martini.
 */

import { MeshBuilder } from '@babylonjs/core/Meshes/meshBuilder.js';
import { Mesh } from '@babylonjs/core/Meshes/mesh.js';
import { Vector3 } from '@babylonjs/core/Maths/math.vector.js';
import { Color3 } from '@babylonjs/core/Maths/math.color.js';
import { createGlassMaterial, createPorcelainMaterial } from '../utils/materials.js';
import { createLathe, createTorus, createCylinder } from '../utils/geometry.js';

// Lathe profiles: [radius, height]
const PROFILES = {
  pint_glass: [
    [0.00, 0.00], [0.03, 0.00], [0.030, 0.005],
    [0.028, 0.01], [0.028, 0.02], [0.032, 0.04],
    [0.033, 0.06], [0.036, 0.10], [0.040, 0.15],
    [0.040, 0.155], [0.038, 0.155], [0.035, 0.10],
    [0.031, 0.06], [0.030, 0.04], [0.026, 0.02],
    [0.026, 0.01], [0.00, 0.01],
  ],
  shot_glass: [
    [0.00, 0.00], [0.022, 0.00], [0.022, 0.005],
    [0.020, 0.008], [0.020, 0.01], [0.024, 0.03],
    [0.028, 0.06], [0.028, 0.065], [0.026, 0.065],
    [0.022, 0.03], [0.018, 0.01], [0.00, 0.01],
  ],
  coffee_mug: [
    [0.00, 0.00], [0.038, 0.00], [0.038, 0.005],
    [0.036, 0.01], [0.036, 0.09], [0.037, 0.095],
    [0.037, 0.10], [0.035, 0.10], [0.034, 0.095],
    [0.034, 0.01], [0.00, 0.01],
  ],
  martini: [
    [0.00, 0.00], [0.02, 0.00], [0.02, 0.005],
    [0.018, 0.008], [0.005, 0.04], [0.004, 0.05],
    [0.004, 0.06], [0.005, 0.065], [0.050, 0.12],
    [0.050, 0.125], [0.048, 0.12], [0.003, 0.068],
    [0.00, 0.065],
  ],
};

/**
 * Create cups (specific variant or all 4 side by side).
 * @param {Scene} scene
 * @param {Object} [options]
 * @returns {Mesh}
 */
export function create(scene, options = {}) {
  const variant = options.variant;

  if (variant && PROFILES[variant]) {
    return createCup(scene, variant, Vector3.Zero());
  }

  // All variants
  const root = new Mesh('cups', scene);
  const variants = Object.keys(PROFILES);
  const spacing = 0.1;
  const totalWidth = (variants.length - 1) * spacing;

  variants.forEach((v, i) => {
    const x = -totalWidth / 2 + i * spacing;
    const cup = createCup(scene, v, new Vector3(x, 0, 0));
    cup.parent = root;
  });

  return root;
}

function createCup(scene, variant, position) {
  const root = new Mesh(`cup_${variant}`, scene);
  root.position = position;

  const segments = 10;

  if (variant === 'coffee_mug') {
    // Porcelain mug body
    const body = createLathe(`mug_body`, PROFILES.coffee_mug, scene, segments);
    body.material = createPorcelainMaterial(scene, 'mug_porcelain');
    body.parent = root;

    // Handle — torus segment on the side
    const handle = createTorus('mug_handle', 0.04, 0.006, 12, scene);
    handle.scaling = new Vector3(1, 1.3, 0.8);
    handle.position = new Vector3(0.04, 0.05, 0);
    handle.material = body.material;
    handle.parent = root;
  } else {
    // Glass cups
    const body = createLathe(`${variant}_body`, PROFILES[variant], scene, segments);
    body.material = createGlassMaterial(scene, `${variant}_glassMat`, null, 0.25);
    body.parent = root;
  }

  return root;
}
