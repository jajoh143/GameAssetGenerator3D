"""Hair geometry builder for the humanoid gltf_pipeline.

Pure numpy port of the ring-based cap system from generators/humanoid/hair.py.
No bmesh/bpy dependency — builds geometry as numpy vertex/index arrays.
"""

import math
import numpy as np


# ── Cap level definitions (same as hair.py _CAP_LEVELS) ──────────────────────
# Each entry: (t_height, rx_scale, ry_scale)
#   t_height  — height offset as fraction of head radius (added to head_z base)
#   rx_scale  — X radius scale relative to head_r_horiz
#   ry_scale  — Y radius scale relative to head_r (front-back)
CAP_LEVELS = [
    (0.00, 0.97, 0.90),  # hairline
    (0.50, 0.84, 0.77),  # upper forehead
    (0.86, 0.52, 0.48),  # upper cranium
    (0.97, 0.14, 0.13),  # crown apex
]


def _ring_verts(cx: float, cy: float, cz: float,
                rx: float, ry: float, n: int = 12) -> list:
    """Generate n vertices of an elliptical ring in the XY plane at height cz.

    Vertex order:
      i=0 → front (y most negative, faces forward)
      ...going counterclockwise when viewed from above.
    """
    verts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        verts.append((
            cx + rx * math.sin(a),
            cy - ry * math.cos(a),
            cz,
        ))
    return verts


def _bridge_faces(ring_a_start: int, ring_b_start: int, n: int) -> list:
    """Build quad faces bridging two same-length rings.

    Args:
        ring_a_start: Starting vertex index of ring A.
        ring_b_start: Starting vertex index of ring B.
        n: Number of vertices per ring.

    Returns:
        List of (i, j, k, l) quad index tuples.
    """
    quads = []
    for i in range(n):
        j = (i + 1) % n
        quads.append((
            ring_a_start + i,
            ring_a_start + j,
            ring_b_start + j,
            ring_b_start + i,
        ))
    return quads


def _close_ring_faces(ring_start: int, n: int, centre_idx: int) -> list:
    """Close a ring with a triangle fan.

    Args:
        ring_start: Starting vertex index of the ring.
        n: Number of vertices in the ring.
        centre_idx: Index of the centre (apex) vertex.

    Returns:
        List of (i, j, k) triangle index tuples.
    """
    tris = []
    for i in range(n):
        j = (i + 1) % n
        tris.append((ring_start + i, ring_start + j, centre_idx))
    return tris


def _triangulate(quads: list) -> list:
    """Split each quad (i,j,k,l) into two triangles."""
    tris = []
    for q in quads:
        i, j, k, l = q
        tris.append((i, j, k))
        tris.append((i, k, l))
    return tris


def build_hair_geometry(head_z: float, head_r: float, style: str = "short",
                        head_r_horiz: float = None) -> tuple:
    """Build hair geometry as numpy arrays.

    Args:
        head_z: Z coordinate of the head base (bottom of head sphere).
        head_r: Head radius (vertical, front-to-back).
        style: Hair style name. Currently supports "short" and "none".
        head_r_horiz: Horizontal head radius (left-right). Defaults to head_r.

    Returns:
        (positions (N,3) float32, indices (M,3) uint32)
        Returns empty arrays for style == "none".
    """
    if style == "none":
        return (np.zeros((0, 3), dtype=np.float32),
                np.zeros((0, 3), dtype=np.uint32))

    if head_r_horiz is None:
        head_r_horiz = head_r

    N_RING = 12  # vertices per ring
    H_SCALE = 1.20  # cap height scaling

    all_verts = []
    all_tris = []

    # ── Build the 4-level cap ────────────────────────────────────────────────
    # Cap covers from hairline up to crown apex.
    # head_z is the base of the head — the cap sits on top.
    # The cap "height" spans from head_z to head_z + 2*head_r*H_SCALE (top).

    cap_rings = []  # list of (start_idx, n) for each ring

    for level_idx, (t_h, rx_scale, ry_scale) in enumerate(CAP_LEVELS):
        cz = head_z + t_h * 2.0 * head_r * H_SCALE
        rx = head_r_horiz * rx_scale
        ry = head_r * ry_scale

        vstart = len(all_verts)
        ring = _ring_verts(0.0, 0.0, cz, rx, ry, N_RING)
        all_verts.extend(ring)
        cap_rings.append((vstart, N_RING))

    # Bridge consecutive rings
    for i in range(len(cap_rings) - 1):
        a_start, a_n = cap_rings[i]
        b_start, b_n = cap_rings[i + 1]
        quads = _bridge_faces(a_start, b_start, a_n)
        tris = _triangulate(quads)
        all_tris.extend(tris)

    # Close the top ring with a fan
    top_start, top_n = cap_rings[-1]
    # Compute crown apex position (average of top ring verts)
    top_verts = all_verts[top_start:top_start + top_n]
    cx_top = sum(v[0] for v in top_verts) / top_n
    cy_top = sum(v[1] for v in top_verts) / top_n
    cz_top = sum(v[2] for v in top_verts) / top_n
    # Raise the apex slightly above the top ring
    apex_z = cz_top + head_r * 0.05
    apex_idx = len(all_verts)
    all_verts.append((cx_top, cy_top, apex_z))
    tris = _close_ring_faces(top_start, top_n, apex_idx)
    all_tris.extend(tris)

    # ── Short style: add back fringe ─────────────────────────────────────────
    if style == "short":
        # Back fringe: lower ring at the back half of the hairline, bridged down
        hairline_start, hairline_n = cap_rings[0]
        fringe_drop = head_r * 0.3  # how far down the fringe hangs
        fringe_cz = head_z - fringe_drop * 0.5

        # Use only the back half of the hairline ring (indices n//4 to 3n//4)
        back_start = hairline_n // 4
        back_end = 3 * hairline_n // 4 + 1
        back_count = back_end - back_start

        # Create a lower fringe ring (back half only)
        fringe_vstart = len(all_verts)
        for i in range(back_start, back_end):
            hv = all_verts[hairline_start + i]
            # Drop it down and slightly outward
            all_verts.append((hv[0] * 1.05, hv[1] * 1.05, fringe_cz))

        # Bridge hairline-back to fringe ring
        for i in range(back_count - 1):
            a = hairline_start + back_start + i
            b = hairline_start + back_start + i + 1
            c = fringe_vstart + i + 1
            d = fringe_vstart + i
            all_tris.append((a, b, c))
            all_tris.append((a, c, d))

        # Close bottom of fringe with a strip
        for i in range(back_count - 1):
            va = fringe_vstart + i
            vb = fringe_vstart + i + 1
            # Add bottom edge vertices
            bot_a = len(all_verts)
            all_verts.append((all_verts[va][0], all_verts[va][1], fringe_cz - fringe_drop))
            bot_b = len(all_verts)
            all_verts.append((all_verts[vb][0], all_verts[vb][1], fringe_cz - fringe_drop))
            all_tris.append((va, vb, bot_b))
            all_tris.append((va, bot_b, bot_a))

    # ── Convert to numpy arrays ────────────────────────────────────────────────
    if not all_verts:
        return (np.zeros((0, 3), dtype=np.float32),
                np.zeros((0, 3), dtype=np.uint32))

    positions = np.array(all_verts, dtype=np.float32)
    indices = np.array(all_tris, dtype=np.uint32)

    return positions, indices
