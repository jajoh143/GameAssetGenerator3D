/**
 * Procedural bathroom items generator.
 * Creates sink, mirror, soap dispenser, and toilet.
 */

import { MeshBuilder } from '@babylonjs/core/Meshes/meshBuilder.js';
import { Mesh } from '@babylonjs/core/Meshes/mesh.js';
import { Vector3 } from '@babylonjs/core/Maths/math.vector.js';
import {
  createPorcelainMaterial,
  createMirrorMaterial,
  createMetalMaterial,
  createColorMaterial,
} from '../utils/materials.js';
import { createLathe } from '../utils/geometry.js';

/**
 * Create bathroom items (all placed together, or a specific item).
 * @param {Scene} scene
 * @param {Object} [options]
 * @param {string} [options.variant] - 'sink'|'mirror'|'soap_dispenser'|'toilet' or omit for all
 * @returns {Mesh}
 */
export function create(scene, options = {}) {
  const variant = options.variant;

  const builders = {
    sink: createSink,
    mirror: createMirror,
    soap_dispenser: createSoapDispenser,
    toilet: createToilet,
  };

  if (variant && builders[variant]) {
    return builders[variant](scene);
  }

  // All items arranged in a row
  const root = new Mesh('bathroom', scene);

  const sink = createSink(scene);
  sink.position = new Vector3(-0.5, 0, 0);
  sink.parent = root;

  const mirror = createMirror(scene);
  mirror.position = new Vector3(-0.5, 1.4, 0.25);
  mirror.parent = root;

  const soap = createSoapDispenser(scene);
  soap.position = new Vector3(-0.2, 0.85, 0);
  soap.parent = root;

  const toilet = createToilet(scene);
  toilet.position = new Vector3(0.5, 0, 0);
  toilet.parent = root;

  return root;
}

function createSink(scene) {
  const root = new Mesh('sink', scene);
  const porcelain = createPorcelainMaterial(scene, 'sink_porcelain');
  const metal = createMetalMaterial(scene, 'sink_metal');

  // Pedestal — tapered cylinder
  const pedestal = MeshBuilder.CreateCylinder('sink_pedestal', {
    height: 0.7,
    diameterTop: 0.12,
    diameterBottom: 0.15,
    tessellation: 10,
  }, scene);
  pedestal.position = new Vector3(0, 0.35, 0);
  pedestal.material = porcelain;
  pedestal.parent = root;

  // Basin — lathe bowl on top
  const basinProfile = [
    [0.00, 0.00],
    [0.18, 0.00],
    [0.20, 0.01],
    [0.20, 0.04],
    [0.19, 0.04],
    [0.17, 0.01],
    [0.12, -0.04],
    [0.05, -0.06],
    [0.00, -0.065],
  ];
  const basin = createLathe('sink_basin', basinProfile, scene, 12);
  basin.position = new Vector3(0, 0.72, 0);
  basin.material = porcelain;
  basin.parent = root;

  // Faucet — vertical pipe + spout
  const faucetBase = MeshBuilder.CreateCylinder('sink_faucet_base', {
    height: 0.12,
    diameter: 0.02,
    tessellation: 8,
  }, scene);
  faucetBase.position = new Vector3(0, 0.82, -0.12);
  faucetBase.material = metal;
  faucetBase.parent = root;

  const faucetSpout = MeshBuilder.CreateCylinder('sink_faucet_spout', {
    height: 0.08,
    diameter: 0.015,
    tessellation: 8,
  }, scene);
  faucetSpout.rotation = new Vector3(Math.PI / 2 - 0.3, 0, 0);
  faucetSpout.position = new Vector3(0, 0.88, -0.08);
  faucetSpout.material = metal;
  faucetSpout.parent = root;

  // Handle knobs
  for (const side of [-1, 1]) {
    const knob = MeshBuilder.CreateSphere(`sink_knob_${side > 0 ? 'R' : 'L'}`, {
      diameter: 0.02,
      segments: 6,
    }, scene);
    knob.position = new Vector3(side * 0.06, 0.78, -0.12);
    knob.material = metal;
    knob.parent = root;
  }

  return root;
}

function createMirror(scene) {
  const root = new Mesh('mirror', scene);
  const mirrorMat = createMirrorMaterial(scene, 'mirror_surface');
  const metal = createMetalMaterial(scene, 'mirror_frame');

  const mirrorW = 0.45;
  const mirrorH = 0.55;
  const frameW = 0.02;

  // Mirror surface
  const surface = MeshBuilder.CreatePlane('mirror_surface', {
    width: mirrorW,
    height: mirrorH,
    sideOrientation: Mesh.DOUBLESIDE,
  }, scene);
  surface.material = mirrorMat;
  surface.parent = root;

  // Frame — 4 bars
  const frameDepth = 0.015;

  const topBar = MeshBuilder.CreateBox('mirror_frame_top', {
    width: mirrorW + frameW * 2, height: frameW, depth: frameDepth,
  }, scene);
  topBar.position = new Vector3(0, mirrorH / 2 + frameW / 2, 0);
  topBar.material = metal;
  topBar.parent = root;

  const bottomBar = MeshBuilder.CreateBox('mirror_frame_bottom', {
    width: mirrorW + frameW * 2, height: frameW, depth: frameDepth,
  }, scene);
  bottomBar.position = new Vector3(0, -mirrorH / 2 - frameW / 2, 0);
  bottomBar.material = metal;
  bottomBar.parent = root;

  for (const side of [-1, 1]) {
    const sideBar = MeshBuilder.CreateBox(`mirror_frame_${side > 0 ? 'R' : 'L'}`, {
      width: frameW, height: mirrorH, depth: frameDepth,
    }, scene);
    sideBar.position = new Vector3(side * (mirrorW / 2 + frameW / 2), 0, 0);
    sideBar.material = metal;
    sideBar.parent = root;
  }

  return root;
}

function createSoapDispenser(scene) {
  const root = new Mesh('soap_dispenser', scene);
  const bodyMat = createColorMaterial(scene, 'soap_body', 0.85, 0.85, 0.82);
  const metal = createMetalMaterial(scene, 'soap_metal');

  // Body — rounded cylinder
  const body = MeshBuilder.CreateCylinder('soap_body', {
    height: 0.12,
    diameterTop: 0.04,
    diameterBottom: 0.045,
    tessellation: 10,
  }, scene);
  body.position = new Vector3(0, 0.06, 0);
  body.material = bodyMat;
  body.parent = root;

  // Cap
  const cap = MeshBuilder.CreateCylinder('soap_cap', {
    height: 0.015,
    diameter: 0.045,
    tessellation: 10,
  }, scene);
  cap.position = new Vector3(0, 0.1275, 0);
  cap.material = metal;
  cap.parent = root;

  // Pump nozzle — horizontal cylinder
  const pump = MeshBuilder.CreateCylinder('soap_pump', {
    height: 0.04,
    diameter: 0.008,
    tessellation: 6,
  }, scene);
  pump.rotation = new Vector3(Math.PI / 2, 0, 0);
  pump.position = new Vector3(0, 0.135, -0.025);
  pump.material = metal;
  pump.parent = root;

  // Pump head (small sphere at end)
  const head = MeshBuilder.CreateSphere('soap_pump_head', {
    diameter: 0.012,
    segments: 4,
  }, scene);
  head.position = new Vector3(0, 0.135, -0.045);
  head.material = metal;
  head.parent = root;

  return root;
}

function createToilet(scene) {
  const root = new Mesh('toilet', scene);
  const porcelain = createPorcelainMaterial(scene, 'toilet_porcelain');
  const metal = createMetalMaterial(scene, 'toilet_metal');

  // Tank (back box)
  const tank = MeshBuilder.CreateBox('toilet_tank', {
    width: 0.36,
    height: 0.32,
    depth: 0.15,
  }, scene);
  tank.position = new Vector3(0, 0.50, 0.14);
  tank.material = porcelain;
  tank.parent = root;

  // Tank lid
  const lid = MeshBuilder.CreateBox('toilet_tank_lid', {
    width: 0.38,
    height: 0.025,
    depth: 0.16,
  }, scene);
  lid.position = new Vector3(0, 0.67, 0.14);
  lid.material = porcelain;
  lid.parent = root;

  // Flush handle
  const flushHandle = MeshBuilder.CreateCylinder('toilet_flush', {
    height: 0.06,
    diameter: 0.01,
    tessellation: 6,
  }, scene);
  flushHandle.rotation = new Vector3(0, 0, Math.PI / 2);
  flushHandle.position = new Vector3(-0.20, 0.62, 0.14);
  flushHandle.material = metal;
  flushHandle.parent = root;

  // Bowl base — tapered box
  const base = MeshBuilder.CreateBox('toilet_base', {
    width: 0.34,
    height: 0.34,
    depth: 0.22,
  }, scene);
  base.position = new Vector3(0, 0.17, 0.05);
  base.material = porcelain;
  base.parent = root;

  // Bowl — lathe shape on top of base
  const bowlProfile = [
    [0.00, 0.00],
    [0.16, 0.00],
    [0.17, 0.01],
    [0.17, 0.04],
    [0.16, 0.04],
    [0.14, 0.01],
    [0.10, -0.04],
    [0.04, -0.06],
    [0.00, -0.065],
  ];
  const bowl = createLathe('toilet_bowl', bowlProfile, scene, 10);
  bowl.position = new Vector3(0, 0.37, -0.08);
  bowl.material = porcelain;
  bowl.parent = root;

  // Seat — flattened torus
  const seat = MeshBuilder.CreateTorus('toilet_seat', {
    diameter: 0.32,
    thickness: 0.025,
    tessellation: 14,
  }, scene);
  seat.position = new Vector3(0, 0.39, -0.08);
  seat.scaling = new Vector3(1.0, 0.3, 1.15); // oval and flat
  seat.material = porcelain;
  seat.parent = root;

  return root;
}
