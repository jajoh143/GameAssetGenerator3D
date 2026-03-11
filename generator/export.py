"""Export utilities for generated assets.

Supports glTF Binary (.glb), glTF (.gltf), FBX, and OBJ formats.
This module runs inside Blender's Python environment.
"""

import os


FORMAT_EXTENSIONS = {
    "glb": ".glb",
    "gltf": ".gltf",
    "fbx": ".fbx",
    "obj": ".obj",
}


def detect_format(filepath):
    """Infer export format from file extension."""
    ext = os.path.splitext(filepath)[1].lower()
    for fmt, fext in FORMAT_EXTENSIONS.items():
        if ext == fext:
            return fmt
    return "glb"  # default


def export(filepath, fmt=None):
    """Export the current scene to the given filepath.

    Must be called from within Blender's Python environment.

    Args:
        filepath: Output path.
        fmt: One of 'glb', 'gltf', 'fbx', 'obj'. Auto-detected if None.
    """
    import bpy

    if fmt is None:
        fmt = detect_format(filepath)

    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

    # Select all mesh and armature objects for export
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.data.objects:
        if obj.type in {'MESH', 'ARMATURE'}:
            obj.select_set(True)

    if fmt in ("glb", "gltf"):
        bpy.ops.export_scene.gltf(
            filepath=filepath,
            export_format='GLB' if fmt == "glb" else 'GLTF_SEPARATE',
            use_selection=True,
            export_animations=True,
            export_skins=True,
            export_apply=True,
            export_draco_mesh_compression=True,
            export_draco_compression_level=6,
            export_draco_position_quantization=14,
            export_draco_normal_quantization=10,
            export_draco_texcoord_quantization=12,
        )
    elif fmt == "fbx":
        bpy.ops.export_scene.fbx(
            filepath=filepath,
            use_selection=True,
            add_leaf_bones=False,
            bake_anim=True,
            object_types={'MESH', 'ARMATURE'},
        )
    elif fmt == "obj":
        bpy.ops.wm.obj_export(
            filepath=filepath,
            export_selected_objects=True,
        )
    else:
        raise ValueError(f"Unsupported format: {fmt}")

    print(f"Exported: {filepath} ({fmt})")
