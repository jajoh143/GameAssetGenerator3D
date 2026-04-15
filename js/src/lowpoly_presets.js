/**
 * Presets for the low-poly character generator.
 *
 * Proportions use a realistic 7–8 head-height scale (vs. the cartoon
 * generator's slightly exaggerated/chibi ratios). The NBM_Lowpoly meshes
 * are modelled at realistic proportions, so these values keep the skeleton
 * and procedural elements (hair, clothing) well-aligned.
 *
 * BUILDS, GENDERS, and SKIN_TONES are identical to the cartoon generator.
 */

import { BUILDS, GENDERS, SKIN_TONES } from './presets.js';
export { BUILDS, GENDERS, SKIN_TONES };

// ---------------------------------------------------------------------------
// Presets — realistic adult proportions
// ---------------------------------------------------------------------------

export const LOWPOLY_PRESETS = {
  average: {
    height:         1.75,
    shoulder_width: 0.24,
    hip_width:      0.14,
    head_size:      0.23,   // ~H/7.6
    arm_length:     0.62,
    leg_length:     0.52,
    torso_length:   0.50,
    neck_length:    0.07,
    hand_size:      0.075,
    foot_length:    0.26,
    foot_width:     0.09,
    limb_thickness: 1.0,
    torso_depth:    0.20,
  },
  tall: {
    height:         1.88,
    shoulder_width: 0.27,
    hip_width:      0.15,
    head_size:      0.25,
    arm_length:     0.68,
    leg_length:     0.59,
    torso_length:   0.55,
    neck_length:    0.08,
    hand_size:      0.08,
    foot_length:    0.29,
    foot_width:     0.10,
    limb_thickness: 0.95,
    torso_depth:    0.21,
  },
  short: {
    height:         1.58,
    shoulder_width: 0.21,
    hip_width:      0.12,
    head_size:      0.21,
    arm_length:     0.55,
    leg_length:     0.45,
    torso_length:   0.44,
    neck_length:    0.06,
    hand_size:      0.068,
    foot_length:    0.23,
    foot_width:     0.085,
    limb_thickness: 1.05,
    torso_depth:    0.18,
  },
  athletic: {
    height:         1.80,
    shoulder_width: 0.28,
    hip_width:      0.14,
    head_size:      0.23,
    arm_length:     0.64,
    leg_length:     0.55,
    torso_length:   0.52,
    neck_length:    0.07,
    hand_size:      0.08,
    foot_length:    0.27,
    foot_width:     0.095,
    limb_thickness: 1.15,
    torso_depth:    0.22,
  },
  heavy: {
    height:         1.76,
    shoulder_width: 0.30,
    hip_width:      0.18,
    head_size:      0.24,
    arm_length:     0.63,
    leg_length:     0.52,
    torso_length:   0.52,
    neck_length:    0.06,
    hand_size:      0.085,
    foot_length:    0.27,
    foot_width:     0.11,
    limb_thickness: 1.35,
    torso_depth:    0.28,
  },
};

// ---------------------------------------------------------------------------
// Config resolver
// ---------------------------------------------------------------------------

/**
 * Resolve a full low-poly character config from user options.
 *
 * @param {Object} opts
 * @param {string} [opts.preset='average']       - one of LOWPOLY_PRESETS keys
 * @param {string} [opts.build='average']        - one of BUILDS keys
 * @param {string} [opts.gender='neutral']       - one of GENDERS keys
 * @param {string|number[]} [opts.skinTone='tan']
 * @param {string} [opts.hairStyle='short']
 * @param {string} [opts.hairColor='brown']
 * @param {string[]|'all'} [opts.animations='all']
 * @param {string} [opts.lod='low']              - default 'low' (matches the mesh tier)
 * @param {string[]} [opts.clothing]
 * @param {Object} [opts.clothingColor]
 * @returns {Object} merged config with modelType='lowpoly'
 */
export function resolveLowPolyConfig(opts = {}) {
  const {
    preset        = 'average',
    build         = 'average',
    gender        = 'neutral',
    skinTone      = 'tan',
    hairStyle     = 'short',
    hairColor     = 'brown',
    animations    = 'all',
    lod           = 'low',
    clothing      = [],
    clothingColor = {},
  } = opts;

  if (!LOWPOLY_PRESETS[preset]) {
    throw new Error(`Unknown low-poly preset '${preset}'. Available: ${Object.keys(LOWPOLY_PRESETS).sort().join(', ')}`);
  }
  if (!BUILDS[build]) {
    throw new Error(`Unknown build '${build}'. Available: ${Object.keys(BUILDS).sort().join(', ')}`);
  }
  if (!GENDERS[gender]) {
    throw new Error(`Unknown gender '${gender}'. Available: ${Object.keys(GENDERS).sort().join(', ')}`);
  }

  // Start from preset
  const cfg = { ...LOWPOLY_PRESETS[preset] };

  // Apply build multipliers
  for (const [key, mult] of Object.entries(BUILDS[build])) {
    if (key in cfg) cfg[key] = cfg[key] * mult;
  }

  // Apply gender multipliers
  for (const [key, mult] of Object.entries(GENDERS[gender])) {
    if (key in cfg) cfg[key] = cfg[key] * mult;
  }

  cfg.gender        = gender;
  cfg.modelType     = 'lowpoly';
  cfg.lod           = lod;

  // Resolve skin tone
  if (Array.isArray(skinTone)) {
    cfg.skinTone = skinTone;
  } else {
    if (!SKIN_TONES[skinTone]) {
      throw new Error(`Unknown skin tone '${skinTone}'. Available: ${Object.keys(SKIN_TONES).sort().join(', ')}`);
    }
    cfg.skinTone = SKIN_TONES[skinTone];
  }

  cfg.hairStyle     = hairStyle;
  cfg.hairColor     = hairColor;
  cfg.animations    = animations;
  cfg.clothing      = clothing;
  cfg.clothingColor = clothingColor;

  return cfg;
}
