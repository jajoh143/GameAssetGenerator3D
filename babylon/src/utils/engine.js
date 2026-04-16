/**
 * Headless Babylon.js engine and scene factory.
 * Uses NullEngine so no GPU/browser is needed.
 */

import { NullEngine } from '@babylonjs/core/Engines/nullEngine.js';
import { Scene } from '@babylonjs/core/scene.js';
import { Vector3 } from '@babylonjs/core/Maths/math.vector.js';
import { HemisphericLight } from '@babylonjs/core/Lights/hemisphericLight.js';
import { Color3 } from '@babylonjs/core/Maths/math.color.js';

let _engine = null;

/**
 * Get or create the shared NullEngine instance.
 */
export function getEngine() {
  if (!_engine) {
    _engine = new NullEngine();
  }
  return _engine;
}

/**
 * Create a new scene with basic lighting.
 * @returns {{ engine: NullEngine, scene: Scene }}
 */
export function createScene() {
  const engine = getEngine();
  const scene = new Scene(engine);

  // Default hemispheric light so PBR materials work
  const light = new HemisphericLight('defaultLight', new Vector3(0, 1, 0), scene);
  light.intensity = 1.0;
  light.diffuse = new Color3(1, 1, 1);
  light.groundColor = new Color3(0.3, 0.3, 0.3);

  return { engine, scene };
}

/**
 * Dispose engine and free resources.
 */
export function disposeEngine() {
  if (_engine) {
    _engine.dispose();
    _engine = null;
  }
}
