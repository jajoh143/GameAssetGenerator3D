"""Low-poly humanoid mesh construction.

Uses a base-mesh + morph-target architecture inspired by MB-Lab:
1. Build a fixed-topology base mesh from ring-based cross-sections
2. Apply morph deltas for body variation (gender, build, preset)
3. Convert to Blender object with deterministic vertex groups

The base mesh is a single unified mesh (~350-450 quads) built with
octagonal cross-section rings connected by quad strips. This gives
clean, predictable topology suitable for animation and clothing fitting.

The skeleton builder (build_body_skeleton) is preserved for backward
compatibility but is no longer used by the main pipeline.
"""

import math


def _clear_scene():
    """Remove default objects."""
    import bpy
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def _apply_material(obj, skin_tone=None):
    """Apply a base material with configurable skin tone."""
    import bpy
    mat = bpy.data.materials.new(name="Humanoid_Base")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        color = skin_tone if skin_tone else (0.65, 0.55, 0.45, 1.0)
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.50  # more sheen for stylized look
        bsdf.inputs["Specular IOR Level"].default_value = 0.35
    obj.data.materials.append(mat)


def _apply_eye_material(obj):
    """Apply dark material for eyes."""
    import bpy
    eye_mat = bpy.data.materials.new(name="Eye_Material")
    eye_mat.use_nodes = True
    eye_bsdf = eye_mat.node_tree.nodes.get("Principled BSDF")
    if eye_bsdf:
        eye_bsdf.inputs["Base Color"].default_value = (0.05, 0.05, 0.08, 1.0)
        eye_bsdf.inputs["Roughness"].default_value = 0.3
    obj.data.materials.append(eye_mat)


def _bmesh_to_object(bm, name, vertex_groups=None):
    """Convert a bmesh to a Blender object with optional vertex groups.

    Args:
        bm: bmesh instance
        name: object name
        vertex_groups: optional dict mapping group names to
            [(vertex_index, weight)] lists

    Returns:
        Blender object
    """
    import bpy
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm.to_mesh(mesh)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Apply vertex groups for deterministic skinning
    if vertex_groups:
        for group_name, vert_weights in vertex_groups.items():
            vg = obj.vertex_groups.new(name=group_name)
            for vert_idx, weight in vert_weights:
                try:
                    vg.add([vert_idx], weight, 'REPLACE')
                except RuntimeError:
                    pass  # vertex index out of range (shouldn't happen)

    return obj


def create_body(cfg):
    """Build the complete humanoid mesh from config values.

    When ``cfg["use_template"]`` is True the mesh is imported from a
    pre-made NBM .blend file (see generators/humanoid/template_mesh.py).
    Otherwise the mesh is built procedurally from cross-section rings.

    Args:
        cfg: dict with body proportion values.

    Returns:
        Tuple of (body_obj, hair_obj_or_None, []).
        The empty list preserves the old (body, hair, clothing_objs) API so
        callers that unpack the tuple continue to work unchanged.
    """
    if cfg.get("use_template", False):
        from .template_mesh import create_body_from_template
        return create_body_from_template(cfg)

    import bpy

    _clear_scene()

    skin_tone = cfg.get("skin_tone", None)

    # --- Build base body bmesh ---
    from .base_mesh import build_base_mesh

    bm, vertex_groups, eye_face_indices = build_base_mesh(cfg)

    # --- Convert unified bmesh to Blender object ---
    body = _bmesh_to_object(bm, "Humanoid_Body", vertex_groups)
    bm.free()

    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

    bpy.ops.object.shade_smooth()
    mod = body.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
    mod.split_angle = math.radians(50)

    # --- Assign materials ---
    # Slot 0: skin
    _apply_material(body, skin_tone)
    # Slot 1: eyes — assign to eye face polygons
    _apply_eye_material(body)
    eye_set = set(eye_face_indices) if eye_face_indices else set()
    for poly in body.data.polygons:
        if poly.index in eye_set:
            poly.material_index = 1

    body.data.update()

    # --- Hair (separate object, parented to Head bone by rig.py) ---
    hair_obj = None
    hair_style = cfg.get("hair_style", "short")
    hair_color = cfg.get("hair_color", None)
    if hair_style and hair_style != "none":
        from . import hair as hair_module
        head_r = cfg["head_size"]
        leg_len = cfg["leg_length"]
        torso_len = cfg["torso_length"]
        neck_len = cfg["neck_length"]
        foot_top = 0.06
        hip_z = foot_top + leg_len
        chest_z = hip_z + torso_len
        neck_z = chest_z + neck_len
        head_z = neck_z + head_r
        hair_obj = hair_module.create_hair(head_z, head_r, hair_style, hair_color)

    # Return empty list as third element to preserve the (body, hair, clothing) API
    return body, hair_obj, []


# ─── Backward compatibility ────────────────────────────────────────────────
# The following constants and functions are preserved for backward
# compatibility. They are no longer used by the main mesh pipeline
# but may be referenced by other code.

# Vertex name constants for the old skeleton-based system
V_PELVIS = 0
V_HIP = 1
V_LOWER_WAIST = 2
V_WAIST = 3
V_LOWER_CHEST = 4
V_CHEST = 5
V_NECK = 6
V_L_INNER_SHOULDER = 7
V_L_SHOULDER = 8
V_L_DELTOID = 9
V_L_BICEP = 10
V_L_ELBOW = 11
V_L_FOREARM = 12
V_L_WRIST = 13
V_R_INNER_SHOULDER = 14
V_R_SHOULDER = 15
V_R_DELTOID = 16
V_R_BICEP = 17
V_R_ELBOW = 18
V_R_FOREARM = 19
V_R_WRIST = 20
V_L_HIP_JOINT = 21
V_L_THIGH = 22
V_L_KNEE = 23
V_L_CALF = 24
V_L_ANKLE = 25
V_R_HIP_JOINT = 26
V_R_THIGH = 27
V_R_KNEE = 28
V_R_CALF = 29
V_R_ANKLE = 30

REGION_SPINE = {V_PELVIS, V_HIP, V_LOWER_WAIST, V_WAIST, V_LOWER_CHEST,
                V_CHEST, V_NECK}
REGION_L_ARM = {V_L_INNER_SHOULDER, V_L_SHOULDER, V_L_DELTOID, V_L_BICEP,
                V_L_ELBOW, V_L_FOREARM, V_L_WRIST}
REGION_R_ARM = {V_R_INNER_SHOULDER, V_R_SHOULDER, V_R_DELTOID, V_R_BICEP,
                V_R_ELBOW, V_R_FOREARM, V_R_WRIST}
REGION_L_LEG = {V_L_HIP_JOINT, V_L_THIGH, V_L_KNEE, V_L_CALF, V_L_ANKLE}
REGION_R_LEG = {V_R_HIP_JOINT, V_R_THIGH, V_R_KNEE, V_R_CALF, V_R_ANKLE}


def build_body_skeleton(cfg):
    """Build the stick-figure skeleton (DEPRECATED).

    Preserved for backward compatibility. The new pipeline uses
    base_mesh.build_base_mesh() instead.
    """
    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    arm_len = cfg["arm_length"]
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    neck_len = cfg["neck_length"]
    lt = cfg.get("limb_thickness", 1.0)
    td = cfg.get("torso_depth", 0.20)

    foot_top = 0.06
    knee_z = foot_top + leg_len * 0.48
    hip_z = foot_top + leg_len
    lower_waist_z = hip_z + torso_len * 0.20
    waist_z = hip_z + torso_len * 0.42
    lower_chest_z = hip_z + torso_len * 0.68
    chest_z = hip_z + torso_len
    neck_z = chest_z + neck_len

    shoulder_x = sw + 0.04
    arm_top_z = chest_z - 0.04
    upper_arm_len = arm_len * 0.48
    elbow_z = arm_top_z - upper_arm_len
    lower_arm_len = arm_len * 0.52
    wrist_z = elbow_z - lower_arm_len

    deltoid_z = arm_top_z - upper_arm_len * 0.25
    bicep_z = arm_top_z - upper_arm_len * 0.60
    forearm_z = elbow_z - lower_arm_len * 0.30

    thigh_z = hip_z - (hip_z - knee_z) * 0.35
    calf_z = knee_z - (knee_z - foot_top) * 0.30

    waist_half_w = min(sw, hw) * 0.72

    verts = [
        (0, 0, hip_z - 0.02), (0, 0, hip_z), (0, 0, lower_waist_z),
        (0, 0, waist_z), (0, 0, lower_chest_z), (0, 0, chest_z),
        (0, 0, neck_z),
        (shoulder_x * 0.4, 0, chest_z - 0.01), (shoulder_x, 0, arm_top_z),
        (shoulder_x, 0, deltoid_z), (shoulder_x, 0, bicep_z),
        (shoulder_x, 0, elbow_z), (shoulder_x, 0, forearm_z),
        (shoulder_x, 0, wrist_z),
        (-shoulder_x * 0.4, 0, chest_z - 0.01), (-shoulder_x, 0, arm_top_z),
        (-shoulder_x, 0, deltoid_z), (-shoulder_x, 0, bicep_z),
        (-shoulder_x, 0, elbow_z), (-shoulder_x, 0, forearm_z),
        (-shoulder_x, 0, wrist_z),
        (hw, 0, hip_z), (hw, 0, thigh_z), (hw, 0, knee_z),
        (hw, 0, calf_z), (hw, 0, foot_top),
        (-hw, 0, hip_z), (-hw, 0, thigh_z), (-hw, 0, knee_z),
        (-hw, 0, calf_z), (-hw, 0, foot_top),
        (hw * 0.5, 0, hip_z), (-hw * 0.5, 0, hip_z),
    ]

    edges = [
        (0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6),
        (5, 7), (7, 8), (8, 9), (9, 10), (10, 11), (11, 12), (12, 13),
        (5, 14), (14, 15), (15, 16), (16, 17), (17, 18), (18, 19), (19, 20),
        (1, 31), (31, 21), (21, 22), (22, 23), (23, 24), (24, 25),
        (1, 32), (32, 26), (26, 27), (27, 28), (28, 29), (29, 30),
    ]

    radii = {
        0: (hw + 0.04, td * 0.48), 1: (hw + 0.05, td * 0.52),
        2: (hw * 0.8, td * 0.44), 3: (waist_half_w, td * 0.40),
        4: (sw * 0.90, td * 0.54), 5: (sw * 1.05, td * 0.58),
        6: (0.055 * lt, 0.055 * lt),
        7: (sw * 0.40, td * 0.45), 8: (0.068 * lt, 0.060 * lt),
        9: (0.072 * lt, 0.064 * lt), 10: (0.062 * lt, 0.058 * lt),
        11: (0.046 * lt, 0.046 * lt), 12: (0.052 * lt, 0.048 * lt),
        13: (0.038 * lt, 0.034 * lt),
        14: (sw * 0.40, td * 0.45), 15: (0.068 * lt, 0.060 * lt),
        16: (0.072 * lt, 0.064 * lt), 17: (0.062 * lt, 0.058 * lt),
        18: (0.046 * lt, 0.046 * lt), 19: (0.052 * lt, 0.048 * lt),
        20: (0.038 * lt, 0.034 * lt),
        21: (0.105 * lt, 0.095 * lt), 22: (0.112 * lt, 0.098 * lt),
        23: (0.074 * lt, 0.072 * lt), 24: (0.082 * lt, 0.074 * lt),
        25: (0.058 * lt, 0.056 * lt),
        26: (0.105 * lt, 0.095 * lt), 27: (0.112 * lt, 0.098 * lt),
        28: (0.074 * lt, 0.072 * lt), 29: (0.082 * lt, 0.074 * lt),
        30: (0.058 * lt, 0.056 * lt),
        31: (hw * 0.6, td * 0.50), 32: (hw * 0.6, td * 0.50),
    }

    return verts, edges, radii
