/**
 * Procedural aviator sunglasses generator.
 * Creates classic teardrop-lens aviator frames with bridge and temples.
 */

import { MeshBuilder } from '@babylonjs/core/Meshes/meshBuilder.js';
import { Mesh } from '@babylonjs/core/Meshes/mesh.js';
import { Vector3 } from '@babylonjs/core/Maths/math.vector.js';
import { Color3 } from '@babylonjs/core/Maths/math.color.js';
import { createDarkMetalMaterial, createGlassMaterial } from '../utils/materials.js';

/**
 * Create aviator sunglasses.
 * @param {Scene} scene
 * @param {Object} [options]
 * @returns {Mesh}
 */
export function create(scene, options = {}) {
  const root = new Mesh('aviator_sunglasses', scene);
  const frameMat = createDarkMetalMaterial(scene, 'aviator_frame');

  // Tinted reflective lens material
  const lensMat = createGlassMaterial(
    scene, 'aviator_lens',
    new Color3(0.15, 0.15, 0.12), // dark tint
    0.6
  );
  lensMat.metallic = 0.4;
  lensMat.roughness = 0.05;

  const lensSpacing = 0.035; // half-distance between lens centers

  // Create left and right lens assemblies
  for (const side of [-1, 1]) {
    const cx = side * lensSpacing;

    // Teardrop lens — approximate with a sphere scaled to teardrop shape
    const lens = MeshBuilder.CreateSphere(`lens_${side > 0 ? 'R' : 'L'}`, {
      diameter: 0.04,
      segments: 8,
    }, scene);
    lens.scaling = new Vector3(1.0, 1.2, 0.1); // flatten + elongate vertically
    lens.position = new Vector3(cx, 0, 0);
    lens.material = lensMat;
    lens.parent = root;

    // Lens frame ring — torus around each lens
    const ring = MeshBuilder.CreateTorus(`frame_ring_${side > 0 ? 'R' : 'L'}`, {
      diameter: 0.042,
      thickness: 0.003,
      tessellation: 16,
    }, scene);
    ring.scaling = new Vector3(1.0, 1.2, 0.3);
    ring.position = new Vector3(cx, 0, 0);
    ring.material = frameMat;
    ring.parent = root;

    // Temple arm (goes back toward the ears)
    const temple = MeshBuilder.CreateCylinder(`temple_${side > 0 ? 'R' : 'L'}`, {
      height: 0.10,
      diameter: 0.003,
      tessellation: 6,
    }, scene);
    temple.rotation = new Vector3(Math.PI / 2 + 0.15, 0, 0); // angle back and slightly down
    temple.position = new Vector3(cx + side * 0.02, 0.005, 0.05);
    temple.material = frameMat;
    temple.parent = root;

    // Temple tip (curved end)
    const tip = MeshBuilder.CreateCylinder(`temple_tip_${side > 0 ? 'R' : 'L'}`, {
      height: 0.02,
      diameter: 0.004,
      tessellation: 6,
    }, scene);
    tip.rotation = new Vector3(Math.PI / 2 + 0.6, 0, 0);
    tip.position = new Vector3(cx + side * 0.022, -0.01, 0.098);
    tip.material = frameMat;
    tip.parent = root;
  }

  // Bridge — bar connecting the two lenses across the nose
  const bridge = MeshBuilder.CreateCylinder('bridge', {
    height: lensSpacing * 2,
    diameter: 0.003,
    tessellation: 6,
  }, scene);
  bridge.rotation = new Vector3(0, 0, Math.PI / 2);
  bridge.position = new Vector3(0, 0.012, -0.002);
  bridge.material = frameMat;
  bridge.parent = root;

  // Nose pads — small spheres
  for (const side of [-1, 1]) {
    const pad = MeshBuilder.CreateSphere(`nose_pad_${side > 0 ? 'R' : 'L'}`, {
      diameter: 0.005,
      segments: 4,
    }, scene);
    pad.position = new Vector3(side * 0.01, -0.005, -0.005);
    pad.material = frameMat;
    pad.parent = root;
  }

  return root;
}
