"""Low-poly humanoid generator for game assets."""

from .presets import (
    PRESETS, BUILDS, SKIN_TONES,
    get_preset_names, get_build_names, get_skin_tone_names,
    resolve_config,
)

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
    skin_tone = config.pop("skin_tone", "medium")
    anim_selection = config.pop("animations", "all")
    randomize = config.pop("randomize", False)
    seed = config.pop("seed", None)

    # Remaining config items become direct overrides
    cfg = resolve_config(
        preset=preset,
        build=build,
        skin_tone=skin_tone,
        overrides=config if config else None,
        randomize=randomize,
        seed=seed,
    )

    body = mesh.create_body(cfg)
    armature = rig.create_rig(cfg, body)

    if anim_selection == "all":
        animation.create_all_animations(armature, cfg)
    else:
        for anim_name in anim_selection:
            builder = animation.ANIMATIONS.get(anim_name)
            if builder:
                builder(armature, cfg)

    return armature
