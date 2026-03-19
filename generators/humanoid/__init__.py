"""Low-poly humanoid generator for game assets."""

from .presets import (
    PRESETS, BUILDS, SKIN_TONES,
    get_preset_names, get_build_names, get_skin_tone_names,
    resolve_config,
)
from .hair import (
    HAIR_STYLES, HAIR_COLORS,
    get_hair_style_names, get_hair_color_names,
)
from .clothing import CLOTHING_TYPES, get_clothing_type_names

# Available animations (importable without bpy)
AVAILABLE_ANIMATIONS = ("idle", "walk", "run", "jump", "attack")


def generate(config=None):
    """Generate a complete rigged and animated humanoid.

    Args:
        config: Optional dict of overrides (height, proportions, etc.)
            Special keys:
                preset: Base character archetype name (default: "average").
                build: Body build modifier (default: "average").
                skin_tone: Named skin tone or RGBA tuple (default: "medium").
                animations: List of animation names or "all" (default: "all").
                randomize: Bool — add slight random variation (default: False).
                seed: Int — random seed for reproducible variation.
            All other keys override the resolved body proportions directly.

    Returns:
        The armature object (which parents the mesh).
    """
    from . import mesh, rig, animation

    config = config or {}

    # Extract control keys before resolving
    preset = config.pop("preset", "average")
    build = config.pop("build", "average")
    gender = config.pop("gender", "neutral")
    skin_tone = config.pop("skin_tone", "medium")
    hair_style = config.pop("hair_style", "short")
    hair_color = config.pop("hair_color", "brown")
    clothing = config.pop("clothing", "tshirt,pants")
    clothing_color = config.pop("clothing_color", None)
    anim_selection = config.pop("animations", "all")
    randomize = config.pop("randomize", False)
    seed = config.pop("seed", None)

    # Remaining config items become direct overrides
    cfg = resolve_config(
        preset=preset,
        build=build,
        gender=gender,
        skin_tone=skin_tone,
        hair_style=hair_style,
        hair_color=hair_color,
        overrides=config if config else None,
        randomize=randomize,
        seed=seed,
    )

    # Store clothing in resolved config so mesh.py can use it
    cfg["clothing"] = clothing
    cfg["clothing_color"] = clothing_color

    # Clothing is merged into the body mesh (single unified object matching
    # reference blend files).  The third return value is always [] now.
    body, hair_obj, clothing_objs = mesh.create_body(cfg)
    armature = rig.create_rig(cfg, body, hair_obj, clothing_objs)

    if anim_selection == "all":
        animation.create_all_animations(armature, cfg)
    else:
        for anim_name in anim_selection:
            builder = animation.ANIMATIONS.get(anim_name)
            if builder:
                builder(armature, cfg)

    return armature
