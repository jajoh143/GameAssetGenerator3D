/**
 * Build and export a low-poly character scene.
 *
 * This is the low-poly counterpart to builder.js. It uses the same
 * skeleton, hair, eye, clothing, and animation pipeline — the only
 * difference is that the body mesh is loaded from the gendered
 * NBM_Lowpoly_Male/Female.glb templates instead of Cartoon_Male.glb.
 */

import './node_polyfills.js';
import {
  NullEngine, Scene, Mesh, VertexData, Skeleton, PBRMaterial, Color3,
  Animation, AnimationGroup, Vector3, Quaternion,
} from '@babylonjs/core';
import { buildSkeleton } from './skeleton.js';
import { buildHairGeometry } from './hair_geo.js';
import { buildEyeGeometry, createEyeMaterials } from './eye_geo.js';
import { buildClothingGeometry, buildCollarGeometry, buildButtonGeometry } from './lowpoly_clothing_geo.js';
import { buildAnimations } from './animation.js';
import { SKIN_TONES } from './presets.js';
import { HAIR_COLORS } from './hair_colors.js';
import { CLOTHING_COLORS, CLOTHING_DEFAULT_COLORS } from './clothing_colors.js';
import { loadLowPolyMesh } from './lowpoly_mesh_loader.js';
import { buildNoseGeometry, buildMouthGeometry } from './face_geo.js';

// Re-export exportGLB so callers only need to import from this module.
export { exportGLB } from './builder.js';

// ── Helpers ───────────────────────────────────────────────────────────────────

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

function applyRawGeoToMesh(mesh, geo) {
  const vd = new VertexData();
  vd.positions = geo.positions;
  vd.normals   = geo.normals;
  if (geo.uvs)    vd.uvs     = geo.uvs;
  if (geo.indices) vd.indices = geo.indices;
  vd.applyToMesh(mesh);
}

function makePBR(scene, name, colorRgba, roughness = 0.5, metallic = 0.0) {
  const mat = new PBRMaterial(name, scene);
  mat.albedoColor = new Color3(colorRgba[0], colorRgba[1], colorRgba[2]);
  mat.roughness   = roughness;
  mat.metallic    = metallic;
  return mat;
}

function buildAnimationGroups(clips, skeleton, scene) {
  const groups = [];

  for (const clip of clips) {
    const group = new AnimationGroup(clip.name, scene);

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
 * Build the full low-poly character scene from a resolved config.
 *
 * @param {Object} cfg - resolved character config (from resolveLowPolyConfig)
 * @returns {Promise<{scene: BABYLON.Scene, engine: BABYLON.NullEngine}>}
 */
export async function buildLowPolyCharacter(cfg) {
  const H = cfg.height ?? 1.75;

  const engine = new NullEngine();
  const scene  = new Scene(engine);

  // 1. Load body mesh data — select male or female GLB based on gender
  const bodyData = await loadLowPolyMesh(cfg.gender ?? 'neutral', H);
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
  if (normals)  vd.normals          = normals;
  if (uvs)      vd.uvs              = uvs;
  vd.indices            = indices;
  vd.matricesIndices    = packSkinIndices(skinIndices, vCount);
  vd.matricesWeights    = skinWeights;
  vd.applyToMesh(bodyMesh);
  bodyMesh.skeleton = skeleton;

  // ── Head geometry detection ───────────────────────────────────────────────
  // Use the top 14% of model height as the head zone. For a realistic 1.75m
  // figure that's the top ~0.245m, safely above the shoulder/neck junction.
  // (The old 80% threshold caught shoulder vertices and inflated headRadius.)
  const headZoneBottom = H * 0.86;
  let hxMin = Infinity, hxMax = -Infinity;
  let hyMax = -Infinity;
  let hzMin = Infinity, hzMax = -Infinity;
  for (let i = 0; i < vCount; i++) {
    const by = positions[i * 3 + 1];
    if (by > headZoneBottom) {
      const bx = positions[i * 3];
      const bz = positions[i * 3 + 2];
      if (bx < hxMin) hxMin = bx;
      if (bx > hxMax) hxMax = bx;
      if (by > hyMax) hyMax = by;
      if (bz < hzMin) hzMin = bz;
      if (bz > hzMax) hzMax = bz;
    }
  }

  // headBoneY: for realistic proportions the head centre sits higher than
  // the cartoon value of H*0.87. Use H*0.92 (7.5:1 head-to-body ratio).
  const headBoneY  = H * 0.92;

  // headRadius: width-based from the tight head zone, clamped to a
  // plausible range. The NBM mesh head half-width is ~0.09-0.11 m;
  // clamping [H*0.055, H*0.085] = [0.096, 0.149] for H=1.75 keeps us
  // in realistic territory without inflating from stray neck vertices.
  const rawWidthR  = hxMin < hxMax ? (hxMax - hxMin) / 2 : H * 0.08;
  const headRadius = Math.min(Math.max(rawWidthR, H * 0.055), H * 0.085);

  // faceFrontZ: the face points toward +Z in our coordinate system.
  // Use the forward (max-Z) extent of head-zone vertices.
  const faceFrontZ = hzMax > -Infinity ? hzMax : headBoneY * 0.06;

  console.log(`[Head] headRadius=${headRadius.toFixed(3)} (raw=${rawWidthR.toFixed(3)}), headBoneY=${headBoneY.toFixed(3)}, faceFrontZ=${faceFrontZ.toFixed(3)}`);

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

      const hp = hairGeo.positions;
      const hn = hairGeo.normals;
      const earY = headBoneY + headRadius * 0.5;
      for (let i = 0; i < hp.length / 3; i++) {
        const hx = hp[i*3], hy = hp[i*3+1], hz = hp[i*3+2];
        hp[i*3]   = hx;
        hp[i*3+1] = hz + earY;
        hp[i*3+2] = -hy;
        const nx = hn[i*3], ny = hn[i*3+1], nz = hn[i*3+2];
        hn[i*3]   = nx;
        hn[i*3+1] = nz;
        hn[i*3+2] = -ny;
      }
      applyRawGeoToMesh(hairMesh, hairGeo);

      console.log(`[Hair] Hair placed at Y=${earY.toFixed(3)}, headRadius=${headRadius.toFixed(3)}`);
    }
  }

  // 6. Eyes
  {
    // Larger eye discs for the realistic mesh — cartoon's 0.10/0.08 is too small
    // at realistic head proportions (headRadius ≈ H*0.11 vs cartoon's H*0.18+)
    const eyeGeos = buildEyeGeometry(headRadius, headBoneY, faceFrontZ, {
      eyeXMult:      0.42,   // slightly inward for a natural look
      eyeHeightMult: 0.08,   // a touch higher than head centre
      rxMult:        0.18,   // ~3.5cm horizontal for H=1.75 — clearly visible
      ryMult:        0.14,   // ~2.7cm vertical
      highlightRMult: 0.06,  // proportionally larger glint
    });
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

  // 7. Nose
  {
    const noseGeo = buildNoseGeometry(headRadius, headBoneY, faceFrontZ);
    const noseMesh = new Mesh('Nose', scene);
    // Slightly darker than skin tone for definition
    const noseMat = makePBR(scene, 'NoseMaterial',
      [skinRgba[0] * 0.88, skinRgba[1] * 0.82, skinRgba[2] * 0.78], 0.55, 0.0);
    noseMesh.material = noseMat;
    applyRawGeoToMesh(noseMesh, noseGeo);
  }

  // 8. Mouth
  {
    const mouthGeo = buildMouthGeometry(headRadius, headBoneY, faceFrontZ);
    const mouthMesh = new Mesh('Mouth', scene);
    // Muted dusty-rose tone
    const mouthMat = makePBR(scene, 'MouthMaterial',
      [skinRgba[0] * 0.78, skinRgba[1] * 0.55, skinRgba[2] * 0.52], 0.60, 0.0);
    mouthMesh.material = mouthMat;
    applyRawGeoToMesh(mouthMesh, mouthGeo);
  }

  // 9. Clothing
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

    let _minY = Infinity, _maxY = -Infinity;
    for (let i = 0; i < vCount; i++) {
      const y = positions[i * 3 + 1];
      if (y < _minY) _minY = y;
      if (y > _maxY) _maxY = y;
    }
    const _bodyH = _maxY - _minY;
    const _armY  = _minY + _bodyH * 0.82;   // realistic: shoulder at 82%
    const _hipY  = _minY + _bodyH * 0.53;   // realistic: hip at 53%

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

  // 10. Animations
  const clips = buildAnimations(cfg);
  buildAnimationGroups(clips, skeleton, scene);

  return { scene, engine };
}
