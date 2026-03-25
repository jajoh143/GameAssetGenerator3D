"""Character presets and body configuration.

Provides named presets (archetypes) that set proportions for common character
types, plus a build system that scales proportions relative to a base.

Presets define the full body config dict. Users can pick a preset and then
override individual values for fine-tuning.

Body build adjusts proportions multiplicatively:
    - "lean":    narrower shoulders/hips, thinner limbs
    - "average": no adjustment (1.0x)
    - "stocky":  wider shoulders/hips, thicker limbs, shorter
    - "heavy":   widest proportions, thickest limbs

Skin tones are named palettes mapping to RGBA base colors.

Hair styles and colors are also configurable per-character.
"""

import random

from .hair import HAIR_STYLES, HAIR_COLORS, get_hair_style_names, get_hair_color_names


# ─── Named presets ──────────────────────────────────────────────────────────

PRESETS = {
    # ── Dimensions reverse-engineered from Characters_Matt.blend ──────────
    # Reference character is 1.5 m tall (scale 1,1,1).  All measurements
    # taken directly from bone positions and mesh cross-sections in that file.
    #
    # Key reference values (unscaled):
    #   hip_z        = 0.518   (= foot_top 0.06 + leg_length 0.458 ≈ 0.46)
    #   chest_z      = 0.945   (= hip_z + torso_length 0.427 ≈ 0.43)
    #   neck_z       = 1.008   (= chest_z + neck_length 0.063 ≈ 0.06)
    #   head_top     ≈ 1.50    (= neck_z + 2 × head_size 0.207 ≈ 0.20)
    #   arm_start_x  = 0.185   (≈ shoulder_width 0.23 × 0.80)
    #   wrist_x      = 0.741   (arm_start + arm_length 0.556 ≈ 0.56)
    #   torso half-w ≈ ±0.23   (chest cross-section)
    #   leg centre x = 0.125   (hip_width)
    #   arm centre z = 0.883   (= hip_z + torso_len × 0.855)

    "average": {
        "height": 1.50,          # matched to Characters_Matt.blend
        "shoulder_width": 0.23,  # torso chest half-width; arm joint at 80 % = 0.184
        "hip_width": 0.125,      # leg centre x (ref UpperLeg head x ≈ 0.122)
        "head_size": 0.20,       # head radius (ref head spans ≈ 0.41 m)
        "arm_length": 0.56,      # shoulder joint → wrist (ref 0.185 → 0.741 = 0.556)
        "leg_length": 0.46,      # hip_z = foot_top(0.06) + 0.46 = 0.52 ≈ ref 0.518
        "torso_length": 0.43,    # chest_z − hip_z (ref 0.427)
        "neck_length": 0.06,     # neck bone length (ref 0.063)
        "hand_size": 0.065,
        "foot_length": 0.19,
        "foot_width": 0.08,
        "limb_thickness": 1.0,
        "torso_depth": 0.16,     # torso ry at chest (ref depth ≈ 0.36 m → half 0.18)
    },
    "tall": {
        "height": 1.70,          # ~1.13× average
        "shoulder_width": 0.26,
        "hip_width": 0.14,
        "head_size": 0.22,
        "arm_length": 0.63,
        "leg_length": 0.54,
        "torso_length": 0.48,
        "neck_length": 0.07,
        "hand_size": 0.07,
        "foot_length": 0.22,
        "foot_width": 0.09,
        "limb_thickness": 0.95,
        "torso_depth": 0.18,
    },
    "short": {
        "height": 1.25,          # ~0.83× average
        "shoulder_width": 0.19,
        "hip_width": 0.10,
        "head_size": 0.18,
        "arm_length": 0.46,
        "leg_length": 0.38,
        "torso_length": 0.36,
        "neck_length": 0.05,
        "hand_size": 0.055,
        "foot_length": 0.16,
        "foot_width": 0.07,
        "limb_thickness": 1.05,
        "torso_depth": 0.13,
    },
    "child": {
        "height": 1.05,          # ~0.70× average; big head for cartoon style
        "shoulder_width": 0.16,
        "hip_width": 0.085,
        "head_size": 0.20,       # deliberately large — chibi proportion
        "arm_length": 0.37,
        "leg_length": 0.30,
        "torso_length": 0.33,
        "neck_length": 0.05,
        "hand_size": 0.045,
        "foot_length": 0.13,
        "foot_width": 0.06,
        "limb_thickness": 0.85,
        "torso_depth": 0.12,
    },
    "brute": {
        "height": 1.65,          # ~1.10× average but stockier
        "shoulder_width": 0.37,  # much wider chest
        "hip_width": 0.175,
        "head_size": 0.18,       # smaller head → massive body reads bigger
        "arm_length": 0.68,
        "leg_length": 0.54,
        "torso_length": 0.54,
        "neck_length": 0.05,     # short thick neck
        "hand_size": 0.10,
        "foot_length": 0.24,
        "foot_width": 0.12,
        "limb_thickness": 1.4,
        "torso_depth": 0.24,
    },
    "slender": {
        "height": 1.58,          # ~1.05× average but lean
        "shoulder_width": 0.19,
        "hip_width": 0.10,
        "head_size": 0.22,
        "arm_length": 0.60,
        "leg_length": 0.52,
        "torso_length": 0.46,
        "neck_length": 0.08,     # longer elegant neck
        "hand_size": 0.06,
        "foot_length": 0.19,
        "foot_width": 0.07,
        "limb_thickness": 0.75,
        "torso_depth": 0.13,
    },
    # ── Kenney-style chibi character (reference: Kenney Characters pack) ──
    # Large round head (~38% of height), very short torso and legs, thick
    # limbs — the "chibi" / toy-figure proportions used in the Kenney asset
    # pack.  Use with use_template=True + Cartoon_Male.glb whose mesh already
    # has the right head-to-body ratio; these values drive clothing placement.
    "kenney": {
        "height": 1.50,          # same as average (Cartoon_Male natural height)
        "shoulder_width": 0.21,  # slightly narrower than average
        "hip_width": 0.115,
        "head_size": 0.24,       # larger head for chibi emphasis
        "arm_length": 0.50,      # shorter arms
        "leg_length": 0.42,      # shorter legs
        "torso_length": 0.38,    # shorter torso
        "neck_length": 0.05,
        "hand_size": 0.062,
        "foot_length": 0.18,
        "foot_width": 0.08,
        "limb_thickness": 1.10,  # thicker limbs for cartoon look
        "torso_depth": 0.15,
    },
}


# ─── Body builds (multiplier profiles) ─────────────────────────────────────

BUILDS = {
    "lean": {
        "shoulder_width": 0.90,
        "hip_width": 0.90,
        "limb_thickness": 0.80,
        "torso_depth": 0.85,
        "hand_size": 0.90,
        "foot_width": 0.90,
    },
    "average": {},  # no modifications
    "stocky": {
        "height": 0.95,
        "shoulder_width": 1.15,
        "hip_width": 1.15,
        "limb_thickness": 1.25,
        "torso_depth": 1.20,
        "hand_size": 1.10,
        "foot_width": 1.15,
        "neck_length": 0.75,
    },
    "heavy": {
        "height": 0.97,
        "shoulder_width": 1.30,
        "hip_width": 1.35,
        "limb_thickness": 1.50,
        "torso_depth": 1.45,
        "hand_size": 1.20,
        "foot_width": 1.25,
        "neck_length": 0.60,
        "torso_length": 1.10,
    },
}


# ─── Gender profiles (multiplier adjustments) ─────────────────────────────

GENDERS = {
    "neutral": {},  # no modifications — current default proportions
    "male": {
        "shoulder_width": 1.12,     # broader shoulders
        "hip_width": 0.92,          # narrower hips relative to shoulders
        "limb_thickness": 1.15,     # thicker arms and legs
        "torso_depth": 1.10,        # deeper chest front-to-back
        "neck_length": 0.85,        # shorter, thicker-looking neck
        "hand_size": 1.08,          # slightly larger hands
        "foot_width": 1.06,         # slightly wider feet
    },
    "female": {
        "shoulder_width": 0.92,     # narrower shoulders
        "hip_width": 1.12,          # wider hips
        "limb_thickness": 0.88,     # slimmer limbs
        "torso_depth": 0.92,        # narrower front-to-back
        "hand_size": 0.90,          # smaller hands
        "foot_length": 0.92,        # smaller feet
        "foot_width": 0.90,
    },
}


# ─── Skin tones ─────────────────────────────────────────────────────────────

SKIN_TONES = {
    "light":    (0.90, 0.75, 0.65, 1.0),
    "fair":     (0.82, 0.66, 0.54, 1.0),
    "medium":   (0.78, 0.60, 0.46, 1.0),
    "olive":    (0.62, 0.50, 0.35, 1.0),
    "tan":      (0.55, 0.42, 0.30, 1.0),
    "brown":    (0.45, 0.32, 0.22, 1.0),
    "dark":     (0.32, 0.22, 0.16, 1.0),
    # Game-specific tones
    "zombie":   (0.45, 0.55, 0.35, 1.0),
    "orc":      (0.30, 0.50, 0.25, 1.0),
    "frost":    (0.70, 0.78, 0.85, 1.0),
    "ember":    (0.65, 0.30, 0.18, 1.0),
    "shadow":   (0.20, 0.18, 0.22, 1.0),
}


# ─── Public API ─────────────────────────────────────────────────────────────

def get_preset_names():
    """Return sorted list of available preset names."""
    return sorted(PRESETS.keys())


def get_build_names():
    """Return sorted list of available build names."""
    return sorted(BUILDS.keys())


def get_skin_tone_names():
    """Return sorted list of available skin tone names."""
    return sorted(SKIN_TONES.keys())


def get_gender_names():
    """Return list of available gender names."""
    return sorted(GENDERS.keys())


def resolve_config(preset="average", build="average", gender="neutral",
                   skin_tone="medium",
                   hair_style="none", hair_color="dark_brown",
                   use_template=True, lod="low",
                   overrides=None, randomize=False, seed=None):
    """Build a complete character config from preset + build + gender + overrides.

    Args:
        preset: Name of the base preset (e.g., "tall", "brute").
        build: Body build modifier ("lean", "average", "stocky", "heavy").
        gender: Body gender ("neutral", "male", "female").
        skin_tone: Named skin tone or custom (R,G,B,A) tuple.
        hair_style: Hair style name ("none", "buzzed", "short", etc.).
        hair_color: Named hair color or custom (R,G,B,A) tuple.
        use_template: If True, import mesh from NBM .blend instead of
            building procedurally.
        lod: Level of detail for template mesh ("very_low", "low", "mid").
            Only used when use_template=True.
        overrides: Dict of individual config values to override.
        randomize: If True, add slight random variation to proportions.
        seed: Random seed for reproducible randomization.

    Returns:
        Complete config dict ready for generate().
    """
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset '{preset}'. Available: {get_preset_names()}")
    if build not in BUILDS:
        raise ValueError(f"Unknown build '{build}'. Available: {get_build_names()}")
    if gender not in GENDERS:
        raise ValueError(f"Unknown gender '{gender}'. Available: {get_gender_names()}")

    # Start from preset
    cfg = dict(PRESETS[preset])

    # Apply build multipliers
    build_mults = BUILDS[build]
    for key, mult in build_mults.items():
        if key in cfg:
            cfg[key] = cfg[key] * mult

    # Apply gender multipliers
    gender_mults = GENDERS[gender]
    for key, mult in gender_mults.items():
        if key in cfg:
            cfg[key] = cfg[key] * mult

    # Store gender in config for mesh.py to use for radii adjustments
    cfg["gender"] = gender

    # Template mesh settings
    cfg["use_template"] = use_template
    cfg["lod"] = lod

    # Resolve skin tone
    if isinstance(skin_tone, str):
        if skin_tone not in SKIN_TONES:
            raise ValueError(f"Unknown skin tone '{skin_tone}'. Available: {get_skin_tone_names()}")
        cfg["skin_tone"] = SKIN_TONES[skin_tone]
    else:
        cfg["skin_tone"] = tuple(skin_tone)

    # Resolve hair
    if isinstance(hair_style, str) and hair_style not in HAIR_STYLES:
        raise ValueError(f"Unknown hair style '{hair_style}'. Available: {list(HAIR_STYLES)}")
    cfg["hair_style"] = hair_style

    if isinstance(hair_color, str):
        if hair_color not in HAIR_COLORS:
            raise ValueError(f"Unknown hair color '{hair_color}'. Available: {get_hair_color_names()}")
        cfg["hair_color"] = hair_color
    else:
        cfg["hair_color"] = tuple(hair_color)

    # Add randomization for crowd variety
    if randomize:
        rng = random.Random(seed)
        _randomize_config(cfg, rng)

    # Apply user overrides last (highest priority)
    if overrides:
        cfg.update(overrides)

    return cfg


def _randomize_config(cfg, rng):
    """Add slight random variation to body proportions."""
    # ±5% on most dimensions, ±3% on height
    variance_map = {
        "height": 0.03,
        "shoulder_width": 0.05,
        "hip_width": 0.05,
        "head_size": 0.04,
        "arm_length": 0.04,
        "leg_length": 0.04,
        "torso_length": 0.04,
        "neck_length": 0.08,
        "hand_size": 0.06,
        "foot_length": 0.05,
        "foot_width": 0.05,
        "limb_thickness": 0.06,
        "torso_depth": 0.05,
    }
    for key, pct in variance_map.items():
        if key in cfg:
            factor = 1.0 + rng.uniform(-pct, pct)
            cfg[key] = cfg[key] * factor
