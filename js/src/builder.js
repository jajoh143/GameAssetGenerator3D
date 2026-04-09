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
import { buildEyeGeometry, createEyeMaterials } from './eye_geo.js';
import { buildEyebrowGeometry, buildNoseGeometry, buildMouthGeometry, buildEarGeometry } from './face_geo.js';
import { buildClothingGeometry, buildCollarGeometry, buildButtonGeometry } from './clothing_geo.js';
import { buildAnimations } from './animation.js';
import { SKIN_TONES } from './presets.js';
import { HAIR_COLORS } from './hair_colors.js';
import { CLOTHING_COLORS, CLOTHING_DEFAULT_COLORS } from './clothing_colors.js';

/**
 * Apply simple vertex-color ambient occlusion to the body mesh.
 * Darkens vertices in concavities (neck, under-chin, armpits) based on Y-position.
 */
function applyVertexAO(bodyGeo, skinColor) {
  const pos = bodyGeo.attributes.position;
  const count = pos.count;

  // Compute Y range
  let minY = Infinity, maxY = -Infinity;
  for (let i = 0; i < count; i++) {
    const y = pos.getY(i);
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  }
  const bodyH = maxY - minY;

  // Define AO zones (normalized Y from 0=feet to 1=top)
  // Each zone: [yNormMin, yNormMax, darkenFactor]
  const aoZones = [
    [0.78, 0.84, 0.82],  // Neck junction — darken by 18%
    [0.84, 0.88, 0.88],  // Under chin — darken by 12%
    [0.56, 0.65, 0.90],  // Armpit area — darken by 10%
    [0.00, 0.03, 0.90],  // Feet/ground contact — darken by 10%
    [0.42, 0.44, 0.92],  // Waist crease — darken by 8%
  ];

  // Create vertex colors
  const colors = new Float32Array(count * 3);
  const baseR = skinColor[0], baseG = skinColor[1], baseB = skinColor[2];

  for (let i = 0; i < count; i++) {
    const y = pos.getY(i);
    const yNorm = (y - minY) / bodyH;

    let factor = 1.0;
    for (const [yMin, yMax, darken] of aoZones) {
      if (yNorm >= yMin && yNorm <= yMax) {
        // Smooth falloff toward zone edges
        const zoneMid = (yMin + yMax) / 2;
        const zoneHalf = (yMax - yMin) / 2;
        const dist = Math.abs(yNorm - zoneMid) / zoneHalf;
        const strength = 1.0 - dist * dist;  // Quadratic falloff
        factor = Math.min(factor, 1.0 - (1.0 - darken) * strength);
      }
    }

    colors[i * 3 + 0] = baseR * factor;
    colors[i * 3 + 1] = baseG * factor;
    colors[i * 3 + 2] = baseB * factor;
  }

  bodyGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
}

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

  // 3. Skin material — improved for cartoony look
  const skinRgba = Array.isArray(cfg.skinTone)
    ? cfg.skinTone
    : (SKIN_TONES[cfg.skinTone] ?? SKIN_TONES.tan);

  // Apply vertex AO before creating the material
  applyVertexAO(bodyGeo, skinRgba);

  const skinMat = new THREE.MeshStandardMaterial({
    roughness: 0.35,          // Smoother for cartoony polish (was 0.42)
    metalness: 0.0,
    vertexColors: true,       // Use vertex colors for AO
    emissive: new THREE.Color(skinRgba[0] * 0.08, skinRgba[1] * 0.04, skinRgba[2] * 0.02),
    emissiveIntensity: 0.3,   // Subtle warm SSS approximation
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

  // Estimate head radius from body width (used by hair, eyes, etc.)
  const box = new THREE.Box3().setFromBufferAttribute(bodyGeo.attributes.position);
  const bodyWidth = box.max.x - box.min.x;
  const headRadius = bodyWidth * 0.18;  // ~18% of body width

  if (hairStyle !== 'none') {
    // Get head bone and calculate radius from body
    const headBoneIdx = BONE_NAMES.indexOf('Head');
    const headBone = skeleton.bones[headBoneIdx];

    console.log(`[Hair] Creating hair: style=${hairStyle}, headRadius=${headRadius.toFixed(3)}`);

    const hairGeo = buildHairGeometry(headRadius, hairStyle);
    if (hairGeo) {
      const hairColorName = cfg.hairColor ?? 'brown';
      const hairRgba = HAIR_COLORS[hairColorName] ?? HAIR_COLORS.brown;
      const hairMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(hairRgba[0], hairRgba[1], hairRgba[2]),
        roughness: 0.75,
        metalness: 0.0,
        side: THREE.DoubleSide,
        flatShading: false,
      });
      const hairMesh = new THREE.Mesh(hairGeo, hairMat);
      hairMesh.name = 'Hair';
      hairMesh.castShadow = true;
      hairMesh.receiveShadow = true;

      // Hair positioning and rotation
      hairMesh.rotation.x = -Math.PI / 2;

      // Position at top of head — increased scale for more volume
      hairMesh.position.set(0, headRadius * 5.5, -headRadius * 0.6);

      // Add to head bone so it moves with animations
      headBone.add(hairMesh);
      hairMesh.scale.set(0.78, 0.78, 0.78);  // Moderate volume increase from original 0.725

      console.log(`[Hair] Hair added to Head bone with ${hairGeo.attributes.position.count} vertices`);
    }
  }

  // 7. Eyes — multi-layer system with sclera, iris, pupil, highlight
  {
    const headBoneIdx = BONE_NAMES.indexOf('Head');
    const headBone = skeleton.bones[headBoneIdx];

    const eyeColorName = cfg.eyeColor ?? 'brown';
    const eyeGeos = buildEyeGeometry(headRadius);
    const eyeMats = createEyeMaterials(eyeColorName);

    // Sclera (white of eye)
    const scleraMesh = new THREE.Mesh(eyeGeos.scleraGeometry, eyeMats.scleraMaterial);
    scleraMesh.name = 'EyeSclera';
    scleraMesh.castShadow = true;
    headBone.add(scleraMesh);

    // Iris (colored ring)
    const irisMesh = new THREE.Mesh(eyeGeos.irisGeometry, eyeMats.irisMaterial);
    irisMesh.name = 'EyeIris';
    headBone.add(irisMesh);

    // Pupil (black center)
    const pupilMesh = new THREE.Mesh(eyeGeos.pupilGeometry, eyeMats.pupilMaterial);
    pupilMesh.name = 'EyePupil';
    headBone.add(pupilMesh);

    // Highlight (white glint)
    const highlightMesh = new THREE.Mesh(eyeGeos.highlightGeometry, eyeMats.highlightMaterial);
    highlightMesh.name = 'EyeHighlights';
    headBone.add(highlightMesh);

    console.log(`[Eyes] Multi-layer eyes added (sclera + iris + pupil + highlight), color=${eyeColorName}`);
  }

  // 8. Facial features — eyebrows, nose, mouth, ears
  {
    const headBoneIdx = BONE_NAMES.indexOf('Head');
    const headBone = skeleton.bones[headBoneIdx];

    // Eyebrows
    if (cfg.eyebrows !== false) {
      const browGeo = buildEyebrowGeometry(headRadius);
      const hairColorName = cfg.hairColor ?? 'brown';
      const hairRgba = HAIR_COLORS[hairColorName] ?? HAIR_COLORS.brown;
      // Eyebrows are darker than hair
      const browMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(hairRgba[0] * 0.6, hairRgba[1] * 0.6, hairRgba[2] * 0.6),
        roughness: 0.8,
        metalness: 0.0,
        side: THREE.DoubleSide,
      });
      const browMesh = new THREE.Mesh(browGeo, browMat);
      browMesh.name = 'Eyebrows';
      headBone.add(browMesh);
      console.log('[Face] Eyebrows added');
    }

    // Nose and mouth
    if (cfg.facialFeatures !== false) {
      // Nose — same color as skin
      const noseGeo = buildNoseGeometry(headRadius);
      const noseMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(skinRgba[0], skinRgba[1], skinRgba[2]),
        roughness: 0.35,
        metalness: 0.0,
      });
      const noseMesh = new THREE.Mesh(noseGeo, noseMat);
      noseMesh.name = 'Nose';
      headBone.add(noseMesh);
      console.log('[Face] Nose added');

      // Mouth — darker than skin
      const mouthGeo = buildMouthGeometry(headRadius);
      const mouthMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(skinRgba[0] * 0.4, skinRgba[1] * 0.3, skinRgba[2] * 0.3),
        roughness: 0.6,
        metalness: 0.0,
        side: THREE.DoubleSide,
      });
      const mouthMesh = new THREE.Mesh(mouthGeo, mouthMat);
      mouthMesh.name = 'Mouth';
      headBone.add(mouthMesh);
      console.log('[Face] Mouth added');

      // Ear stubs
      const earGeo = buildEarGeometry(headRadius);
      const earMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(skinRgba[0] * 0.92, skinRgba[1] * 0.90, skinRgba[2] * 0.88),
        roughness: 0.4,
        metalness: 0.0,
      });
      const earMesh = new THREE.Mesh(earGeo, earMat);
      earMesh.name = 'Ears';
      headBone.add(earMesh);
      console.log('[Face] Ear stubs added');
    }
  }

  // 9. Clothing — face-extrusion using Y-axis height filtering and X-Z plane radial extrusion.
  if (cfg.clothing && cfg.clothing.length > 0) {
    const clothingColors = cfg.clothingColor ?? {};
    const clothingGeos = buildClothingGeometry(bodyGeo, cfg);

    // Clothing vertices are in scene/world space (same as bodyGeo).
    // Add directly to scene — NOT to a bone — to avoid double-transform.
    const clothingGroup = new THREE.Group();
    clothingGroup.name = 'Clothing';
    scene.add(clothingGroup);

    for (const [ctype, geo] of Object.entries(clothingGeos)) {
      const colorName = clothingColors[ctype] ?? CLOTHING_DEFAULT_COLORS[ctype] ?? 'grey';
      const rgba = CLOTHING_COLORS[colorName] ?? CLOTHING_COLORS.grey;
      const mat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(rgba[0], rgba[1], rgba[2]),
        roughness: 0.65,
        metalness: 0.0,
        side: THREE.DoubleSide,  // Render both sides to prevent clipping
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.name = `Clothing_${ctype}`;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      clothingGroup.add(mesh);

      console.log(`[Clothing] Added ${ctype} (${geo.attributes.position.count} verts) with color ${colorName}`);
    }

    // Compute Y range for collar / button placement (same math as clothing_geo.js)
    const _pos = bodyGeo.attributes.position;
    let _minY = Infinity, _maxY = -Infinity;
    for (let i = 0; i < _pos.count; i++) { const y = _pos.getY(i); if (y < _minY) _minY = y; if (y > _maxY) _maxY = y; }
    const _bodyH = _maxY - _minY;
    const _armY  = _minY + _bodyH * 0.63;
    const _hipY  = _minY + _bodyH * 0.43;

    const clothingList = Array.isArray(cfg.clothing) ? cfg.clothing : [];

    // Polo collar — procedural ring around the neck
    if (clothingList.includes('polo')) {
      const collarGeo = buildCollarGeometry(bodyGeo, _armY, _bodyH, 0.020);
      if (collarGeo) {
        const topColorName = (cfg.clothingColor ?? {})['polo'] ?? 'grey';
        const topRgba = CLOTHING_COLORS[topColorName] ?? CLOTHING_COLORS.grey;
        const collarMat = new THREE.MeshStandardMaterial({
          color: new THREE.Color(
            Math.min(1, topRgba[0] * 1.15),
            Math.min(1, topRgba[1] * 1.15),
            Math.min(1, topRgba[2] * 1.15)
          ),
          roughness: 0.55, metalness: 0.0, side: THREE.DoubleSide,
        });
        const collarMesh = new THREE.Mesh(collarGeo, collarMat);
        collarMesh.name = 'Clothing_polo_collar';
        collarMesh.castShadow = true;
        clothingGroup.add(collarMesh);
        console.log('[Clothing] Added polo collar');
      }
    }

    // Buttons — available on polo, short_sleeve, v_neck, long_sleeve
    if (cfg.buttons) {
      const shirtTypes = ['polo', 'short_sleeve', 'v_neck', 'long_sleeve'];
      if (clothingList.some(c => shirtTypes.includes(c))) {
        const buttonGeo = buildButtonGeometry(bodyGeo, _hipY, _armY, 4);
        if (buttonGeo) {
          const buttonMat = new THREE.MeshStandardMaterial({
            color: new THREE.Color(0.92, 0.92, 0.92),
            roughness: 0.3, metalness: 0.1,
          });
          const buttonMesh = new THREE.Mesh(buttonGeo, buttonMat);
          buttonMesh.name = 'Clothing_buttons';
          buttonMesh.castShadow = true;
          clothingGroup.add(buttonMesh);
          console.log('[Clothing] Added buttons');
        }
      }
    }
  }

  // 10. Animations
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
