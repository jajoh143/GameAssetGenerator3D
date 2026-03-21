"""Template-mesh import pipeline for humanoid generation.

Instead of procedurally building geometry, this module imports a pre-made
base mesh from the assets/TemplateMeshes/ directory and normalises it to the
target height and position.

Primary template
----------------
Cartoon_Male.glb — imported via bpy.ops.import_scene.gltf().  Used as the
default for all male/neutral characters across every LOD tier.

NBM fallback (legacy .blend files)
-----------------------------------
"very_low"  →  NBM_VeryLowpoly_{sex}.blend   (~<300 faces, mobile/web)
"low"        →  NBM_Lowpoly_{sex}.blend        (300-500 faces, default)
"mid"        →  NBM_Midpoly_{sex}.blend        (500+ faces, high quality)

Female characters still use the NBM_*.blend pipeline until a Cartoon_Female
template is provided.

Gender / sex mapping
--------------------
"male" or "neutral"  →  Cartoon_Male.glb  (or NBM Male if GLB absent)
"female"             →  NBM Female variant
"""

import os
import math

# Project-root-relative path to the template meshes directory
_TEMPLATE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "assets", "TemplateMeshes")
)

# Cartoon_Male GLB — primary template for male/neutral characters
CARTOON_MALE_GLB = os.path.join(_TEMPLATE_DIR, "Cartoon_Male.glb")

# Map (lod_key, sex_key) → filename stem (NBM fallback)
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


def _import_glb_mesh(glb_path: str):
    """Import all mesh objects from a GLB/GLTF file and join them into one.

    GLB files frequently contain several separate mesh objects (e.g. body,
    head, hands).  Returning only the first would cause all other parts to
    be silently deleted by _clear_non_mesh_objects().  This function:

      1. Imports the GLB via bpy.ops.import_scene.gltf().
      2. Collects every newly-added MESH object.
      3. Unparents each from any bundled armature (keeping world transform)
         and strips armature modifiers — rig.py will re-apply skinning.
      4. If more than one mesh was imported, joins them all into one object.
      5. Returns the single combined mesh object.

    Args:
        glb_path: Absolute path to the .glb or .gltf file.

    Returns:
        A single Blender MESH object containing all imported geometry.

    Raises:
        RuntimeError: if no MESH object was found after import.
    """
    import bpy

    before = {o.name for o in bpy.data.objects}

    bpy.ops.import_scene.gltf(filepath=glb_path)

    after     = {o.name for o in bpy.data.objects}
    new_names = after - before

    # Collect every new MESH object
    mesh_objs = [
        bpy.data.objects[n]
        for n in new_names
        if bpy.data.objects[n].type == 'MESH'
    ]

    if not mesh_objs:
        raise RuntimeError(
            f"No MESH object found after importing {glb_path}. "
            f"New objects: {list(new_names)}"
        )

    print(f"[template_mesh] GLB imported {len(mesh_objs)} mesh part(s): "
          f"{[o.name for o in mesh_objs]}")

    # Unparent from bundled armatures (keep world transform) and remove
    # armature modifiers so rig.py can apply its own skinning cleanly.
    bpy.ops.object.select_all(action='DESELECT')
    for obj in mesh_objs:
        if obj.parent is not None:
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            obj.select_set(False)
        for mod in list(obj.modifiers):
            if mod.type == 'ARMATURE':
                obj.modifiers.remove(mod)

    # Single part — return as-is
    if len(mesh_objs) == 1:
        return mesh_objs[0]

    # Multiple parts — join into one mesh object
    bpy.ops.object.select_all(action='DESELECT')
    for obj in mesh_objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objs[0]
    bpy.ops.object.join()

    joined = bpy.context.view_layer.objects.active
    print(f"[template_mesh] Joined into single mesh: {joined.name}")
    return joined


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


def _normalise_mesh(obj, target_height: float, x_scale: float = 1.0,
                    y_scale: float = 1.0) -> float:
    """Apply transforms, position feet at Z=0, and scale to target dimensions.

    Always scales the mesh to target_height (Z), then applies x_scale / y_scale
    for body-width and body-depth proportions relative to the average template.

    Args:
        obj:           Blender mesh object.
        target_height: Target height in metres (always applied).
        x_scale:       Multiplier for X (width) relative to the average template.
        y_scale:       Multiplier for Y (depth) relative to the average template.

    Returns:
        Actual mesh height in metres after scaling (= target_height).
    """
    import bpy

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    local_coords = [obj.matrix_world @ __import__('mathutils').Vector(v) for v in obj.bound_box]
    min_z = min(v.z for v in local_coords)
    max_z = max(v.z for v in local_coords)
    mesh_height = max_z - min_z

    if mesh_height < 1e-6:
        raise RuntimeError("Imported mesh has zero height — cannot normalise.")

    # Position feet at Z=0
    obj.location.z -= min_z
    bpy.ops.object.transform_apply(location=True)

    # Scale Z to target height, X/Y for body proportions
    z_factor = target_height / mesh_height
    obj.scale = (z_factor * x_scale, z_factor * y_scale, z_factor)
    bpy.ops.object.transform_apply(scale=True)

    return target_height


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
    skin_tone = cfg.get("skin_tone", None)

    # Compute proportion scale factors relative to the "average" template.
    # The template mesh was built to average proportions (height=1.50,
    # shoulder_width=0.23, torso_depth=0.16).  Preset/build values are applied
    # as non-uniform XYZ scale so a "brute" comes out wide and a "slender"
    # comes out narrow without touching the artist geometry.
    from .presets import PRESETS as _PRESETS
    _avg = _PRESETS["average"]
    target_height   = cfg.get("height",         _avg["height"])
    target_sw       = cfg.get("shoulder_width",  _avg["shoulder_width"])
    target_td       = cfg.get("torso_depth",     _avg["torso_depth"])
    x_scale = target_sw / _avg["shoulder_width"]   # width multiplier
    y_scale = target_td / _avg["torso_depth"]       # depth multiplier

    # ── Clear scene ────────────────────────────────────────────────────────
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    scene_before = {o.name for o in bpy.data.objects}

    # ── Import template mesh ───────────────────────────────────────────────
    # Prefer Cartoon_Male.glb for male/neutral characters.
    # Fall back to NBM .blend files if the GLB is absent or gender=female.
    use_cartoon_glb = (
        gender in ("male", "neutral")
        and os.path.exists(CARTOON_MALE_GLB)
    )

    if use_cartoon_glb:
        print(f"[template_mesh] Importing Cartoon_Male from: {CARTOON_MALE_GLB}")
        mesh_obj = _import_glb_mesh(CARTOON_MALE_GLB)
    else:
        blend_path = _resolve_blend_path(gender, lod)
        print(f"[template_mesh] Importing NBM template from: {blend_path}")
        mesh_obj = _import_mesh_from_blend(blend_path)

    mesh_obj.name = "Humanoid_Body"

    # Remove any non-mesh objects that came along (armatures, lights, etc.)
    keep = scene_before | {mesh_obj.name}
    _clear_non_mesh_objects(keep)

    # ── Scale to preset proportions ────────────────────────────────────────
    actual_height = _normalise_mesh(mesh_obj, target_height, x_scale, y_scale)

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
    # Cartoon_Male has a proportionally larger head than a realistic NBM mesh
    # (cartoon proportion ~1/4 body height vs realistic ~1/7.5).  Using a
    # larger head_r multiplier (0.085) keeps hair and eyes sized correctly.
    # NBM meshes use the original 0.065 multiplier.
    head_r_mult = 0.085 if use_cartoon_glb else 0.065
    head_r = actual_height * head_r_mult
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
