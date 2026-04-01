"""Low-poly clothing generation for humanoid characters.

Available clothing types:
    - "short_sleeve":  Crew-neck shirt with sleeves to mid-upper-arm
    - "long_sleeve":   Crew-neck shirt with sleeves to wrist
    - "v_neck":        V-neck shirt with sleeves to wrist
    - "shorts":        Short pants from waist to just above knee
    - "jeans":         Full-length trousers from waist to ankle

Data constants (CLOTHING_TYPES, CLOTHING_COLORS) are importable without bpy.
Builder functions (build_clothing_bmesh_for_type) require bmesh.
"""

import math

CLOTHING_TYPES = ("none", "short_sleeve", "long_sleeve", "v_neck", "shorts", "jeans")

CLOTHING_COLORS = {
    "white":      (0.90, 0.90, 0.90, 1.0),
    "black":      (0.06, 0.06, 0.08, 1.0),
    "grey":       (0.50, 0.52, 0.55, 1.0),
    "red":        (0.80, 0.10, 0.10, 1.0),
    "blue":       (0.15, 0.30, 0.75, 1.0),
    "green":      (0.20, 0.60, 0.25, 1.0),
    "brown":      (0.32, 0.20, 0.10, 1.0),
    "tan":        (0.68, 0.56, 0.35, 1.0),
    "navy":       (0.08, 0.10, 0.38, 1.0),
    "purple":     (0.45, 0.15, 0.58, 1.0),
    "orange":     (0.85, 0.48, 0.10, 1.0),
    "yellow":     (0.90, 0.82, 0.18, 1.0),
    "denim":      (0.20, 0.30, 0.55, 1.0),
    "light_denim": (0.40, 0.52, 0.72, 1.0),
}

CLOTHING_DEFAULT_COLORS = {
    "short_sleeve": "red",
    "long_sleeve":  "white",
    "v_neck":       "navy",
    "shorts":       "tan",
    "jeans":        "denim",
}

RING_VERTS = 8


def get_clothing_type_names():
    return list(CLOTHING_TYPES)


def get_clothing_color_names():
    return sorted(CLOTHING_COLORS.keys())


def resolve_clothing_rgba(ctype, color=None):
    if color is not None:
        if isinstance(color, str):
            return CLOTHING_COLORS.get(color, CLOTHING_COLORS["grey"])
        return tuple(color)
    default_name = CLOTHING_DEFAULT_COLORS.get(ctype, "grey")
    return CLOTHING_COLORS[default_name]


# ─── Ring helpers ────────────────────────────────────────────────────────────

def _make_ring(bm, center, rx, ry, n=RING_VERTS):
    verts = []
    cx, cy, cz = center
    for i in range(n):
        angle = 2 * math.pi * i / n
        lx = cx + rx * math.sin(angle)
        ly = cy - ry * math.cos(angle)
        verts.append(bm.verts.new((lx, ly, cz)))
    return verts


def _bridge_rings(bm, ring_a, ring_b):
    n = len(ring_a)
    faces = []
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new([ring_a[i], ring_a[j], ring_b[j], ring_b[i]])
        faces.append(f)
    return faces


def _cap_ring(bm, ring, top=True):
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


def _torso_rings(bm, cfg, s, hem_fraction):
    """Build the shared torso tube. hem_fraction controls hem height (0=hip, 1=mid-torso)."""
    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    foot_top = 0.06
    hip_z = foot_top + leg_len
    hem_z = hip_z + torso_len * hem_fraction
    waist_z = hip_z + torso_len * 0.42
    lower_chest_z = hip_z + torso_len * 0.68
    chest_z = hip_z + torso_len

    specs = [
        (hem_z,         hw * 0.80 * s,  td * 0.44 * s),
        (waist_z,       sw * 0.65 * s,  td * 0.40 * s),
        (lower_chest_z, sw * 0.90 * s,  td * 0.54 * s),
        (chest_z,       sw * 1.05 * s,  td * 0.58 * s),
    ]
    rings = []
    for z, rx, ry in specs:
        rings.append(_make_ring(bm, (0, 0, z), rx, ry))
    for i in range(len(rings) - 1):
        _bridge_rings(bm, rings[i], rings[i + 1])
    _cap_ring(bm, rings[0], top=False)
    return rings, hip_z + torso_len  # return rings and chest_z


def _sleeve_rings(bm, cfg, s, to_wrist=True):
    """Build both sleeves. to_wrist=True → full sleeve; False → mid-upper-arm."""
    sw = cfg["shoulder_width"]
    lt = cfg.get("limb_thickness", 1.0)
    arm_len = cfg["arm_length"]
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    foot_top = 0.06
    chest_z = foot_top + leg_len + torso_len
    shoulder_x = sw + 0.04
    arm_top_z = chest_z - 0.02
    upper_arm_len = arm_len * 0.48
    elbow_z = arm_top_z - upper_arm_len
    lower_arm_len = arm_len * 0.52
    wrist_z = elbow_z - lower_arm_len

    for sign in [1, -1]:
        sx = sign * shoulder_x
        if to_wrist:
            specs = [
                (arm_top_z,                        0.080 * lt * s, 0.070 * lt * s),
                (arm_top_z - upper_arm_len * 0.45, 0.072 * lt * s, 0.064 * lt * s),
                (elbow_z,                          0.058 * lt * s, 0.054 * lt * s),
                (elbow_z - lower_arm_len * 0.40,   0.060 * lt * s, 0.054 * lt * s),
                (wrist_z,                          0.046 * lt * s, 0.042 * lt * s),
            ]
        else:
            # Short sleeve: shoulder to mid-upper arm only
            mid_arm_z = arm_top_z - upper_arm_len * 0.45
            specs = [
                (arm_top_z,                        0.080 * lt * s, 0.070 * lt * s),
                (arm_top_z - upper_arm_len * 0.25, 0.076 * lt * s, 0.068 * lt * s),
                (mid_arm_z,                        0.068 * lt * s, 0.062 * lt * s),
            ]
        sleeve_rings = []
        for z, rx, ry in specs:
            sleeve_rings.append(_make_ring(bm, (sx, 0, z), rx, ry))
        for i in range(len(sleeve_rings) - 1):
            _bridge_rings(bm, sleeve_rings[i], sleeve_rings[i + 1])
        _cap_ring(bm, sleeve_rings[-1], top=False)


def _build_short_sleeve(cfg):
    """Crew-neck shirt with short sleeves ending at mid-upper arm."""
    import bmesh as bmesh_mod
    bm = bmesh_mod.new()
    s = 1.25
    _torso_rings(bm, cfg, s, hem_fraction=0.22)
    _sleeve_rings(bm, cfg, s, to_wrist=False)
    return bm


def _build_long_sleeve(cfg):
    """Crew-neck shirt with full sleeves to the wrist."""
    import bmesh as bmesh_mod
    bm = bmesh_mod.new()
    s = 1.22
    _torso_rings(bm, cfg, s, hem_fraction=0.18)
    _sleeve_rings(bm, cfg, s, to_wrist=True)
    return bm


def _build_v_neck(cfg):
    """V-neck shirt with full sleeves and a V-shaped neckline.

    The V-neck is created by pulling the 3 front vertices of the top
    torso ring downward to form the V dip, then capping the resulting
    open neckline with a simple triangle fan.
    """
    import bmesh as bmesh_mod
    bm = bmesh_mod.new()
    s = 1.22

    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    td = cfg.get("torso_depth", 0.20)
    lt = cfg.get("limb_thickness", 1.0)
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    arm_len = cfg["arm_length"]
    foot_top = 0.06
    hip_z = foot_top + leg_len
    hem_z = hip_z + torso_len * 0.18
    waist_z = hip_z + torso_len * 0.42
    lower_chest_z = hip_z + torso_len * 0.68
    chest_z = hip_z + torso_len

    # Torso tube
    specs = [
        (hem_z,         hw * 0.80 * s,  td * 0.44 * s),
        (waist_z,       sw * 0.65 * s,  td * 0.40 * s),
        (lower_chest_z, sw * 0.90 * s,  td * 0.54 * s),
        (chest_z,       sw * 1.05 * s,  td * 0.58 * s),
    ]
    rings = []
    for z, rx, ry in specs:
        rings.append(_make_ring(bm, (0, 0, z), rx, ry))
    for i in range(len(rings) - 1):
        _bridge_rings(bm, rings[i], rings[i + 1])
    _cap_ring(bm, rings[0], top=False)

    # V-neck: pull the front-centre vertex of the top ring downward
    # Ring vertex 0 = front, n//4 = left, n//2 = back, 3n//4 = right
    top_ring = rings[-1]
    n = len(top_ring)
    v_depth = torso_len * 0.22   # how deep the V drops below chest_z
    # Front 3 vertices (index n-1, 0, 1) get pulled down proportionally
    for offset, fraction in [(-1, 0.55), (0, 1.00), (1, 0.55)]:
        idx = offset % n
        top_ring[idx].co.z -= v_depth * fraction

    # Build a second ring slightly above the chest ring for the collar band
    collar_rx = sw * 0.38 * s
    collar_ry = td * 0.28 * s
    collar_z = chest_z + torso_len * 0.04
    collar_ring = _make_ring(bm, (0, 0, collar_z), collar_rx, collar_ry)
    # Bridge back/side verts only (skip front 3) to form the back collar band
    back_start = 2
    back_end = n - 1
    for i in range(back_start, back_end):
        j = i + 1
        try:
            bm.faces.new([top_ring[i], top_ring[j], collar_ring[j], collar_ring[i]])
        except ValueError:
            pass
    _cap_ring(bm, collar_ring, top=True)

    # Sleeves
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
            (arm_top_z - upper_arm_len * 0.45, 0.072 * lt * s, 0.064 * lt * s),
            (elbow_z,                          0.058 * lt * s, 0.054 * lt * s),
            (elbow_z - lower_arm_len * 0.40,   0.060 * lt * s, 0.054 * lt * s),
            (wrist_z,                          0.046 * lt * s, 0.042 * lt * s),
        ]
        arm_rings = []
        for z, rx, ry in arm_specs:
            arm_rings.append(_make_ring(bm, (sx, 0, z), rx, ry))
        for i in range(len(arm_rings) - 1):
            _bridge_rings(bm, arm_rings[i], arm_rings[i + 1])
        _cap_ring(bm, arm_rings[-1], top=False)

    return bm


def _build_shorts(cfg):
    """Shorts: waistband + short leg tubes ending just above the knee."""
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
    short_hem_z = hip_z - (hip_z - knee_z) * 0.60  # just above knee
    belt_z = hip_z + torso_len * 0.12
    crotch_z = hip_z - (hip_z - knee_z) * 0.15

    s = 1.25

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

    for sign in [1, -1]:
        x = sign * hw
        leg_specs = [
            (hip_z,      0.114 * lt * s, 0.102 * lt * s),
            (thigh_z,    0.118 * lt * s, 0.102 * lt * s),
            (short_hem_z, 0.090 * lt * s, 0.084 * lt * s),
        ]
        leg_rings = []
        for z, rx, ry in leg_specs:
            leg_rings.append(_make_ring(bm, (x, 0, z), rx, ry))
        for i in range(len(leg_rings) - 1):
            _bridge_rings(bm, leg_rings[i], leg_rings[i + 1])
        _cap_ring(bm, leg_rings[-1], top=False)

    return bm


def _build_jeans(cfg):
    """Jeans: waistband + full leg tubes from hip to ankle."""
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

    s = 1.25

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
        _cap_ring(bm, leg_rings[-1], top=False)

    return bm


_TEMPLATE_BUILDERS = {
    "short_sleeve": _build_short_sleeve,
    "long_sleeve":  _build_long_sleeve,
    "v_neck":       _build_v_neck,
    "shorts":       _build_shorts,
    "jeans":        _build_jeans,
}


def build_clothing_bmesh_for_type(cfg, ctype):
    builder = _TEMPLATE_BUILDERS.get(ctype)
    if builder is None:
        return None
    return builder(cfg)


def create_clothing(cfg, clothing_spec, color=None):
    """DEPRECATED — clothing is now merged into the body mesh in mesh.py."""
    return []
