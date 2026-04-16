/**
 * GLB export utility using Babylon.js serializers.
 */

import { writeFileSync, mkdirSync } from 'fs';
import { dirname } from 'path';
import '@babylonjs/serializers/glTF/2.0/index.js';
import { GLTF2Export } from '@babylonjs/serializers/glTF/2.0/glTFSerializer.js';

/**
 * Export a Babylon.js scene to a GLB file.
 * @param {Scene} scene
 * @param {string} outputPath - file path for the .glb output
 * @param {string} [assetName] - optional name for the glTF asset
 */
export async function exportGLB(scene, outputPath, assetName = 'BarAsset') {
  // Ensure output directory exists
  mkdirSync(dirname(outputPath), { recursive: true });

  const glb = await GLTF2Export.GLBAsync(scene, assetName);
  const file = glb.glTFFiles[`${assetName}.glb`];

  // file is an ArrayBuffer-like or Blob — convert to Buffer for Node.js writeFileSync
  let buffer;
  if (file instanceof ArrayBuffer || ArrayBuffer.isView(file)) {
    buffer = Buffer.from(file instanceof ArrayBuffer ? file : file.buffer);
  } else if (typeof file.arrayBuffer === 'function') {
    buffer = Buffer.from(await file.arrayBuffer());
  } else {
    buffer = Buffer.from(file);
  }

  writeFileSync(outputPath, buffer);
  const kb = (buffer.byteLength / 1024).toFixed(1);
  console.log(`[export] Saved ${outputPath} (${kb} KB)`);
}
