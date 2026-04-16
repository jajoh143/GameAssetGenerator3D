/**
 * Bar scene composer.
 * Places all individual assets into a coherent queer bar layout.
 *
 * Layout (top-down, Z+ = "back" wall, X+ = right):
 *
 *   +-------------------------------------------+
 *   |  [back wall / shelves / bottles]           |  Z = +4
 *   |  ========= BAR COUNTER =========          |
 *   |   [register] [cups]                        |
 *   |                                            |
 *   |  [posters]     [open floor]    [posters]   |
 *   |                                            |
 *   |           [hat/sunglasses on shelf]        |
 *   |                                            |
 *   |  [bathroom door]       [entrance door]     |  Z = -4
 *   +-------------------------------------------+
 *     X = -3                              X = +3
 */

import { Mesh } from '@babylonjs/core/Meshes/mesh.js';
import { Vector3 } from '@babylonjs/core/Maths/math.vector.js';

import { create as createBrickWall } from './assets/brick_wall.js';
import { create as createBarCounter } from './assets/bar_counter.js';
import { create as createBottles } from './assets/bottles.js';
import { create as createCups } from './assets/cups.js';
import { create as createPridePosters } from './assets/pride_posters.js';
import { create as createLeatherHat } from './assets/leather_hat.js';
import { create as createAviatorSunglasses } from './assets/aviator_sunglasses.js';
import { create as createCashRegister } from './assets/cash_register.js';
import { create as createDoors } from './assets/doors.js';
import { create as createBathroom } from './assets/bathroom.js';

/**
 * Compose the full queer bar scene.
 * @param {Scene} scene
 * @param {Object} [options]
 * @returns {Mesh} root node
 */
export function create(scene, options = {}) {
  const root = new Mesh('queer_bar', scene);

  // --- Walls ---
  // Back wall
  const backWall = createBrickWall(scene, { width: 6, height: 3 });
  backWall.position = new Vector3(0, 0, 4);
  backWall.parent = root;

  // Left wall
  const leftWall = createBrickWall(scene, { width: 8, height: 3 });
  leftWall.rotation = new Vector3(0, Math.PI / 2, 0);
  leftWall.position = new Vector3(-3, 0, 0);
  leftWall.parent = root;

  // Right wall
  const rightWall = createBrickWall(scene, { width: 8, height: 3 });
  rightWall.rotation = new Vector3(0, -Math.PI / 2, 0);
  rightWall.position = new Vector3(3, 0, 0);
  rightWall.parent = root;

  // Front wall (with gap for entrance door)
  const frontWallLeft = createBrickWall(scene, { width: 2.5, height: 3 });
  frontWallLeft.position = new Vector3(-1.75, 0, -4);
  frontWallLeft.parent = root;

  const frontWallRight = createBrickWall(scene, { width: 2.5, height: 3 });
  frontWallRight.position = new Vector3(1.75, 0, -4);
  frontWallRight.parent = root;

  // --- Bar counter ---
  const bar = createBarCounter(scene, { width: 4, variant: 'l_shape' });
  bar.position = new Vector3(0, 0, 2.5);
  bar.parent = root;

  // --- Bottles on back shelf (4 types) ---
  const bottleSet = createBottles(scene);
  bottleSet.position = new Vector3(0, 1.3, 3.5);
  bottleSet.parent = root;

  // Second row of bottles
  const bottleSet2 = createBottles(scene);
  bottleSet2.position = new Vector3(0.5, 0.9, 3.5);
  bottleSet2.parent = root;

  // --- Cups on the bar ---
  const cups = createCups(scene);
  cups.position = new Vector3(1.0, 1.15, 2.5);
  cups.parent = root;

  // --- Cash register on bar ---
  const register = createCashRegister(scene);
  register.position = new Vector3(-1.2, 1.15, 2.5);
  register.parent = root;

  // --- Pride posters on left wall ---
  const postersLeft = createPridePosters(scene);
  postersLeft.rotation = new Vector3(0, Math.PI / 2, 0);
  postersLeft.position = new Vector3(-2.95, 1.8, 1.0);
  postersLeft.parent = root;

  // --- More pride posters on right wall ---
  const postersRight = createPridePosters(scene, { variant: 'pan' });
  postersRight.rotation = new Vector3(0, -Math.PI / 2, 0);
  postersRight.position = new Vector3(2.95, 1.8, 0);
  postersRight.parent = root;

  const posterProgress = createPridePosters(scene, { variant: 'progress' });
  posterProgress.rotation = new Vector3(0, -Math.PI / 2, 0);
  posterProgress.position = new Vector3(2.95, 1.8, 1.5);
  posterProgress.parent = root;

  // --- Decorative items on a small shelf ---
  const hat = createLeatherHat(scene);
  hat.position = new Vector3(-1.5, 1.6, -2.0);
  hat.parent = root;

  const sunglasses = createAviatorSunglasses(scene);
  sunglasses.position = new Vector3(-1.2, 1.6, -2.0);
  sunglasses.parent = root;

  // --- Entrance door ---
  const entranceDoor = createDoors(scene, { variant: 'entrance' });
  entranceDoor.position = new Vector3(0, 0, -4);
  entranceDoor.parent = root;

  // --- Bathroom area (left side, through a door) ---
  const bathroomDoor = createDoors(scene, { variant: 'bathroom' });
  bathroomDoor.rotation = new Vector3(0, Math.PI / 2, 0);
  bathroomDoor.position = new Vector3(-2.95, 0, -2.5);
  bathroomDoor.parent = root;

  // Bathroom items behind the bathroom door
  const bathroomItems = createBathroom(scene);
  bathroomItems.position = new Vector3(-4.5, 0, -2.5);
  bathroomItems.parent = root;

  return root;
}
