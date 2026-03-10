"""Low-poly humanoid generator for game assets."""

# Available animations (importable without bpy)
AVAILABLE_ANIMATIONS = ("idle", "walk", "run", "jump", "attack")


def generate(config=None):
    """Generate a complete rigged and animated humanoid.

    Args:
        config: Optional dict of overrides (height, proportions, etc.)
            Special keys:
                animations: list of animation names to generate, or "all".
                            Defaults to "all".

    Returns:
        The armature object (which parents the mesh).
    """
    from . import mesh, rig, animation

    cfg = {
        "height": 1.8,
        "shoulder_width": 0.42,
        "hip_width": 0.28,
        "head_size": 0.22,
        "arm_length": 0.7,
        "leg_length": 0.9,
        "torso_length": 0.55,
        "neck_length": 0.08,
        "hand_size": 0.08,
        "foot_length": 0.24,
        "foot_width": 0.1,
    }
    if config:
        cfg.update(config)

    # Extract animation selection before passing to mesh/rig
    anim_selection = cfg.pop("animations", "all")

    body = mesh.create_body(cfg)
    armature = rig.create_rig(cfg, body)

    if anim_selection == "all":
        animation.create_all_animations(armature, cfg)
    else:
        # Generate only the requested animations
        for anim_name in anim_selection:
            builder = animation.ANIMATIONS.get(anim_name)
            if builder:
                builder(armature, cfg)

    return armature
