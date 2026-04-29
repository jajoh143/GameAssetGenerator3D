"""Blender-side job: import a TRELLIS.2 GLB, rig as humanoid, animate, export.

Invoked as::

    blender --background --python rig_and_animate.py -- <job.json>

The job JSON contains:
    {
      "input_glb": "...",
      "output_glb": "...",
      "asset_type": "humanoid" | "prop",
      "animations": ["idle", "walk", ...],
      "normalize_height": 1.8
    }

For props we just re-export with normalization. For humanoids we fit a
skeleton from the mesh bounding box, apply heat-diffusion auto-weights, and
keyframe the requested animation cycles.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

# Make the project package importable inside Blender's Python.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gag3d.rigging.skeleton import fit_skeleton_from_bounds  # noqa: E402
from gag3d.animation import ANIMATIONS  # noqa: E402


# ─── Scene helpers ───────────────────────────────────────────────────────────

def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path: Path) -> bpy.types.Object:
    bpy.ops.import_scene.gltf(filepath=str(path))
    meshes = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No mesh imported from {path}")
    if len(meshes) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for m in meshes:
            m.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.object.join()
    return bpy.context.view_layer.objects.active


def normalize_mesh(obj: bpy.types.Object, target_height: float) -> None:
    """Scale the mesh to target_height (world Y) and set feet at Z/Y=0.

    glTF convention is Y-up; Blender is Z-up. The glTF importer remaps so
    that what was Y-up becomes Z-up. After import the mesh's vertical axis
    is Z. We use Z as the height axis here.
    """
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    zs = [v.z for v in bbox]
    height = max(zs) - min(zs)
    if height <= 0:
        return
    scale = target_height / height
    obj.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]
    obj.location = (
        -(min(xs) + max(xs)) / 2.0,
        -(min(ys) + max(ys)) / 2.0,
        -min(zs),
    )
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def mesh_bounds_zup(obj: bpy.types.Object) -> tuple[float, float, float, float, float, float]:
    """Return (xmin, xmax, ymin, ymax, zmin, zmax) for the fitter.

    The fitter expects Y-up bounds, but our scene is Z-up. We swap so the
    fitter's "y_frac" maps to Blender's Z (vertical) axis: returned tuple is
    (X, Z, Y) reordered as the fitter wants.
    """
    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]
    return (min(xs), max(xs), min(zs), max(zs), min(ys), max(ys))


# ─── Rigging ─────────────────────────────────────────────────────────────────

def build_armature(skeleton, name: str = "Armature") -> bpy.types.Object:
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    arm_obj = bpy.context.object
    arm_obj.name = name
    arm = arm_obj.data
    arm.name = name

    # Remove default Bone
    bpy.ops.armature.select_all(action="SELECT")
    bpy.ops.armature.delete()

    edit_bones = arm.edit_bones

    def to_zup(p):
        # Skeleton fitter uses Y-up; remap to Blender Z-up: (x, z=0, y)
        x, y_up, z_depth = p
        return (x, z_depth, y_up)

    created: dict[str, bpy.types.EditBone] = {}
    for fb in skeleton.bones:
        eb = edit_bones.new(fb.name)
        eb.head = to_zup(fb.head)
        eb.tail = to_zup(fb.tail)
        if fb.parent:
            eb.parent = created[fb.parent]
            eb.use_connect = False
        created[fb.name] = eb

    bpy.ops.object.mode_set(mode="OBJECT")
    return arm_obj


def bind_mesh_to_armature(mesh_obj: bpy.types.Object, arm_obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")


# ─── Pipeline ────────────────────────────────────────────────────────────────

def run_humanoid(job: dict) -> None:
    reset_scene()

    mesh_obj = import_glb(Path(job["input_glb"]))
    target_height = float(job.get("normalize_height", 1.8))
    normalize_mesh(mesh_obj, target_height)

    bounds = mesh_bounds_zup(mesh_obj)
    skeleton = fit_skeleton_from_bounds(bounds)

    arm_obj = build_armature(skeleton)
    bind_mesh_to_armature(mesh_obj, arm_obj)

    for anim_name in job.get("animations", []):
        if anim_name not in ANIMATIONS:
            print(f"[gag3d] skipping unknown animation '{anim_name}'")
            continue
        ANIMATIONS[anim_name](arm_obj)

    export_path = Path(job["output_glb"])
    export_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(export_path),
        export_format="GLB",
        use_selection=False,
        export_animations=True,
        export_skins=True,
    )


def run_prop(job: dict) -> None:
    reset_scene()
    mesh_obj = import_glb(Path(job["input_glb"]))
    target_height = float(job.get("normalize_height", 1.0))
    normalize_mesh(mesh_obj, target_height)

    export_path = Path(job["output_glb"])
    export_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(export_path),
        export_format="GLB",
        use_selection=False,
        export_animations=False,
    )


def main() -> None:
    argv = sys.argv
    if "--" not in argv:
        raise SystemExit("Usage: blender --background --python rig_and_animate.py -- <job.json>")
    job_path = Path(argv[argv.index("--") + 1])
    job = json.loads(job_path.read_text())

    asset_type = job.get("asset_type", "humanoid")
    if asset_type == "humanoid":
        run_humanoid(job)
    elif asset_type == "prop":
        run_prop(job)
    else:
        raise SystemExit(f"Unknown asset_type: {asset_type}")


if __name__ == "__main__":
    main()
