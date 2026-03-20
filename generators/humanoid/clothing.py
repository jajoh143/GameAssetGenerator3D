"""Low-poly clothing generation for humanoid characters.

Clothing is built as ring-based geometry that is MERGED into the single
body bmesh, matching the reference blend files (Characters_Matt.blend,
Characters_Shaun.blend) where clothing and body are one unified mesh.

The approach:
1. Build a clothing template bmesh using ring-based construction calibrated
   to the body proportions (same ring positions, slightly enlarged radii).
2. Merge clothing bmesh into the body bmesh in mesh.py BEFORE converting
   to a Blender object — resulting in one mesh, multiple material slots.

No BVH surface projection is used. Rings are directly sized to sit just
outside the body surface based on known body ring radii.

Available clothing types:
    - "tshirt":    Simple t-shirt covering torso and upper arms
    - "jacket":    Jacket covering torso and full arms with collar
    - "pants":     Trousers from waist to ankles
    - "shorts":    Short pants from waist to above knee
    - "armor":     Chest plate with separate shoulder pads
    - "robe":      Full-length robe from shoulders to ankles

Data constants (CLOTHING_TYPES, CLOTHING_COLORS) are importable without bpy.
Builder functions (build_clothing_bmesh_for_type) require bmesh.
"""

import math

# ─── Data constants (no bpy dependency) ────────────────────────────────────

CLOTHING_TYPES = ("none", "tshirt", "jacket", "pants", "shorts", "armor", "robe")

CLOTHING_COLORS = {
    "white":      (0.85, 0.85, 0.85, 1.0),
    "black":      (0.08, 0.08, 0.08, 1.0),
    "grey":       (0.40, 0.40, 0.40, 1.0),
    "red":        (0.65, 0.10, 0.10, 1.0),
    "blue":       (0.12, 0.20, 0.60, 1.0),
    "green":      (0.15, 0.45, 0.15, 1.0),
    "brown":      (0.35, 0.22, 0.10, 1.0),
    "tan":        (0.65, 0.55, 0.35, 1.0),
    "navy":       (0.08, 0.10, 0.30, 1.0),
    "purple":     (0.35, 0.12, 0.45, 1.0),
    "orange":     (0.75, 0.40, 0.08, 1.0),
    "yellow":     (0.80, 0.75, 0.15, 1.0),
    # Metal / armor
    "steel":      (0.55, 0.56, 0.58, 1.0),
    "gold":       (0.72, 0.60, 0.20, 1.0),
    "bronze":     (0.55, 0.40, 0.18, 1.0),
}

# Default color per clothing type
CLOTHING_DEFAULT_COLORS = {
    "tshirt":  "grey",
    "jacket":  "brown",
    "pants":   "navy",
    "shorts":  "tan",
    "armor":   "steel",
    "robe":    "brown",
}

# Ring vertex count (matches base_mesh.py)
RING_VERTS = 8


def get_clothing_type_names():
    """Return list of available clothing type names."""
    return list(CLOTHING_TYPES)


def get_clothing_color_names():
    """Return sorted list of available clothing color names."""
    return sorted(CLOTHING_COLORS.keys())


def resolve_clothing_rgba(ctype, color=None):
    """Return RGBA tuple for a clothing type + optional color override.

    Args:
        ctype: clothing type name (e.g. "tshirt")
        color: optional RGBA tuple, named color string, or None for default

    Returns:
        RGBA tuple (r, g, b, a)
    """
    if color is not None:
        if isinstance(color, str):
            return CLOTHING_COLORS.get(color, CLOTHING_COLORS["grey"])
        return tuple(color)
    default_name = CLOTHING_DEFAULT_COLORS.get(ctype, "grey")
    return CLOTHING_COLORS[default_name]


# ─── Ring helpers ───────────────────────────────────────────────────────────

def _make_ring(bm, center, rx, ry, n=RING_VERTS):
    """Create a ring of vertices in an elliptical cross-section."""
    verts = []
    cx, cy, cz = center
    for i in range(n):
        angle = 2 * math.pi * i / n
        lx = cx + rx * math.sin(angle)
        ly = cy - ry * math.cos(angle)
        verts.append(bm.verts.new((lx, ly, cz)))
    return verts


def _bridge_rings(bm, ring_a, ring_b):
    """Connect two rings with quad faces."""
    n = len(ring_a)
    assert len(ring_b) == n
    faces = []
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new([ring_a[i], ring_a[j], ring_b[j], ring_b[i]])
        faces.append(f)
    return faces


def _cap_ring(bm, ring, top=True):
    """Close an open ring end with a triangle fan pointing inward (hem/cuff)."""
    cx = sum(v.co.x for v in ring) / len(ring)
    cy = sum(v.co.y for v in ring) / len(ring)
    cz = sum(v.co.z for v in ring) / len(ring)
    center = bm.verts.new((cx, cy, cz))
    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        if not top:
            bm.faces.new([ring[j], ring[i], center])
        else:
            bm.faces.new([ring[i], ring[j], center])
    return center


# ─── Clothing template builders ─────────────────────────────────────────────
# Each builder constructs a bmesh at the correct world-space positions for
# the given body config, with ring radii scaled ~4–8% larger than the
# underlying body rings to sit cleanly outside the surface.
#
# Positions mirror _build_torso_rings / _build_leg / _build_arm in base_mesh.py.
# The scale factor replaces BVH surface projection — a fixed outward offset
# is sufficient for low-poly stylised characters and avoids z-fighting.

def _build_tshirt_template(cfg):
    """T-shirt: torso tube + short sleeve tubes down to elbow."""
    import bmesh as bmesh_mod
    bm = bmesh_mod.new()

    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    lt = cfg.get("limb_thickness", 1.0)
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    arm_len = cfg["arm_length"]

    foot_top = 0.06
    hip_z = foot_top + leg_len
    waist_z = hip_z + torso_len * 0.42
    lower_chest_z = hip_z + torso_len * 0.68
    chest_z = hip_z + torso_len

    # Shirt hem falls at lower abdomen (~25% up the torso)
    shirt_hem_z = hip_z + torso_len * 0.25

    # Scale factor: ~5% larger than body rings so clothing sits proud of skin.
    # This replaces BVH projection — no z-fighting and fast to compute.
    s = 1.05

    # Torso tube
    torso_specs = [
        (shirt_hem_z,   hw * 0.78 * s, td * 0.43 * s),
        (waist_z,       sw * 0.65 * s, td * 0.40 * s),
        (lower_chest_z, sw * 0.90 * s, td * 0.54 * s),
        (chest_z,       sw * 1.05 * s, td * 0.58 * s),
    ]
    torso_rings = []
    for z, rx, ry in torso_specs:
        torso_rings.append(_make_ring(bm, (0, 0, z), rx, ry))
    for i in range(len(torso_rings) - 1):
        _bridge_rings(bm, torso_rings[i], torso_rings[i + 1])
    _cap_ring(bm, torso_rings[0], top=False)   # hem — faces downward

    # Sleeve tubes: shoulder to elbow only (t-shirt length)
    shoulder_x = sw + 0.04
    arm_top_z = chest_z - 0.02
    upper_arm_len = arm_len * 0.48
    elbow_z = arm_top_z - upper_arm_len

    for sign in [1, -1]:
        sx = sign * shoulder_x
        sleeve_specs = [
            (arm_top_z,                        0.080 * lt * s, 0.070 * lt * s),
            (arm_top_z - upper_arm_len * 0.35, 0.074 * lt * s, 0.066 * lt * s),
            (arm_top_z - upper_arm_len * 0.70, 0.064 * lt * s, 0.060 * lt * s),
            (elbow_z,                          0.056 * lt * s, 0.054 * lt * s),
        ]
        sleeve_rings = []
        for z, rx, ry in sleeve_specs:
            sleeve_rings.append(_make_ring(bm, (sx, 0, z), rx, ry))
        for i in range(len(sleeve_rings) - 1):
            _bridge_rings(bm, sleeve_rings[i], sleeve_rings[i + 1])
        _cap_ring(bm, sleeve_rings[-1], top=False)   # sleeve cuff

    return bm


def _build_jacket_template(cfg):
    """Jacket: torso + full arms + raised collar."""
    import bmesh as bmesh_mod
    bm = bmesh_mod.new()

    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    lt = cfg.get("limb_thickness", 1.0)
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    arm_len = cfg["arm_length"]
    neck_len = cfg["neck_length"]
    head_r = cfg.get("head_size", 0.17)

    foot_top = 0.06
    hip_z = foot_top + leg_len
    lower_waist_z = hip_z + torso_len * 0.20
    waist_z = hip_z + torso_len * 0.42
    lower_chest_z = hip_z + torso_len * 0.68
    chest_z = hip_z + torso_len

    s = 1.08

    torso_specs = [
        (hip_z,         (hw + 0.04) * s,  td * 0.52 * s),
        (lower_waist_z, hw * 0.80 * s,    td * 0.44 * s),
        (waist_z,       sw * 0.65 * s,    td * 0.40 * s),
        (lower_chest_z, sw * 0.90 * s,    td * 0.54 * s),
        (chest_z,       sw * 1.05 * s,    td * 0.58 * s),
    ]
    torso_rings = []
    for z, rx, ry in torso_specs:
        torso_rings.append(_make_ring(bm, (0, 0, z), rx, ry))
    for i in range(len(torso_rings) - 1):
        _bridge_rings(bm, torso_rings[i], torso_rings[i + 1])
    _cap_ring(bm, torso_rings[0], top=False)

    # Collar ring
    collar_z = chest_z + neck_len * 0.35
    collar_rx = head_r * 0.40
    collar_ring = _make_ring(bm, (0, 0, collar_z), collar_rx, collar_rx * 0.90)
    _bridge_rings(bm, torso_rings[-1], collar_ring)
    _cap_ring(bm, collar_ring, top=True)

    # Full arm tubes: shoulder to wrist
    shoulder_x = sw + 0.04
    arm_top_z = chest_z - 0.02
    upper_arm_len = arm_len * 0.48
    elbow_z = arm_top_z - upper_arm_len
    lower_arm_len = arm_len * 0.52
    wrist_z = elbow_z - lower_arm_len

    for sign in [1, -1]:
        sx = sign * shoulder_x
        arm_specs = [
            (arm_top_z,                        0.080 * lt * s, 0.070 * lt * s),
            (arm_top_z - upper_arm_len * 0.5,  0.070 * lt * s, 0.064 * lt * s),
            (elbow_z,                          0.056 * lt * s, 0.056 * lt * s),
            (elbow_z - lower_arm_len * 0.3,    0.060 * lt * s, 0.056 * lt * s),
            (wrist_z,                          0.046 * lt * s, 0.042 * lt * s),
        ]
        arm_rings = []
        for z, rx, ry in arm_specs:
            arm_rings.append(_make_ring(bm, (sx, 0, z), rx, ry))
        for i in range(len(arm_rings) - 1):
            _bridge_rings(bm, arm_rings[i], arm_rings[i + 1])
        _cap_ring(bm, arm_rings[-1], top=False)

    return bm


def _build_pants_template(cfg):
    """Pants: waistband tube + separate leg tubes from hip to ankle."""
    import bmesh as bmesh_mod
    bm = bmesh_mod.new()

    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    lt = cfg.get("limb_thickness", 1.0)
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]

    foot_top = 0.06
    hip_z = foot_top + leg_len
    lower_waist_z = hip_z + torso_len * 0.20
    knee_z = foot_top + leg_len * 0.48
    thigh_z = hip_z - (hip_z - knee_z) * 0.35
    calf_z = knee_z - (knee_z - foot_top) * 0.30
    belt_z = hip_z + torso_len * 0.12
    crotch_z = hip_z - (hip_z - knee_z) * 0.15

    s = 1.05

    # Waistband / hip section
    waist_specs = [
        (lower_waist_z, hw * 0.80 * s, td * 0.44 * s),
        (belt_z,        hw * 0.90 * s, td * 0.48 * s),
        (hip_z,         (hw + 0.04) * s, td * 0.52 * s),
        (crotch_z,      (hw + 0.03) * s, td * 0.50 * s),
    ]
    waist_rings = []
    for z, rx, ry in waist_specs:
        waist_rings.append(_make_ring(bm, (0, 0, z), rx, ry))
    for i in range(len(waist_rings) - 1):
        _bridge_rings(bm, waist_rings[i], waist_rings[i + 1])
    _cap_ring(bm, waist_rings[0], top=True)   # waistband top — faces upward

    # Separate leg tubes
    for sign in [1, -1]:
        x = sign * hw
        leg_specs = [
            (hip_z,    0.114 * lt * s, 0.102 * lt * s),
            (thigh_z,  0.118 * lt * s, 0.102 * lt * s),
            (knee_z,   0.080 * lt * s, 0.078 * lt * s),
            (calf_z,   0.088 * lt * s, 0.080 * lt * s),
            (foot_top, 0.064 * lt * s, 0.062 * lt * s),
        ]
        leg_rings = []
        for z, rx, ry in leg_specs:
            leg_rings.append(_make_ring(bm, (x, 0, z), rx, ry))
        for i in range(len(leg_rings) - 1):
            _bridge_rings(bm, leg_rings[i], leg_rings[i + 1])
        _cap_ring(bm, leg_rings[-1], top=False)   # trouser cuff

    return bm


def _build_shorts_template(cfg):
    """Shorts: waistband + short leg tubes to mid-thigh."""
    import bmesh as bmesh_mod
    bm = bmesh_mod.new()

    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    lt = cfg.get("limb_thickness", 1.0)
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]

    foot_top = 0.06
    hip_z = foot_top + leg_len
    lower_waist_z = hip_z + torso_len * 0.20
    knee_z = foot_top + leg_len * 0.48
    thigh_z = hip_z - (hip_z - knee_z) * 0.35
    belt_z = hip_z + torso_len * 0.12
    crotch_z = hip_z - (hip_z - knee_z) * 0.15

    s = 1.06

    waist_specs = [
        (lower_waist_z, hw * 0.80 * s, td * 0.44 * s),
        (belt_z,        hw * 0.90 * s, td * 0.48 * s),
        (hip_z,         (hw + 0.04) * s, td * 0.52 * s),
        (crotch_z,      (hw + 0.03) * s, td * 0.50 * s),
    ]
    waist_rings = []
    for z, rx, ry in waist_specs:
        waist_rings.append(_make_ring(bm, (0, 0, z), rx, ry))
    for i in range(len(waist_rings) - 1):
        _bridge_rings(bm, waist_rings[i], waist_rings[i + 1])
    _cap_ring(bm, waist_rings[0], top=True)

    # Short leg tubes ending at mid-thigh
    for sign in [1, -1]:
        x = sign * hw
        leg_specs = [
            (hip_z,    0.114 * lt * s, 0.102 * lt * s),
            (thigh_z,  0.118 * lt * s, 0.102 * lt * s),
            (knee_z,   0.084 * lt * s, 0.080 * lt * s),
        ]
        leg_rings = []
        for z, rx, ry in leg_specs:
            leg_rings.append(_make_ring(bm, (x, 0, z), rx, ry))
        for i in range(len(leg_rings) - 1):
            _bridge_rings(bm, leg_rings[i], leg_rings[i + 1])
        _cap_ring(bm, leg_rings[-1], top=False)

    return bm


def _build_armor_template(cfg):
    """Armor: thick chest plate with separate shoulder pads."""
    import bmesh as bmesh_mod
    bm = bmesh_mod.new()

    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    lt = cfg.get("limb_thickness", 1.0)
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]

    foot_top = 0.06
    hip_z = foot_top + leg_len
    lower_waist_z = hip_z + torso_len * 0.20
    waist_z = hip_z + torso_len * 0.42
    lower_chest_z = hip_z + torso_len * 0.68
    chest_z = hip_z + torso_len

    s = 1.12

    torso_specs = [
        (hip_z,         (hw + 0.04) * s,  td * 0.52 * s),
        (lower_waist_z, hw * 0.80 * s,    td * 0.44 * s),
        (waist_z,       sw * 0.65 * s,    td * 0.40 * s),
        (lower_chest_z, sw * 0.90 * s,    td * 0.54 * s),
        (chest_z,       sw * 1.05 * s,    td * 0.58 * s),
    ]
    torso_rings = []
    for z, rx, ry in torso_specs:
        torso_rings.append(_make_ring(bm, (0, 0, z), rx, ry))
    for i in range(len(torso_rings) - 1):
        _bridge_rings(bm, torso_rings[i], torso_rings[i + 1])
    _cap_ring(bm, torso_rings[0], top=False)

    # Shoulder pads
    shoulder_x = sw + 0.04
    arm_top_z = chest_z - 0.02

    for sign in [1, -1]:
        sx = sign * shoulder_x
        pad_specs = [
            (arm_top_z,        0.092 * lt * s, 0.082 * lt * s),
            (arm_top_z - 0.10, 0.080 * lt * s, 0.070 * lt * s),
        ]
        pad_rings = []
        for z, rx, ry in pad_specs:
            pad_rings.append(_make_ring(bm, (sx, 0, z), rx, ry))
        for i in range(len(pad_rings) - 1):
            _bridge_rings(bm, pad_rings[i], pad_rings[i + 1])
        _cap_ring(bm, pad_rings[-1], top=False)

    return bm


def _build_robe_template(cfg):
    """Robe: full torso + skirt + loose sleeve tubes."""
    import bmesh as bmesh_mod
    bm = bmesh_mod.new()

    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    lt = cfg.get("limb_thickness", 1.0)
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    arm_len = cfg["arm_length"]

    foot_top = 0.06
    hip_z = foot_top + leg_len
    lower_waist_z = hip_z + torso_len * 0.20
    waist_z = hip_z + torso_len * 0.42
    lower_chest_z = hip_z + torso_len * 0.68
    chest_z = hip_z + torso_len

    s = 1.06

    body_specs = [
        (foot_top + 0.10, hw + 0.18,          td * 0.65),
        (hip_z * 0.70,    hw + 0.12,          td * 0.60),
        (hip_z,           (hw + 0.05) * s,    td * 0.55 * s),
        (lower_waist_z,   hw * 0.80 * s,      td * 0.44 * s),
        (waist_z,         sw * 0.65 * s,      td * 0.40 * s),
        (lower_chest_z,   sw * 0.90 * s,      td * 0.54 * s),
        (chest_z,         sw * 1.05 * s,      td * 0.58 * s),
    ]
    body_rings = []
    for z, rx, ry in body_specs:
        body_rings.append(_make_ring(bm, (0, 0, z), rx, ry))
    for i in range(len(body_rings) - 1):
        _bridge_rings(bm, body_rings[i], body_rings[i + 1])
    _cap_ring(bm, body_rings[0], top=False)

    # Loose sleeve tubes
    shoulder_x = sw + 0.04
    arm_top_z = chest_z - 0.02
    upper_arm_len = arm_len * 0.48
    elbow_z = arm_top_z - upper_arm_len
    lower_arm_len = arm_len * 0.52
    forearm_z = elbow_z - lower_arm_len * 0.3

    for sign in [1, -1]:
        sx = sign * shoulder_x
        arm_specs = [
            (arm_top_z,                        0.080 * lt * s, 0.072 * lt * s),
            (arm_top_z - upper_arm_len * 0.5,  0.072 * lt * s, 0.066 * lt * s),
            (elbow_z,                          0.060 * lt * s, 0.060 * lt * s),
            (forearm_z,                        0.062 * lt * s, 0.058 * lt * s),
        ]
        arm_rings = []
        for z, rx, ry in arm_specs:
            arm_rings.append(_make_ring(bm, (sx, 0, z), rx, ry))
        for i in range(len(arm_rings) - 1):
            _bridge_rings(bm, arm_rings[i], arm_rings[i + 1])
        _cap_ring(bm, arm_rings[-1], top=False)

    return bm


# ─── Template dispatch ──────────────────────────────────────────────────────

_TEMPLATE_BUILDERS = {
    "tshirt":  _build_tshirt_template,
    "jacket":  _build_jacket_template,
    "pants":   _build_pants_template,
    "shorts":  _build_shorts_template,
    "armor":   _build_armor_template,
    "robe":    _build_robe_template,
}


def build_clothing_bmesh_for_type(cfg, ctype):
    """Build a clothing bmesh for a single clothing type.

    Returns a new bmesh (caller must free). Returns None for unknown types.
    """
    builder = _TEMPLATE_BUILDERS.get(ctype)
    if builder is None:
        return None
    return builder(cfg)


# ─── Backward-compat stub ───────────────────────────────────────────────────

def create_clothing(cfg, clothing_spec, color=None):
    """DEPRECATED — clothing is now merged into the body mesh in mesh.py.

    Returns an empty list so existing callers that iterate the result
    continue to work without modification.
    """
    return []
