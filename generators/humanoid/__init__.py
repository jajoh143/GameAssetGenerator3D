"""Low-poly humanoid generator for game assets."""

from . import mesh, rig, animation


def generate(config=None):
    """Generate a complete rigged and animated humanoid.

    Args:
        config: Optional dict of overrides (height, proportions, etc.)

    Returns:
        The armature object (which parents the mesh).
    """
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

    body = mesh.create_body(cfg)
    armature = rig.create_rig(cfg, body)
    animation.create_walk_cycle(armature, cfg)

    return armature
