"""Skeleton definitions for the humanoid gltf_pipeline.

19-bone hierarchy with rest positions, parent indices, and inverse bind matrices.
All bone positions are computed proportionally based on character height H.
"""

import numpy as np

# ── Bone list (index order matches JOINTS in glTF skin) ──────────────────────

BONE_NAMES = [
    "Hips",                                             # 0  — root
    "Spine", "Chest", "Neck", "Head",                  # 1-4
    "Shoulder.L", "UpperArm.L", "LowerArm.L", "Hand.L",  # 5-8
    "Shoulder.R", "UpperArm.R", "LowerArm.R", "Hand.R",  # 9-12
    "UpperLeg.L", "LowerLeg.L", "Foot.L",              # 13-15
    "UpperLeg.R", "LowerLeg.R", "Foot.R",              # 16-18
]

NUM_BONES = len(BONE_NAMES)  # 19

# ── Parent indices (-1 = root) ────────────────────────────────────────────────

BONE_PARENTS = [
    -1,   # Hips
     0,   # Spine → Hips
     1,   # Chest → Spine
     2,   # Neck → Chest
     3,   # Head → Neck
     2,   # Shoulder.L → Chest
     5,   # UpperArm.L → Shoulder.L
     6,   # LowerArm.L → UpperArm.L
     7,   # Hand.L → LowerArm.L
     2,   # Shoulder.R → Chest
     9,   # UpperArm.R → Shoulder.R
    10,   # LowerArm.R → UpperArm.R
    11,   # Hand.R → LowerArm.R
     0,   # UpperLeg.L → Hips
    13,   # LowerLeg.L → UpperLeg.L
    14,   # Foot.L → LowerLeg.L
     0,   # UpperLeg.R → Hips
    16,   # LowerLeg.R → UpperLeg.R
    17,   # Foot.R → LowerLeg.R
]


def compute_bone_world_positions(H: float) -> np.ndarray:
    """Compute rest (bind) world positions for each bone proportional to height H.

    Args:
        H: Character height in meters.

    Returns:
        Array of shape (19, 3) float32 with (x, y, z) world positions.
    """
    positions = np.array([
        # Spine / head chain
        [0.0,       0.0,       H * 0.52],   # 0  Hips
        [0.0,       0.0,       H * 0.60],   # 1  Spine
        [0.0,       0.0,       H * 0.68],   # 2  Chest
        [0.0,       0.0,       H * 0.82],   # 3  Neck
        [0.0,       0.0,       H * 0.87],   # 4  Head
        # Left arm chain
        [+H * 0.08, 0.0,       H * 0.72],   # 5  Shoulder.L
        [+H * 0.14, 0.0,       H * 0.70],   # 6  UpperArm.L
        [+H * 0.14, 0.0,       H * 0.53],   # 7  LowerArm.L
        [+H * 0.14, 0.0,       H * 0.38],   # 8  Hand.L
        # Right arm chain
        [-H * 0.08, 0.0,       H * 0.72],   # 9  Shoulder.R
        [-H * 0.14, 0.0,       H * 0.70],   # 10 UpperArm.R
        [-H * 0.14, 0.0,       H * 0.53],   # 11 LowerArm.R
        [-H * 0.14, 0.0,       H * 0.38],   # 12 Hand.R
        # Left leg chain
        [+H * 0.09, 0.0,       H * 0.50],   # 13 UpperLeg.L
        [+H * 0.09, 0.0,       H * 0.27],   # 14 LowerLeg.L
        [+H * 0.09, H * 0.08,  H * 0.03],   # 15 Foot.L
        # Right leg chain
        [-H * 0.09, 0.0,       H * 0.50],   # 16 UpperLeg.R
        [-H * 0.09, 0.0,       H * 0.27],   # 17 LowerLeg.R
        [-H * 0.09, H * 0.08,  H * 0.03],   # 18 Foot.R
    ], dtype=np.float32)
    return positions


def compute_inverse_bind_matrices(world_positions: np.ndarray) -> np.ndarray:
    """Compute inverse bind matrices for each bone.

    Since bones are just translations at rest (no rotation), the bind matrix is:
        [[1, 0, 0, -px],
         [0, 1, 0, -py],
         [0, 0, 1, -pz],
         [0, 0, 0,   1]]

    glTF stores matrices in column-major order.

    Args:
        world_positions: Array of shape (19, 3).

    Returns:
        Array of shape (19, 4, 4) float32 — inverse bind matrices in column-major
        layout (ready to flatten with .flatten(order='F') or .T.flatten() per bone).
    """
    n = len(world_positions)
    inv_bind = np.zeros((n, 4, 4), dtype=np.float32)

    for i, (px, py, pz) in enumerate(world_positions):
        # Row-major inverse bind matrix (translation negated)
        mat = np.eye(4, dtype=np.float32)
        mat[0, 3] = -px
        mat[1, 3] = -py
        mat[2, 3] = -pz
        inv_bind[i] = mat

    return inv_bind


def bone_name_to_index(name: str) -> int:
    """Return the bone index for a given bone name, or -1 if not found."""
    try:
        return BONE_NAMES.index(name)
    except ValueError:
        return -1
