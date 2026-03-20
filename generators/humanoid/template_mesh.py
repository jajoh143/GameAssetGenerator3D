"""Template-mesh import pipeline for humanoid generation.

Instead of procedurally building geometry, this module imports a pre-made
base mesh from the NBM (Next Base Mesh) .blend files in assets/TemplateMeshes/
and normalises it to the target height and position.

The imported mesh provides all the geometry; vertex groups are cleared and
re-assigned by Blender's heat-map auto-weight when rig.py calls
parent_set(ARMATURE_AUTO).  This lets the full rig/animation pipeline work
unchanged regardless of which template was used.

LOD tiers
---------
"very_low"  →  NBM_VeryLowpoly_{sex}.blend   (~<300 faces, mobile/web)
"low"        →  NBM_Lowpoly_{sex}.blend        (300-500 faces, default)
"mid"        →  NBM_Midpoly_{sex}.blend        (500+ faces, high quality)

Gender / sex mapping
--------------------
"male" or "neutral"  →  Male variant
"female"             →  Female variant
"""

import os
import math

# Project-root-relative path to the template meshes directory
_TEMPLATE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "assets", "TemplateMeshes")
)

# Map (lod_key, sex_key) → filename stem
_LOD_SEX_MAP = {
    ("very_low", "Male"):   "NBM_VeryLowpoly_Male",
    ("very_low", "Female"): "NBM_VeryLowpoly_Female",
    ("low",      "Male"):   "NBM_Lowpoly_Male",
    ("low",      "Female"): "NBM_Lowpoly_Female",
    ("mid",      "Male"):   "NBM_Midpoly_Male",
    ("mid",      "Female"): "NBM_Midpoly_Female",
}

VALID_LODS = ("very_low", "low", "mid")


def _resolve_blend_path(gender: str, lod: str) -> str:
    """Return the absolute path to the .blend file for the given gender/lod.

    Args:
        gender: "male", "female", or "neutral"
        lod:    "very_low", "low", or "mid"

    Returns:
        Absolute path string.

    Raises:
        ValueError: if lod is not one of the valid tiers.
        FileNotFoundError: if the resolved .blend file does not exist.
    """
    if lod not in VALID_LODS:
        raise ValueError(f"Unknown LOD '{lod}'. Valid options: {VALID_LODS}")

    sex = "Female" if gender == "female" else "Male"
    stem = _LOD_SEX_MAP[(lod, sex)]
    path = os.path.join(_TEMPLATE_DIR, f"{stem}.blend")

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Template mesh not found: {path}\n"
            f"Expected NBM .blend files in: {_TEMPLATE_DIR}"
        )
    return path


def _import_mesh_from_blend(blend_path: str):
    """Append the first mesh object found inside a .blend file.

    Uses bpy.ops.wm.append() to bring the object into the current scene.
    All mesh objects in the file are tried; the first successfully appended
    one is returned.

    Args:
        blend_path: Absolute path to the source .blend file.

    Returns:
        The newly appended Blender object (bpy.types.Object).

    Raises:
        RuntimeError: if no mesh object could be imported.
    """
    import bpy

    # Collect object names already in the scene before import
    before = {o.name for o in bpy.data.objects}

    # List object entries inside the blend file
    with bpy.data.libraries.load(blend_path, link=False) as (src, _dst):
        available_objects = list(src.objects)

    if not available_objects:
        raise RuntimeError(f"No objects found in {blend_path}")

    # Try to append each object; take the first mesh we successfully get
    for obj_name in available_objects:
        bpy.ops.wm.append(
            filepath=os.path.join(blend_path, "Object", obj_name),
            directory=os.path.join(blend_path, "Object"),
            filename=obj_name,
            link=False,
            autoselect=True,
        )

        # Find what was actually added
        after = {o.name for o in bpy.data.objects}
        new_names = after - before
        for name in new_names:
            obj = bpy.data.objects[name]
            if obj.type == 'MESH':
                return obj
            # Not a mesh (e.g. armature that came along) — will be cleaned up later
        before = after  # update baseline for next iteration

    raise RuntimeError(
        f"No MESH type object could be imported from {blend_path}. "
        f"Available objects: {available_objects}"
    )


def _clear_non_mesh_objects(keep_names: set):
    """Remove any objects added during import that are not the target mesh.

    This cleans up armatures, empties, or lights that may have been appended
    alongside the mesh object.

    Args:
        keep_names: Set of object names to preserve (mesh + pre-existing).
    """
    import bpy
    to_remove = [o for o in bpy.data.objects if o.name not in keep_names]
    for obj in to_remove:
        bpy.data.objects.remove(obj, do_unlink=True)


def _normalise_mesh(obj, target_height: float = None) -> float:
    """Apply transforms and position feet at Z=0.

    Optionally scales the mesh to a specific height — only used when the user
    has explicitly requested a non-default height via --height.  Otherwise the
    mesh is imported at its natural dimensions so the artist's proportions are
    preserved exactly.

    Args:
        obj: Blender mesh object.
        target_height: If provided, scale the mesh uniformly to this height
            (metres).  If None, no scaling is applied.

    Returns:
        Actual mesh height in metres after positioning (and optional scaling).
    """
    import bpy

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Apply all transforms (location, rotation, scale) so values are clean
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Measure bounding box
    local_coords = [obj.matrix_world @ __import__('mathutils').Vector(v) for v in obj.bound_box]
    min_z = min(v.z for v in local_coords)
    max_z = max(v.z for v in local_coords)
    mesh_height = max_z - min_z

    if mesh_height < 1e-6:
        raise RuntimeError("Imported mesh has zero height — cannot normalise.")

    # Always position feet at Z=0
    obj.location.z -= min_z
    bpy.ops.object.transform_apply(location=True)

    # Only scale if the caller explicitly requested a specific height
    if target_height is not None:
        scale_factor = target_height / mesh_height
        obj.scale = (scale_factor, scale_factor, scale_factor)
        bpy.ops.object.transform_apply(scale=True)
        return target_height

    return mesh_height


def _clear_vertex_groups(obj):
    """Remove all vertex groups so auto-weight starts fresh.

    The rig.py auto-weight (heat-map) will create correct groups matching
    our bone names when parent_set(ARMATURE_AUTO) is called.
    """
    obj.vertex_groups.clear()


def _apply_skin_material(obj, skin_tone=None):
    """Assign a Principled BSDF skin material to the object.

    Replaces any existing materials on the object with a single skin slot.

    Args:
        obj: Blender mesh object.
        skin_tone: RGBA tuple or None for a neutral default.
    """
    import bpy

    # Remove existing materials
    obj.data.materials.clear()

    mat = bpy.data.materials.new(name="Humanoid_Base")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        color = skin_tone if skin_tone else (0.65, 0.55, 0.45, 1.0)
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.69
        # Slight subsurface for skin realism
        if "Subsurface Weight" in bsdf.inputs:
            bsdf.inputs["Subsurface Weight"].default_value = 0.05
        elif "Subsurface" in bsdf.inputs:
            bsdf.inputs["Subsurface"].default_value = 0.05

    obj.data.materials.append(mat)


def create_body_from_template(cfg: dict):
    """Import and prepare a template mesh body for the humanoid pipeline.

    This is the template-mesh alternative to mesh.create_body().  It returns
    the same ``(body_obj, hair_obj, clothing_objs)`` tuple so that callers
    (rig.py, animation.py) work unchanged.

    Args:
        cfg: Resolved character config dict.  Relevant keys:
            - gender      (str)   "male" / "female" / "neutral"
            - lod         (str)   "very_low" / "low" / "mid"
            - height      (float) target height in metres
            - skin_tone   (tuple) RGBA skin colour
            - hair_style  (str)   forwarded to hair module
            - hair_color  (str/tuple)

    Returns:
        Tuple ``(body_obj, hair_obj_or_None, [])``.
    """
    import bpy
    from . import hair as hair_module

    gender = cfg.get("gender", "neutral")
    lod = cfg.get("lod", "low")
    # Only scale if the user explicitly passed --height; never apply preset/build/gender
    # multiplied heights to the template mesh — that would distort the artist's work.
    height_override = cfg.get("height_override", None)
    skin_tone = cfg.get("skin_tone", None)

    # ── Clear scene ────────────────────────────────────────────────────────
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    scene_before = {o.name for o in bpy.data.objects}

    # ── Import template mesh ───────────────────────────────────────────────
    blend_path = _resolve_blend_path(gender, lod)
    print(f"[template_mesh] Importing from: {blend_path}")

    mesh_obj = _import_mesh_from_blend(blend_path)
    mesh_obj.name = "Humanoid_Body"

    # Remove any non-mesh objects that came along (armatures, lights, etc.)
    keep = scene_before | {mesh_obj.name}
    _clear_non_mesh_objects(keep)

    # ── Position (and optionally scale) ───────────────────────────────────
    # Pass height_override only when user explicitly requested a specific height.
    # Otherwise the mesh is imported at its natural dimensions.
    actual_height = _normalise_mesh(mesh_obj, height_override)

    # Update cfg so that rig.py positions bones against the mesh's real height,
    # not a preset value that may not match the template mesh.
    cfg["height"] = actual_height

    # ── Clear vertex groups so auto-weight works cleanly ──────────────────
    _clear_vertex_groups(mesh_obj)

    # ── Apply edge-split for a clean low-poly look ────────────────────────
    mod = mesh_obj.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
    mod.split_angle = math.radians(50)
    bpy.ops.object.shade_smooth()

    # ── Materials ─────────────────────────────────────────────────────────
    _apply_skin_material(mesh_obj, skin_tone)

    # ── Derive head geometry parameters from actual mesh height ───────────────
    # head_z = head CENTRE = mesh top − head radius.
    # With head_r ≈ 0.065 × height the crown lands at head_z + 0.97×head_r,
    # which is ~3 mm below the top of the mesh — exactly right.
    # The OLD formula (0.90×height + head_r) pushed the crown ~5 cm above the
    # mesh for typical NBM heights, so the hair floated off the head.
    head_r = actual_height * 0.065
    head_z = actual_height - head_r   # head centre (= neck_top + head_r)

    # ── Measure actual face Y so eye spheres sit inside the mesh ─────────────
    # The mesh bounding box min-Y ≈ nose tip (most forward point in -Y).
    # Eyes sit a little behind the nose, which is head_r*0.20 ahead of the
    # eye socket.  Passing face_y to create_eyes lets it anchor to the real
    # mesh surface rather than a spherical approximation.
    import mathutils as _mu
    world_verts = [mesh_obj.matrix_world @ _mu.Vector(v) for v in mesh_obj.bound_box]
    face_y = min(v.y for v in world_verts)   # nose-tip Y ≈ front of face

    # ── Hair ──────────────────────────────────────────────────────────────────
    hair_obj = None
    hair_style = cfg.get("hair_style", "short")
    hair_color = cfg.get("hair_color", None)
    if hair_style and hair_style != "none":
        hair_obj = hair_module.create_hair(head_z, head_r, hair_style, hair_color)

    # ── Eyes ──────────────────────────────────────────────────────────────────
    from . import eyes as eyes_module
    eye_color = cfg.get("eye_color", None)
    eye_objs = eyes_module.create_eyes(head_z, head_r, eye_color, face_y=face_y)

    # Return eye objects as (obj, "Head") tuples so the rig can parent them
    # rigidly to the Head bone, matching how hair is handled.
    extra_head_objs = [(e, "Head") for e in eye_objs]

    # ── Eyebrows ──────────────────────────────────────────────────────────────
    brow_color = cfg.get("brow_color", None)
    brow_obj = eyes_module.create_eyebrows(head_z, head_r, face_y=face_y,
                                           brow_color=brow_color)
    extra_head_objs.append((brow_obj, "Head"))

    return mesh_obj, hair_obj, extra_head_objs
