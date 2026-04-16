/**
 * Procedural glass alcohol bottle generator.
 * Variants: whiskey, vodka, beer, wine.
 * Each uses a lathe profile with glass + liquid interior.
 */

import { MeshBuilder } from '@babylonjs/core/Meshes/meshBuilder.js';
import { Mesh } from '@babylonjs/core/Meshes/mesh.js';
import { Vector3 } from '@babylonjs/core/Maths/math.vector.js';
import { Color3 } from '@babylonjs/core/Maths/math.color.js';
import { createGlassMaterial, createLiquidMaterial } from '../utils/materials.js';
import { createLathe } from '../utils/geometry.js';

// Lathe profiles: [radius, height] from bottom to top
const PROFILES = {
  whiskey: [
    [0.00, 0.00], [0.04, 0.00], [0.04, 0.005],
    [0.038, 0.01], [0.038, 0.16], [0.035, 0.18],
    [0.015, 0.20], [0.012, 0.22], [0.012, 0.27],
    [0.014, 0.28], [0.012, 0.29], [0.00, 0.29],
  ],
  vodka: [
    [0.00, 0.00], [0.03, 0.00], [0.03, 0.005],
    [0.028, 0.01], [0.028, 0.22], [0.025, 0.24],
    [0.010, 0.26], [0.008, 0.28], [0.008, 0.32],
    [0.010, 0.33], [0.008, 0.34], [0.00, 0.34],
  ],
  beer: [
    [0.00, 0.00], [0.035, 0.00], [0.035, 0.005],
    [0.033, 0.01], [0.033, 0.14], [0.028, 0.16],
    [0.013, 0.17], [0.011, 0.18], [0.011, 0.22],
    [0.013, 0.225], [0.011, 0.23], [0.00, 0.23],
  ],
  wine: [
    [0.00, 0.00], [0.04, 0.00], [0.04, 0.005],
    [0.038, 0.01], [0.038, 0.10], [0.032, 0.14],
    [0.012, 0.17], [0.010, 0.19], [0.010, 0.28],
    [0.012, 0.285], [0.010, 0.29], [0.00, 0.29],
  ],
};

const LIQUID_COLORS = {
  whiskey: new Color3(0.6, 0.35, 0.05),
  vodka:   new Color3(0.8, 0.8, 0.82),
  beer:    new Color3(0.7, 0.5, 0.1),
  wine:    new Color3(0.4, 0.05, 0.1),
};

const GLASS_TINTS = {
  whiskey: new Color3(0.7, 0.85, 0.7),
  vodka:   new Color3(0.9, 0.92, 0.95),
  beer:    new Color3(0.4, 0.3, 0.15),
  wine:    new Color3(0.3, 0.4, 0.3),
};

/**
 * Create a bottle (or set of all 4 variants placed side by side).
 * @param {Scene} scene
 * @param {Object} [options]
 * @param {string} [options.variant] - 'whiskey'|'vodka'|'beer'|'wine' or omit for all 4
 * @returns {Mesh}
 */
export function create(scene, options = {}) {
  const variant = options.variant;

  if (variant && PROFILES[variant]) {
    return createBottle(scene, variant, Vector3.Zero());
  }

  // Create all 4 variants side by side
  const root = new Mesh('bottles', scene);
  const variants = Object.keys(PROFILES);
  const spacing = 0.1;
  const totalWidth = (variants.length - 1) * spacing;

  variants.forEach((v, i) => {
    const x = -totalWidth / 2 + i * spacing;
    const bottle = createBottle(scene, v, new Vector3(x, 0, 0));
    bottle.parent = root;
  });

  return root;
}

function createBottle(scene, variant, position) {
  const root = new Mesh(`bottle_${variant}`, scene);
  root.position = position;

  const profile = PROFILES[variant];
  const segments = 10;

  // Glass exterior
  const glass = createLathe(`${variant}_glass`, profile, scene, segments);
  glass.material = createGlassMaterial(
    scene, `${variant}_glassMat`, GLASS_TINTS[variant], 0.3
  );
  glass.parent = root;

  // Liquid interior — same profile but slightly smaller radius, lower fill
  const fillHeight = profile[profile.length - 4][1]; // fill to shoulder
  const liquidProfile = profile
    .filter(([, y]) => y <= fillHeight)
    .map(([r, y]) => [r * 0.85, y + 0.005]);

  if (liquidProfile.length >= 3) {
    // Close the top of the liquid
    const topR = liquidProfile[liquidProfile.length - 1][0];
    const topY = liquidProfile[liquidProfile.length - 1][1];
    liquidProfile.push([0, topY]);

    const liquid = createLathe(`${variant}_liquid`, liquidProfile, scene, segments);
    liquid.material = createLiquidMaterial(
      scene, `${variant}_liquidMat`, LIQUID_COLORS[variant]
    );
    liquid.parent = root;
  }

  return root;
}
