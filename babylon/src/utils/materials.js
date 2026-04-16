/**
 * PBR material factory functions for bar scene assets.
 */

import { PBRMaterial } from '@babylonjs/core/Materials/PBR/pbrMaterial.js';
import { Color3 } from '@babylonjs/core/Maths/math.color.js';

/**
 * Dark, worn wood — bar counter, shelves, door frames.
 */
export function createWoodMaterial(scene, name = 'wood') {
  const mat = new PBRMaterial(name, scene);
  mat.albedoColor = new Color3(0.35, 0.2, 0.1);
  mat.roughness = 0.75;
  mat.metallic = 0.0;
  return mat;
}

/**
 * Light pine wood — lighter furniture accents.
 */
export function createLightWoodMaterial(scene, name = 'lightWood') {
  const mat = new PBRMaterial(name, scene);
  mat.albedoColor = new Color3(0.65, 0.45, 0.25);
  mat.roughness = 0.7;
  mat.metallic = 0.0;
  return mat;
}

/**
 * Red/brown brick — walls.
 */
export function createBrickMaterial(scene, name = 'brick') {
  const mat = new PBRMaterial(name, scene);
  mat.albedoColor = new Color3(0.55, 0.22, 0.15);
  mat.roughness = 0.9;
  mat.metallic = 0.0;
  return mat;
}

/**
 * Light grey mortar — between bricks.
 */
export function createMortarMaterial(scene, name = 'mortar') {
  const mat = new PBRMaterial(name, scene);
  mat.albedoColor = new Color3(0.65, 0.62, 0.58);
  mat.roughness = 0.95;
  mat.metallic = 0.0;
  return mat;
}

/**
 * Transparent/tinted glass — bottles, windows.
 * @param {Color3} tint - glass color tint
 * @param {number} alpha - transparency (0 = invisible, 1 = opaque)
 */
export function createGlassMaterial(scene, name = 'glass', tint = null, alpha = 0.3) {
  const mat = new PBRMaterial(name, scene);
  mat.albedoColor = tint || new Color3(0.85, 0.9, 0.85);
  mat.roughness = 0.05;
  mat.metallic = 0.1;
  mat.alpha = alpha;
  mat.transparencyMode = 2; // ALPHA_BLEND
  mat.backFaceCulling = false;
  mat.twoSidedLighting = true;
  return mat;
}

/**
 * Coloured liquid — inside bottles.
 */
export function createLiquidMaterial(scene, name = 'liquid', color = null) {
  const mat = new PBRMaterial(name, scene);
  mat.albedoColor = color || new Color3(0.6, 0.3, 0.05);
  mat.roughness = 0.1;
  mat.metallic = 0.0;
  mat.alpha = 0.7;
  mat.transparencyMode = 2;
  mat.backFaceCulling = false;
  mat.twoSidedLighting = true;
  return mat;
}

/**
 * Brown leather — hat, seat upholstery.
 */
export function createLeatherMaterial(scene, name = 'leather') {
  const mat = new PBRMaterial(name, scene);
  mat.albedoColor = new Color3(0.3, 0.15, 0.07);
  mat.roughness = 0.6;
  mat.metallic = 0.0;
  return mat;
}

/**
 * Brushed/polished metal — taps, handles, register.
 */
export function createMetalMaterial(scene, name = 'metal') {
  const mat = new PBRMaterial(name, scene);
  mat.albedoColor = new Color3(0.7, 0.7, 0.72);
  mat.roughness = 0.35;
  mat.metallic = 0.85;
  return mat;
}

/**
 * Dark gunmetal — sunglasses frames, register body.
 */
export function createDarkMetalMaterial(scene, name = 'darkMetal') {
  const mat = new PBRMaterial(name, scene);
  mat.albedoColor = new Color3(0.15, 0.15, 0.17);
  mat.roughness = 0.3;
  mat.metallic = 0.9;
  return mat;
}

/**
 * Fabric / cloth — poster backing, upholstery.
 */
export function createFabricMaterial(scene, name = 'fabric', color = null) {
  const mat = new PBRMaterial(name, scene);
  mat.albedoColor = color || new Color3(0.8, 0.8, 0.75);
  mat.roughness = 0.9;
  mat.metallic = 0.0;
  return mat;
}

/**
 * White porcelain — bathroom fixtures.
 */
export function createPorcelainMaterial(scene, name = 'porcelain') {
  const mat = new PBRMaterial(name, scene);
  mat.albedoColor = new Color3(0.95, 0.95, 0.93);
  mat.roughness = 0.15;
  mat.metallic = 0.05;
  return mat;
}

/**
 * Reflective mirror surface.
 */
export function createMirrorMaterial(scene, name = 'mirror') {
  const mat = new PBRMaterial(name, scene);
  mat.albedoColor = new Color3(0.85, 0.88, 0.9);
  mat.roughness = 0.02;
  mat.metallic = 0.95;
  return mat;
}

/**
 * Generic flat color PBR.
 */
export function createColorMaterial(scene, name, r, g, b) {
  const mat = new PBRMaterial(name, scene);
  mat.albedoColor = new Color3(r, g, b);
  mat.roughness = 0.5;
  mat.metallic = 0.0;
  return mat;
}
