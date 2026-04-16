/**
 * Procedural leather hat generator.
 * Creates a cowboy/biker-style leather hat with crown and brim.
 */

import { MeshBuilder } from '@babylonjs/core/Meshes/meshBuilder.js';
import { Mesh } from '@babylonjs/core/Meshes/mesh.js';
import { Vector3 } from '@babylonjs/core/Maths/math.vector.js';
import { Color3 } from '@babylonjs/core/Maths/math.color.js';
import { createLeatherMaterial, createMetalMaterial } from '../utils/materials.js';
import { createLathe } from '../utils/geometry.js';

/**
 * Create a leather hat.
 * @param {Scene} scene
 * @param {Object} [options]
 * @returns {Mesh}
 */
export function create(scene, options = {}) {
  const root = new Mesh('leather_hat', scene);
  const leather = createLeatherMaterial(scene, 'hat_leather');
  const metal = createMetalMaterial(scene, 'hat_metal');

  // Crown — lathe profile (dome shape)
  const crownProfile = [
    [0.00, 0.00],   // center bottom
    [0.08, 0.00],   // base edge
    [0.085, 0.005],
    [0.085, 0.06],  // straight sides
    [0.082, 0.08],  // slight taper
    [0.075, 0.10],
    [0.060, 0.115],
    [0.040, 0.12],  // top curve
    [0.020, 0.118], // pinch at top (cowboy hat dip)
    [0.000, 0.115],
  ];

  const crown = createLathe('hat_crown', crownProfile, scene, 14);
  crown.material = leather;
  crown.parent = root;

  // Brim — flat disc with slight droop at edges
  const brimProfile = [
    [0.07, 0.00],   // inner edge (where crown meets brim)
    [0.10, 0.002],
    [0.13, 0.000],
    [0.15, -0.008], // slight droop
    [0.16, -0.015],
    [0.16, -0.020],
    [0.155, -0.020],
    [0.145, -0.013],
    [0.12, -0.003],
    [0.09, 0.000],
    [0.07, -0.003],
  ];

  const brim = createLathe('hat_brim', brimProfile, scene, 14);
  brim.material = leather;
  brim.parent = root;

  // Hat band — thin cylinder/torus around the base of the crown
  const band = MeshBuilder.CreateTorus('hat_band', {
    diameter: 0.17,
    thickness: 0.012,
    tessellation: 14,
  }, scene);
  band.position = new Vector3(0, 0.015, 0);
  band.scaling = new Vector3(1, 0.4, 1); // flatten to a band
  band.material = metal;
  band.parent = root;

  // Small buckle on the band (front)
  const buckle = MeshBuilder.CreateBox('hat_buckle', {
    width: 0.018,
    height: 0.012,
    depth: 0.005,
  }, scene);
  buckle.position = new Vector3(0, 0.015, -0.088);
  buckle.material = metal;
  buckle.parent = root;

  return root;
}
