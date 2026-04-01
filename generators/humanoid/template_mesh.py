"""Template-mesh import pipeline for humanoid generation.

Instead of procedurally building geometry, this module imports a pre-made
base mesh from the assets/TemplateMeshes/ directory and normalises it to the
target height and position.

Template
--------
Cartoon_Male.glb — imported via bpy.ops.import_scene.gltf().  Used for all
characters regardless of gender/LOD setting.
"""

import os
import math

# Project-root-relative path to the template meshes directory
_TEMPLATE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "assets", "TemplateMeshes")
)

# Cartoon_Male GLB — the sole template mesh
CARTOON_MALE_GLB = os.path.join(_TEMPLATE_DIR, "Cartoon_Male.glb")


def _import_glb_mesh(glb_path: str):
    """Import all mesh objects from a GLB/GLTF file and join them into one.

    GLB files frequently contain several separate mesh objects (e.g. body,
    head, hands).  Returning only the first would cause all other parts to
    be silently deleted by _clear_non_mesh_objects().  This function:

      1. Imports the GLB via bpy.ops.import_scene.gltf().
      2. Collects every newly-added MESH object that is in the main scene
         collection (skips objects in 'glTF_not_exported', which are internal
         bone-display helpers and must not be merged into the body mesh).
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

    # Collect every new MESH object that is NOT in the 'glTF_not_exported'
    # collection.  That collection holds bone-display helper shapes (Icosphere
    # IK targets, etc.) that must remain isolated — joining them into the body
    # mesh would add unwanted geometry (e.g. a ball at the feet).
    gltf_hidden = bpy.data.collections.get("glTF_not_exported")
    hidden_names = {o.name for o in gltf_hidden.objects} if gltf_hidden else set()

    mesh_objs = [
        bpy.data.objects[n]
        for n in new_names
        if bpy.data.objects[n].type == 'MESH' and n not in hidden_names
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



def _purge_gltf_not_exported():
    """Delete the glTF_not_exported collection and every object inside it.

    Blender's glTF importer puts bone display-shape meshes (Icospheres for IK
    targets, etc.) in this collection.  They can survive _clear_non_mesh_objects
    if Blender holds a reference through the bone's custom_shape pointer.
    Removing the collection explicitly ensures they do not appear in the viewport
    or the outliner after the import step.
    """
    import bpy
    col = bpy.data.collections.get("glTF_not_exported")
    if col is None:
        return
    for obj in list(col.objects):
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception:
            pass
    bpy.data.collections.remove(col)


def _clear_non_mesh_objects(keep_names: set):
    """Remove any stray objects that are not in keep_names.

    With the mesh-data-only import approach, no foreign objects are ever
    imported, so this is mainly a safety net for any objects that existed in
    the default Blender scene (cameras, lights, etc.).
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

    # ── Auto-orient: ensure height (longest axis) aligns with Z ──────────────
    # Different import paths (FBX, GLB, .blend) may leave the character lying
    # on a different axis depending on the file's coordinate system and how
    # Blender's importer handles the conversion.  Measure the three vertex
    # extents and rotate so the longest axis becomes Z before doing anything else.
    verts = obj.data.vertices
    if verts:
        xs = [v.co.x for v in verts]
        ys = [v.co.y for v in verts]
        zs = [v.co.z for v in verts]
        x_ext = max(xs) - min(xs)
        y_ext = max(ys) - min(ys)
        z_ext = max(zs) - min(zs)
        print(f"[normalise_mesh] extents before orient: X={x_ext:.3f} Y={y_ext:.3f} Z={z_ext:.3f}")

        if y_ext > z_ext * 1.5 and y_ext >= x_ext:
            # Character is lying with height along +Y → rotate +90° X: Y→Z
            obj.rotation_euler[0] = math.pi / 2
            bpy.ops.object.transform_apply(rotation=True)
            print("[normalise_mesh] Auto-rotated +90° X (Y-up → Z-up)")
        elif x_ext > z_ext * 1.5 and x_ext >= y_ext:
            # Character is lying with height along X → rotate -90° Y: X→Z
            obj.rotation_euler[1] = -math.pi / 2
            bpy.ops.object.transform_apply(rotation=True)
            print("[normalise_mesh] Auto-rotated -90° Y (X-up → Z-up)")

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


# ── Bone name mapping: Cartoon_Male.glb bones → our rig bone names ────────
# The GLB was built for a Mixamo/Rigify-style armature.  We rename vertex
# groups in-place so the existing artist-made skin weights work with our
# Humanoid_Armature without running ARMATURE_AUTO (which often fails for
# cartoon meshes whose proportions differ from our rig's bone positions).
#
# Bones absent from this dict (IK controls, toe details) are collected into
# the nearest logical parent so we keep 100 % of the mesh covered.
_GLB_TO_OUR_BONES = {
    # Spine chain
    "Hips":            "Hips",
    "HipsCtrl":        "Hips",
    "Spine":           "Spine",
    "Chest":           "Chest",
    "UpperChest":      "Chest",
    "Neck":            "Neck",
    "Head":            "Head",
    # Left arm
    "LeftShoulder":    "Shoulder.L",
    "LeftArm":         "UpperArm.L",
    "LeftForeArm":     "LowerArm.L",
    "LeftHand":        "Hand.L",
    "LeftHandIndex1":  "Hand.L",
    "LeftHandIndex2":  "Hand.L",
    "LeftHandIndex3":  "Hand.L",
    "LeftHandThumb1":  "Hand.L",
    "LeftHandThumb2":  "Hand.L",
    # Right arm
    "RightShoulder":   "Shoulder.R",
    "RightArm":        "UpperArm.R",
    "RightForeArm":    "LowerArm.R",
    "RightHand":       "Hand.R",
    "RightHandIndex1": "Hand.R",
    "RightHandIndex2": "Hand.R",
    "RightHandIndex3": "Hand.R",
    "RightHandThumb1": "Hand.R",
    "RightHandThumb2": "Hand.R",
    # Left leg
    "LeftUpLeg":       "UpperLeg.L",
    "LeftLeg":         "LowerLeg.L",
    "LeftFoot":        "Foot.L",
    "LeftToes":        "Foot.L",
    # Right leg
    "RightUpLeg":      "UpperLeg.R",
    "RightLeg":        "LowerLeg.R",
    "RightFoot":       "Foot.R",
    "RightToes":       "Foot.R",
}


def _remap_glb_vertex_groups(obj):
    """Remap Cartoon_Male.glb vertex groups to our Humanoid_Armature bone names.

    The GLB carries perfectly-painted skin weights bound to Mixamo-style bone
    names.  Rather than discarding them and re-computing with ARMATURE_AUTO
    (which often fails for cartoon meshes), we:

      1. Rename each group that has a direct entry in _GLB_TO_OUR_BONES.
      2. If a target name already exists (multiple GLB bones map to one of
         ours, e.g. finger bones → Hand.L), we add the weights from the
         source group into the target group, then delete the source.
      3. Delete any remaining groups that don't map to anything (IK controls,
         roll helpers, etc.) — they have no corresponding bone in our rig.
    """
    vg_map = obj.vertex_groups

    # Build a work-list: (source_name, target_name) for every group present
    renames = []
    for vg in list(vg_map):
        target = _GLB_TO_OUR_BONES.get(vg.name)
        if target:
            renames.append((vg.name, target))

    for src_name, dst_name in renames:
        src_vg = vg_map.get(src_name)
        if src_vg is None:
            continue  # already removed in a previous iteration

        dst_vg = vg_map.get(dst_name)

        if dst_vg is None:
            # Simple rename
            src_vg.name = dst_name
        else:
            # Merge src weights INTO dst (vertex can be in both groups)
            for v in obj.data.vertices:
                try:
                    w = src_vg.weight(v.index)
                    if w > 0.0:
                        existing = 0.0
                        try:
                            existing = dst_vg.weight(v.index)
                        except RuntimeError:
                            pass
                        dst_vg.add([v.index], min(existing + w, 1.0), 'REPLACE')
                except RuntimeError:
                    pass  # vertex not in src group
            vg_map.remove(src_vg)

    # Remove any leftover groups that have no corresponding rig bone
    # (IK controls, roll helpers, Root, etc.)
    our_bones = set(_GLB_TO_OUR_BONES.values())
    for vg in list(vg_map):
        if vg.name not in our_bones:
            vg_map.remove(vg)

    print(f"[template_mesh] Vertex groups after remap: "
          f"{[vg.name for vg in obj.vertex_groups]}")



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
        color = skin_tone if skin_tone else (0.72, 0.55, 0.42, 1.0)
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.42  # smooth toy-like sheen
        bsdf.inputs["Specular IOR Level"].default_value = 0.45
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
    if not os.path.exists(CARTOON_MALE_GLB):
        raise RuntimeError(
            f"Template mesh not found: {CARTOON_MALE_GLB}\n"
            f"Expected Cartoon_Male.glb in: {_TEMPLATE_DIR}"
        )
    print(f"[template_mesh] Importing Cartoon_Male from: {CARTOON_MALE_GLB}")
    mesh_obj = _import_glb_mesh(CARTOON_MALE_GLB)
    use_glb = True

    mesh_obj.name = "Humanoid_Body"

    # Remove any non-mesh objects that came along (armatures, lights, etc.)
    keep = scene_before | {mesh_obj.name}
    _clear_non_mesh_objects(keep)

    # Explicitly purge the glTF_not_exported collection (IK bone custom-shape
    # Icospheres live here and can survive _clear_non_mesh_objects when Blender
    # holds an extra reference via the bone's custom_shape pointer).
    _purge_gltf_not_exported()

    # Final sweep: purge any orphaned data blocks (meshes, objects, armatures)
    # that survived due to reference chains (e.g. bone custom_shape → mesh).
    try:
        bpy.ops.outliner.orphans_purge(
            do_local_ids=True, do_linked_ids=True, do_recursive=True
        )
    except Exception:
        pass

    # ── Scale to preset proportions ────────────────────────────────────────
    actual_height = _normalise_mesh(mesh_obj, target_height, x_scale, y_scale)

    # Update cfg so that rig.py positions bones against the mesh's real height,
    # not a preset value that may not match the template mesh.
    cfg["height"] = actual_height

    # ── Vertex groups: remap GLB bone names → our Humanoid_Armature names ───
    # The Cartoon_Male GLB carries artist-painted skin weights bound to
    # Mixamo-style bone names.  Remap them so rig.py can use the direct
    # Armature modifier path rather than the ARMATURE_AUTO fallback.
    _remap_glb_vertex_groups(mesh_obj)

    # ── Apply edge-split for a clean low-poly look ────────────────────────
    mod = mesh_obj.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
    mod.split_angle = math.radians(38)  # tighter angle for crisp faceted low-poly look
    bpy.ops.object.shade_smooth()

    # ── Materials ─────────────────────────────────────────────────────────
    _apply_skin_material(mesh_obj, skin_tone)

    # ── Derive head geometry from actual mesh vertices ────────────────────────
    # Rather than using a fixed height multiplier (which is wrong for cartoon
    # meshes whose heads are proportionally much larger), we sample every
    # vertex whose Z is above 60 % of the body height and within HEAD_X_CAP.
    #
    #   head_r  =  vertical half-height of the head
    #   head_z  =  midpoint between chin and crown (true head centre)
    #   face_y  =  minimum Y of head verts (nose-tip depth)
    import mathutils as _mu

    if True:
        # ── Full-head detection via neck scan ────────────────────────────
        # The old "equator method" only measured crown-to-widest-point,
        # giving a tiny head_r for chibi meshes whose heads extend far
        # below the widest point.  Instead, we detect the FULL head by
        # scanning downward from the crown to find the neck — the
        # narrowest horizontal extent between head and shoulders.
        #
        # Algorithm:
        #   1. Collect all vertices above 65 % height (head + upper body)
        #      with abs(x) < HEAD_X_CAP to exclude T-pose arms.
        #   2. Bucket by Z into thin slices and find max abs(x) per slice.
        #   3. Walk slices downward from the crown; the first local minimum
        #      in max-abs-x is the neck centre.  The head bottom = chin is
        #      the slice just above where the profile starts narrowing
        #      toward the neck.
        #   4. head_z = midpoint between chin and crown (true centre of head)
        #      head_r = (crown - chin) / 2  (vertical half-height)
        #
        HEAD_X_CAP = 0.25          # max abs(x) for head verts
        scan_floor_z = actual_height * 0.60   # scan from here up
        crown_z = actual_height

        # Collect all candidate vertices
        head_candidate_verts = []
        for v in mesh_obj.data.vertices:
            wco = mesh_obj.matrix_world @ v.co
            if wco.z > scan_floor_z and abs(wco.x) < HEAD_X_CAP:
                head_candidate_verts.append(wco)

        # Bucket into Z slices (1 cm each)
        slice_height = 0.01
        n_slices = int((crown_z - scan_floor_z) / slice_height) + 1
        slice_max_ax = [0.0] * n_slices
        slice_min_y  = [0.0] * n_slices
        slice_count  = [0] * n_slices

        for wco in head_candidate_verts:
            idx = int((wco.z - scan_floor_z) / slice_height)
            if 0 <= idx < n_slices:
                ax = abs(wco.x)
                if ax > slice_max_ax[idx]:
                    slice_max_ax[idx] = ax
                if slice_count[idx] == 0 or wco.y < slice_min_y[idx]:
                    slice_min_y[idx] = wco.y
                slice_count[idx] += 1

        # Find neck: walk downward from top, look for the first sharp
        # narrowing that is at least 40 % narrower than the widest head slice
        top_idx = n_slices - 1
        # Find the widest slice in the top 30 % (head region)
        head_region_start = int(n_slices * 0.70)
        max_head_width = 0.0
        widest_idx = top_idx
        for i in range(top_idx, head_region_start, -1):
            if slice_max_ax[i] > max_head_width:
                max_head_width = slice_max_ax[i]
                widest_idx = i

        # Walk down from the widest point to find the neck minimum
        neck_idx = widest_idx
        neck_width = max_head_width
        for i in range(widest_idx, 0, -1):
            if slice_count[i] == 0:
                continue
            if slice_max_ax[i] < neck_width:
                neck_width = slice_max_ax[i]
                neck_idx = i
            # If width starts increasing again significantly, we've passed
            # the neck and are into the shoulders — stop
            if slice_max_ax[i] > neck_width * 1.3 and neck_width < max_head_width * 0.70:
                break

        # Chin Z = bottom of the narrowing region (where head meets neck)
        # Walk upward from neck to find where the head widens significantly
        chin_idx = neck_idx
        for i in range(neck_idx, widest_idx):
            if slice_count[i] > 0 and slice_max_ax[i] > neck_width * 1.2:
                chin_idx = i
                break

        chin_z = scan_floor_z + chin_idx * slice_height
        # Ensure chin_z is reasonable (head should be at least 15% of height)
        min_chin_z = actual_height * 0.70
        if chin_z < min_chin_z:
            chin_z = min_chin_z

        # Full head measurements
        full_head_height = crown_z - chin_z
        head_r       = full_head_height * 0.5      # vertical half-height
        head_z       = chin_z + head_r              # centre of head
        head_r_horiz = max_head_width               # horizontal half-width

        # ── face_y: face-surface Y at eye level ──────────────────────────
        # Sample vertices near the head centre (where eyes go), restricted
        # to the central X third, to find the face surface depth.
        eye_level_z = head_z + head_r * 0.15  # eyes sit above centre on chibi
        face_lo = eye_level_z - head_r * 0.30
        face_hi = eye_level_z + head_r * 0.30
        face_ys = []
        head_ys_all = []
        for wco in head_candidate_verts:
            if wco.z > chin_z:
                head_ys_all.append(wco.y)
            if face_lo < wco.z < face_hi and abs(wco.x) < head_r_horiz * 0.4:
                face_ys.append(wco.y)

        if face_ys:
            face_y = min(face_ys)
        elif head_ys_all:
            face_y = min(head_ys_all)
        else:
            face_y = 0.0

        # Also compute the equator Z (widest point of head) for hair placement.
        # Hair _build_cap expects head_z = equator and head_r = crown − equator.
        # We keep those as hair_head_z / hair_head_r.
        equator_z = scan_floor_z + widest_idx * slice_height
        hair_head_z = equator_z
        hair_head_r = crown_z - equator_z

        print(f"[template_mesh] Head detection: chin_z={chin_z:.4f}, crown={crown_z:.4f}, "
              f"head_z={head_z:.4f} (centre), head_r={head_r:.4f} (vert half), "
              f"head_r_horiz={head_r_horiz:.4f}, face_y={face_y:.4f}, "
              f"equator_z={equator_z:.4f} (hair)")

        # ── Detect body proportions for clothing fit ────────────────────────
        # Sample mesh vertices to find actual hip and chest geometry so
        # clothing builders use the true template proportions rather than the
        # preset values (which were designed for the procedural mesh).
        #
        # Arm vertices in T-pose sit at abs(x) > body_width; capping at 0.25 m
        # restricts the search to the torso region.
        BODY_X_CAP = 0.25   # max abs(x) for torso body verts (excludes arms)
        foot_top = 0.06

        # Hip zone: 27-52 % of height (pelvis / waist area)
        hip_lo = actual_height * 0.27
        hip_hi = actual_height * 0.52
        max_hip_ax = 0.0; detected_hip_z = actual_height * 0.35
        for v in mesh_obj.data.vertices:
            wco = mesh_obj.matrix_world @ v.co
            if hip_lo < wco.z < hip_hi and abs(wco.x) < BODY_X_CAP:
                ax = abs(wco.x)
                if ax > max_hip_ax:
                    max_hip_ax = ax; detected_hip_z = wco.z

        # Chest zone: 52-72 % of height (torso / shoulder)
        chest_lo = actual_height * 0.52
        chest_hi = actual_height * 0.72
        max_chest_ax = 0.0; detected_chest_z = actual_height * 0.63
        for v in mesh_obj.data.vertices:
            wco = mesh_obj.matrix_world @ v.co
            if chest_lo < wco.z < chest_hi and abs(wco.x) < BODY_X_CAP:
                ax = abs(wco.x)
                if ax > max_chest_ax:
                    max_chest_ax = ax; detected_chest_z = wco.z

        # Torso depth: max abs(Y) in the chest zone (same verts as shoulder scan)
        max_torso_ay = 0.0
        for v in mesh_obj.data.vertices:
            wco = mesh_obj.matrix_world @ v.co
            if chest_lo < wco.z < chest_hi and abs(wco.x) < BODY_X_CAP:
                ay = abs(wco.y)
                if ay > max_torso_ay:
                    max_torso_ay = ay

        # Overwrite cfg keys used by clothing builders with detected values
        detected_leg_len   = detected_hip_z - foot_top
        detected_torso_len = detected_chest_z - detected_hip_z
        detected_torso_depth = max_torso_ay if max_torso_ay > 0.05 else 0.20
        cfg["leg_length"]      = detected_leg_len
        cfg["torso_length"]    = detected_torso_len
        cfg["hip_width"]       = max_hip_ax
        cfg["shoulder_width"]  = max_chest_ax
        cfg["torso_depth"]     = detected_torso_depth
        # arm_length: keep preset (no arm geometry detection needed for basic fit)
        print(f"[template_mesh] Body geometry: hip_z={detected_hip_z:.3f} "
              f"(leg={detected_leg_len:.3f}), chest_z={detected_chest_z:.3f} "
              f"(torso={detected_torso_len:.3f}), "
              f"hip_w={max_hip_ax:.3f}, chest_w={max_chest_ax:.3f}, "
              f"torso_depth={detected_torso_depth:.3f}")

    # ── Ensure new objects land in the main scene collection ─────────────────
    # After importing a GLB the active layer-collection can be left pointing
    # at 'glTF_not_exported'.  Any object created with
    # bpy.context.collection.objects.link() would then become hidden and
    # excluded from export.  Reset to the view-layer root so hair, eyes, and
    # eyebrows end up in the top-level Collection.
    bpy.context.view_layer.active_layer_collection = (
        bpy.context.view_layer.layer_collection
    )

    # ── Hair ──────────────────────────────────────────────────────────────────
    # Hair cap uses equator-based coordinates (head_z = widest point of head,
    # head_r = crown − equator), NOT the full-head centre used for facial features.
    hair_obj = None
    hair_style = cfg.get("hair_style", "short")
    hair_color = cfg.get("hair_color", None)
    # hair_head_z / hair_head_r are populated by the vertex scan above.
    # Nudge the cap base lower (0.25 × head_r) so it covers more of the head,
    # and scale both the vertical radius and horizontal radius up so the cap
    # sits proud of the cartoon head's larger proportions.
    h_hz = hair_head_z - hair_head_r * 0.25
    h_hr = hair_head_r * 1.40
    h_horiz = head_r_horiz * 1.25
    if hair_style and hair_style != "none":
        hair_obj = hair_module.create_hair(h_hz, h_hr, hair_style, hair_color,
                                           head_r_horiz=h_horiz)

    if hair_obj:
        hair_obj.location.y += 0.02 # nudge hair backward a bit

    # Eyes, eyebrows, nose, mouth and mustache are disabled — the template mesh
    # already has these features baked into the model geometry.
    extra_head_objs = []

    # ── Clothing ──────────────────────────────────────────────────────────────
    # Build clothing by duplicating body-mesh faces in the relevant Z-range
    # and pushing them outward.  This gives clothing that exactly conforms to
    # the template mesh shape — far better than ring-based cylinders.
    clothing_spec = cfg.get("clothing", ["short_sleeve", "jeans"])
    if isinstance(clothing_spec, str):
        clothing_spec = [c.strip() for c in clothing_spec.split(",") if c.strip()]
    clothing_color = cfg.get("clothing_color", None)

    from . import clothing as clothing_module
    import bmesh as _bmesh
    from mathutils import Vector as _Vec

    # Precompute body vertex world coords for Z-range checks
    body_wcos = {}
    for v in mesh_obj.data.vertices:
        body_wcos[v.index] = mesh_obj.matrix_world @ v.co

    # Z-ranges for each clothing type (relative to detected body proportions)
    foot_top = 0.06
    _hip_z   = cfg["leg_length"] + foot_top
    _chest_z = _hip_z + cfg["torso_length"]
    _arm_len = cfg.get("arm_length", 0.45)
    _sw      = cfg["shoulder_width"]

    # Define which body regions each clothing type covers.
    # z_lo, z_hi = vertical extent.  include_arms = whether to include
    # vertices beyond the torso X cap (i.e. arm/shoulder verts).
    # Ranges are deliberately generous — better to slightly over-cover than
    # leave skin showing through gaps.
    # Clothing zones: z_lo, z_hi, include_arms
    # IMPORTANT: tshirt bottom and pants top must NOT overlap at the hip
    # or they blend into one solid block.  Leave a ~2cm skin gap at the waist.
    _waist_gap = 0.02
    _CLOTHING_ZONES = {
        "short_sleeve": (_hip_z + _waist_gap,                 _chest_z + 0.05, True),
        "long_sleeve":  (_hip_z + _waist_gap,                 _chest_z + 0.05, True),
        "v_neck":       (_hip_z + _waist_gap,                 _chest_z + 0.05, True),
        "jeans":        (foot_top - 0.02,                     _hip_z + cfg["torso_length"] * 0.10, False),
        "shorts":       (foot_top + cfg["leg_length"] * 0.38, _hip_z + cfg["torso_length"] * 0.10, False),
    }

    BODY_X_CAP = 0.28  # torso width cap — verts beyond this are arms

    extra_clothing_objs = []
    for ctype in clothing_spec:
        if ctype == "none":
            continue

        zone = _CLOTHING_ZONES.get(ctype)
        if zone is None:
            continue
        z_lo, z_hi, include_arms = zone

        # Collect faces where ANY vertex falls in the clothing zone.
        # Using any-vertex (not centre) avoids gaps at zone boundaries.
        clothing_faces = []
        for poly in mesh_obj.data.polygons:
            verts_wco = [body_wcos[vi] for vi in poly.vertices]
            any_in_zone = any(z_lo <= v.z <= z_hi for v in verts_wco)
            if not any_in_zone:
                continue
            # For non-arm clothing (pants), skip faces centred in the arm area
            if not include_arms:
                centre_ax = max(abs(v.x) for v in verts_wco)
                if centre_ax > BODY_X_CAP:
                    continue
            clothing_faces.append(poly)

        if not clothing_faces:
            continue

        # Build clothing bmesh from selected faces, offset outward
        bm_c = _bmesh.new()
        vert_map = {}  # body vert index → clothing bmesh vert

        for poly in clothing_faces:
            bm_verts = []
            for vi in poly.vertices:
                if vi not in vert_map:
                    wco = body_wcos[vi]
                    # Push vertex outward from body centre along the
                    # local surface normal approximation (radial from Y axis
                    # for torso, from leg axis for legs).
                    # Simple approach: scale outward from the Z-axis
                    offset_dir = _Vec((wco.x, wco.y, 0.0))
                    if offset_dir.length > 0.001:
                        offset_dir.normalize()
                    else:
                        offset_dir = _Vec((0.0, -1.0, 0.0))
                    offset = offset_dir * 0.015  # 15mm outward
                    new_co = wco + offset
                    vert_map[vi] = bm_c.verts.new(new_co)
                bm_verts.append(vert_map[vi])
            try:
                bm_c.faces.new(bm_verts)
            except ValueError:
                pass

        _bmesh.ops.recalc_face_normals(bm_c, faces=bm_c.faces)

        mesh_c = bpy.data.meshes.new(f"Clothing_{ctype}_Mesh")
        bm_c.to_mesh(mesh_c)
        mesh_c.update()
        bm_c.free()

        obj_c = bpy.data.objects.new(f"Clothing_{ctype}", mesh_c)
        bpy.context.collection.objects.link(obj_c)

        # Resolve colour
        if isinstance(clothing_color, dict):
            color_for_item = clothing_color.get(ctype, None)
        else:
            color_for_item = clothing_color
        rgba_c = clothing_module.resolve_clothing_rgba(ctype, color_for_item)

        mat_c = bpy.data.materials.new(f"Clothing_{ctype}_Mat")
        mat_c.use_nodes = True
        bsdf_c = mat_c.node_tree.nodes.get("Principled BSDF")
        if bsdf_c:
            bsdf_c.inputs["Base Color"].default_value = rgba_c
            bsdf_c.inputs["Roughness"].default_value = 0.65
            bsdf_c.inputs["Specular IOR Level"].default_value = 0.15
        obj_c.data.materials.append(mat_c)

        # Edge-split for consistent faceted look matching the body
        es_mod = obj_c.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
        es_mod.split_angle = math.radians(38)

        # Smooth shade
        bpy.context.view_layer.objects.active = obj_c
        obj_c.select_set(True)
        bpy.ops.object.shade_smooth()
        obj_c.select_set(False)

        extra_clothing_objs.append((obj_c, None))

    return mesh_obj, hair_obj, extra_head_objs + extra_clothing_objs
