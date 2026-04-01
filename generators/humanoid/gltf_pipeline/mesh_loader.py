"""Mesh loader for the humanoid gltf_pipeline.

Loads Cartoon_Male.glb using pygltflib, extracts geometry as numpy arrays,
remaps GLB joint indices to our 19-bone skeleton, and normalizes the mesh height.
"""

import os
from dataclasses import dataclass

import numpy as np

try:
    import pygltflib
except ImportError:
    raise ImportError("pygltflib is required: pip install pygltflib")

from ..template_mesh import CARTOON_MALE_GLB
from .skeleton import BONE_NAMES

# ── Joint name → our bone index mapping ───────────────────────────────────────

GLB_JOINT_TO_BONE_IDX: dict[str, int] = {
    "Hips": 0, "HipsCtrl": 0,
    "Spine": 1, "Chest": 2, "UpperChest": 2,
    "Neck": 3, "Head": 4,
    "LeftShoulder": 5, "LeftArm": 6, "LeftForeArm": 7,
    "LeftHand": 8, "LeftHandIndex1": 8, "LeftHandIndex2": 8,
    "LeftHandIndex3": 8, "LeftHandThumb1": 8, "LeftHandThumb2": 8,
    "RightShoulder": 9, "RightArm": 10, "RightForeArm": 11,
    "RightHand": 12, "RightHandIndex1": 12, "RightHandIndex2": 12,
    "RightHandIndex3": 12, "RightHandThumb1": 12, "RightHandThumb2": 12,
    "LeftUpLeg": 13, "LeftLeg": 14, "LeftFoot": 15, "LeftToes": 15,
    "RightUpLeg": 16, "RightLeg": 17, "RightFoot": 18, "RightToes": 18,
}


@dataclass
class MeshData:
    positions: np.ndarray   # (N, 3) float32
    normals: np.ndarray     # (N, 3) float32
    texcoords: np.ndarray   # (N, 2) float32
    joints: np.ndarray      # (N, 4) uint8
    weights: np.ndarray     # (N, 4) float32, rows sum to 1
    indices: np.ndarray     # (M,) uint32
    height: float           # actual mesh height after normalization


def _compute_flat_normals(positions: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Compute flat normals: same normal for all 3 vertices of each triangle."""
    normals = np.zeros_like(positions)
    tri_count = len(indices) // 3
    tris = indices[:tri_count * 3].reshape(-1, 3)
    a = positions[tris[:, 0]]
    b = positions[tris[:, 1]]
    c = positions[tris[:, 2]]
    edge1 = b - a
    edge2 = c - a
    face_normals = np.cross(edge1, edge2)
    lengths = np.linalg.norm(face_normals, axis=1, keepdims=True)
    lengths = np.where(lengths < 1e-8, 1.0, lengths)
    face_normals /= lengths
    for i, tri in enumerate(tris):
        for vi in tri:
            normals[vi] += face_normals[i]
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    lengths = np.where(lengths < 1e-8, 1.0, lengths)
    normals /= lengths
    return normals.astype(np.float32)


def _get_accessor_data(gltf: "pygltflib.GLTF2", accessor_idx: int) -> np.ndarray:
    """Extract accessor data as a numpy array."""
    accessor = gltf.accessors[accessor_idx]
    data = gltf.get_data_from_accessor(accessor_idx)
    arr = np.array(data)

    # Determine component dtype
    ct = accessor.componentType
    if ct == pygltflib.FLOAT:
        arr = arr.astype(np.float32)
    elif ct == pygltflib.UNSIGNED_BYTE:
        arr = arr.astype(np.uint8)
    elif ct == pygltflib.UNSIGNED_SHORT:
        arr = arr.astype(np.uint16)
    elif ct == pygltflib.UNSIGNED_INT:
        arr = arr.astype(np.uint32)
    else:
        arr = arr.astype(np.float32)

    return arr


def _extract_primitive(gltf: "pygltflib.GLTF2", prim) -> dict:
    """Extract a single mesh primitive as numpy arrays."""
    attrs = prim.attributes

    # Positions (required)
    pos = _get_accessor_data(gltf, attrs.POSITION).reshape(-1, 3).astype(np.float32)

    # Normals (optional)
    if attrs.NORMAL is not None:
        nrm = _get_accessor_data(gltf, attrs.NORMAL).reshape(-1, 3).astype(np.float32)
    else:
        nrm = None  # computed after merging

    # Texcoords (optional)
    if attrs.TEXCOORD_0 is not None:
        uvs = _get_accessor_data(gltf, attrs.TEXCOORD_0).reshape(-1, 2).astype(np.float32)
    else:
        uvs = np.zeros((len(pos), 2), dtype=np.float32)

    # Joints (optional — may be absent for non-skinned primitives)
    if attrs.JOINTS_0 is not None:
        jnts = _get_accessor_data(gltf, attrs.JOINTS_0).reshape(-1, 4)
        jnts = jnts.astype(np.uint16)
    else:
        jnts = np.zeros((len(pos), 4), dtype=np.uint16)

    # Weights (optional)
    if attrs.WEIGHTS_0 is not None:
        wgts = _get_accessor_data(gltf, attrs.WEIGHTS_0).reshape(-1, 4).astype(np.float32)
    else:
        wgts = np.zeros((len(pos), 4), dtype=np.float32)
        wgts[:, 0] = 1.0  # full weight on bone 0

    # Indices
    if prim.indices is not None:
        idx = _get_accessor_data(gltf, prim.indices).flatten().astype(np.uint32)
    else:
        idx = np.arange(len(pos), dtype=np.uint32)

    return {
        "positions": pos,
        "normals": nrm,
        "texcoords": uvs,
        "joints": jnts,
        "weights": wgts,
        "indices": idx,
    }


def _remap_joints(joints: np.ndarray, weights: np.ndarray,
                  glb_joint_idx_to_ours: dict[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Remap GLB joint indices to our 19-bone skeleton, merge duplicates, renormalize.

    Args:
        joints: (N, 4) uint16 GLB joint indices.
        weights: (N, 4) float32 weights.
        glb_joint_idx_to_ours: mapping from GLB joint index → our bone index (0-18).

    Returns:
        (remapped_joints (N,4) uint8, renormalized_weights (N,4) float32)
    """
    N = len(joints)
    out_joints = np.zeros((N, 4), dtype=np.uint8)
    out_weights = np.zeros((N, 4), dtype=np.float32)

    for vi in range(N):
        # Accumulate weights per our-bone-index
        bone_weights: dict[int, float] = {}
        for slot in range(4):
            glb_idx = int(joints[vi, slot])
            our_idx = glb_joint_idx_to_ours.get(glb_idx, 0)
            w = float(weights[vi, slot])
            if w > 0.0:
                bone_weights[our_idx] = bone_weights.get(our_idx, 0.0) + w

        # Sort by weight descending, take top 4
        sorted_bones = sorted(bone_weights.items(), key=lambda x: x[1], reverse=True)[:4]

        total = sum(w for _, w in sorted_bones)
        if total < 1e-8:
            # Fallback: all weight on bone 0 (Hips)
            sorted_bones = [(0, 1.0)]
            total = 1.0

        for slot, (bone_idx, w) in enumerate(sorted_bones):
            out_joints[vi, slot] = bone_idx
            out_weights[vi, slot] = w / total

    return out_joints, out_weights


def load_cartoon_male(target_height: float) -> MeshData:
    """Load Cartoon_Male.glb, normalize it to target_height, remap joints.

    Args:
        target_height: Desired character height in meters.

    Returns:
        MeshData with normalized mesh at the target height.

    Raises:
        FileNotFoundError: If Cartoon_Male.glb does not exist.
        RuntimeError: If no mesh/skin data is found.
    """
    glb_path = CARTOON_MALE_GLB
    if not os.path.isfile(glb_path):
        raise FileNotFoundError(
            f"Template mesh not found: {glb_path}\n"
            f"Expected Cartoon_Male.glb in assets/TemplateMeshes/"
        )

    gltf = pygltflib.GLTF2().load(glb_path)

    # ── Build joint index mapping ──────────────────────────────────────────────
    if not gltf.skins:
        raise RuntimeError("No skin found in Cartoon_Male.glb")

    skin = gltf.skins[0]
    glb_joint_names = [gltf.nodes[j].name for j in skin.joints]

    # GLB joint list index → our bone index
    glb_joint_idx_to_ours: dict[int, int] = {}
    for glb_i, joint_name in enumerate(glb_joint_names):
        our_idx = GLB_JOINT_TO_BONE_IDX.get(joint_name, None)
        if our_idx is not None:
            glb_joint_idx_to_ours[glb_i] = our_idx
        # else: unmapped joints will fallback to bone 0 (Hips) during remap

    # ── Extract and merge all mesh primitives ─────────────────────────────────
    all_prims = []
    for mesh in gltf.meshes:
        for prim in mesh.primitives:
            all_prims.append(_extract_primitive(gltf, prim))

    if not all_prims:
        raise RuntimeError("No mesh primitives found in Cartoon_Male.glb")

    # Merge primitives (offset indices, concatenate vertices)
    merged_pos = []
    merged_nrm = []
    merged_uvs = []
    merged_jnts = []
    merged_wgts = []
    merged_idx = []
    vertex_offset = 0

    for prim in all_prims:
        n = len(prim["positions"])
        merged_pos.append(prim["positions"])
        merged_uvs.append(prim["texcoords"])
        merged_jnts.append(prim["joints"])
        merged_wgts.append(prim["weights"])

        if prim["normals"] is not None:
            merged_nrm.append(prim["normals"])
        else:
            merged_nrm.append(np.zeros((n, 3), dtype=np.float32))  # placeholder

        merged_idx.append(prim["indices"] + vertex_offset)
        vertex_offset += n

    positions = np.concatenate(merged_pos, axis=0)
    normals = np.concatenate(merged_nrm, axis=0)
    texcoords = np.concatenate(merged_uvs, axis=0)
    joints_raw = np.concatenate(merged_jnts, axis=0)
    weights_raw = np.concatenate(merged_wgts, axis=0)
    indices = np.concatenate(merged_idx, axis=0).astype(np.uint32)

    # Recompute flat normals if any primitive was missing normals
    # (safer: always compute if the merged normals appear to be all-zero)
    if np.all(normals == 0):
        normals = _compute_flat_normals(positions, indices)

    # ── Normalize mesh height ──────────────────────────────────────────────────
    min_z = float(positions[:, 2].min())
    max_z = float(positions[:, 2].max())
    mesh_height = max_z - min_z

    if mesh_height < 1e-6:
        raise RuntimeError("Mesh has zero height — cannot normalize.")

    scale = target_height / mesh_height
    positions = positions * scale

    # Shift so feet are at Z=0
    min_z_new = float(positions[:, 2].min())
    positions[:, 2] -= min_z_new

    actual_height = float(positions[:, 2].max())

    # ── Remap joints ──────────────────────────────────────────────────────────
    joints_remapped, weights_remapped = _remap_joints(
        joints_raw, weights_raw, glb_joint_idx_to_ours
    )

    return MeshData(
        positions=positions.astype(np.float32),
        normals=normals.astype(np.float32),
        texcoords=texcoords.astype(np.float32),
        joints=joints_remapped.astype(np.uint8),
        weights=weights_remapped.astype(np.float32),
        indices=indices.astype(np.uint32),
        height=actual_height,
    )
