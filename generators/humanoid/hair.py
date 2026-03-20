"""Low-poly hair generation for the humanoid pipeline.

Mesh-based, no particle systems or alpha textures.  All styles use solid
opaque geometry so they render correctly on any mobile/web real-time renderer
without transparency-sorting artifacts.

Architecture
------------
Every style is composed of two parts:

  1. A *cap* — a domed shell sitting ~3-9% outside the head surface,
     covering from the hairline ring up to the crown.

  2. *Extensions* — panel rows, ring stacks, or clumps that add the
     style-defining volume (nape, curtains, fringe, spikes, ponytail bundle).

All geometry is built into a single bmesh then converted to one Blender mesh
object so there is only one draw call per character.

Public interface
----------------
  create_hair(head_z, head_r, style, color)  →  bpy.types.Object or None
  HAIR_STYLES   — tuple of valid style name strings
  HAIR_COLORS   — dict mapping name → RGBA tuple

Face budget (mobile target: 300-500 faces per complete asset)
-------------------------------------------------------------
  buzzed    ≈  50–80 faces
  short     ≈ 100–160 faces
  spiky     ≈ 120–200 faces
  long      ≈ 180–280 faces
  mohawk    ≈ 140–200 faces
  ponytail  ≈ 150–220 faces
"""

import math

# ── Data constants (no bpy dependency) ────────────────────────────────────────

HAIR_STYLES = ("none", "buzzed", "short", "spiky", "long", "mohawk", "ponytail")

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


# ── Core bmesh geometry helpers ────────────────────────────────────────────────

def _ring(bm, cx, cy, cz, rx, ry, n=8):
    """Create an n-vertex elliptical ring in the XY plane at height cz.

    Vertex order for n=8 (used by the region helpers below):
      i=0  front      (y most negative — faces forward)
      i=1  front-right (+x, -y)
      i=2  right       (+x)
      i=3  back-right  (+x, +y)
      i=4  back        (y most positive)
      i=5  back-left   (-x, +y)
      i=6  left        (-x)
      i=7  front-left  (-x, -y)
    """
    verts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        verts.append(bm.verts.new((
            cx + rx * math.sin(a),
            cy - ry * math.cos(a),
            cz,
        )))
    return verts


def _bridge(bm, ring_a, ring_b):
    """Connect two equal-length rings with a quad strip."""
    n = len(ring_a)
    for i in range(n):
        j = (i + 1) % n
        try:
            bm.faces.new([ring_a[i], ring_a[j], ring_b[j], ring_b[i]])
        except ValueError:
            pass


def _close_ring(bm, ring, top=True):
    """Close a ring with a triangle fan.  Returns the centre vertex."""
    cx = sum(v.co.x for v in ring) / len(ring)
    cy = sum(v.co.y for v in ring) / len(ring)
    cz = sum(v.co.z for v in ring) / len(ring)
    centre = bm.verts.new((cx, cy, cz))
    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        try:
            if top:
                bm.faces.new([ring[i], ring[j], centre])
            else:
                bm.faces.new([ring[j], ring[i], centre])
        except ValueError:
            pass
    return centre


# ── Ring region selectors (8-vert rings only) ──────────────────────────────────

def _back_verts(ring):
    return [ring[3], ring[4], ring[5]]


def _left_verts(ring):
    return [ring[1], ring[2], ring[3]]


def _right_verts(ring):
    return [ring[5], ring[6], ring[7]]


def _front_verts(ring):
    return [ring[7], ring[0], ring[1]]


# ── Panel row builder ──────────────────────────────────────────────────────────

def _panel_rows(bm, top_verts, rows_spec):
    """Extrude a strip of vertices downward in sequential quad rows.

    Args:
        top_verts:  List of Blender verts forming the top edge of the panel.
        rows_spec:  List of (dz, x_scale, y_scale) tuples where:
                    - dz is cumulative (each step moves further from top_verts)
                    - x_scale and y_scale are absolute — applied to the
                      original top_verts x/y so the taper is fully controlled

    Returns:
        (last_row_verts, list_of_all_new_rows)
    """
    prev = top_verts
    all_rows = []
    cumulative_dz = 0.0
    for dz, xm, ym in rows_spec:
        cumulative_dz += dz
        new_row = [
            bm.verts.new((v.co.x * xm, v.co.y * ym, v.co.z + cumulative_dz))
            for v in top_verts
        ]
        for i in range(len(prev) - 1):
            try:
                bm.faces.new([prev[i], prev[i + 1], new_row[i + 1], new_row[i]])
            except ValueError:
                pass
        all_rows.append(new_row)
        prev = new_row
    return prev, all_rows


# ── Shared cap builder ─────────────────────────────────────────────────────────
#
# Reference proportions (standard human head geometry, normalised to head_r):
#
#   Level            z_offset   rx_mult   ry_mult
#   hairline/brow    0.00       0.88      0.82
#   forehead         0.28       0.74      0.68
#   upper cranium    0.58       0.54      0.50
#   crown            0.90       0.31      0.28
#
# h_scale pushes the cap shell outward from the head surface:
#   1.03 → near skin-tight (buzz cut)
#   1.07 → normal short/medium hair
#   1.09 → voluminous long hair

_CAP_LEVELS = [
    (0.00, 0.88, 0.82),   # hairline / brow
    (0.28, 0.74, 0.68),   # forehead
    (0.58, 0.54, 0.50),   # upper cranium
    (0.90, 0.31, 0.28),   # crown
]


def _build_cap(bm, head_z, head_r, h_scale=1.07):
    """Build the shared domed cap from hairline to crown.

    Returns [hairline, forehead, upper, crown] ring lists.
    Crown is closed; hairline is left open so skin shows below it.
    """
    rings = []
    for z_off, rx_m, ry_m in _CAP_LEVELS:
        z = head_z + head_r * z_off
        rings.append(_ring(bm, 0, 0, z,
                           head_r * rx_m * h_scale,
                           head_r * ry_m * h_scale))
    for i in range(len(rings) - 1):
        _bridge(bm, rings[i], rings[i + 1])
    _close_ring(bm, rings[-1], top=True)
    return rings  # rings[0] = hairline ring


# ── Style builders ─────────────────────────────────────────────────────────────

def _build_buzzed(bm, head_z, head_r):
    """Skullcap hugging the head tightly — very short all over."""
    rings = _build_cap(bm, head_z, head_r, h_scale=1.03)
    hl = rings[0]
    # One row of side and back panels for ear/nape coverage
    for region in [_back_verts(hl), _left_verts(hl), _right_verts(hl)]:
        _panel_rows(bm, region, [
            (-head_r * 0.18, 1.0, 1.0),
        ])


def _build_short(bm, head_z, head_r):
    """Short hair: cap + tapering nape panel + side coverage + fringe."""
    rings = _build_cap(bm, head_z, head_r, h_scale=1.07)
    hl = rings[0]
    hl_z = hl[0].co.z

    # Nape — 3 rows tapering toward the neck
    _panel_rows(bm, _back_verts(hl), [
        (-head_r * 0.22, 1.00, 1.00),
        (-head_r * 0.42, 0.92, 0.97),
        (-head_r * 0.58, 0.80, 0.94),
    ])

    # Side coverage — 2 rows
    for region in [_left_verts(hl), _right_verts(hl)]:
        _panel_rows(bm, region, [
            (-head_r * 0.20, 1.00, 1.00),
            (-head_r * 0.36, 0.90, 0.98),
        ])

    # Fringe — two-row flat panel just in front of the brow
    fr_w  = head_r * 1.60
    fr_y  = -(head_r * 0.82 * 1.07) - 0.005
    fr_zt = hl_z + head_r * 0.06
    fr_zb = hl_z - head_r * 0.18
    tl = bm.verts.new((-fr_w * 0.50, fr_y, fr_zt))
    tr = bm.verts.new(( fr_w * 0.50, fr_y, fr_zt))
    ml = bm.verts.new((-fr_w * 0.44, fr_y, fr_zb))
    mr = bm.verts.new(( fr_w * 0.44, fr_y, fr_zb))
    bl = bm.verts.new((-fr_w * 0.34, fr_y + head_r * 0.04, fr_zb - head_r * 0.10))
    br = bm.verts.new(( fr_w * 0.34, fr_y + head_r * 0.04, fr_zb - head_r * 0.10))
    for fv in [[tl, tr, mr, ml], [ml, mr, br, bl]]:
        try:
            bm.faces.new(fv)
        except ValueError:
            pass


def _build_spiky(bm, head_z, head_r):
    """Toon-style cone spikes radiating from the crown over a tight cap."""
    rings = _build_cap(bm, head_z, head_r, h_scale=1.05)
    hl = rings[0]

    # Minimal side coverage
    for region in [_left_verts(hl), _right_verts(hl)]:
        _panel_rows(bm, region, [(-head_r * 0.15, 1.0, 1.0)])

    # Spike layout: (x_frac, y_frac, height_mult) relative to crown extents
    crown_z  = head_z + head_r * 0.90
    crown_rx = head_r * 0.31 * 1.05
    crown_ry = head_r * 0.28 * 1.05
    base_r   = head_r * 0.10
    spike_h  = head_r * 0.80
    layout = [
        ( 0.00,  0.00, 1.00),   # centre top
        ( 0.55,  0.00, 0.85),   # left
        (-0.55,  0.00, 0.85),   # right
        ( 0.00,  0.55, 0.80),   # back
        ( 0.00, -0.55, 0.80),   # front
        ( 0.40,  0.40, 0.72),   # back-left
        (-0.40,  0.40, 0.72),   # back-right
        ( 0.40, -0.40, 0.72),   # front-left
        (-0.40, -0.40, 0.72),   # front-right
    ]
    for xf, yf, hm in layout:
        sx, sy, sz = xf * crown_rx, yf * crown_ry, crown_z
        h = spike_h * hm
        base = _ring(bm, sx,        sy,        sz,          base_r,        base_r * 0.88, n=6)
        mid  = _ring(bm, sx * 1.06, sy * 1.06, sz + h * 0.55, base_r * 0.50, base_r * 0.45, n=6)
        tip  = _ring(bm, sx * 1.12, sy * 1.12, sz + h,        base_r * 0.12, base_r * 0.12, n=6)
        _bridge(bm, base, mid)
        _bridge(bm, mid, tip)
        _close_ring(bm, tip, top=True)


def _build_long(bm, head_z, head_r):
    """Long hair flowing past the shoulders: cap + wide back curtain + fringe."""
    rings = _build_cap(bm, head_z, head_r, h_scale=1.09)
    hl = rings[0]
    hl_z = hl[0].co.z

    # Back curtain — fans wider as it falls, reaching waist level
    _panel_rows(bm, _back_verts(hl), [
        (-head_r * 0.28, 1.02, 1.00),
        (-head_r * 0.58, 1.05, 1.00),
        (-head_r * 0.90, 1.08, 0.99),
        (-head_r * 1.25, 1.10, 0.98),
        (-head_r * 1.65, 1.08, 0.97),
        (-head_r * 2.00, 1.03, 0.96),   # waist level
    ])

    # Side curtains
    for region in [_left_verts(hl), _right_verts(hl)]:
        _panel_rows(bm, region, [
            (-head_r * 0.25, 1.00, 1.00),
            (-head_r * 0.55, 1.00, 1.00),
            (-head_r * 0.88, 0.95, 0.99),
            (-head_r * 1.22, 0.88, 0.98),
        ])

    # Fringe (slightly longer than short)
    fr_w  = head_r * 1.72
    fr_y  = -(head_r * 0.82 * 1.09) - 0.005
    fr_zt = hl_z + head_r * 0.06
    fr_zb = hl_z - head_r * 0.24
    tl = bm.verts.new((-fr_w * 0.50, fr_y, fr_zt))
    tr = bm.verts.new(( fr_w * 0.50, fr_y, fr_zt))
    ml = bm.verts.new((-fr_w * 0.44, fr_y, fr_zb))
    mr = bm.verts.new(( fr_w * 0.44, fr_y, fr_zb))
    bl = bm.verts.new((-fr_w * 0.34, fr_y + head_r * 0.05, fr_zb - head_r * 0.14))
    br = bm.verts.new(( fr_w * 0.34, fr_y + head_r * 0.05, fr_zb - head_r * 0.14))
    for fv in [[tl, tr, mr, ml], [ml, mr, br, bl]]:
        try:
            bm.faces.new(fv)
        except ValueError:
            pass


def _build_mohawk(bm, head_z, head_r):
    """Tall central fin front-to-back with closely-cropped side caps."""
    # Two partial side domes, offset left/right
    for x_sign in [1, -1]:
        cx = x_sign * head_r * 0.50
        side_rings = []
        for z_off, rx_m, ry_m in [
            (0.00, 0.36, 0.80),
            (0.22, 0.28, 0.70),
            (0.46, 0.16, 0.48),
        ]:
            side_rings.append(
                _ring(bm, cx, 0, head_z + head_r * z_off,
                      head_r * rx_m, head_r * ry_m)
            )
        for i in range(len(side_rings) - 1):
            _bridge(bm, side_rings[i], side_rings[i + 1])
        _close_ring(bm, side_rings[-1], top=True)

    # Central fin: 7 tapered segments, tallest at centre
    crown_z = head_z + head_r * 0.90
    ridge_w = head_r * 0.20    # half-width of each fin panel
    ridge_d = head_r * 0.14    # front-to-back depth per segment
    peak_h  = head_r * 1.10
    y_start = -head_r * 0.28
    y_end   =  head_r * 0.28
    n_segs  = 7
    for i in range(n_segs):
        yc = y_start + i * (y_end - y_start) / (n_segs - 1)
        t  = abs(i - (n_segs - 1) / 2) / ((n_segs - 1) / 2)
        h  = peak_h * (1.0 - 0.35 * t)
        b_fl = bm.verts.new((-ridge_w, yc - ridge_d * 0.5, crown_z))
        b_fr = bm.verts.new(( ridge_w, yc - ridge_d * 0.5, crown_z))
        b_bl = bm.verts.new((-ridge_w, yc + ridge_d * 0.5, crown_z))
        b_br = bm.verts.new(( ridge_w, yc + ridge_d * 0.5, crown_z))
        pk_l = bm.verts.new((-ridge_w * 0.25, yc, crown_z + h))
        pk_r = bm.verts.new(( ridge_w * 0.25, yc, crown_z + h))
        for fv in [
            [b_fl, b_fr, pk_r, pk_l],   # front slope
            [b_br, b_bl, pk_l, pk_r],   # back slope
            [b_fl, pk_l, b_bl],          # left triangle
            [b_fr, b_br, pk_r],          # right triangle
        ]:
            try:
                bm.faces.new(fv)
            except ValueError:
                pass


def _build_ponytail(bm, head_z, head_r):
    """Short front/sides with a gathered bundle hanging at the back."""
    rings = _build_cap(bm, head_z, head_r, h_scale=1.07)
    hl = rings[0]
    hl_z = hl[0].co.z

    # Short nape panel — gathers inward toward the bundle root
    _panel_rows(bm, _back_verts(hl), [
        (-head_r * 0.22, 1.00, 1.00),
        (-head_r * 0.42, 0.85, 0.96),
    ])

    # Side coverage
    for region in [_left_verts(hl), _right_verts(hl)]:
        _panel_rows(bm, region, [
            (-head_r * 0.20, 1.00, 1.00),
            (-head_r * 0.36, 0.90, 0.98),
        ])

    # Single-row fringe
    fr_w  = head_r * 1.60
    fr_y  = -(head_r * 0.82 * 1.07) - 0.005
    fr_zt = hl_z + head_r * 0.06
    fr_zb = hl_z - head_r * 0.18
    tl = bm.verts.new((-fr_w * 0.50, fr_y, fr_zt))
    tr = bm.verts.new(( fr_w * 0.50, fr_y, fr_zt))
    ml = bm.verts.new((-fr_w * 0.44, fr_y, fr_zb))
    mr = bm.verts.new(( fr_w * 0.44, fr_y, fr_zb))
    try:
        bm.faces.new([tl, tr, mr, ml])
    except ValueError:
        pass

    # Ponytail bundle — stacked rings hanging from the nape
    pt_cy  = head_r * 0.85        # sits behind the head
    pt_cz  = head_z - head_r * 0.42   # nape level
    pt_r   = head_r * 0.16        # bundle root radius
    pt_len = head_r * 1.80        # total drop length

    # (relative_dz, radius_multiplier) — dz is a fraction of pt_len
    bundle_spec = [
        (0.00, 1.00),   # root
        (0.14, 0.88),   # slight gather toward tie
        (0.14, 0.72),   # hair-tie pinch
        (0.14, 0.84),   # just below tie — slight flare
        (0.24, 0.90),
        (0.28, 0.88),
        (0.28, 0.82),
        (0.22, 0.68),   # taper toward tip
        (0.18, 0.42),
        (0.14, 0.18),   # tip
    ]
    prev_ring = None
    cumz = 0.0
    for rel_dz, rm in bundle_spec:
        cumz += rel_dz * pt_len
        r = pt_r * rm
        ring = _ring(bm, 0, pt_cy, pt_cz - cumz, r, r * 0.90, n=8)
        if prev_ring is not None:
            _bridge(bm, prev_ring, ring)
        prev_ring = ring
    _close_ring(bm, prev_ring, top=False)

    # Hair-tie band at the pinch point (~28% down from root)
    tie_z   = pt_cz - pt_len * 0.28
    tie_ro  = pt_r * 0.80    # outer radius
    tie_ri  = pt_r * 0.60    # inner radius
    tie_h   = head_r * 0.035  # half-height of the band
    bo = _ring(bm, 0, pt_cy, tie_z - tie_h, tie_ro, tie_ro * 0.90, n=8)
    to = _ring(bm, 0, pt_cy, tie_z + tie_h, tie_ro, tie_ro * 0.90, n=8)
    bi = _ring(bm, 0, pt_cy, tie_z - tie_h, tie_ri, tie_ri * 0.90, n=8)
    ti = _ring(bm, 0, pt_cy, tie_z + tie_h, tie_ri, tie_ri * 0.90, n=8)
    _bridge(bm, bo, to)           # outer wall
    _bridge(bm, ti, bi)           # inner wall (reversed winding)
    _bridge(bm, ti, to)           # top face
    _bridge(bm, bo, bi)           # bottom face


# ── Style dispatch ─────────────────────────────────────────────────────────────

_STYLE_BUILDERS = {
    "buzzed":   _build_buzzed,
    "short":    _build_short,
    "spiky":    _build_spiky,
    "long":     _build_long,
    "mohawk":   _build_mohawk,
    "ponytail": _build_ponytail,
}

# Public alias expected by tests and external callers
HAIR_BUILDERS = _STYLE_BUILDERS


# ── Public entry point ─────────────────────────────────────────────────────────

def create_hair(head_z, head_r, style="short", color=None):
    """Build hair geometry and return a linked Blender mesh object.

    Args:
        head_z: Z coordinate of the head *centre* (= neck_z + head_r).
        head_r: Head radius in metres.
        style:  Name from HAIR_STYLES.  "none" returns None.
        color:  RGBA tuple, a key from HAIR_COLORS, or None (→ dark_brown).

    Returns:
        A linked bpy.types.Object, or None when style is "none".
    """
    import bpy
    import bmesh as bmesh_mod

    if style == "none":
        return None

    if style not in _STYLE_BUILDERS:
        raise ValueError(
            f"Unknown hair style '{style}'. Valid styles: {list(HAIR_STYLES)}"
        )

    # Resolve color
    if color is None:
        rgba = HAIR_COLORS["dark_brown"]
    elif isinstance(color, str):
        rgba = HAIR_COLORS.get(color, HAIR_COLORS["dark_brown"])
    else:
        rgba = tuple(color)

    # Build geometry
    bm = bmesh_mod.new()
    _STYLE_BUILDERS[style](bm, head_z, head_r)
    bmesh_mod.ops.recalc_face_normals(bm, faces=bm.faces)

    # Convert to Blender mesh object
    mesh = bpy.data.meshes.new("Hair_Mesh")
    bm.to_mesh(mesh)
    mesh.update()
    bm.free()

    obj = bpy.data.objects.new("Hair", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()

    # Opaque Principled BSDF with a subtle anisotropic sheen
    mat = bpy.data.materials.new(name="Hair_Material")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = 0.85
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.10
        elif "Specular" in bsdf.inputs:
            bsdf.inputs["Specular"].default_value = 0.10
        if "Anisotropic" in bsdf.inputs:
            bsdf.inputs["Anisotropic"].default_value = 0.35
    obj.data.materials.append(mat)

    return obj
