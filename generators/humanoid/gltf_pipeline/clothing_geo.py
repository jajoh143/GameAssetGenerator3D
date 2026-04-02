"""Clothing geometry builder for the humanoid gltf_pipeline.

Face-extrusion approach in pure numpy — no bmesh/bpy.
Selects body mesh triangles by Z range and offsets them outward radially.
"""

import numpy as np
from .mesh_loader import MeshData


# ── Clothing zone definitions ────────────────────────────────────────────────
# Built dynamically from mesh height. See ZONES computation in build_clothing_geometry.

BODY_X_CAP = 0.28  # X threshold for leg/arm separation


def _select_zone_tris(positions: np.ndarray, indices: np.ndarray,
                      z_min: float, z_max: float,
                      x_cap: float = None) -> np.ndarray:
    """Return triangle indices whose vertices all fall within [z_min, z_max].

    Args:
        positions: (N, 3) vertex positions.
        indices: (M,) flat triangle indices (M % 3 == 0).
        z_min: Minimum Z threshold.
        z_max: Maximum Z threshold.
        x_cap: If given, further restrict to |x| < x_cap.

    Returns:
        Boolean mask of shape (M//3,) — True for selected triangles.
    """
    tris = indices.reshape(-1, 3)
    v0_z = positions[tris[:, 0], 2]
    v1_z = positions[tris[:, 1], 2]
    v2_z = positions[tris[:, 2], 2]

    # Triangle is in zone if ANY vertex is in range
    in_z = (
        ((v0_z >= z_min) & (v0_z <= z_max)) |
        ((v1_z >= z_min) & (v1_z <= z_max)) |
        ((v2_z >= z_min) & (v2_z <= z_max))
    )

    if x_cap is not None:
        v0_x = np.abs(positions[tris[:, 0], 0])
        v1_x = np.abs(positions[tris[:, 1], 0])
        v2_x = np.abs(positions[tris[:, 2], 0])
        in_x = (v0_x < x_cap) & (v1_x < x_cap) & (v2_x < x_cap)
        return in_z & in_x

    return in_z


def _offset_verts_radially(positions: np.ndarray, offset: float = 0.015) -> np.ndarray:
    """Offset vertices outward radially from the Z-axis by `offset` meters.

    Args:
        positions: (N, 3) vertex positions.
        offset: Radial offset in meters (default 15mm).

    Returns:
        (N, 3) offset positions.
    """
    xy = positions[:, :2].copy()
    r = np.linalg.norm(xy, axis=1, keepdims=True)
    # Avoid division by zero at the Z-axis
    r_safe = np.where(r < 1e-6, 1.0, r)
    direction = xy / r_safe
    new_xy = xy + direction * offset
    result = positions.copy()
    result[:, :2] = new_xy
    return result


def build_clothing_geometry(mesh: MeshData, cfg: dict) -> dict:
    """Build clothing geometry by extruding body mesh faces outward.

    Args:
        mesh: Loaded body MeshData.
        cfg: Character config dict. Expected key: cfg["clothing"] (list of str).

    Returns:
        Dict mapping clothing type name → (positions (N,3) float32, indices (M,3) uint32).
        Returns only the types found in cfg["clothing"].
    """
    H = mesh.height
    positions = mesh.positions
    indices = mesh.indices

    # ── Zone boundaries (Z values relative to mesh height) ──────────────────
    foot_top = 0.06
    hip_z = H * 0.50
    chest_z = H * 0.68
    waist_gap = 0.02

    ZONES = {
        "short_sleeve": (hip_z + waist_gap, chest_z + 0.05, True),
        "long_sleeve":  (hip_z + waist_gap, chest_z + 0.05, True),
        "v_neck":       (hip_z + waist_gap, chest_z + 0.05, True),
        "jeans":        (foot_top - 0.02,   hip_z + (chest_z - hip_z) * 0.10, False),
        "shorts":       (foot_top + (hip_z - foot_top) * 0.38,
                         hip_z + (chest_z - hip_z) * 0.10, False),
    }

    clothing_list = cfg.get("clothing", [])
    if not clothing_list:
        return {}

    result = {}

    for ctype in clothing_list:
        zone = ZONES.get(ctype)
        if zone is None:
            continue

        z_min, z_max, is_upper = zone
        # For leg clothing, restrict to torso X range
        x_cap = BODY_X_CAP if not is_upper else None

        tri_mask = _select_zone_tris(positions, indices, z_min, z_max, x_cap)

        if not np.any(tri_mask):
            continue

        # Extract selected triangles
        tris = indices.reshape(-1, 3)[tri_mask]

        # Gather unique vertices used by these triangles
        unique_verts, new_tri_indices = np.unique(tris, return_inverse=True)
        sub_positions = positions[unique_verts]

        # Offset outward
        sub_positions = _offset_verts_radially(sub_positions, offset=0.015)

        new_tris = new_tri_indices.reshape(-1, 3).astype(np.uint32)

        result[ctype] = (sub_positions.astype(np.float32), new_tris)

    return result
