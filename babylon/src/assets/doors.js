/**
 * Procedural door generator.
 * Variants: entrance (with window), interior, bathroom.
 */

import { MeshBuilder } from '@babylonjs/core/Meshes/meshBuilder.js';
import { Mesh } from '@babylonjs/core/Meshes/mesh.js';
import { Vector3 } from '@babylonjs/core/Maths/math.vector.js';
import { createWoodMaterial, createMetalMaterial, createGlassMaterial } from '../utils/materials.js';

const DOOR_DEFAULTS = {
  width: 0.9,
  height: 2.1,
  depth: 0.05,
  variant: 'interior', // 'entrance', 'interior', 'bathroom'
};

/**
 * Create a door with frame and handle.
 * @param {Scene} scene
 * @param {Object} [options]
 * @returns {Mesh} root mesh
 */
export function create(scene, options = {}) {
  const cfg = { ...DOOR_DEFAULTS, ...options };
  const variant = options.variant || cfg.variant;
  const { width, height, depth } = cfg;

  const root = new Mesh('door', scene);
  const wood = createWoodMaterial(scene, 'door_wood');
  const metal = createMetalMaterial(scene, 'door_metal');

  // Door frame
  const frameThick = 0.08;
  const frameDepth = depth + 0.02;

  // Top frame
  const topFrame = MeshBuilder.CreateBox('door_frame_top', {
    width: width + frameThick * 2,
    height: frameThick,
    depth: frameDepth,
  }, scene);
  topFrame.position = new Vector3(0, height + frameThick / 2, 0);
  topFrame.material = wood;
  topFrame.parent = root;

  // Side frames
  for (const side of [-1, 1]) {
    const sf = MeshBuilder.CreateBox(`door_frame_${side > 0 ? 'R' : 'L'}`, {
      width: frameThick,
      height: height,
      depth: frameDepth,
    }, scene);
    sf.position = new Vector3(side * (width / 2 + frameThick / 2), height / 2, 0);
    sf.material = wood;
    sf.parent = root;
  }

  // Door panel
  if (variant === 'entrance') {
    // Entrance door: solid bottom half + glass window top half
    const panelH = height * 0.55;
    const panel = MeshBuilder.CreateBox('door_panel', {
      width, height: panelH, depth,
    }, scene);
    panel.position = new Vector3(0, panelH / 2, 0);
    panel.material = wood;
    panel.parent = root;

    const windowH = height * 0.35;
    const windowW = width * 0.6;
    const glass = MeshBuilder.CreateBox('door_window', {
      width: windowW, height: windowH, depth: depth * 0.5,
    }, scene);
    glass.position = new Vector3(0, panelH + windowH / 2 + 0.05, 0);
    glass.material = createGlassMaterial(scene, 'door_glass', null, 0.25);
    glass.parent = root;

    // Window frame strips
    const wfTop = MeshBuilder.CreateBox('door_wf_top', {
      width: windowW + 0.02, height: 0.02, depth: depth,
    }, scene);
    wfTop.position = new Vector3(0, panelH + windowH + 0.06, 0);
    wfTop.material = wood;
    wfTop.parent = root;
  } else {
    // Interior / bathroom: solid panel with inset rectangles
    const panel = MeshBuilder.CreateBox('door_panel', {
      width, height, depth,
    }, scene);
    panel.position = new Vector3(0, height / 2, 0);
    panel.material = wood;
    panel.parent = root;

    // Decorative inset panels
    const insetW = width * 0.35;
    const insetH = height * 0.3;
    for (let i = 0; i < 2; i++) {
      const inset = MeshBuilder.CreateBox(`door_inset_${i}`, {
        width: insetW, height: insetH, depth: 0.008,
      }, scene);
      const y = height * 0.25 + i * (insetH + 0.15);
      inset.position = new Vector3(0, y, -depth / 2 - 0.004);
      inset.material = wood;
      inset.parent = root;
    }
  }

  // Door handle — cylinder + knob
  const handleSide = 0.3; // right side
  const handleY = height * 0.47;

  const handle = MeshBuilder.CreateCylinder('door_handle', {
    height: 0.12,
    diameter: 0.015,
    tessellation: 8,
  }, scene);
  handle.rotation = new Vector3(Math.PI / 2, 0, 0);
  handle.position = new Vector3(width * handleSide, handleY, -depth / 2 - 0.06);
  handle.material = metal;
  handle.parent = root;

  const knob = MeshBuilder.CreateSphere('door_knob', {
    diameter: 0.035,
    segments: 6,
  }, scene);
  knob.position = new Vector3(width * handleSide, handleY, -depth / 2 - 0.12);
  knob.material = metal;
  knob.parent = root;

  // Bathroom sign (small rectangle on door)
  if (variant === 'bathroom') {
    const sign = MeshBuilder.CreateBox('door_sign', {
      width: 0.15, height: 0.1, depth: 0.005,
    }, scene);
    sign.position = new Vector3(0, height * 0.75, -depth / 2 - 0.003);
    sign.material = metal;
    sign.parent = root;
  }

  return root;
}
