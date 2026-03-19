"""Low-poly hair generation using bmesh ring-based construction.

Each style is built as a single bmesh that closely follows the head geometry
defined in base_mesh.py.  Ring positions and dimensions match the head rings
but are scaled outward (style-dependent thickness) so hair sits cleanly
outside the skull surface with no z-fighting.

The cap is an open-bottomed dome from hairline to crown.  Style extensions
(fringe, back panels, side curtains, spikes) are built as additional bmesh
regions merged into the same bmesh before conversion to a Blender object.

Available styles: buzzed, short, spiky, long, mohawk
Data constants (HAIR_STYLES, HAIR_COLORS) are importable without bpy.
Builder functions and create_hair() require Blender's Python environment.
"""

import math

# ─── Data constants (no bpy dependency) ────────────────────────────────────

HAIR_STYLES = ("none", "buzzed", "short", "spiky", "long", "mohawk")

HAIR_COLORS = {
    "black":      (0.05, 0.04, 0.04, 1.0),
    "dark_brown": (0.18, 0.10, 0.06, 1.0),
    "brown":      (0.30, 0.18, 0.08, 1.0),
    "auburn":     (0.42, 0.16, 0.08, 1.0),
    "red":        (0.55, 0.12, 0.06, 1.0),
    "blonde":     (0.72, 0.58, 0.30, 1.0),
    "platinum":   (0.85, 0.82, 0.72, 1.0),
    "white":      (0.90, 0.88, 0.85, 1.0),
    "grey":       (0.50, 0.48, 0.46, 1.0),
    "blue":       (0.15, 0.25, 0.65, 1.0),
    "green":      (0.12, 0.50, 0.18, 1.0),
    "purple":     (0.40, 0.12, 0.55, 1.0),
    "pink":       (0.75, 0.30, 0.50, 1.0),
}


def get_hair_style_names():
    return list(HAIR_STYLES)


def get_hair_color_names():
    return sorted(HAIR_COLORS.keys())


# ─── bmesh geometry helpers ─────────────────────────────────────────────────
# These mirror base_mesh.py helpers but are local so hair.py is self-contained.

def _make_ring(bm, center, rx, ry, n=8):
    """Octagonal (or n-gon) cross-section ring."""
    verts = []
    cx, cy, cz = center
    for i in range(n):
        angle = 2 * math.pi * i / n
        verts.append(bm.verts.new((
            cx + rx * math.sin(angle),
            cy - ry * math.cos(angle),
            cz,
        )))
    return verts


def _bridge_rings(bm, ring_a, ring_b):
    """Connect two same-size rings with quad faces."""
    n = len(ring_a)
    assert len(ring_b) == n
    for i in range(n):
        j = (i + 1) % n
        try:
            bm.faces.new([ring_a[i], ring_a[j], ring_b[j], ring_b[i]])
        except ValueError:
            pass


def _cap_ring(bm, ring, top=True):
    """Close a ring with a triangle fan."""
    cx = sum(v.co.x for v in ring) / len(ring)
    cy = sum(v.co.y for v in ring) / len(ring)
    cz = sum(v.co.z for v in ring) / len(ring)
    center = bm.verts.new((cx, cy, cz))
    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        try:
            if top:
                bm.faces.new([ring[i], ring[j], center])
            else:
                bm.faces.new([ring[j], ring[i], center])
        except ValueError:
            pass
    return center


# ─── Head ring reference dimensions (from base_mesh.py) ────────────────────
#
# All positions relative to head_z (= neck_z + head_r = head centre Z).
# z_offset is multiplied by head_r and added to head_z.
#
# Level          z_offset  rx_mult  ry_mult
# brow (hairline)   0.00    0.88     0.82
# forehead          0.28    0.74     0.68
# upper cranium     0.58    0.54     0.50
# crown             0.90    0.31     0.28
#
# Hair cap rings scale each rx/ry by H (the hair thickness factor) so the
# hair shell sits cleanly outside the head at each level.


def _build_cap(bm, head_z, head_r, h_scale=1.07):
    """Build the base hair cap dome from hairline to crown.

    Returns the four rings as a list [hairline, forehead, upper, crown].
    The hairline ring is open (no bottom cap) — head skin shows below it.
    Crown ring is closed with a triangle fan.
    """
    ring_defs = [
        # (z_offset_mult, rx_mult, ry_mult)
        (0.00, 0.88 * h_scale, 0.82 * h_scale),  # hairline (at brow level)
        (0.28, 0.74 * h_scale, 0.68 * h_scale),  # forehead
        (0.58, 0.54 * h_scale, 0.50 * h_scale),  # upper cranium
        (0.90, 0.31 * h_scale, 0.28 * h_scale),  # crown
    ]
    rings = []
    for z_off, rx_m, ry_m in ring_defs:
        z = head_z + head_r * z_off
        rings.append(_make_ring(bm, (0, 0, z), head_r * rx_m, head_r * ry_m))

    for i in range(len(rings) - 1):
        _bridge_rings(bm, rings[i], rings[i + 1])

    _cap_ring(bm, rings[-1], top=True)  # close crown

    return rings  # rings[0] = hairline ring


# ─── Ring index reference for an 8-vert ring centred at (0,0,z)
# _make_ring uses angle = 2*pi*i/n, lx = rx*sin(angle), ly = -ry*cos(angle)
# i=0: front (y most negative, face direction)
# i=1: front-right (+x, -y)    i=2: right (+x)
# i=3: back-right (+x, +y)     i=4: back (y most positive)
# i=5: back-left (-x, +y)      i=6: left (-x)
# i=7: front-left (-x, -y)


def _back_verts(ring):
    """Return the 3 back-facing verts of an 8-vert ring (indices 3, 4, 5)."""
    return [ring[3], ring[4], ring[5]]


def _left_verts(ring):
    """Verts on the +X (character left) side (indices 1, 2, 3)."""
    return [ring[1], ring[2], ring[3]]


def _right_verts(ring):
    """Verts on the -X (character right) side (indices 5, 6, 7)."""
    return [ring[5], ring[6], ring[7]]


def _front_verts(ring):
    """Verts on the front face side (indices 7, 0, 1)."""
    return [ring[7], ring[0], ring[1]]


def _extend_strip(bm, top_verts, z_offsets, x_scale=1.0, y_scale=1.0):
    """Build a tapered panel below a strip of verts.

    Args:
        top_verts: list of Blender verts forming the top edge
        z_offsets: list of (dz, x_scale_row, y_scale_row) for each new row
        x_scale, y_scale: initial scale applied to x/y of new verts

    Returns:
        list of all new rows (each row is a list of verts)
    """
    rows = []
    prev = top_verts
    sx, sy = x_scale, y_scale
    for dz, xsc, ysc in z_offsets:
        sx *= xsc
        sy *= ysc
        row = []
        for v in prev:
            nx = v.co.x * sx / (sx / xsc)   # use absolute scale per row
            # Simpler: just scale from origin each time
            pass
        # Reset: build each row by scaling top_verts co-ords
        rows.append(row)
        prev = row
    return rows


def _panel_rows(bm, top_verts, rows_spec):
    """Build a series of panels below top_verts.

    rows_spec: list of (dz, x_mult, y_mult) where coords are multiplied
               from the TOP vertex positions for each new row.

    Returns the last row verts.
    """
    prev = top_verts
    all_rows = []
    for dz, xm, ym in rows_spec:
        new_row = []
        for v in top_verts:   # scale from top vert positions
            new_row.append(bm.verts.new((
                v.co.x * xm,
                v.co.y * ym,
                v.co.z + dz,
            )))
        # Bridge prev row to new row as quad strip
        for i in range(len(prev) - 1):
            try:
                bm.faces.new([prev[i], prev[i + 1], new_row[i + 1], new_row[i]])
            except ValueError:
                pass
        all_rows.append(new_row)
        prev = new_row
    return prev, all_rows


# ─── Style builders ─────────────────────────────────────────────────────────

def _build_buzzed(bm, head_z, head_r):
    """Thin skullcap hugging the head closely — very short all over."""
    # H=1.03: tightest fit, ~3% outward from head surface
    caps = _build_cap(bm, head_z, head_r, h_scale=1.03)
    hairline = caps[0]

    # Extend sides down to just above ear level for coverage
    for side_verts in [_left_verts(hairline), _right_verts(hairline)]:
        _panel_rows(bm, side_verts, [
            (-head_r * 0.18, 1.0, 1.0),   # one row down to ear
        ])


def _build_short(bm, head_z, head_r):
    """Short hair: cap + forehead fringe + side coverage + nape panel."""
    caps = _build_cap(bm, head_z, head_r, h_scale=1.07)
    hairline = caps[0]
    z_hair = head_z  # hairline ring Z (brow level)

    # ── Nape / back panel ──────────────────────────────────────────────────
    # Three rows extending below the back of the hairline.
    back = _back_verts(hairline)
    _panel_rows(bm, back, [
        (-head_r * 0.22, 1.00, 1.00),
        (-head_r * 0.22, 0.92, 0.97),
        (-head_r * 0.20, 0.80, 0.94),
    ])

    # ── Side coverage ──────────────────────────────────────────────────────
    for side_verts in [_left_verts(hairline), _right_verts(hairline)]:
        _panel_rows(bm, side_verts, [
            (-head_r * 0.20, 1.00, 1.00),
            (-head_r * 0.18, 0.90, 0.98),
        ])

    # ── Fringe / bangs ─────────────────────────────────────────────────────
    # Flat panel hanging in front of the hairline. Built from 4 verts
    # positioned just in front of the brow so it reads as a fringe.
    fr_w  = head_r * 1.60                   # width (wider than head at brow)
    fr_y  = -(head_r * 0.82 * 1.07) - 0.01 # just in front of hairline ry
    fr_zt = z_hair + head_r * 0.06          # top of fringe
    fr_zb = z_hair - head_r * 0.18          # bottom of fringe (hangs down)

    tl = bm.verts.new((-fr_w * 0.5, fr_y, fr_zt))
    tr = bm.verts.new(( fr_w * 0.5, fr_y, fr_zt))
    bl = bm.verts.new((-fr_w * 0.4, fr_y + head_r * 0.03, fr_zb))
    br = bm.verts.new(( fr_w * 0.4, fr_y + head_r * 0.03, fr_zb))
    try:
        bm.faces.new([tl, tr, br, bl])
    except ValueError:
        pass

    # Second fringe row (thicker look)
    bl2 = bm.verts.new((-fr_w * 0.32, fr_y + head_r * 0.05, fr_zb - head_r * 0.08))
    br2 = bm.verts.new(( fr_w * 0.32, fr_y + head_r * 0.05, fr_zb - head_r * 0.08))
    try:
        bm.faces.new([bl, br, br2, bl2])
    except ValueError:
        pass


def _build_spiky(bm, head_z, head_r):
    """Dense spikes radiating from the crown with a tight base cap."""
    caps = _build_cap(bm, head_z, head_r, h_scale=1.05)
    hairline = caps[0]

    # Side coverage matching buzzed
    for side_verts in [_left_verts(hairline), _right_verts(hairline)]:
        _panel_rows(bm, side_verts, [(-head_r * 0.15, 1.0, 1.0)])

    # Spike layout: (x_off, y_off, height_mult, base_rx_mult)
    # Positions are fractions of head_r, measured from crown.
    crown_z = head_z + head_r * 0.90
    crown_rx = head_r * 0.31 * 1.05
    crown_ry = head_r * 0.28 * 1.05
    spike_base_r = head_r * 0.10  # base radius of each spike

    spike_layout = [
        # (x_frac, y_frac, h_mult)  — coordinates on crown ring surface
        ( 0.00,  0.00, 1.00),  # centre
        ( 0.55,  0.00, 0.85),  # left
        (-0.55,  0.00, 0.85),  # right
        ( 0.00,  0.55, 0.80),  # back
        ( 0.00, -0.55, 0.80),  # front
        ( 0.38,  0.38, 0.75),  # back-left
        (-0.38,  0.38, 0.75),  # back-right
        ( 0.38, -0.38, 0.75),  # front-left
        (-0.38, -0.38, 0.75),  # front-right
    ]

    for x_frac, y_frac, h_mult in spike_layout:
        sx = x_frac * crown_rx
        sy = y_frac * crown_ry
        sz = crown_z
        spike_h = head_r * 0.75 * h_mult
        tilt_y = math.atan2(sx, spike_h) * 0.5  # slight outward tilt
        tilt_x = math.atan2(-sy, spike_h) * 0.5

        # Base ring
        base = _make_ring(bm, (sx, sy, sz), spike_base_r, spike_base_r * 0.88, n=6)
        # Mid ring (narrower, halfway up)
        mid_r = spike_base_r * 0.55
        mid = _make_ring(bm, (sx * 1.08, sy * 1.08, sz + spike_h * 0.55),
                         mid_r, mid_r * 0.88, n=6)
        # Tip ring
        tip_r = spike_base_r * 0.18
        tip = _make_ring(bm, (sx * 1.14, sy * 1.14, sz + spike_h),
                         tip_r, tip_r, n=6)

        _bridge_rings(bm, base, mid)
        _bridge_rings(bm, mid, tip)
        _cap_ring(bm, tip, top=True)


def _build_long(bm, head_z, head_r):
    """Long hair flowing from crown past the shoulders."""
    caps = _build_cap(bm, head_z, head_r, h_scale=1.09)
    hairline = caps[0]
    z_hair = head_z  # hairline Z

    # ── Long back flow ─────────────────────────────────────────────────────
    # Start from back + side verts of hairline, cascade in 5 rows.
    back = _back_verts(hairline)
    back_rows, _ = _panel_rows(bm, back, [
        (-head_r * 0.28, 1.02, 1.00),  # nape
        (-head_r * 0.35, 1.05, 1.00),  # upper back
        (-head_r * 0.40, 1.08, 0.99),  # mid back
        (-head_r * 0.45, 1.10, 0.98),  # lower back
        (-head_r * 0.50, 1.08, 0.97),  # waist
        (-head_r * 0.45, 1.03, 0.96),  # taper toward tip
    ])
    # Cap the bottom row to close the curtain
    try:
        _cap_ring(bm, list(reversed(back_rows)), top=False)
    except Exception:
        pass

    # ── Side curtains ──────────────────────────────────────────────────────
    for side_verts in [_left_verts(hairline), _right_verts(hairline)]:
        _, rows = _panel_rows(bm, side_verts, [
            (-head_r * 0.25, 1.00, 1.00),
            (-head_r * 0.30, 1.00, 1.00),
            (-head_r * 0.35, 0.95, 0.99),
            (-head_r * 0.40, 0.90, 0.98),
            (-head_r * 0.40, 0.83, 0.97),
        ])

    # ── Fringe ────────────────────────────────────────────────────────────
    fr_w  = head_r * 1.72
    fr_y  = -(head_r * 0.82 * 1.09) - 0.01
    fr_zt = z_hair + head_r * 0.06
    fr_zb = z_hair - head_r * 0.25

    tl = bm.verts.new((-fr_w * 0.5, fr_y, fr_zt))
    tr = bm.verts.new(( fr_w * 0.5, fr_y, fr_zt))
    bl = bm.verts.new((-fr_w * 0.42, fr_y + head_r * 0.04, fr_zb))
    br = bm.verts.new(( fr_w * 0.42, fr_y + head_r * 0.04, fr_zb))
    try:
        bm.faces.new([tl, tr, br, bl])
    except ValueError:
        pass
    bl2 = bm.verts.new((-fr_w * 0.32, fr_y + head_r * 0.07, fr_zb - head_r * 0.12))
    br2 = bm.verts.new(( fr_w * 0.32, fr_y + head_r * 0.07, fr_zb - head_r * 0.12))
    try:
        bm.faces.new([bl, br, br2, bl2])
    except ValueError:
        pass


def _build_mohawk(bm, head_z, head_r):
    """Tall central ridge front-to-back with buzzed sides."""
    # Side buzz sections (minimal caps on left and right)
    for x_sign in [1, -1]:
        cx = x_sign * head_r * 0.50
        for z_off, rx_m, ry_m in [
            (0.00, 0.38, 0.82),
            (0.22, 0.30, 0.72),
            (0.48, 0.18, 0.50),
        ]:
            z = head_z + head_r * z_off
            r = _make_ring(bm, (cx, 0, z), head_r * rx_m, head_r * ry_m)

        # Minimal 2-ring cap for each side
        side_rings = []
        for z_off, rx_m, ry_m in [
            (0.00, 0.36, 0.80),
            (0.22, 0.28, 0.70),
            (0.46, 0.16, 0.48),
        ]:
            side_rings.append(
                _make_ring(bm, (cx, 0, head_z + head_r * z_off),
                           head_r * rx_m, head_r * ry_m)
            )
        for i in range(len(side_rings) - 1):
            _bridge_rings(bm, side_rings[i], side_rings[i + 1])
        _cap_ring(bm, side_rings[-1], top=True)

    # Central ridge: 7 tapered panels running from front to back
    ridge_w  = head_r * 0.20   # half-width of mohawk strip
    ridge_d  = head_r * 0.14   # depth front-to-back per segment
    peak_h   = head_r * 1.10   # tallest spike height above crown ring

    # Y positions: from front (-Y) to back (+Y), centred on head crown
    crown_z  = head_z + head_r * 0.90
    y_start  = -head_r * 0.28
    y_end    =  head_r * 0.28
    n_segs   = 7
    y_step   = (y_end - y_start) / (n_segs - 1)

    for i in range(n_segs):
        y_c = y_start + i * y_step
        # Height profile: tallest at centre, shorter at front/back
        t = abs(i - (n_segs - 1) / 2) / ((n_segs - 1) / 2)
        h = peak_h * (1.0 - 0.35 * t)
        y_h = y_c  # Y position of spike tip

        # Base quad (4 verts at crown level)
        b_fl = bm.verts.new((-ridge_w, y_c - ridge_d * 0.5, crown_z))
        b_fr = bm.verts.new(( ridge_w, y_c - ridge_d * 0.5, crown_z))
        b_bl = bm.verts.new((-ridge_w, y_c + ridge_d * 0.5, crown_z))
        b_br = bm.verts.new(( ridge_w, y_c + ridge_d * 0.5, crown_z))
        # Peak (single vert, narrow tip)
        pk_l = bm.verts.new((-ridge_w * 0.25, y_h, crown_z + h))
        pk_r = bm.verts.new(( ridge_w * 0.25, y_h, crown_z + h))

        # Faces: front slope, back slope, left slope, right slope
        try: bm.faces.new([b_fl, b_fr, pk_r, pk_l])  # front
        except ValueError: pass
        try: bm.faces.new([b_br, b_bl, pk_l, pk_r])  # back
        except ValueError: pass
        try: bm.faces.new([b_fl, pk_l, b_bl])         # left
        except ValueError: pass
        try: bm.faces.new([b_fr, b_br, pk_r])         # right
        except ValueError: pass


# ─── Style dispatch ─────────────────────────────────────────────────────────

_STYLE_BUILDERS = {
    "buzzed":  _build_buzzed,
    "short":   _build_short,
    "spiky":   _build_spiky,
    "long":    _build_long,
    "mohawk":  _build_mohawk,
}

# Public alias expected by tests and external callers
HAIR_BUILDERS = _STYLE_BUILDERS


def create_hair(head_z, head_r, style="short", color=None):
    """Create hair geometry and return a single Blender mesh object.

    Args:
        head_z: Z position of head centre (= neck_z + head_r).
        head_r: Head radius (half-height of the head).
        style:  Hair style name or "none" for bald.
        color:  RGBA tuple, named color string, or None (defaults to dark_brown).

    Returns:
        A single Blender mesh object, or None if style is "none".
    """
    import bpy
    import bmesh as bmesh_mod

    if style == "none":
        return None

    if style not in _STYLE_BUILDERS:
        raise ValueError(
            f"Unknown hair style '{style}'. Available: {list(HAIR_STYLES)}"
        )

    # Resolve color
    if color is None:
        rgba = HAIR_COLORS["dark_brown"]
    elif isinstance(color, str):
        rgba = HAIR_COLORS.get(color, HAIR_COLORS["dark_brown"])
    else:
        rgba = tuple(color)

    # Build all hair geometry into a single bmesh
    bm = bmesh_mod.new()
    _STYLE_BUILDERS[style](bm, head_z, head_r)

    # Recalculate normals for consistent outward facing
    bmesh_mod.ops.recalc_face_normals(bm, faces=bm.faces)

    # Convert bmesh to Blender mesh object
    mesh = bpy.data.meshes.new("Hair_Mesh")
    bm.to_mesh(mesh)
    mesh.update()
    bm.free()

    obj = bpy.data.objects.new("Hair", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Apply smooth shading
    bpy.ops.object.shade_smooth()

    # Apply hair material
    mat = bpy.data.materials.new(name="Hair_Material")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = 0.88
        # Slight specular for a slight sheen
        bsdf.inputs["Specular IOR Level"].default_value = 0.08
    obj.data.materials.append(mat)

    return obj
