/**
 * Character presets and body configuration.
 * Port of generators/humanoid/presets.py
 */

export const PRESETS = {
  average: {
    height: 1.50,
    shoulder_width: 0.23,
    hip_width: 0.125,
    head_size: 0.20,
    arm_length: 0.56,
    leg_length: 0.46,
    torso_length: 0.43,
    neck_length: 0.06,
    hand_size: 0.065,
    foot_length: 0.19,
    foot_width: 0.08,
    limb_thickness: 1.0,
    torso_depth: 0.16,
  },
  tall: {
    height: 1.70,
    shoulder_width: 0.26,
    hip_width: 0.14,
    head_size: 0.22,
    arm_length: 0.63,
    leg_length: 0.54,
    torso_length: 0.48,
    neck_length: 0.07,
    hand_size: 0.07,
    foot_length: 0.22,
    foot_width: 0.09,
    limb_thickness: 0.95,
    torso_depth: 0.18,
  },
  short: {
    height: 1.25,
    shoulder_width: 0.19,
    hip_width: 0.10,
    head_size: 0.18,
    arm_length: 0.46,
    leg_length: 0.38,
    torso_length: 0.36,
    neck_length: 0.05,
    hand_size: 0.055,
    foot_length: 0.16,
    foot_width: 0.07,
    limb_thickness: 1.05,
    torso_depth: 0.13,
  },
  child: {
    height: 1.05,
    shoulder_width: 0.16,
    hip_width: 0.085,
    head_size: 0.20,
    arm_length: 0.37,
    leg_length: 0.30,
    torso_length: 0.33,
    neck_length: 0.05,
    hand_size: 0.045,
    foot_length: 0.13,
    foot_width: 0.06,
    limb_thickness: 0.85,
    torso_depth: 0.12,
  },
  brute: {
    height: 1.65,
    shoulder_width: 0.37,
    hip_width: 0.175,
    head_size: 0.18,
    arm_length: 0.68,
    leg_length: 0.54,
    torso_length: 0.54,
    neck_length: 0.05,
    hand_size: 0.10,
    foot_length: 0.24,
    foot_width: 0.12,
    limb_thickness: 1.4,
    torso_depth: 0.24,
  },
  slender: {
    height: 1.58,
    shoulder_width: 0.19,
    hip_width: 0.10,
    head_size: 0.22,
    arm_length: 0.60,
    leg_length: 0.52,
    torso_length: 0.46,
    neck_length: 0.08,
    hand_size: 0.06,
    foot_length: 0.19,
    foot_width: 0.07,
    limb_thickness: 0.75,
    torso_depth: 0.13,
  },
  kenney: {
    height: 1.50,
    shoulder_width: 0.21,
    hip_width: 0.115,
    head_size: 0.24,
    arm_length: 0.50,
    leg_length: 0.42,
    torso_length: 0.38,
    neck_length: 0.05,
    hand_size: 0.062,
    foot_length: 0.18,
    foot_width: 0.08,
    limb_thickness: 1.10,
    torso_depth: 0.15,
  },
};

export const BUILDS = {
  lean: {
    shoulder_width: 0.90,
    hip_width: 0.90,
    limb_thickness: 0.80,
    torso_depth: 0.85,
    hand_size: 0.90,
    foot_width: 0.90,
  },
  average: {},
  stocky: {
    height: 0.95,
    shoulder_width: 1.15,
    hip_width: 1.15,
    limb_thickness: 1.25,
    torso_depth: 1.20,
    hand_size: 1.10,
    foot_width: 1.15,
    neck_length: 0.75,
  },
  heavy: {
    height: 0.97,
    shoulder_width: 1.30,
    hip_width: 1.35,
    limb_thickness: 1.50,
    torso_depth: 1.45,
    hand_size: 1.20,
    foot_width: 1.25,
    neck_length: 0.60,
    torso_length: 1.10,
  },
};

export const GENDERS = {
  neutral: {},
  male: {
    shoulder_width: 1.12,
    hip_width: 0.92,
    limb_thickness: 1.15,
    torso_depth: 1.10,
    neck_length: 0.85,
    hand_size: 1.08,
    foot_width: 1.06,
  },
  female: {
    shoulder_width: 0.92,
    hip_width: 1.12,
    limb_thickness: 0.88,
    torso_depth: 0.92,
    hand_size: 0.90,
    foot_length: 0.92,
    foot_width: 0.90,
  },
};

export const SKIN_TONES = {
  light:  [0.90, 0.75, 0.65, 1.0],
  fair:   [0.82, 0.66, 0.54, 1.0],
  medium: [0.78, 0.60, 0.46, 1.0],
  olive:  [0.62, 0.50, 0.35, 1.0],
  tan:    [0.55, 0.42, 0.30, 1.0],
  brown:  [0.45, 0.32, 0.22, 1.0],
  dark:   [0.32, 0.22, 0.16, 1.0],
  zombie: [0.45, 0.55, 0.35, 1.0],
  orc:    [0.30, 0.50, 0.25, 1.0],
  frost:  [0.70, 0.78, 0.85, 1.0],
  ember:  [0.65, 0.30, 0.18, 1.0],
  shadow: [0.20, 0.18, 0.22, 1.0],
};

/**
 * Resolve a full character config from user options.
 *
 * @param {Object} opts
 * @param {string} [opts.preset='average']
 * @param {string} [opts.build='average']
 * @param {string} [opts.gender='neutral']
 * @param {string|number[]} [opts.skinTone='tan']
 * @param {string} [opts.hairStyle='short']
 * @param {string} [opts.hairColor='brown']
 * @param {string[]|'all'} [opts.animations='all']
 * @param {string} [opts.lod='mid']
 * @param {boolean} [opts.useTemplate=true]
 * @param {string[]} [opts.clothing]
 * @param {Object} [opts.clothingColor]
 * @returns {Object} merged config
 */
export function resolveConfig(opts = {}) {
  const {
    preset = 'average',
    build = 'average',
    gender = 'neutral',
    skinTone = 'tan',
    hairStyle = 'short',
    hairColor = 'brown',
    animations = 'all',
    lod = 'mid',
    useTemplate = true,
    clothing = ['short_sleeve', 'jeans'],
    clothingColor = {},
  } = opts;

  if (!PRESETS[preset]) {
    throw new Error(`Unknown preset '${preset}'. Available: ${Object.keys(PRESETS).sort().join(', ')}`);
  }
  if (!BUILDS[build]) {
    throw new Error(`Unknown build '${build}'. Available: ${Object.keys(BUILDS).sort().join(', ')}`);
  }
  if (!GENDERS[gender]) {
    throw new Error(`Unknown gender '${gender}'. Available: ${Object.keys(GENDERS).sort().join(', ')}`);
  }

  // Start from preset
  const cfg = { ...PRESETS[preset] };

  // Apply build multipliers
  for (const [key, mult] of Object.entries(BUILDS[build])) {
    if (key in cfg) cfg[key] = cfg[key] * mult;
  }

  // Apply gender multipliers
  for (const [key, mult] of Object.entries(GENDERS[gender])) {
    if (key in cfg) cfg[key] = cfg[key] * mult;
  }

  cfg.gender = gender;
  cfg.useTemplate = useTemplate;
  cfg.lod = lod;

  // Resolve skin tone
  if (Array.isArray(skinTone)) {
    cfg.skinTone = skinTone;
  } else {
    if (!SKIN_TONES[skinTone]) {
      throw new Error(`Unknown skin tone '${skinTone}'. Available: ${Object.keys(SKIN_TONES).sort().join(', ')}`);
    }
    cfg.skinTone = SKIN_TONES[skinTone];
  }

  cfg.hairStyle = hairStyle;
  cfg.hairColor = hairColor;
  cfg.animations = animations;
  cfg.clothing = clothing;
  cfg.clothingColor = clothingColor;

  return cfg;
}
