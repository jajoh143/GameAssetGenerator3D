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

HAIR_STYLES = ("none", "buzzed", "short", "spiky", "slicked", "long", "mohawk", "ponytail")

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


def _fringe_clumps(bm, head_r, hl_z, fr_y, clump_defs, head_r_horiz=None):
    """Lay out overlapping hair clumps forming a fringe / bangs.

    Args:
        head_r:       Head radius (vertical) in metres — used for Z offsets.
        head_r_horiz: Horizontal head half-width in metres — used for X/Y
                      positioning.  Falls back to head_r when None.
        hl_z:         Z of the hairline ring (= head_z for the equatorial ring).
        fr_y:         Y of the cap front surface (negative = forward).
        clump_defs: list of tuples:
          (cx, x_drift, y_fwd, z_mid, z_tip, w_root)
          cx        — X centre as multiple of head_r_horiz
          x_drift   — extra X at tip (×head_r_horiz), for sideways sweep
          y_fwd     — how far the tip comes forward (×head_r_horiz, added to fr_y)
          z_mid     — Z drop at mid-point below root (×head_r)
          z_tip     — Z drop at tip below root (×head_r)
          w_root    — half-width at root (×head_r_horiz)
    """
    hr_h = head_r_horiz if head_r_horiz is not None else head_r
    for cx, x_drift, y_fwd, z_mid, z_tip, w_root in clump_defs:
        rx      = cx      * hr_h
        drift   = x_drift * hr_h
        wd_root = w_root  * hr_h
        wd_mid  = wd_root * 0.58   # tapers to ~58 % at mid-point

        spine = [
            (rx,                  fr_y,                        hl_z + head_r * 0.02),
            (rx + drift * 0.5,    fr_y - hr_h * y_fwd * 0.5,  hl_z - head_r * z_mid),
            (rx + drift,          fr_y - hr_h * y_fwd,         hl_z - head_r * z_tip),
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


def _build_cap(bm, head_z, head_r, h_scale=1.20, levels=None, head_r_horiz=None):
    """Build the shared domed cap from hairline to crown.

    Args:
        head_r:       Vertical head radius (equator→crown) — used for Z offsets.
        head_r_horiz: Horizontal head half-width — used for ring rx/ry so the
                      cap clears the actual head surface.  Falls back to head_r.
        levels: list of (z_off, rx_mult, ry_mult) tuples overriding _CAP_LEVELS.
                Useful for styles that need a non-equatorial hairline start.

    Returns ring lists; crown is closed, hairline is left open.
    """
    hr_h = head_r_horiz if head_r_horiz is not None else head_r
    if levels is None:
        levels = _CAP_LEVELS
    rings = []
    for z_off, rx_m, ry_m in levels:
        z = head_z + head_r * z_off        # Z position: vertical radius
        rings.append(_ring(bm, 0, 0, z,
                           hr_h * rx_m * h_scale,   # ring width: horizontal radius
                           hr_h * ry_m * h_scale,   # ring depth: horizontal radius
                           n=_CAP_RING_N))
    for i in range(len(rings) - 1):
        _bridge(bm, rings[i], rings[i + 1])
    _close_ring(bm, rings[-1], top=True)
    return rings  # rings[0] = hairline ring


# ── Style builders ─────────────────────────────────────────────────────────────

def _build_buzzed(bm, head_z, head_r, head_r_horiz=None):
    """Skullcap hugging the head tightly — very short all over."""
    rings = _build_cap(bm, head_z, head_r, h_scale=1.15, head_r_horiz=head_r_horiz)
    hl = rings[0]
    # Single unified row around the back 270° for seamless ear/nape coverage
    _panel_rows(bm, _back_half_verts(hl), [
        (-head_r * 0.18, 1.0, 1.0),
    ])



# Cap levels for the short style.
# Hairline starts at z_off=0.00 (equatorial = ear/temple level) so the cap
# wraps fully around the head circumference.  Crown compressed to z_off=0.92
# for a flat low-profile look.  h_scale=1.20 gives ~3 % clearance from the
# head surface using the actual horizontal radius (head_r_horiz).
_SHORT_CAP_LEVELS = [
    (0.00, 0.97, 0.90),   # hairline — equatorial (ear/temple, full circumference)
    (0.45, 0.86, 0.79),   # upper sides
    (0.78, 0.55, 0.50),   # upper cranium
    (0.92, 0.18, 0.16),   # crown apex
]


def _build_short(bm, head_z, head_r, head_r_horiz=None):
    """Short flat hair: full-circumference cap from ear level to crown,
    nape panel, and short fringe clumps over the forehead.

    Hairline sits at the equatorial ring (ear/temple level) so hair wraps all
    the way around the head.  A back-half panel drops from the hairline to the
    nape.  Short fringe clumps fill the front/forehead zone.
    """
    hr_h = head_r_horiz if head_r_horiz is not None else head_r
    rings = _build_cap(bm, head_z, head_r, h_scale=1.20, levels=_SHORT_CAP_LEVELS,
                       head_r_horiz=head_r_horiz)
    hl = rings[0]

    # Back-half panel — 3 rows from ear level down to nape.
    _panel_rows(bm, _back_half_verts(hl), [
        (-head_r * 0.16, 0.97, 0.95),   # just below ear level
        (-head_r * 0.15, 0.93, 0.90),   # nape
        (-head_r * 0.13, 0.88, 0.85),   # lower nape
    ])

    # Short fringe — 5 shallow clumps just above the brow line.
    # fr_y: front surface of the cap at hairline level.
    hl_z = hl[0].co.z
    fr_y = -(hr_h * 0.90 * 1.06) - 0.003
    _fringe_clumps(bm, head_r, hl_z, fr_y, [
        (-0.46, -0.05, 0.04, 0.04, 0.12, 0.13),   # left temple
        (-0.22,  0.00, 0.05, 0.04, 0.13, 0.13),
        ( 0.00,  0.00, 0.05, 0.04, 0.14, 0.15),   # centre
        ( 0.22,  0.00, 0.05, 0.04, 0.13, 0.13),
        ( 0.46,  0.05, 0.04, 0.04, 0.12, 0.13),   # right temple
    ], head_r_horiz=hr_h)


# Cap levels for the spiky style.  The hairline is lower (z_off=0.20) than
# the short style so the cap covers more of the sides, giving the spikes a
# solid base to grow from.  The crown ring is kept small so it blends into
# the spike bases cleanly.
_SPIKY_CAP_LEVELS = [
    (0.20, 0.98, 0.98),   # hairline — low on forehead, wide coverage
    (0.48, 0.86, 0.79),   # upper sides
    (0.72, 0.60, 0.55),   # upper cranium
    (0.88, 0.30, 0.28),   # crown — small ring; spike bases sit at this level
]


def _build_spiky(bm, head_z, head_r, head_r_horiz=None):
    """Anime-style spiky hair: tight side/back cap + angular wedge spike crest.

    Redesigned from the old round-cone radial layout to match the anime
    convention described by the CGCookie/polycount research:

      • Spikes are flat angular *wedges* (4-triangle open pyramid), not
        round cones.  The narrow X width (0.07 hr) gives a sharp fin
        silhouette from the front; the wider Y depth (0.09 hr) gives
        a solid clump silhouette from the side.

      • Spikes form a front-to-back *crest* along the top-centre (X=0)
        rather than a radial sunburst.  This matches the clustered,
        directional look of Dragon Ball / Naruto-style hair.

      • Heights follow a bell curve: tallest near the crown centre,
        shorter toward the forehead and nape.

      • Tips lean slightly backward (+lean in Y) for the "swept-back"
        anime silhouette.

    Face budget: cap ≈ 48 + back panel ≈ 24 + spikes 6 × 4 = 24 → ~96 total.
    """
    rings = _build_cap(bm, head_z, head_r, h_scale=1.20, levels=_SPIKY_CAP_LEVELS,
                       head_r_horiz=head_r_horiz)
    hl = rings[0]

    # Side/back panel — 3 rows, same sphere-tracking taper as short style
    _panel_rows(bm, _back_half_verts(hl), [
        (-head_r * 0.16, 0.96, 0.96),
        (-head_r * 0.16, 0.94, 0.94),
        (-head_r * 0.15, 0.91, 0.91),
    ])

    # ── Anime wedge spike crest ──────────────────────────────────────────────
    crown_z = head_z + head_r * 0.88   # aligns with cap crown ring level
    spike_h = head_r * 0.90            # maximum spike height above crown_z
    bw      = head_r * 0.07            # half-width in X (sharp/narrow)
    bd      = head_r * 0.09            # half-depth in Y per spike
    lean    = head_r * 0.05            # tip leans backward (+Y = swept-back)

    # (y_centre as fraction of head_r, height_multiplier)
    spike_defs = [
        (-0.26, 0.58),   # front — shorter, sits over the forehead
        (-0.10, 0.82),
        ( 0.05, 1.00),   # tallest — crown centre
        ( 0.20, 0.86),
        ( 0.34, 0.66),
        ( 0.46, 0.48),   # back — shortest
    ]

    for yf, hm in spike_defs:
        cy  = yf * head_r
        h   = spike_h * hm
        fl  = bm.verts.new((-bw, cy - bd, crown_z))
        fr  = bm.verts.new(( bw, cy - bd, crown_z))
        bl  = bm.verts.new((-bw, cy + bd, crown_z))
        br  = bm.verts.new(( bw, cy + bd, crown_z))
        tip = bm.verts.new((0.0, cy + lean, crown_z + h))

        for fv in [
            [fl, fr, tip],   # front slope
            [br, bl, tip],   # back slope
            [bl, fl, tip],   # left face
            [fr, br, tip],   # right face
        ]:
            try:
                bm.faces.new(fv)
            except ValueError:
                pass


def _build_slicked(bm, head_z, head_r, head_r_horiz=None):
    """Slicked-back / pompadour hair: full cap + clean back panel + front quiff.

    The fringe clumps rise *upward* from the front hairline rather than
    drooping forward — creating the swept-back, voluminous-front look of
    classic 1950s-style slicked hair (à la Freddie Mercury / Kenney char4).

    Cap levels reuse _SHORT_CAP_LEVELS (equatorial hairline → crown).
    Back panel drops slightly further than "short" for a clean nape.
    Quiff: 5 clumps with negative z_tip so tips rise above the hairline.
    """
    hr_h = head_r_horiz if head_r_horiz is not None else head_r
    rings = _build_cap(bm, head_z, head_r, h_scale=1.20, levels=_SHORT_CAP_LEVELS,
                       head_r_horiz=head_r_horiz)
    hl = rings[0]
    hl_z = hl[0].co.z

    # Back panel — 4 rows, tucks under the nape cleanly
    _panel_rows(bm, _back_half_verts(hl), [
        (-head_r * 0.18, 0.97, 0.95),
        (-head_r * 0.17, 0.94, 0.92),
        (-head_r * 0.15, 0.90, 0.87),
        (-head_r * 0.13, 0.85, 0.82),
    ])

    # Front quiff — clumps start at the hairline, tips sweep UP (negative z_tip)
    # z_tip = -0.22 → tip Z = hl_z + head_r*0.22 (22 % radius above hairline)
    fr_y = -(hr_h * 0.90 * 1.06) - 0.003
    _fringe_clumps(bm, head_r, hl_z, fr_y, [
        (-0.45,  0.10, 0.00, -0.07, -0.18, 0.05),   # far left
        (-0.22,  0.05, 0.00, -0.08, -0.22, 0.06),
        ( 0.00,  0.00, 0.00, -0.09, -0.26, 0.07),   # centre — tallest
        ( 0.22, -0.05, 0.00, -0.08, -0.22, 0.06),
        ( 0.45, -0.10, 0.00, -0.07, -0.18, 0.05),   # far right
    ], head_r_horiz=hr_h)


def _build_long(bm, head_z, head_r, head_r_horiz=None):
    """Long hair flowing past the shoulders: cap + wide back curtain + fringe."""
    hr_h = head_r_horiz if head_r_horiz is not None else head_r
    rings = _build_cap(bm, head_z, head_r, h_scale=1.22, head_r_horiz=hr_h)
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
    fr_y = -(hr_h * 0.90 * 1.09) - 0.005
    _fringe_clumps(bm, head_r, hl_z, fr_y, [
        (-0.52, -0.08, 0.07, 0.06, 0.22, 0.15),
        (-0.26,  0.00, 0.08, 0.06, 0.20, 0.15),
        ( 0.00,  0.00, 0.09, 0.06, 0.22, 0.17),
        ( 0.26,  0.00, 0.08, 0.06, 0.20, 0.15),
        ( 0.52,  0.08, 0.07, 0.06, 0.22, 0.15),
    ], head_r_horiz=hr_h)


def _build_mohawk(bm, head_z, head_r, head_r_horiz=None):
    """Tall central fin front-to-back with closely-cropped side caps."""
    hr_h = head_r_horiz if head_r_horiz is not None else head_r
    # Two partial side domes, offset left/right
    for x_sign in [1, -1]:
        cx = x_sign * hr_h * 0.50
        side_rings = []
        for z_off, rx_m, ry_m in [
            (0.00, 0.36, 0.80),
            (0.22, 0.28, 0.70),
            (0.46, 0.16, 0.48),
        ]:
            side_rings.append(
                _ring(bm, cx, 0, head_z + head_r * z_off,
                      hr_h * rx_m, hr_h * ry_m)
            )
        for i in range(len(side_rings) - 1):
            _bridge(bm, side_rings[i], side_rings[i + 1])
        _close_ring(bm, side_rings[-1], top=True)

    # Central fin: 7 tapered segments, tallest at centre
    crown_z = head_z + head_r * 0.90
    ridge_w = hr_h * 0.20      # half-width of each fin panel (horizontal scale)
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


def _build_ponytail(bm, head_z, head_r, head_r_horiz=None):
    """Short front/sides with a gathered bundle hanging at the back."""
    hr_h = head_r_horiz if head_r_horiz is not None else head_r
    rings = _build_cap(bm, head_z, head_r, h_scale=1.20, head_r_horiz=hr_h)
    hl = rings[0]
    hl_z = hl[0].co.z

    # Unified back-half panel — gathers inward toward the bundle root
    _panel_rows(bm, _back_half_verts(hl), [
        (-head_r * 0.22, 1.00, 1.00),
        (-head_r * 0.42, 0.85, 0.96),
    ])

    # Fringe — 3 shorter clumps (less drop; most hair is in the ponytail).
    fr_y = -(hr_h * 0.90 * 1.07) - 0.005
    _fringe_clumps(bm, head_r, hl_z, fr_y, [
        (-0.38, -0.05, 0.05, 0.04, 0.14, 0.13),
        ( 0.00,  0.00, 0.06, 0.04, 0.14, 0.14),
        ( 0.38,  0.05, 0.05, 0.04, 0.14, 0.13),
    ], head_r_horiz=hr_h)

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
    "slicked":  _build_slicked,
    "long":     _build_long,
    "mohawk":   _build_mohawk,
    "ponytail": _build_ponytail,
}

# Public alias expected by tests and external callers
HAIR_BUILDERS = _STYLE_BUILDERS


# ── Public entry point ─────────────────────────────────────────────────────────

def create_hair(head_z, head_r, style="short", color=None, head_r_horiz=None):
    """Build hair geometry and return a linked Blender mesh object.

    Args:
        head_z:       Z coordinate of the head equator (ear/temple level).
        head_r:       Vertical head radius (equator→crown) in metres.
        head_r_horiz: Horizontal head half-width in metres.  Used for ring
                      sizing so the cap clears non-spherical heads.  Falls
                      back to head_r when None (NBM meshes / legacy callers).
        style:        Name from HAIR_STYLES.  "none" returns None.
        color:        RGBA tuple, a key from HAIR_COLORS, or None (→ dark_brown).

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
    _STYLE_BUILDERS[style](bm, head_z, head_r, head_r_horiz=head_r_horiz)
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

    # Flat cartoon hair material
    # ──────────────────────────────────────────────────────────────────────
    # Research findings (CGCookie, Blender Artists, polycount):
    #
    #   Cartoon hair reads as "flat" when specular highlights are eliminated
    #   and colour variation is minimal across the surface.  The standard
    #   technique for game-ready cartoon assets is:
    #
    #     1. Mix a small Emission contribution (~30 %) with a near-fully-matte
    #        Diffuse BSDF (roughness ≥ 0.92).
    #     2. Emission flattens shadowed areas so the colour stays uniform;
    #        Diffuse retains just enough depth cueing to read the 3-D shape.
    #     3. Zero specular — no glossy highlights that would break the toon look.
    #
    #   This approach works identically in both Cycles and Eevee, which
    #   Principled Hair BSDF does not (it is Cycles-only).
    #
    # Node graph:
    #   Emission(rgba, 0.35) ─┐
    #                          Mix(fac=0.30) → Material Output
    #   Diffuse(rgba, 0.92)  ─┘
    mat = bpy.data.materials.new(name="Hair_Material")
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Material Output
    out_node = nodes.new('ShaderNodeOutputMaterial')
    out_node.location = (600, 0)

    # Mix Shader — 30 % emission, 70 % diffuse
    mix_node = nodes.new('ShaderNodeMixShader')
    mix_node.inputs[0].default_value = 0.30
    mix_node.location = (400, 0)

    # Emission — provides the flat, self-lit cartoon colour
    emit_node = nodes.new('ShaderNodeEmission')
    emit_node.inputs['Color'].default_value = rgba
    emit_node.inputs['Strength'].default_value = 0.50
    emit_node.location = (150, 120)

    # Diffuse BSDF — near-fully matte; supplies subtle depth cueing
    diff_node = nodes.new('ShaderNodeBsdfDiffuse')
    diff_node.inputs['Color'].default_value = rgba
    diff_node.inputs['Roughness'].default_value = 0.92
    diff_node.location = (150, -80)

    links.new(emit_node.outputs['Emission'],  mix_node.inputs[1])
    links.new(diff_node.outputs['BSDF'],      mix_node.inputs[2])
    links.new(mix_node.outputs['Shader'],     out_node.inputs['Surface'])

    obj.data.materials.append(mat)

    return obj
