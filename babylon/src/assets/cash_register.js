/**
 * Procedural cash register generator.
 * Retro-style register with body, drawer, button grid, and display.
 */

import { MeshBuilder } from '@babylonjs/core/Meshes/meshBuilder.js';
import { Mesh } from '@babylonjs/core/Meshes/mesh.js';
import { Vector3 } from '@babylonjs/core/Maths/math.vector.js';
import { Color3 } from '@babylonjs/core/Maths/math.color.js';
import { createDarkMetalMaterial, createMetalMaterial, createColorMaterial } from '../utils/materials.js';

/**
 * Create a retro cash register.
 * @param {Scene} scene
 * @param {Object} [options]
 * @returns {Mesh}
 */
export function create(scene, options = {}) {
  const root = new Mesh('cash_register', scene);
  const darkMetal = createDarkMetalMaterial(scene, 'register_body');
  const shineMetal = createMetalMaterial(scene, 'register_chrome');

  // Main body — slightly tapered box
  const bodyW = 0.30;
  const bodyH = 0.20;
  const bodyD = 0.25;
  const body = MeshBuilder.CreateBox('register_body', {
    width: bodyW, height: bodyH, depth: bodyD,
  }, scene);
  body.position = new Vector3(0, bodyH / 2, 0);
  body.material = darkMetal;
  body.parent = root;

  // Cash drawer — slides out from the front bottom
  const drawerH = 0.05;
  const drawer = MeshBuilder.CreateBox('register_drawer', {
    width: bodyW * 0.9,
    height: drawerH,
    depth: bodyD * 0.6,
  }, scene);
  drawer.position = new Vector3(0, drawerH / 2, -bodyD * 0.05);
  drawer.material = shineMetal;
  drawer.parent = root;

  // Drawer handle
  const handle = MeshBuilder.CreateCylinder('register_drawer_handle', {
    height: bodyW * 0.5,
    diameter: 0.012,
    tessellation: 8,
  }, scene);
  handle.rotation = new Vector3(0, 0, Math.PI / 2);
  handle.position = new Vector3(0, drawerH + 0.006, -bodyD * 0.35);
  handle.material = shineMetal;
  handle.parent = root;

  // Display screen — angled panel on top-back
  const displayW = bodyW * 0.7;
  const displayH = 0.08;
  const display = MeshBuilder.CreateBox('register_display', {
    width: displayW, height: displayH, depth: 0.015,
  }, scene);
  display.rotation = new Vector3(-0.5, 0, 0); // tilt backward
  display.position = new Vector3(0, bodyH + displayH / 2 - 0.01, bodyD * 0.15);
  display.material = createColorMaterial(scene, 'register_screen', 0.1, 0.3, 0.1);
  display.parent = root;

  // Display frame
  const displayFrame = MeshBuilder.CreateBox('register_display_frame', {
    width: displayW + 0.01, height: displayH + 0.01, depth: 0.02,
  }, scene);
  displayFrame.rotation = display.rotation.clone();
  displayFrame.position = display.position.clone();
  displayFrame.position.z += 0.005;
  displayFrame.material = shineMetal;
  displayFrame.parent = root;

  // Button grid — 4x3 array of small cylinders on top surface
  const buttonRows = 4;
  const buttonCols = 3;
  const buttonSpacing = 0.03;
  const buttonR = 0.008;
  const gridStartX = -(buttonCols - 1) * buttonSpacing / 2;
  const gridStartZ = -(buttonRows - 1) * buttonSpacing / 2 - 0.02;

  const buttonColors = [
    new Color3(0.8, 0.8, 0.8),
    new Color3(0.9, 0.6, 0.2),
    new Color3(0.3, 0.7, 0.3),
    new Color3(0.8, 0.2, 0.2),
  ];

  for (let r = 0; r < buttonRows; r++) {
    for (let c = 0; c < buttonCols; c++) {
      const btn = MeshBuilder.CreateCylinder(`register_btn_${r}_${c}`, {
        height: 0.01,
        diameter: buttonR * 2,
        tessellation: 8,
      }, scene);
      btn.position = new Vector3(
        gridStartX + c * buttonSpacing,
        bodyH + 0.005,
        gridStartZ + r * buttonSpacing
      );
      const mat = createColorMaterial(
        scene, `btn_mat_${r}_${c}`,
        buttonColors[r].r, buttonColors[r].g, buttonColors[r].b
      );
      btn.material = mat;
      btn.parent = root;
    }
  }

  return root;
}
