"""Core assembler for the humanoid gltf_pipeline.

Builds a complete GLTF2 object with body mesh, skeleton, hair, clothing,
and animations — all without Blender (pure pygltflib + numpy).
"""

import struct
import numpy as np

from pygltflib import (
    GLTF2, Scene, Node, Mesh, Primitive, Skin, Animation,
    AnimationSampler, AnimationChannel, AnimationChannelTarget,
    Accessor, BufferView, Buffer, Asset, Attributes,
    FLOAT, UNSIGNED_INT, UNSIGNED_BYTE, UNSIGNED_SHORT,
    VEC3, VEC4, SCALAR, MAT4, LINEAR,
)

from . import skeleton as skel_mod
from . import mesh_loader
from . import hair_geo
from . import clothing_geo
from . import materials as mat_mod
from . import anim_data


# glTF buffer target constants (array buffer / element array buffer)
ARRAY_BUFFER = 34962
ELEMENT_ARRAY_BUFFER = 34963


# ── Default clothing colors ────────────────────────────────────────────────────

_DEFAULT_CLOTHING_COLORS = {
    "short_sleeve": (0.25, 0.35, 0.65, 1.0),
    "long_sleeve":  (0.20, 0.30, 0.55, 1.0),
    "v_neck":       (0.55, 0.25, 0.25, 1.0),
    "jeans":        (0.20, 0.25, 0.45, 1.0),
    "shorts":       (0.35, 0.45, 0.30, 1.0),
}

_DEFAULT_HAIR_COLOR = (0.18, 0.10, 0.06, 1.0)  # dark_brown


# ── Buffer packing helper ─────────────────────────────────────────────────────

class BufferBuilder:
    """Accumulates binary data for a single glTF buffer."""

    def __init__(self):
        self._data = bytearray()
        self.views = []  # list of (offset, length, target_or_None)

    def add(self, array: np.ndarray, target=None) -> int:
        """Append array bytes (4-byte aligned), return view index."""
        raw = array.tobytes()
        # Pad current offset to 4-byte alignment
        pad = (4 - len(self._data) % 4) % 4
        self._data += b'\x00' * pad
        offset = len(self._data)
        self._data += raw
        idx = len(self.views)
        self.views.append((offset, len(raw), target))
        return idx

    def build(self) -> bytes:
        return bytes(self._data)


def _type_str_to_components(type_str: str) -> int:
    """Return number of components for a glTF accessor type string."""
    return {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[type_str]


def _component_size(component_type: int) -> int:
    """Return byte size for a glTF component type constant."""
    return {
        FLOAT: 4,
        UNSIGNED_INT: 4,
        UNSIGNED_SHORT: 2,
        UNSIGNED_BYTE: 1,
    }.get(component_type, 4)


def make_accessor(gltf: GLTF2, buf_builder: BufferBuilder,
                  array: np.ndarray, component_type: int, type_str: str,
                  target=None) -> int:
    """Add array to buffer, create BufferView + Accessor, return accessor index.

    Args:
        gltf: GLTF2 object being built.
        buf_builder: BufferBuilder accumulating binary data.
        array: numpy array to store.
        component_type: glTF component type constant (FLOAT, UNSIGNED_INT, etc.).
        type_str: glTF type string ("SCALAR", "VEC3", "MAT4", etc.).
        target: Optional buffer view target (ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER).

    Returns:
        Index of the new accessor in gltf.accessors.
    """
    view_idx = buf_builder.add(array, target)
    offset, length, _ = buf_builder.views[view_idx]

    # BufferView
    bv = BufferView(
        buffer=0,
        byteOffset=offset,
        byteLength=length,
        target=target,
    )
    bv_idx = len(gltf.bufferViews)
    gltf.bufferViews.append(bv)

    # Count = number of elements (considering multi-component types)
    n_components = _type_str_to_components(type_str)
    flat_count = array.size
    count = flat_count // n_components

    # Accessor min/max for POSITION accessor (required by spec)
    accessor_min = None
    accessor_max = None
    if type_str == "VEC3" and component_type == FLOAT:
        arr3 = array.reshape(-1, 3)
        accessor_min = arr3.min(axis=0).tolist()
        accessor_max = arr3.max(axis=0).tolist()

    acc = Accessor(
        bufferView=bv_idx,
        byteOffset=0,
        componentType=component_type,
        count=count,
        type=type_str,
        min=accessor_min,
        max=accessor_max,
    )
    acc_idx = len(gltf.accessors)
    gltf.accessors.append(acc)
    return acc_idx


# ── Main builder ──────────────────────────────────────────────────────────────

def build_humanoid_gltf(cfg: dict) -> GLTF2:
    """Build a complete GLTF2 object for a rigged animated humanoid.

    Args:
        cfg: Character config dict (from presets.resolve_config or equivalent).

    Returns:
        GLTF2 object ready to be saved as GLB.
    """
    gltf = GLTF2()
    gltf.asset = Asset(version="2.0", generator="GameAssetGenerator3D/gltf_pipeline")

    buf_builder = BufferBuilder()

    target_height = cfg.get("height", 1.75)
    hair_style = cfg.get("hair_style", "none")
    skin_tone = cfg.get("skin_tone", (0.78, 0.60, 0.46, 1.0))
    hair_color = cfg.get("hair_color", "dark_brown")
    clothing_list = cfg.get("clothing", [])
    animations_cfg = cfg.get("animations", [])

    # ── A. Load body mesh ────────────────────────────────────────────────────
    try:
        mesh_data = mesh_loader.load_cartoon_male(target_height)
    except FileNotFoundError as e:
        # Fallback: create a minimal placeholder mesh (a simple box)
        print(f"[gltf_pipeline] WARNING: {e}")
        print("[gltf_pipeline] Using placeholder mesh.")
        mesh_data = _make_placeholder_mesh(target_height)

    H = mesh_data.height

    # ── B. Build skeleton nodes ───────────────────────────────────────────────
    world_pos = skel_mod.compute_bone_world_positions(H)
    inv_bind = skel_mod.compute_inverse_bind_matrices(world_pos)
    n_bones = skel_mod.NUM_BONES

    # Node index offset: we'll add one scene root node first
    SCENE_ROOT_IDX = 0
    BONE_NODE_OFFSET = 1  # bone nodes start at index 1

    # Create bone nodes
    bone_nodes = []
    for i in range(n_bones):
        parent_idx = skel_mod.BONE_PARENTS[i]
        if parent_idx == -1:
            # Root bone: translation = world position
            tx, ty, tz = world_pos[i].tolist()
        else:
            # Local translation = world - parent_world
            px, py, pz = world_pos[parent_idx].tolist()
            wx, wy, wz = world_pos[i].tolist()
            tx, ty, tz = wx - px, wy - py, wz - pz

        node = Node(
            name=skel_mod.BONE_NAMES[i],
            translation=[float(tx), float(ty), float(tz)],
            children=[],
        )
        bone_nodes.append(node)

    # Wire up children
    for i in range(n_bones):
        parent_idx = skel_mod.BONE_PARENTS[i]
        if parent_idx != -1:
            bone_nodes[parent_idx].children.append(BONE_NODE_OFFSET + i)

    # ── C. Build inverse bind matrix accessor ────────────────────────────────
    # glTF matrices are column-major, so we need to transpose each row-major matrix
    ibm_flat = np.zeros((n_bones, 16), dtype=np.float32)
    for i in range(n_bones):
        # inv_bind[i] is row-major 4x4, glTF wants column-major → transpose
        ibm_flat[i] = inv_bind[i].T.flatten()

    ibm_array = ibm_flat.flatten()
    ibm_acc_idx = make_accessor(gltf, buf_builder, ibm_array, FLOAT, MAT4)

    # ── D. Build skin ────────────────────────────────────────────────────────
    joint_indices = list(range(BONE_NODE_OFFSET, BONE_NODE_OFFSET + n_bones))
    skin = Skin(
        name="HumanoidSkin",
        inverseBindMatrices=ibm_acc_idx,
        joints=joint_indices,
    )
    skin_idx = len(gltf.skins)
    gltf.skins.append(skin)

    # ── E. Add body mesh primitive ────────────────────────────────────────────
    pos_acc = make_accessor(gltf, buf_builder, mesh_data.positions,
                            FLOAT, VEC3, ARRAY_BUFFER)
    nrm_acc = make_accessor(gltf, buf_builder, mesh_data.normals,
                            FLOAT, VEC3, ARRAY_BUFFER)
    uv_acc = make_accessor(gltf, buf_builder, mesh_data.texcoords,
                           FLOAT, "VEC2", ARRAY_BUFFER)
    jnt_acc = make_accessor(gltf, buf_builder, mesh_data.joints,
                            UNSIGNED_BYTE, VEC4, ARRAY_BUFFER)
    wgt_acc = make_accessor(gltf, buf_builder, mesh_data.weights,
                            FLOAT, VEC4, ARRAY_BUFFER)
    idx_acc = make_accessor(gltf, buf_builder, mesh_data.indices,
                            UNSIGNED_INT, SCALAR, ELEMENT_ARRAY_BUFFER)

    # Skin material
    skin_mat = mat_mod.skin_material(_resolve_rgba(skin_tone))
    skin_mat_idx = len(gltf.materials)
    gltf.materials.append(skin_mat)

    body_prim = Primitive(
        attributes=Attributes(
            POSITION=pos_acc,
            NORMAL=nrm_acc,
            TEXCOORD_0=uv_acc,
            JOINTS_0=jnt_acc,
            WEIGHTS_0=wgt_acc,
        ),
        indices=idx_acc,
        material=skin_mat_idx,
        mode=4,  # TRIANGLES
    )
    body_mesh = Mesh(name="Body", primitives=[body_prim])
    body_mesh_idx = len(gltf.meshes)
    gltf.meshes.append(body_mesh)

    # Scene root node
    scene_root = Node(name="HumanoidRoot", children=[])
    gltf.nodes.append(scene_root)  # index 0

    # Add bone nodes
    for bn in bone_nodes:
        gltf.nodes.append(bn)

    # Body node (skinned, references skin)
    body_node = Node(name="BodyMesh", mesh=body_mesh_idx, skin=skin_idx)
    body_node_idx = len(gltf.nodes)
    gltf.nodes.append(body_node)

    # Add body node as child of root hips bone? No — skinned nodes sit at root
    # per glTF spec the skinned mesh node should be a child of the scene root
    scene_root.children.append(body_node_idx)
    # Also add skeleton root (bone 0 = Hips) as child of scene root
    scene_root.children.append(BONE_NODE_OFFSET + 0)

    # ── F. Hair ───────────────────────────────────────────────────────────────
    if hair_style and hair_style != "none":
        head_bone_world = world_pos[4]  # Head bone index 4
        head_z_local = float(head_bone_world[2])

        head_size = cfg.get("head_size", H * 0.13)
        hair_positions, hair_indices = hair_geo.build_hair_geometry(
            head_z=head_z_local,
            head_r=head_size,
            style=hair_style,
        )

        if len(hair_positions) > 0 and len(hair_indices) > 0:
            hair_rgba = _resolve_hair_rgba(hair_color)
            h_mat = mat_mod.hair_material(hair_rgba)
            h_mat_idx = len(gltf.materials)
            gltf.materials.append(h_mat)

            h_pos_acc = make_accessor(gltf, buf_builder, hair_positions,
                                      FLOAT, VEC3, ARRAY_BUFFER)
            # Simple flat normals for hair
            h_normals = _flat_normals_from_mesh(hair_positions, hair_indices)
            h_nrm_acc = make_accessor(gltf, buf_builder, h_normals,
                                      FLOAT, VEC3, ARRAY_BUFFER)
            h_idx_acc = make_accessor(gltf, buf_builder,
                                      hair_indices.flatten().astype(np.uint32),
                                      UNSIGNED_INT, SCALAR, ELEMENT_ARRAY_BUFFER)

            hair_prim = Primitive(
                attributes=Attributes(
                    POSITION=h_pos_acc,
                    NORMAL=h_nrm_acc,
                ),
                indices=h_idx_acc,
                material=h_mat_idx,
                mode=4,
            )
            hair_mesh = Mesh(name="Hair", primitives=[hair_prim])
            hair_mesh_idx = len(gltf.meshes)
            gltf.meshes.append(hair_mesh)

            # Hair node is child of Head bone (bone index 4)
            # Hair geometry is in world space so we offset by -head_bone_world
            hair_node = Node(
                name="HairMesh",
                mesh=hair_mesh_idx,
                translation=[0.0, 0.0, 0.0],
            )
            hair_node_idx = len(gltf.nodes)
            gltf.nodes.append(hair_node)
            head_bone_node_idx = BONE_NODE_OFFSET + 4  # Head bone
            gltf.nodes[head_bone_node_idx].children.append(hair_node_idx)

    # ── G. Clothing ───────────────────────────────────────────────────────────
    if clothing_list:
        clothing_geos = clothing_geo.build_clothing_geometry(mesh_data, cfg)
        clothing_colors = cfg.get("clothing_color") or {}
        hips_bone_node_idx = BONE_NODE_OFFSET + 0  # Hips bone

        for ctype, (c_pos, c_idx) in clothing_geos.items():
            # Get color
            if isinstance(clothing_colors, dict):
                c_rgba = _resolve_rgba(clothing_colors.get(ctype,
                                       _DEFAULT_CLOTHING_COLORS.get(ctype, (0.3, 0.3, 0.7, 1.0))))
            elif clothing_colors:
                c_rgba = _resolve_rgba(clothing_colors)
            else:
                c_rgba = _DEFAULT_CLOTHING_COLORS.get(ctype, (0.3, 0.3, 0.7, 1.0))

            c_mat = mat_mod.clothing_material(ctype, c_rgba)
            c_mat_idx = len(gltf.materials)
            gltf.materials.append(c_mat)

            c_pos_acc = make_accessor(gltf, buf_builder, c_pos,
                                      FLOAT, VEC3, ARRAY_BUFFER)
            c_normals = _flat_normals_from_mesh(c_pos, c_idx)
            c_nrm_acc = make_accessor(gltf, buf_builder, c_normals,
                                      FLOAT, VEC3, ARRAY_BUFFER)
            c_idx_acc = make_accessor(gltf, buf_builder,
                                      c_idx.flatten().astype(np.uint32),
                                      UNSIGNED_INT, SCALAR, ELEMENT_ARRAY_BUFFER)

            c_prim = Primitive(
                attributes=Attributes(
                    POSITION=c_pos_acc,
                    NORMAL=c_nrm_acc,
                ),
                indices=c_idx_acc,
                material=c_mat_idx,
                mode=4,
            )
            c_mesh = Mesh(name=f"Clothing_{ctype}", primitives=[c_prim])
            c_mesh_idx = len(gltf.meshes)
            gltf.meshes.append(c_mesh)

            c_node = Node(name=f"Clothing_{ctype}", mesh=c_mesh_idx,
                          translation=[0.0, 0.0, 0.0])
            c_node_idx = len(gltf.nodes)
            gltf.nodes.append(c_node)
            # Attach to Hips bone so clothing moves with skeleton
            gltf.nodes[hips_bone_node_idx].children.append(c_node_idx)

    # ── H. Animations ─────────────────────────────────────────────────────────
    _anim_list = _resolve_animation_list(animations_cfg)

    _anim_builders = {
        "idle":   anim_data.idle_keyframes,
        "walk":   anim_data.walk_keyframes,
        "run":    anim_data.run_keyframes,
        "jump":   anim_data.jump_keyframes,
        "attack": anim_data.attack_keyframes,
    }

    bone_name_to_node = {
        skel_mod.BONE_NAMES[i]: BONE_NODE_OFFSET + i
        for i in range(n_bones)
    }

    for anim_name in _anim_list:
        builder_fn = _anim_builders.get(anim_name)
        if builder_fn is None:
            continue

        rot_kfs, trans_kfs = builder_fn(cfg)
        if not rot_kfs and not trans_kfs:
            continue

        anim_obj = _build_animation(
            gltf, buf_builder, anim_name,
            rot_kfs, trans_kfs, bone_name_to_node,
        )
        if anim_obj is not None:
            gltf.animations.append(anim_obj)

    # ── I. Pack buffer ────────────────────────────────────────────────────────
    blob = buf_builder.build()
    gltf.buffers.append(Buffer(byteLength=len(blob)))
    gltf.set_binary_blob(blob)

    # ── J. Scene ──────────────────────────────────────────────────────────────
    gltf.scenes.append(Scene(name="Scene", nodes=[SCENE_ROOT_IDX]))
    gltf.scene = 0

    return gltf


def _build_animation(gltf: GLTF2, buf_builder: BufferBuilder,
                     name: str, rot_kfs: list, trans_kfs: list,
                     bone_name_to_node: dict) -> "Animation | None":
    """Build a glTF Animation object from keyframe lists.

    Args:
        gltf: GLTF2 object being built.
        buf_builder: Buffer accumulator.
        name: Animation name.
        rot_kfs: List of (time, bone_name, quat_xyzw).
        trans_kfs: List of (time, bone_name, vec3).
        bone_name_to_node: Dict bone_name → node index.

    Returns:
        Animation object, or None if no valid channels.
    """
    samplers = []
    channels = []

    # Group rotation keyframes by bone
    rot_by_bone: dict[str, list] = {}
    for t, bone, quat in rot_kfs:
        rot_by_bone.setdefault(bone, []).append((t, quat))

    # Group translation keyframes by bone
    trans_by_bone: dict[str, list] = {}
    for t, bone, vec in trans_kfs:
        trans_by_bone.setdefault(bone, []).append((t, vec))

    def _add_sampler_channel(times_arr, values_arr, node_idx, path, type_str):
        """Add a sampler + channel pair, return True if successful."""
        if len(times_arr) == 0:
            return False

        t_acc = make_accessor(gltf, buf_builder, times_arr, FLOAT, SCALAR)
        v_acc = make_accessor(gltf, buf_builder, values_arr, FLOAT, type_str)

        s_idx = len(samplers)
        samplers.append(AnimationSampler(
            input=t_acc,
            output=v_acc,
            interpolation=LINEAR,
        ))
        channels.append(AnimationChannel(
            sampler=s_idx,
            target=AnimationChannelTarget(node=node_idx, path=path),
        ))
        return True

    # Rotation channels
    for bone_name, kfs in rot_by_bone.items():
        node_idx = bone_name_to_node.get(bone_name)
        if node_idx is None:
            continue
        kfs_sorted = sorted(kfs, key=lambda x: x[0])
        # Deduplicate times
        seen_times = set()
        unique_kfs = []
        for t, q in kfs_sorted:
            if t not in seen_times:
                seen_times.add(t)
                unique_kfs.append((t, q))
        times = np.array([kf[0] for kf in unique_kfs], dtype=np.float32)
        quats = np.array([kf[1] for kf in unique_kfs], dtype=np.float32).flatten()
        _add_sampler_channel(times, quats, node_idx, "rotation", VEC4)

    # Translation channels
    for bone_name, kfs in trans_by_bone.items():
        node_idx = bone_name_to_node.get(bone_name)
        if node_idx is None:
            continue
        kfs_sorted = sorted(kfs, key=lambda x: x[0])
        seen_times = set()
        unique_kfs = []
        for t, v in kfs_sorted:
            if t not in seen_times:
                seen_times.add(t)
                unique_kfs.append((t, v))
        times = np.array([kf[0] for kf in unique_kfs], dtype=np.float32)
        vecs = np.array([kf[1] for kf in unique_kfs], dtype=np.float32).flatten()
        _add_sampler_channel(times, vecs, node_idx, "translation", VEC3)

    if not channels:
        return None

    return Animation(name=name, samplers=samplers, channels=channels)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_rgba(color) -> tuple:
    """Ensure color is a 4-tuple of floats."""
    if isinstance(color, str):
        # Named skin tones are already resolved before this point
        # Fallback: return a neutral grey
        return (0.5, 0.5, 0.5, 1.0)
    c = tuple(float(x) for x in color)
    if len(c) == 3:
        return c + (1.0,)
    return c


def _resolve_hair_rgba(hair_color) -> tuple:
    """Resolve hair color to RGBA tuple."""
    from ..hair import HAIR_COLORS
    if isinstance(hair_color, str):
        return HAIR_COLORS.get(hair_color, _DEFAULT_HAIR_COLOR)
    return _resolve_rgba(hair_color)


def _resolve_animation_list(animations_cfg) -> list:
    """Convert animations config to list of animation names."""
    all_anims = ["idle", "walk", "run", "jump", "attack"]
    if animations_cfg == "all":
        return all_anims
    if not animations_cfg:
        return []
    if isinstance(animations_cfg, list):
        if "none" in animations_cfg:
            return []
        return [a for a in animations_cfg if a in all_anims]
    return []


def _flat_normals_from_mesh(positions: np.ndarray,
                             indices: np.ndarray) -> np.ndarray:
    """Compute flat per-vertex normals from a triangle mesh."""
    normals = np.zeros_like(positions)
    tris = indices.reshape(-1, 3)
    a = positions[tris[:, 0]]
    b = positions[tris[:, 1]]
    c = positions[tris[:, 2]]
    face_n = np.cross(b - a, c - a)
    lengths = np.linalg.norm(face_n, axis=1, keepdims=True)
    lengths = np.where(lengths < 1e-8, 1.0, lengths)
    face_n /= lengths
    for i in range(len(tris)):
        for vi in tris[i]:
            normals[vi] += face_n[i]
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    lengths = np.where(lengths < 1e-8, 1.0, lengths)
    normals /= lengths
    return normals.astype(np.float32)


def _make_placeholder_mesh(height: float) -> mesh_loader.MeshData:
    """Create a minimal box mesh as a placeholder when GLB is not found."""
    H = height
    # Simple cuboid representing a body
    w, d = 0.25, 0.15
    verts = np.array([
        # Bottom face
        [-w, -d, 0], [w, -d, 0], [w, d, 0], [-w, d, 0],
        # Top face
        [-w, -d, H], [w, -d, H], [w, d, H], [-w, d, H],
    ], dtype=np.float32)

    faces = np.array([
        # Bottom
        [0, 2, 1], [0, 3, 2],
        # Top
        [4, 5, 6], [4, 6, 7],
        # Front
        [0, 1, 5], [0, 5, 4],
        # Back
        [2, 3, 7], [2, 7, 6],
        # Left
        [3, 0, 4], [3, 4, 7],
        # Right
        [1, 2, 6], [1, 6, 5],
    ], dtype=np.uint32)

    N = len(verts)
    normals = np.tile([0.0, 0.0, 1.0], (N, 1)).astype(np.float32)
    texcoords = np.zeros((N, 2), dtype=np.float32)
    joints = np.zeros((N, 4), dtype=np.uint8)
    joints[:, 0] = 0  # all vertices on bone 0
    weights = np.zeros((N, 4), dtype=np.float32)
    weights[:, 0] = 1.0

    return mesh_loader.MeshData(
        positions=verts,
        normals=normals,
        texcoords=texcoords,
        joints=joints,
        weights=weights,
        indices=faces.flatten(),
        height=float(H),
    )
