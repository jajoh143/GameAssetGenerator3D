"""Morph target system for body variation.

Provides vertex-delta-based body morphing inspired by MB-Lab. Instead of
rebuilding the entire mesh for each body variation, the base mesh is built
once with neutral proportions, then morph deltas are applied additively
to shift vertex positions for gender, build, and preset variation.

Each morph target is a dict: {vertex_index: (dx, dy, dz)}

Morphs are generated procedurally by building the base mesh with variant
configs and computing the difference from the neutral base. This means
morph data is always consistent with the mesh topology.

Usage:
    from .base_mesh import build_base_mesh
    from .morphs import config_to_morphs, apply_morphs

    bm, vertex_groups = build_base_mesh()
    morphs = config_to_morphs(cfg)
    apply_morphs(bm, morphs)
"""

def compute_morph_deltas(base_positions, target_positions, threshold=1e-6):
    """Compare two vertex position lists and return delta dict.

    Args:
        base_positions: list of (x, y, z) tuples for base mesh
        target_positions: list of (x, y, z) tuples for target mesh
        threshold: minimum delta magnitude to include (skip zero-change verts)

    Returns:
        Dict mapping vertex_index to (dx, dy, dz) delta tuple.
    """
    assert len(base_positions) == len(target_positions), \
        f"Vertex count mismatch: {len(base_positions)} vs {len(target_positions)}"

    deltas = {}
    for i, (base, target) in enumerate(zip(base_positions, target_positions)):
        dx = target[0] - base[0]
        dy = target[1] - base[1]
        dz = target[2] - base[2]
        if abs(dx) > threshold or abs(dy) > threshold or abs(dz) > threshold:
            deltas[i] = (dx, dy, dz)

    return deltas


def apply_morphs(bm, morph_deltas_list):
    """Apply a list of morph delta dicts to a bmesh.

    Each entry in morph_deltas_list is a dict {vert_index: (dx, dy, dz)}.
    Deltas are applied additively — order doesn't matter for additive morphs.

    Args:
        bm: bmesh with base mesh topology
        morph_deltas_list: list of morph delta dicts to apply
    """
    bm.verts.ensure_lookup_table()
    for deltas in morph_deltas_list:
        for vi, (dx, dy, dz) in deltas.items():
            if vi < len(bm.verts):
                bm.verts[vi].co.x += dx
                bm.verts[vi].co.y += dy
                bm.verts[vi].co.z += dz


def config_to_morphs(cfg):
    """Convert a resolved config dict into a list of morph deltas.

    Builds the base mesh with neutral config, then builds with the target
    config, and returns the delta between them.

    This is the main entry point — it produces exactly one morph that
    transforms the neutral base mesh into the target body shape.

    Args:
        cfg: resolved config dict (from resolve_config())

    Returns:
        List containing a single morph delta dict that transforms
        the neutral base to the target config's shape.
    """
    from .base_mesh import build_base_mesh_positions
    from .presets import PRESETS

    # Build neutral base positions
    neutral_cfg = dict(PRESETS["average"])
    neutral_cfg["gender"] = "neutral"
    base_positions = build_base_mesh_positions(neutral_cfg)

    # Build target positions with the given config
    target_positions = build_base_mesh_positions(cfg)

    # Compute delta
    deltas = compute_morph_deltas(base_positions, target_positions)

    if deltas:
        return [deltas]
    return []


def is_neutral_config(cfg):
    """Check if a config is equivalent to the neutral average (no morphing needed).

    Args:
        cfg: resolved config dict

    Returns:
        True if the config matches neutral average proportions.
    """
    from .presets import PRESETS

    neutral = PRESETS["average"]
    proportion_keys = [
        "shoulder_width", "hip_width", "head_size", "arm_length",
        "leg_length", "torso_length", "neck_length", "hand_size",
        "foot_length", "foot_width", "limb_thickness", "torso_depth",
    ]

    for key in proportion_keys:
        if abs(cfg.get(key, neutral[key]) - neutral[key]) > 1e-4:
            return False

    return cfg.get("gender", "neutral") == "neutral"
