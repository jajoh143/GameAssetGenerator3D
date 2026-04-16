/**
 * Shared geometry helpers for procedural asset generation.
 */

import { MeshBuilder } from '@babylonjs/core/Meshes/meshBuilder.js';
import { Mesh } from '@babylonjs/core/Meshes/mesh.js';
import { Vector3 } from '@babylonjs/core/Maths/math.vector.js';
import { VertexData } from '@babylonjs/core/Meshes/mesh.vertexData.js';

/**
 * Create a lathe (surface of revolution) mesh from a 2D profile.
 * Profile is an array of [x, y] pairs where x = radius, y = height.
 * Revolves around the Y axis.
 *
 * @param {string} name
 * @param {Array<[number, number]>} profile - [radius, height] pairs from bottom to top
 * @param {Scene} scene
 * @param {number} segments - number of radial segments (default 12)
 * @returns {Mesh}
 */
export function createLathe(name, profile, scene, segments = 12) {
  const path = profile.map(([x, y]) => new Vector3(x, y, 0));
  return MeshBuilder.CreateLathe(name, {
    shape: path,
    tessellation: segments,
    sideOrientation: Mesh.DOUBLESIDE,
  }, scene);
}

/**
 * Create a simple box mesh.
 */
export function createBox(name, width, height, depth, scene) {
  return MeshBuilder.CreateBox(name, { width, height, depth }, scene);
}

/**
 * Create a cylinder mesh.
 */
export function createCylinder(name, height, diameterTop, diameterBottom, segments, scene) {
  return MeshBuilder.CreateCylinder(name, {
    height,
    diameterTop,
    diameterBottom,
    tessellation: segments || 12,
  }, scene);
}

/**
 * Create a sphere mesh.
 */
export function createSphere(name, diameter, segments, scene) {
  return MeshBuilder.CreateSphere(name, {
    diameter,
    segments: segments || 8,
  }, scene);
}

/**
 * Create a plane mesh (single-sided by default).
 */
export function createPlane(name, width, height, scene) {
  return MeshBuilder.CreatePlane(name, {
    width,
    height,
    sideOrientation: Mesh.DOUBLESIDE,
  }, scene);
}

/**
 * Create a torus mesh.
 */
export function createTorus(name, diameter, thickness, segments, scene) {
  return MeshBuilder.CreateTorus(name, {
    diameter,
    thickness,
    tessellation: segments || 16,
  }, scene);
}

/**
 * Create a disc (flat circle) mesh.
 */
export function createDisc(name, radius, segments, scene) {
  return MeshBuilder.CreateDisc(name, {
    radius,
    tessellation: segments || 12,
    sideOrientation: Mesh.DOUBLESIDE,
  }, scene);
}

/**
 * Merge multiple meshes into one, optionally disposing the originals.
 * @param {string} name
 * @param {Mesh[]} meshes
 * @param {Scene} scene
 * @param {boolean} disposeSource - dispose source meshes after merge (default true)
 * @returns {Mesh}
 */
export function mergeMeshes(name, meshes, scene, disposeSource = true) {
  const merged = Mesh.MergeMeshes(meshes, disposeSource, true, undefined, false, true);
  if (merged) {
    merged.name = name;
  }
  return merged;
}

/**
 * Set mesh position shorthand.
 */
export function setPosition(mesh, x, y, z) {
  mesh.position = new Vector3(x, y, z);
  return mesh;
}
