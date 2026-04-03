/**
 * Assemble full humanoid scene and export to GLB.
 */

import './node_polyfills.js';
import * as THREE from 'three';
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js';
import { writeFileSync } from 'fs';
import { loadCartoonMale } from './mesh_loader.js';
import { buildSkeleton, BONE_NAMES } from './skeleton.js';
import { buildHairGeometry } from './hair_geo.js';
import { buildClothingGeometry } from './clothing_geo.js';
import { buildAnimations } from './animation.js';
import { SKIN_TONES } from './presets.js';
import { HAIR_COLORS } from './hair_colors.js';
import { CLOTHING_COLORS, CLOTHING_DEFAULT_COLORS } from './clothing_colors.js';

/**
 * Build the full humanoid scene from a resolved config.
 * @param {Object} cfg - resolved character config
 * @returns {Promise<{scene: THREE.Scene, clips: THREE.AnimationClip[]}>}
 */
export async function buildHumanoid(cfg) {
  const H = cfg.height ?? 1.75;

  // 1. Load body mesh
  const { geometry: bodyGeo } = await loadCartoonMale(H);

  // 2. Build skeleton
  const skeleton = buildSkeleton(H);
  const rootBone = skeleton.bones[0]; // Hips

  // 3. Skin material
  const skinRgba = Array.isArray(cfg.skinTone)
    ? cfg.skinTone
    : (SKIN_TONES[cfg.skinTone] ?? SKIN_TONES.tan);
  const skinMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(skinRgba[0], skinRgba[1], skinRgba[2]),
    roughness: 0.42,
    metalness: 0.0,
  });

  // 4. Create skinned mesh
  const skinnedMesh = new THREE.SkinnedMesh(bodyGeo, skinMat);
  skinnedMesh.name = 'Body';
  skinnedMesh.add(rootBone);
  skinnedMesh.bind(skeleton);

  // 5. Build scene
  const scene = new THREE.Scene();
  scene.add(skinnedMesh);

  // 6. Hair
  const hairStyle = cfg.hairStyle ?? 'short';
  if (hairStyle !== 'none') {
    // Get head bone and calculate radius from body
    const headBoneIdx = BONE_NAMES.indexOf('Head');
    const headBone = skeleton.bones[headBoneIdx];

    // Estimate head radius from body width (simpler and more reliable)
    const box = new THREE.Box3().setFromBufferAttribute(bodyGeo.attributes.position);
    const bodyWidth = box.max.x - box.min.x;
    const headRadius = bodyWidth * 0.18;  // ~18% of body width

    console.log(`[Hair] Creating hair: style=${hairStyle}, headRadius=${headRadius.toFixed(3)}`);

    const hairGeo = buildHairGeometry(headRadius, hairStyle);
    if (hairGeo) {
      const hairColorName = cfg.hairColor ?? 'brown';
      const hairRgba = HAIR_COLORS[hairColorName] ?? HAIR_COLORS.brown;
      const hairMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(hairRgba[0], hairRgba[1], hairRgba[2]),
        roughness: 0.75,  // Increased for more realistic hair appearance
        metalness: 0.0,
        side: THREE.DoubleSide,  // Render both sides for better layered appearance
        flatShading: false,  // Smooth shading to reduce geometric look
      });
      const hairMesh = new THREE.Mesh(hairGeo, hairMat);
      hairMesh.name = 'Hair';
      hairMesh.castShadow = true;
      hairMesh.receiveShadow = true;

      // Position hair on the head
      // Y: lowered to sit properly on head (was 6.25, now adjusted lower)
      hairMesh.position.set(0, headRadius * 4.8, -0.5);

      // Add to head bone so it moves with animations
      headBone.add(hairMesh);

      console.log(`[Hair] Hair added to Head bone with ${hairGeo.attributes.position.count} vertices`);
    }
  }

  // 7. Clothing
  const clothingColors = cfg.clothingColor ?? {};
  const clothingGeos = buildClothingGeometry(bodyGeo, cfg);
  for (const [ctype, geo] of Object.entries(clothingGeos)) {
    const colorName = clothingColors[ctype] ?? CLOTHING_DEFAULT_COLORS[ctype] ?? 'grey';
    const rgba = CLOTHING_COLORS[colorName] ?? CLOTHING_COLORS.grey;
    const mat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(rgba[0], rgba[1], rgba[2]),
      roughness: 0.65,
      metalness: 0.0,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.name = `Clothing_${ctype}`;
    scene.add(mesh);
  }

  // 8. Animations
  const clips = buildAnimations(cfg);

  return { scene, clips };
}

/**
 * Export scene + clips to a GLB file.
 * @param {THREE.Scene} scene
 * @param {THREE.AnimationClip[]} clips
 * @param {string} outputPath
 */
export async function exportGLB(scene, clips, outputPath) {
  const exporter = new GLTFExporter();
  const result = await exporter.parseAsync(scene, {
    binary: true,
    animations: clips,
    onlyVisible: false,
  });
  writeFileSync(outputPath, Buffer.from(result));
  console.log(`[builder] Saved ${outputPath} (${result.byteLength} bytes)`);
}
