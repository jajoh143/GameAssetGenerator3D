/**
 * Assemble full humanoid scene and export to GLB.
 */

import './node_polyfills.js';
import {
  NullEngine, Scene, Mesh, VertexData, Skeleton, PBRMaterial, Color3,
  Animation, AnimationGroup, Vector3, Quaternion,
} from '@babylonjs/core';
import { GLTF2Export } from '@babylonjs/serializers';
import { writeFileSync } from 'fs';
import { loadCartoonMale } from './mesh_loader.js';
import { buildSkeleton, BONE_NAMES } from './skeleton.js';
import { buildHairGeometry } from './hair_geo.js';
import { buildEyeGeometry, createEyeMaterials } from './eye_geo.js';
import { buildClothingGeometry, buildCollarGeometry, buildButtonGeometry } from './clothing_geo.js';
import { buildAnimations } from './animation.js';
import { SKIN_TONES } from './presets.js';
import { HAIR_COLORS } from './hair_colors.js';
import { CLOTHING_COLORS, CLOTHING_DEFAULT_COLORS } from './clothing_colors.js';

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Pack flat Uint16Array bone indices into Babylon's format:
 * 4 floats per vertex, each float stores one uint8 index in its low byte.
 */
function packSkinIndices(skinIndices, vCount) {
  const packed = new Float32Array(vCount * 4);
  const buf = new ArrayBuffer(4);
  const dv  = new DataView(buf);
  for (let v = 0; v < vCount; v++) {
    for (let j = 0; j < 4; j++) {
      dv.setUint8(0, skinIndices[v * 4 + j]);
      dv.setUint8(1, 0);
      dv.setUint8(2, 0);
      dv.setUint8(3, 0);
      packed[v * 4 + j] = dv.getFloat32(0, true);
    }
  }
  return packed;
}

/**
 * Apply a raw geometry object { positions, normals, uvs?, indices } to a Babylon Mesh.
 */
function applyRawGeoToMesh(mesh, geo) {
  const vd = new VertexData();
  vd.positions = geo.positions;
  vd.normals   = geo.normals;
  if (geo.uvs)    vd.uvs     = geo.uvs;
  if (geo.indices) vd.indices = geo.indices;
  vd.applyToMesh(mesh);
}

/**
 * Create a PBRMaterial from a plain params object or [r,g,b] array.
 */
function makePBR(scene, name, colorRgba, roughness = 0.5, metallic = 0.0) {
  const mat = new PBRMaterial(name, scene);
  mat.albedoColor = new Color3(colorRgba[0], colorRgba[1], colorRgba[2]);
  mat.roughness  = roughness;
  mat.metallic   = metallic;
  return mat;
}

/**
 * Build Babylon AnimationGroups from the plain clip data returned by buildAnimations().
 */
function buildAnimationGroups(clips, skeleton, scene) {
  const groups = [];

  for (const clip of clips) {
    const group = new AnimationGroup(clip.name, scene);

    // Rotation tracks
    for (const [boneName, { times, values }] of clip.rotByBone) {
      const bone = skeleton.bones.find(b => b.name === boneName);
      if (!bone) continue;

      const anim = new Animation(
        `${clip.name}_${boneName}_rot`,
        'rotationQuaternion',
        clip.fps,
        Animation.ANIMATIONTYPE_QUATERNION,
        Animation.ANIMATIONLOOPMODE_CYCLE,
      );

      const keys = [];
      for (let i = 0; i < times.length; i++) {
        keys.push({
          frame: Math.round(times[i] * clip.fps),
          value: new Quaternion(
            values[i * 4],
            values[i * 4 + 1],
            values[i * 4 + 2],
            values[i * 4 + 3],
          ),
        });
      }
      anim.setKeys(keys);
      group.addTargetedAnimation(anim, bone);
    }

    // Translation tracks
    for (const [boneName, { times, values }] of clip.transByBone) {
      const bone = skeleton.bones.find(b => b.name === boneName);
      if (!bone) continue;

      const anim = new Animation(
        `${clip.name}_${boneName}_pos`,
        'position',
        clip.fps,
        Animation.ANIMATIONTYPE_VECTOR3,
        Animation.ANIMATIONLOOPMODE_CYCLE,
      );

      const keys = [];
      for (let i = 0; i < times.length; i++) {
        keys.push({
          frame: Math.round(times[i] * clip.fps),
          value: new Vector3(values[i * 3], values[i * 3 + 1], values[i * 3 + 2]),
        });
      }
      anim.setKeys(keys);
      group.addTargetedAnimation(anim, bone);
    }

    groups.push(group);
  }

  return groups;
}

// ── Main builder ──────────────────────────────────────────────────────────────

/**
 * Build the full humanoid scene from a resolved config.
 * @param {Object} cfg - resolved character config
 * @returns {Promise<{scene: BABYLON.Scene, engine: BABYLON.NullEngine}>}
 */
export async function buildHumanoid(cfg) {
  const H = cfg.height ?? 1.75;

  const engine = new NullEngine();
  const scene  = new Scene(engine);

  // 1. Load body mesh data
  const bodyData = await loadCartoonMale(H);
  const { positions, normals, uvs, skinIndices, skinWeights, indices } = bodyData;
  const vCount = positions.length / 3;

  // 2. Build skeleton
  const skeleton = buildSkeleton(H, scene);

  // 3. Skin material
  const skinRgba = Array.isArray(cfg.skinTone)
    ? cfg.skinTone
    : (SKIN_TONES[cfg.skinTone] ?? SKIN_TONES.tan);
  const skinMat = makePBR(scene, 'SkinMaterial', skinRgba, 0.42, 0.0);

  // 4. Create skinned mesh
  const bodyMesh = new Mesh('Body', scene);
  bodyMesh.material = skinMat;

  const vd = new VertexData();
  vd.positions = positions;
  if (normals)  vd.normals   = normals;
  if (uvs)      vd.uvs       = uvs;
  vd.indices   = indices;
  vd.matricesIndices = packSkinIndices(skinIndices, vCount);
  vd.matricesWeights = skinWeights;
  vd.applyToMesh(bodyMesh);
  bodyMesh.skeleton = skeleton;

  // Compute head bounding box from vertices above 80% of body height (avoids arm span).
  // Body uses Y as height (Babylon/glTF Y-up), Z as forward depth.
  const headYThresh = H * 0.80;
  let hxMin = Infinity, hxMax = -Infinity, hyMax = -Infinity, hzMax = -Infinity;
  for (let i = 0; i < vCount; i++) {
    const by = positions[i * 3 + 1];  // Y = height
    if (by > headYThresh) {
      const bx = positions[i * 3];
      const bz = positions[i * 3 + 2];  // Z = forward
      if (bx < hxMin) hxMin = bx;
      if (bx > hxMax) hxMax = bx;
      if (by > hyMax) hyMax = by;
      if (bz > hzMax) hzMax = bz;
    }
  }
  const headBoneY  = H * 0.87;  // world Y of Head bone
  // Two estimates of head radius — take the larger so the cap covers the full head.
  //   widthR: half the X span in the head zone
  //   heightR: how far the head top extends above the head bone
  const headWidthR  = hxMin < hxMax ? (hxMax - hxMin) / 2 : H * 0.13;
  const headHeightR = hyMax > headBoneY ? hyMax - headBoneY : H * 0.13;
  const headRadius  = Math.max(headWidthR, headHeightR, H * 0.12);
  // faceFrontZ = world Z of the front face surface (for eye/hair forward placement)
  const faceFrontZ  = hzMax > -Infinity ? hzMax : H * 0.10;

  console.log(`[Head] headRadius=${headRadius.toFixed(3)} (widthR=${headWidthR.toFixed(3)}, heightR=${headHeightR.toFixed(3)}), headBoneY=${headBoneY.toFixed(3)}, faceFrontZ=${faceFrontZ.toFixed(3)}`);

  // 5. Hair
  const hairStyle = cfg.hairStyle ?? 'short';
  if (hairStyle !== 'none') {
    const hairGeo = buildHairGeometry(headRadius, hairStyle);
    if (hairGeo) {
      const hairColorName = cfg.hairColor ?? 'brown';
      const hairRgba = HAIR_COLORS[hairColorName] ?? HAIR_COLORS.brown;
      const hairMat = makePBR(scene, 'HairMaterial', hairRgba, 0.75, 0.0);
      hairMat.backFaceCulling = false;

      const hairMesh = new Mesh('Hair', scene);
      hairMesh.material = hairMat;

      // Bake Z-up → Y-up transform directly into positions/normals before applying.
      // hair_geo builds rings in XY plane with Z as height.
      // Transform: (x, y, z) → (x, z + earY, -y) where earY = headBoneY + headRadius*0.05.
      // Doing this in JS rather than via hairMesh.rotation avoids GLTF2Export's
      // handedness fix which would flip the sign of rotation.x (inverting the cap).
      const hp = hairGeo.positions;
      const hn = hairGeo.normals;
      const earY = headBoneY + headRadius * 0.5;
      for (let i = 0; i < hp.length / 3; i++) {
        const hx = hp[i*3], hy = hp[i*3+1], hz = hp[i*3+2];
        hp[i*3]   = hx;
        hp[i*3+1] = hz + earY;  // new Y = old Z (height) + ear-level offset
        hp[i*3+2] = -hy;         // new Z = -old Y (hair's -Y was "front"; +Z faces viewer)
        const nx = hn[i*3], ny = hn[i*3+1], nz = hn[i*3+2];
        hn[i*3]   = nx;
        hn[i*3+1] = nz;
        hn[i*3+2] = -ny;
      }
      applyRawGeoToMesh(hairMesh, hairGeo);

      console.log(`[Hair] Hair placed at Y=${earY.toFixed(3)}, headRadius=${headRadius.toFixed(3)}`);
    }
  }

  // 6. Eyes — geometry is in absolute world space (Y-up); no rotation needed.
  {
    const eyeGeos = buildEyeGeometry(headRadius, headBoneY, faceFrontZ);
    const eyeMatParams = createEyeMaterials();

    const eyeDiscMesh = new Mesh('Eyes', scene);
    const eyeMat = new PBRMaterial('EyeMaterial', scene);
    eyeMat.albedoColor    = new Color3(...eyeMatParams.eyeDiscMaterial.albedoColor);
    eyeMat.roughness      = eyeMatParams.eyeDiscMaterial.roughness;
    eyeMat.metallic       = eyeMatParams.eyeDiscMaterial.metallic;
    eyeMat.backFaceCulling = false;
    eyeDiscMesh.material  = eyeMat;
    applyRawGeoToMesh(eyeDiscMesh, eyeGeos.eyeDiscGeometry);

    const highlightMesh = new Mesh('EyeHighlights', scene);
    const hlMat = new PBRMaterial('HighlightMaterial', scene);
    hlMat.albedoColor     = new Color3(...eyeMatParams.highlightMaterial.albedoColor);
    hlMat.roughness       = eyeMatParams.highlightMaterial.roughness;
    hlMat.metallic        = eyeMatParams.highlightMaterial.metallic;
    hlMat.emissiveColor   = new Color3(...eyeMatParams.highlightMaterial.emissiveColor);
    hlMat.backFaceCulling = false;
    highlightMesh.material = hlMat;
    applyRawGeoToMesh(highlightMesh, eyeGeos.highlightGeometry);

    console.log(`[Eyes] Eyes placed at world Y=${(headBoneY + headRadius * 0.20).toFixed(3)}, Z=${(faceFrontZ + 0.003).toFixed(3)}`);
  }

  // 7. Clothing
  if (cfg.clothing && cfg.clothing.length > 0) {
    const clothingColors = cfg.clothingColor ?? {};
    const clothingGeos = buildClothingGeometry(bodyData, cfg);

    for (const [ctype, geo] of Object.entries(clothingGeos)) {
      const colorName = clothingColors[ctype] ?? CLOTHING_DEFAULT_COLORS[ctype] ?? 'grey';
      const rgba = CLOTHING_COLORS[colorName] ?? CLOTHING_COLORS.grey;
      const mat = makePBR(scene, `ClothingMat_${ctype}`, rgba, 0.65, 0.0);
      mat.backFaceCulling = false;

      const mesh = new Mesh(`Clothing_${ctype}`, scene);
      mesh.material = mat;
      applyRawGeoToMesh(mesh, geo);

      console.log(`[Clothing] Added ${ctype} (${geo.positions.length / 3} verts) with color ${colorName}`);
    }

    // Compute Y range for collar / button placement
    let _minY = Infinity, _maxY = -Infinity;
    for (let i = 0; i < vCount; i++) {
      const y = positions[i * 3 + 1];
      if (y < _minY) _minY = y;
      if (y > _maxY) _maxY = y;
    }
    const _bodyH = _maxY - _minY;
    const _armY  = _minY + _bodyH * 0.63;
    const _hipY  = _minY + _bodyH * 0.43;

    const clothingList = Array.isArray(cfg.clothing) ? cfg.clothing : [];

    if (clothingList.includes('polo')) {
      const collarGeo = buildCollarGeometry(bodyData, _armY, _bodyH, 0.020);
      if (collarGeo) {
        const topColorName = (cfg.clothingColor ?? {})['polo'] ?? 'grey';
        const topRgba = CLOTHING_COLORS[topColorName] ?? CLOTHING_COLORS.grey;
        const lighterRgba = [
          Math.min(1, topRgba[0] * 1.15),
          Math.min(1, topRgba[1] * 1.15),
          Math.min(1, topRgba[2] * 1.15),
        ];
        const collarMat = makePBR(scene, 'CollarMat', lighterRgba, 0.55, 0.0);
        collarMat.backFaceCulling = false;
        const collarMesh = new Mesh('Clothing_polo_collar', scene);
        collarMesh.material = collarMat;
        applyRawGeoToMesh(collarMesh, collarGeo);
        console.log('[Clothing] Added polo collar');
      }
    }

    if (cfg.buttons) {
      const shirtTypes = ['polo', 'short_sleeve', 'v_neck', 'long_sleeve'];
      if (clothingList.some(c => shirtTypes.includes(c))) {
        const buttonGeo = buildButtonGeometry(bodyData, _hipY, _armY, 4);
        if (buttonGeo) {
          const buttonMat = makePBR(scene, 'ButtonMat', [0.92, 0.92, 0.92], 0.3, 0.1);
          const buttonMesh = new Mesh('Clothing_buttons', scene);
          buttonMesh.material = buttonMat;
          applyRawGeoToMesh(buttonMesh, buttonGeo);
          console.log('[Clothing] Added buttons');
        }
      }
    }
  }

  // 8. Animations
  const clips = buildAnimations(cfg);
  buildAnimationGroups(clips, skeleton, scene);

  return { scene, engine };
}

/**
 * Export scene to a GLB file.
 * @param {BABYLON.Scene} scene
 * @param {BABYLON.NullEngine} engine
 * @param {string} outputPath
 */
export async function exportGLB(scene, engine, outputPath) {
  const result = await GLTF2Export.GLBAsync(scene, 'export', {});

  // result is an object { 'export.glb': ArrayBuffer | Blob }
  const glbData = result.glTFFiles['export.glb'];

  let buffer;
  if (glbData instanceof ArrayBuffer) {
    buffer = Buffer.from(glbData);
  } else {
    // Blob (shouldn't happen in Node with NullEngine, but handle anyway)
    const ab = await glbData.arrayBuffer();
    buffer = Buffer.from(ab);
  }

  writeFileSync(outputPath, buffer);
  console.log(`[builder] Saved ${outputPath} (${buffer.length} bytes)`);

  engine.dispose();
}
