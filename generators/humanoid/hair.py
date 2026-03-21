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


# ── Ring region selectors (work for any n) ────────────────────────────────────
#
# For a ring of n vertices produced by _ring():
#   i=0        → front centre
#   i=n//4     → left centre   (+x)
#   i=n//2     → back centre
#   i=3*n//4   → right centre  (-x)

def _back_verts(ring):
    n = len(ring)
    c = n // 2
    return [ring[c - 1], ring[c], ring[c + 1]]


def _left_verts(ring):
    n = len(ring)
    c = n // 4
    return [ring[c - 1], ring[c], ring[c + 1]]


def _right_verts(ring):
    n = len(ring)
    c = 3 * n // 4
    return [ring[c - 1], ring[c], ring[c + 1]]


def _front_verts(ring):
    n = len(ring)
    return [ring[n - 1], ring[0], ring[1]]


def _back_half_verts(ring):
    """Back 270° of the ring — everything except the 3 front-centre verts.

    For n=12 this returns ring[2]..ring[10], spanning from the front-left
    shoulder, around the full back, to the front-right shoulder.  Combined
    with a fringe panel for the remaining 90°, this gives seamless coverage
    of the entire head circumference below the hairline.
    """
    n = len(ring)
    return [ring[i] for i in range(2, n - 1)]


# ── Hair clump builder (CGCookie "big→medium→small" technique) ────────────────
#
# Instead of flat rectangular fringe panels, hair is composed of individual
# tapered "locks" — each wide at the scalp root and narrowing to a pointed tip.
# This matches the Bézier-curve clump workflow from CGCookie's cartoon-hair
# tutorial: define a spine (root→mid→tip), give it a cross-section that tapers,
# and layer 4-6 overlapping clumps across the fringe to read as distinct strands.

def _hair_clump(bm, spine, widths):
    """Build one tapered flat hair lock.

    Args:
        spine:   [(x, y, z), ...] — 3–5 centre-line points, root first.
        widths:  [half_width, ...] in X at each point; last entry = 0 (tip).

    Geometry: quad strip for all segments except the last, which terminates
    in a single tip vertex (triangle) so the clump reads as pointed.
    """
    n = len(spine)
    # All points except the tip get left+right edge verts
    left  = [bm.verts.new((spine[i][0] - widths[i], spine[i][1], spine[i][2]))
             for i in range(n - 1)]
    right = [bm.verts.new((spine[i][0] + widths[i], spine[i][1], spine[i][2]))
             for i in range(n - 1)]
    tip = bm.verts.new(spine[-1])   # single pointed tip vertex

    for i in range(n - 2):
        try:
            bm.faces.new([left[i], left[i + 1], right[i + 1], right[i]])
        except ValueError:
            pass
    # Triangulated tip
    try:
        bm.faces.new([left[-1], tip, right[-1]])
    except ValueError:
        pass


def _fringe_clumps(bm, head_r, hl_z, fr_y, clump_defs):
    """Lay out overlapping hair clumps forming a fringe / bangs.

    Args:
        head_r:     Head radius in metres.
        hl_z:       Z of the hairline ring (= head_z for the equatorial ring).
        fr_y:       Y of the cap front surface (negative = forward).
        clump_defs: list of tuples:
          (cx, x_drift, y_fwd, z_mid, z_tip, w_root)
          cx        — X centre as multiple of head_r
          x_drift   — extra X at tip (×head_r), for sideways sweep
          y_fwd     — how far the tip comes forward (×head_r, added to fr_y)
          z_mid     — Z drop at mid-point below root (×head_r)
          z_tip     — Z drop at tip below root (×head_r)
          w_root    — half-width at root (×head_r)
    """
    for cx, x_drift, y_fwd, z_mid, z_tip, w_root in clump_defs:
        rx      = cx     * head_r
        drift   = x_drift * head_r
        wd_root = w_root  * head_r
        wd_mid  = wd_root * 0.58   # tapers to ~58 % at mid-point

        spine = [
            (rx,                  fr_y,                       hl_z + head_r * 0.02),
            (rx + drift * 0.5,    fr_y - head_r * y_fwd * 0.5, hl_z - head_r * z_mid),
            (rx + drift,          fr_y - head_r * y_fwd,       hl_z - head_r * z_tip),
        ]
        _hair_clump(bm, spine, [wd_root, wd_mid, 0])


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
# Proportions follow a spherical dome (sin/cos of elevation angle θ):
#
#   θ      z_offset = sin(θ)   rx_mult ≈ cos(θ)   ry_mult (head is slightly
#                                                    narrower front-to-back)
#   0°     0.00                0.97               0.90   ← hairline / brow
#   30°    0.50                0.84               0.77   ← upper forehead
#   60°    0.86                0.52               0.48   ← upper cranium
#   80°    0.97                0.14               0.13   ← crown apex
#
# This gives a visibly rounder dome than the old flat profile.
# 12-sided rings (n=12) ensure the silhouette reads as circular.
#
# h_scale pushes the cap shell outward from the head surface:
#   1.03 → near skin-tight (buzz cut)
#   1.07 → normal short/medium hair
#   1.09 → voluminous long hair

_CAP_LEVELS = [
    (0.00, 0.97, 0.90),   # hairline / brow  — equatorial
    (0.50, 0.84, 0.77),   # upper forehead
    (0.86, 0.52, 0.48),   # upper cranium
    (0.97, 0.14, 0.13),   # crown apex
]

_CAP_RING_N = 12   # sides per ring — 12 gives a smooth round silhouette


def _build_cap(bm, head_z, head_r, h_scale=1.07, levels=None):
    """Build the shared domed cap from hairline to crown.

    Args:
        levels: list of (z_off, rx_mult, ry_mult) tuples overriding _CAP_LEVELS.
                Useful for styles that need a non-equatorial hairline start.

    Returns ring lists; crown is closed, hairline is left open.
    """
    if levels is None:
        levels = _CAP_LEVELS
    rings = []
    for z_off, rx_m, ry_m in levels:
        z = head_z + head_r * z_off
        rings.append(_ring(bm, 0, 0, z,
                           head_r * rx_m * h_scale,
                           head_r * ry_m * h_scale,
                           n=_CAP_RING_N))
    for i in range(len(rings) - 1):
        _bridge(bm, rings[i], rings[i + 1])
    _close_ring(bm, rings[-1], top=True)
    return rings  # rings[0] = hairline ring


# ── Style builders ─────────────────────────────────────────────────────────────

def _build_buzzed(bm, head_z, head_r):
    """Skullcap hugging the head tightly — very short all over."""
    rings = _build_cap(bm, head_z, head_r, h_scale=1.03)
    hl = rings[0]
    # Single unified row around the back 270° for seamless ear/nape coverage
    _panel_rows(bm, _back_half_verts(hl), [
        (-head_r * 0.18, 1.0, 1.0),
    ])



# Custom cap levels for the short style.
# Hairline at θ≈19° above the equator (sin 19° ≈ 0.33 → forehead level).
# h_scale=1.05 keeps the cap tight (~1 mm gap for a 0.10 m head).
# At z_off=0.33: sphere_xy ≈ 0.944 hr; cap_rx = 0.91 × 1.05 hr = 0.956 hr ✓
_SHORT_CAP_LEVELS = [
    (0.33, 0.91, 0.91),   # hairline — upper-forehead elevation (symmetric rx/ry)
    (0.50, 0.84, 0.77),   # upper forehead  (unchanged from shared levels)
    (0.86, 0.52, 0.48),   # upper cranium
    (0.97, 0.14, 0.13),   # crown apex
]


def _build_short(bm, head_z, head_r):
    """Short hair: forehead-level cap + sphere-conforming back panel + fringe.

    Key fixes vs. previous implementation
    --------------------------------------
    1. Hairline raised from z_off=0.00 (equator = ear/eye level) to
       z_off=0.33 (forehead/hairline level).
    2. h_scale reduced 1.07 → 1.05 so the cap sits ~1 mm off the scalp
       rather than ~7 mm.  rx_mult raised to 0.91 so the ring still
       clears the sphere at this elevation.
    3. Panel dz values are equal small increments (0.16 hr each) that
       cumulate to 0.63 hr — ending at the nape (z_off ≈ -0.30), NOT
       at the shoulders.  The previous bug used dz as large steps that
       accumulated to 1.65 hr, pushing the bottom past shoulder level.
    4. Panel x/y_scale > 1.0 tracks the sphere widening below the
       raised hairline before easing inward at the nape.

    Row z_off reference (hairline +0.33, steps cumulative):
      row 1  z_off ≈ +0.17  sphere ≈ 0.985 hr  scale 1.06 → 1.013 hr ✓
      row 2  z_off ≈ +0.01  sphere ≈ 1.000 hr  scale 1.08 → 1.032 hr ✓
      row 3  z_off ≈ -0.15  sphere ≈ 0.989 hr  scale 1.07 → 1.022 hr ✓
      row 4  z_off ≈ -0.30  sphere ≈ 0.954 hr  scale 1.03 → 0.984 hr ✓
    (hr = head_r; hairline_rx = 0.91 × 1.05 hr = 0.9555 hr)
    """
    rings = _build_cap(bm, head_z, head_r, h_scale=1.05, levels=_SHORT_CAP_LEVELS)
    hl = rings[0]
    hl_z = hl[0].co.z   # = head_z + head_r * 0.33

    # Back-half panel — four equal steps totalling 0.63 × head_r.
    # Nape row (row 4) lands at z_off ≈ -0.30, just above the neck joint.
    _panel_rows(bm, _back_half_verts(hl), [
        (-head_r * 0.16, 1.06, 1.04),   # z_off≈+0.17 — widen to track sphere
        (-head_r * 0.16, 1.08, 1.06),   # z_off≈+0.01 — equatorial, widest
        (-head_r * 0.16, 1.07, 1.05),   # z_off≈-0.15 — below equator
        (-head_r * 0.15, 1.03, 1.02),   # z_off≈-0.30 — nape, begin taper
    ])

    # Fringe — 5 overlapping tapered clumps anchored to the raised hairline.
    # fr_y = front-face Y of hairline ring = −(0.91 × 1.05 × head_r)
    fr_y = -(head_r * 0.91 * 1.05) - 0.005
    # (cx, x_drift, y_fwd, z_mid, z_tip, w_root)
    _fringe_clumps(bm, head_r, hl_z, fr_y, [
        (-0.52, -0.07, 0.05, 0.03, 0.07, 0.14),   # far-left, sweeps left
        (-0.26,  0.00, 0.06, 0.03, 0.07, 0.14),   # left
        ( 0.00,  0.00, 0.07, 0.03, 0.08, 0.16),   # centre (slightly wider)
        ( 0.26,  0.00, 0.06, 0.03, 0.07, 0.14),   # right
        ( 0.52,  0.07, 0.05, 0.03, 0.07, 0.14),   # far-right, sweeps right
    ])


def _build_spiky(bm, head_z, head_r):
    """Toon-style cone spikes radiating from the crown over a tight cap."""
    rings = _build_cap(bm, head_z, head_r, h_scale=1.05)
    hl = rings[0]

    # Minimal back-half coverage — one row keeps ear/nape from showing through
    _panel_rows(bm, _back_half_verts(hl), [(-head_r * 0.15, 1.0, 1.0)])

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

    # Unified back-half curtain — fans out as it falls toward waist level.
    # The side verts (at ±rx) get the same rows and merge seamlessly into
    # the back without the gap that the old separate panels had.
    _panel_rows(bm, _back_half_verts(hl), [
        (-head_r * 0.28, 1.02, 1.00),
        (-head_r * 0.58, 1.05, 1.00),
        (-head_r * 0.90, 1.08, 0.99),
        (-head_r * 1.25, 1.10, 0.98),
        (-head_r * 1.65, 1.08, 0.97),
        (-head_r * 2.00, 1.03, 0.96),   # waist level
    ])

    # Fringe — 5 tapered clumps, longer drop than short style.
    fr_y = -(head_r * 0.90 * 1.09) - 0.005
    _fringe_clumps(bm, head_r, hl_z, fr_y, [
        (-0.52, -0.08, 0.07, 0.06, 0.22, 0.15),
        (-0.26,  0.00, 0.08, 0.06, 0.20, 0.15),
        ( 0.00,  0.00, 0.09, 0.06, 0.22, 0.17),
        ( 0.26,  0.00, 0.08, 0.06, 0.20, 0.15),
        ( 0.52,  0.08, 0.07, 0.06, 0.22, 0.15),
    ])


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

    # Unified back-half panel — gathers inward toward the bundle root
    _panel_rows(bm, _back_half_verts(hl), [
        (-head_r * 0.22, 1.00, 1.00),
        (-head_r * 0.42, 0.85, 0.96),
    ])

    # Fringe — 3 shorter clumps (less drop; most hair is in the ponytail).
    fr_y = -(head_r * 0.90 * 1.07) - 0.005
    _fringe_clumps(bm, head_r, hl_z, fr_y, [
        (-0.38, -0.05, 0.05, 0.04, 0.14, 0.13),
        ( 0.00,  0.00, 0.06, 0.04, 0.14, 0.14),
        ( 0.38,  0.05, 0.05, 0.04, 0.14, 0.13),
    ])

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

    # Principled BSDF tuned for stylized low-poly hair:
    #   - Mid roughness (0.55) avoids the chalky look of high roughness
    #   - Low anisotropy (0.15) + rotation (0.1) adds directionality
    #     without creating confusing highlights on flat poly geometry
    #   - Sheen (0.2) gives a soft rim edge that reads as hair fibre
    #   - Slight specular tint warms the highlight toward the hair colour
    # Sources: Blender 4.x Principled BSDF manual, Blender Artists community
    mat = bpy.data.materials.new(name="Hair_Material")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = 0.55

        # Specular (input name changed in Blender 4.0)
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.15
        elif "Specular" in bsdf.inputs:
            bsdf.inputs["Specular"].default_value = 0.15

        # Directional sheen — keep low so it reads on simple geometry
        if "Anisotropic" in bsdf.inputs:
            bsdf.inputs["Anisotropic"].default_value = 0.15
        if "Anisotropic Rotation" in bsdf.inputs:
            bsdf.inputs["Anisotropic Rotation"].default_value = 0.1

        # Soft edge rim — simulates fine surface fibres
        if "Sheen Weight" in bsdf.inputs:       # Blender 4.x
            bsdf.inputs["Sheen Weight"].default_value = 0.20
        elif "Sheen" in bsdf.inputs:             # Blender 3.x
            bsdf.inputs["Sheen"].default_value = 0.20
        if "Sheen Roughness" in bsdf.inputs:
            bsdf.inputs["Sheen Roughness"].default_value = 0.50

        # Warm the specular highlight toward the hair colour
        if "Specular Tint" in bsdf.inputs:
            si = bsdf.inputs["Specular Tint"]
            try:
                # Blender 4.x — colour input
                r, g, b, a = rgba
                si.default_value = (
                    min(r * 1.15, 1.0),
                    min(g * 1.10, 1.0),
                    min(b * 1.05, 1.0),
                    1.0,
                )
            except TypeError:
                si.default_value = 0.4   # Blender 3.x — float input
    obj.data.materials.append(mat)

    return obj
