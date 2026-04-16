/**
 * Procedural wooden bar counter generator.
 * Creates a bar with a countertop, front panel, foot rail, and shelving back.
 */

import { MeshBuilder } from '@babylonjs/core/Meshes/meshBuilder.js';
import { Mesh } from '@babylonjs/core/Meshes/mesh.js';
import { Vector3 } from '@babylonjs/core/Maths/math.vector.js';
import { createWoodMaterial, createLightWoodMaterial, createMetalMaterial } from '../utils/materials.js';

const BAR_DEFAULTS = {
  width: 3.0,       // length of the bar
  depth: 0.7,       // front-to-back
  height: 1.1,      // counter height
  variant: 'straight', // 'straight' or 'l_shape'
};

/**
 * Create a wooden bar counter.
 * @param {Scene} scene
 * @param {Object} [options]
 * @returns {Mesh} root mesh
 */
export function create(scene, options = {}) {
  const cfg = { ...BAR_DEFAULTS, ...options };
  const { width, depth, height } = cfg;
  const variant = options.variant || cfg.variant;

  const root = new Mesh('bar_counter', scene);
  const darkWood = createWoodMaterial(scene, 'bar_darkWood');
  const lightWood = createLightWoodMaterial(scene, 'bar_lightWood');
  const metal = createMetalMaterial(scene, 'bar_metal');

  // Countertop — slightly wider than the body, thicker slab
  const topThick = 0.05;
  const topOverhang = 0.08;
  const top = MeshBuilder.CreateBox('bar_top', {
    width: width + topOverhang * 2,
    height: topThick,
    depth: depth + topOverhang,
  }, scene);
  top.position = new Vector3(0, height, 0);
  top.material = darkWood;
  top.parent = root;

  // Front panel
  const panelHeight = height - 0.15; // leave gap at bottom
  const front = MeshBuilder.CreateBox('bar_front', {
    width,
    height: panelHeight,
    depth: 0.04,
  }, scene);
  front.position = new Vector3(0, panelHeight / 2 + 0.05, -depth / 2);
  front.material = lightWood;
  front.parent = root;

  // Side panels (left and right)
  for (const side of [-1, 1]) {
    const panel = MeshBuilder.CreateBox(`bar_side_${side > 0 ? 'R' : 'L'}`, {
      width: 0.04,
      height: panelHeight,
      depth,
    }, scene);
    panel.position = new Vector3(side * width / 2, panelHeight / 2 + 0.05, 0);
    panel.material = lightWood;
    panel.parent = root;
  }

  // Foot rail — metal cylinder along the front base
  const rail = MeshBuilder.CreateCylinder('bar_footrail', {
    height: width * 0.9,
    diameter: 0.04,
    tessellation: 8,
  }, scene);
  rail.rotation = new Vector3(0, 0, Math.PI / 2);
  rail.position = new Vector3(0, 0.15, -depth / 2 - 0.06);
  rail.material = metal;
  rail.parent = root;

  // Back shelf — two horizontal shelves behind the bar
  const shelfDepth = 0.25;
  for (let i = 0; i < 2; i++) {
    const shelf = MeshBuilder.CreateBox(`bar_shelf_${i}`, {
      width: width * 0.9,
      height: 0.02,
      depth: shelfDepth,
    }, scene);
    shelf.position = new Vector3(0, 0.5 + i * 0.4, depth / 2 + shelfDepth / 2 + 0.1);
    shelf.material = darkWood;
    shelf.parent = root;
  }

  // Back panel (wall behind shelves)
  const backPanel = MeshBuilder.CreateBox('bar_back', {
    width: width * 0.9,
    height: height + 0.5,
    depth: 0.03,
  }, scene);
  backPanel.position = new Vector3(0, (height + 0.5) / 2, depth / 2 + shelfDepth + 0.12);
  backPanel.material = darkWood;
  backPanel.parent = root;

  // L-shape extension
  if (variant === 'l_shape') {
    const extLen = width * 0.4;
    const ext = MeshBuilder.CreateBox('bar_l_ext_top', {
      width: depth + topOverhang,
      height: topThick,
      depth: extLen,
    }, scene);
    ext.position = new Vector3(-width / 2 - depth / 2, height, -depth / 2 - extLen / 2);
    ext.material = darkWood;
    ext.parent = root;

    const extFront = MeshBuilder.CreateBox('bar_l_ext_front', {
      width: 0.04,
      height: panelHeight,
      depth: extLen,
    }, scene);
    extFront.position = new Vector3(-width / 2 - depth, panelHeight / 2 + 0.05, -depth / 2 - extLen / 2);
    extFront.material = lightWood;
    extFront.parent = root;
  }

  return root;
}
