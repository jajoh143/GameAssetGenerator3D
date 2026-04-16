/**
 * Procedural pride poster generator.
 * Creates framed wall posters with pride flag stripes using vertex colors.
 * Variants: rainbow, trans, bi, pan, nonbinary, lesbian, progress.
 */

import { MeshBuilder } from '@babylonjs/core/Meshes/meshBuilder.js';
import { Mesh } from '@babylonjs/core/Meshes/mesh.js';
import { Vector3 } from '@babylonjs/core/Maths/math.vector.js';
import { Color3, Color4 } from '@babylonjs/core/Maths/math.color.js';
import { VertexData } from '@babylonjs/core/Meshes/mesh.vertexData.js';
import { PBRMaterial } from '@babylonjs/core/Materials/PBR/pbrMaterial.js';
import { createWoodMaterial, createDarkMetalMaterial } from '../utils/materials.js';

// Flag definitions: arrays of [r, g, b] stripe colors (top to bottom)
const FLAGS = {
  rainbow: [
    [0.89, 0.13, 0.11],  // red
    [1.00, 0.55, 0.00],  // orange
    [1.00, 0.93, 0.00],  // yellow
    [0.00, 0.50, 0.15],  // green
    [0.00, 0.30, 0.77],  // blue
    [0.45, 0.16, 0.51],  // violet
  ],
  trans: [
    [0.36, 0.81, 0.98],  // light blue
    [0.96, 0.66, 0.72],  // pink
    [1.00, 1.00, 1.00],  // white
    [0.96, 0.66, 0.72],  // pink
    [0.36, 0.81, 0.98],  // light blue
  ],
  bi: [
    [0.84, 0.00, 0.44],  // magenta
    [0.84, 0.00, 0.44],  // magenta
    [0.61, 0.31, 0.64],  // lavender
    [0.00, 0.22, 0.66],  // blue
    [0.00, 0.22, 0.66],  // blue
  ],
  pan: [
    [1.00, 0.13, 0.55],  // pink
    [1.00, 0.13, 0.55],  // pink
    [1.00, 0.85, 0.00],  // yellow
    [1.00, 0.85, 0.00],  // yellow
    [0.13, 0.69, 0.93],  // blue
    [0.13, 0.69, 0.93],  // blue
  ],
  nonbinary: [
    [0.98, 0.95, 0.20],  // yellow
    [1.00, 1.00, 1.00],  // white
    [0.61, 0.35, 0.82],  // purple
    [0.18, 0.18, 0.18],  // black
  ],
  lesbian: [
    [0.83, 0.18, 0.00],  // dark orange
    [0.99, 0.61, 0.35],  // orange
    [1.00, 1.00, 1.00],  // white
    [0.84, 0.39, 0.64],  // pink
    [0.64, 0.03, 0.35],  // dark pink
  ],
  progress: [
    [0.89, 0.13, 0.11],  // red
    [1.00, 0.55, 0.00],  // orange
    [1.00, 0.93, 0.00],  // yellow
    [0.00, 0.50, 0.15],  // green
    [0.00, 0.30, 0.77],  // blue
    [0.45, 0.16, 0.51],  // violet
  ],
};

const POSTER_DEFAULTS = {
  width: 0.4,
  height: 0.28,
  frameWidth: 0.015,
};

/**
 * Create pride poster(s).
 * @param {Scene} scene
 * @param {Object} [options]
 * @param {string} [options.variant] - flag name or omit for a set of 3 (rainbow, trans, bi)
 * @returns {Mesh}
 */
export function create(scene, options = {}) {
  const variant = options.variant;

  if (variant && FLAGS[variant]) {
    return createPoster(scene, variant, Vector3.Zero());
  }

  // Default: create a row of 3 posters
  const root = new Mesh('pride_posters', scene);
  const set = ['rainbow', 'trans', 'bi'];
  const spacing = 0.55;

  set.forEach((flag, i) => {
    const x = (i - 1) * spacing;
    const poster = createPoster(scene, flag, new Vector3(x, 0, 0));
    poster.parent = root;
  });

  return root;
}

function createPoster(scene, flagName, position) {
  const root = new Mesh(`poster_${flagName}`, scene);
  root.position = position;

  const { width, height, frameWidth } = POSTER_DEFAULTS;
  const stripes = FLAGS[flagName];
  const stripeCount = stripes.length;

  // Build flag face as a custom mesh with vertex colors
  const flagMesh = buildFlagMesh(scene, flagName, width, height, stripes);
  flagMesh.parent = root;

  // Frame — 4 bars around the flag
  const frameMat = createWoodMaterial(scene, `frame_${flagName}`);
  const frameDepth = 0.02;

  // Top bar
  const topBar = MeshBuilder.CreateBox(`frame_top_${flagName}`, {
    width: width + frameWidth * 2,
    height: frameWidth,
    depth: frameDepth,
  }, scene);
  topBar.position = new Vector3(0, height / 2 + frameWidth / 2, 0);
  topBar.material = frameMat;
  topBar.parent = root;

  // Bottom bar
  const bottomBar = MeshBuilder.CreateBox(`frame_bottom_${flagName}`, {
    width: width + frameWidth * 2,
    height: frameWidth,
    depth: frameDepth,
  }, scene);
  bottomBar.position = new Vector3(0, -height / 2 - frameWidth / 2, 0);
  bottomBar.material = frameMat;
  bottomBar.parent = root;

  // Side bars
  for (const side of [-1, 1]) {
    const sideBar = MeshBuilder.CreateBox(`frame_side_${flagName}_${side}`, {
      width: frameWidth,
      height: height,
      depth: frameDepth,
    }, scene);
    sideBar.position = new Vector3(side * (width / 2 + frameWidth / 2), 0, 0);
    sideBar.material = frameMat;
    sideBar.parent = root;
  }

  return root;
}

/**
 * Build a flat plane mesh with horizontal stripe vertex colors.
 */
function buildFlagMesh(scene, name, width, height, stripes) {
  const stripeCount = stripes.length;
  const stripeH = height / stripeCount;

  // Build 2 triangles per stripe
  const positions = [];
  const indices = [];
  const normals = [];
  const colors = [];

  for (let i = 0; i < stripeCount; i++) {
    const y0 = height / 2 - (i + 1) * stripeH;
    const y1 = height / 2 - i * stripeH;
    const [r, g, b] = stripes[i];
    const baseIdx = i * 4;

    // 4 vertices per stripe (quad)
    positions.push(
      -width / 2, y0, 0,   // bottom-left
       width / 2, y0, 0,   // bottom-right
       width / 2, y1, 0,   // top-right
      -width / 2, y1, 0,   // top-left
    );

    // 2 triangles
    indices.push(
      baseIdx, baseIdx + 1, baseIdx + 2,
      baseIdx, baseIdx + 2, baseIdx + 3,
    );

    // All 4 verts same color
    for (let v = 0; v < 4; v++) {
      normals.push(0, 0, -1);
      colors.push(r, g, b, 1);
    }
  }

  const mesh = new Mesh(`flag_${name}`, scene);
  const vertexData = new VertexData();
  vertexData.positions = positions;
  vertexData.indices = indices;
  vertexData.normals = normals;
  vertexData.colors = colors;
  vertexData.applyToMesh(mesh);

  // Material that shows vertex colors
  const mat = new PBRMaterial(`flag_mat_${name}`, scene);
  mat.roughness = 0.85;
  mat.metallic = 0.0;
  mat.useVertexColors = true;
  // Set albedo white so vertex colors come through
  mat.albedoColor = new Color3(1, 1, 1);
  mesh.material = mat;

  return mesh;
}
