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
    "average": {
        "height": 2.00,          # actual mesh height ~2.0m
        "shoulder_width": 0.36,
        "hip_width": 0.25,
        "head_size": 0.25,       # 4-head cartoon proportion matching Synty style
        "arm_length": 0.68,
        "leg_length": 0.88,
        "torso_length": 0.64,
        "neck_length": 0.10,     # longer neck for clearer neck silhouette
        "hand_size": 0.08,
        "foot_length": 0.24,
        "foot_width": 0.10,
        "limb_thickness": 1.0,
        "torso_depth": 0.22,     # slightly deeper torso for better front profile
    },
    "tall": {
        "height": 2.25,          # actual mesh height ~2.25m
        "shoulder_width": 0.38,
        "hip_width": 0.24,
        "head_size": 0.26,       # 4-head cartoon proportion
        "arm_length": 0.78,
        "leg_length": 1.02,
        "torso_length": 0.72,
        "neck_length": 0.12,
        "hand_size": 0.09,
        "foot_length": 0.27,
        "foot_width": 0.10,
        "limb_thickness": 0.95,
        "torso_depth": 0.22,
    },
    "short": {
        "height": 1.65,          # actual mesh height ~1.65m
        "shoulder_width": 0.31,
        "hip_width": 0.24,
        "head_size": 0.21,       # 4-head cartoon proportion
        "arm_length": 0.55,
        "leg_length": 0.72,
        "torso_length": 0.54,
        "neck_length": 0.08,
        "hand_size": 0.07,
        "foot_length": 0.20,
        "foot_width": 0.09,
        "limb_thickness": 1.05,
        "torso_depth": 0.21,
    },
    "child": {
        "height": 1.40,          # actual mesh height ~1.4m
        "shoulder_width": 0.26,
        "hip_width": 0.22,
        "head_size": 0.22,       # ~3.2-head proportion — chibi/cartoon child style
        "arm_length": 0.42,
        "leg_length": 0.52,
        "torso_length": 0.44,
        "neck_length": 0.06,
        "hand_size": 0.06,
        "foot_length": 0.16,
        "foot_width": 0.08,
        "limb_thickness": 0.85,
        "torso_depth": 0.16,
    },
    "brute": {
        "height": 2.20,          # actual mesh height ~2.2m
        "shoulder_width": 0.58,
        "hip_width": 0.35,
        "head_size": 0.20,       # slightly below 5-head — massive body reads bigger
        "arm_length": 0.82,
        "leg_length": 1.00,
        "torso_length": 0.76,
        "neck_length": 0.07,     # thick, short neck
        "hand_size": 0.12,
        "foot_length": 0.30,
        "foot_width": 0.14,
        "limb_thickness": 1.4,
        "torso_depth": 0.30,
    },
    "slender": {
        "height": 2.10,          # actual mesh height ~2.1m
        "shoulder_width": 0.29,
        "hip_width": 0.20,
        "head_size": 0.25,       # 4-head cartoon proportion
        "arm_length": 0.75,
        "leg_length": 0.98,
        "torso_length": 0.62,
        "neck_length": 0.12,     # long elegant neck
        "hand_size": 0.07,
        "foot_length": 0.23,
        "foot_width": 0.08,
        "limb_thickness": 0.75,
        "torso_depth": 0.18,
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
    "light":    (0.85, 0.72, 0.60, 1.0),
    "fair":     (0.76, 0.61, 0.48, 1.0),
    "medium":   (0.65, 0.50, 0.38, 1.0),
    "olive":    (0.58, 0.45, 0.30, 1.0),
    "tan":      (0.50, 0.38, 0.25, 1.0),
    "brown":    (0.40, 0.28, 0.18, 1.0),
    "dark":     (0.28, 0.18, 0.12, 1.0),
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
                   overrides=None, randomize=False, seed=None):
    """Build a complete character config from preset + build + gender + overrides.

    Args:
        preset: Name of the base preset (e.g., "tall", "brute").
        build: Body build modifier ("lean", "average", "stocky", "heavy").
        gender: Body gender ("neutral", "male", "female").
        skin_tone: Named skin tone or custom (R,G,B,A) tuple.
        hair_style: Hair style name ("none", "buzzed", "short", etc.).
        hair_color: Named hair color or custom (R,G,B,A) tuple.
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
