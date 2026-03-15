"""Low-poly humanoid mesh construction.

Builds the body using Blender's Skin modifier on a stick-figure skeleton.
The Skin modifier generates smooth, organic geometry from vertices and edges,
with per-vertex radii controlling body thickness at each joint. This produces
natural shoulder rounding, smooth torso tapering, and subtle muscle definition
without stacking primitives.

The skeleton includes intermediate vertices for muscle bulges (deltoid, bicep,
forearm, thigh, calf) and torso shaping (lower chest, lower waist). A
Subdivision Surface modifier (level 1) is applied on top for additional
smoothing.

The skeleton builder is exposed via build_body_skeleton() so clothing.py can
reuse the same skeleton with inflated radii for perfectly fitting clothing.
"""

import bpy
import math
from mathutils import Vector, Matrix


def _clear_scene():
    """Remove default objects."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def _create_box(name, size, location, scale=(1, 1, 1)):
    """Create a box mesh at the given location."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0] * scale[0], size[1] * scale[1], size[2] * scale[2])
    bpy.ops.object.transform_apply(scale=True)
    return obj


def _create_sphere(name, radius, location, segments=12, rings=8):
    """Create a UV sphere."""
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        radius=radius,
        location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _join_objects(objects):
    """Join multiple objects into one mesh."""
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = "Humanoid_Body"
    return result


def _apply_material(obj, skin_tone=None):
    """Apply a base material with configurable skin tone."""
    mat = bpy.data.materials.new(name="Humanoid_Base")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        color = skin_tone if skin_tone else (0.65, 0.55, 0.45, 1.0)
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.69
    obj.data.materials.append(mat)


# ─── Skeleton builder (shared with clothing.py) ────────────────────────────

# Vertex name constants for indexing into the skeleton.
# These define which vertices belong to which body region, so clothing
# builders can select subsets of the skeleton.

# Spine: 0-6
V_PELVIS = 0
V_HIP = 1
V_LOWER_WAIST = 2
V_WAIST = 3
V_LOWER_CHEST = 4
V_CHEST = 5
V_NECK = 6

# Left arm: 7-13
V_L_INNER_SHOULDER = 7
V_L_SHOULDER = 8
V_L_DELTOID = 9
V_L_BICEP = 10
V_L_ELBOW = 11
V_L_FOREARM = 12
V_L_WRIST = 13

# Right arm: 14-20
V_R_INNER_SHOULDER = 14
V_R_SHOULDER = 15
V_R_DELTOID = 16
V_R_BICEP = 17
V_R_ELBOW = 18
V_R_FOREARM = 19
V_R_WRIST = 20

# Left leg: 21-26
V_L_HIP_JOINT = 21
V_L_THIGH = 22
V_L_KNEE = 23
V_L_CALF = 24
V_L_ANKLE = 25

# Right leg: 26-30
V_R_HIP_JOINT = 26
V_R_THIGH = 27
V_R_KNEE = 28
V_R_CALF = 29
V_R_ANKLE = 30

# Region sets for clothing
REGION_SPINE = {V_PELVIS, V_HIP, V_LOWER_WAIST, V_WAIST, V_LOWER_CHEST,
                V_CHEST, V_NECK}
REGION_L_ARM = {V_L_INNER_SHOULDER, V_L_SHOULDER, V_L_DELTOID, V_L_BICEP,
                V_L_ELBOW, V_L_FOREARM, V_L_WRIST}
REGION_R_ARM = {V_R_INNER_SHOULDER, V_R_SHOULDER, V_R_DELTOID, V_R_BICEP,
                V_R_ELBOW, V_R_FOREARM, V_R_WRIST}
REGION_L_LEG = {V_L_HIP_JOINT, V_L_THIGH, V_L_KNEE, V_L_CALF, V_L_ANKLE}
REGION_R_LEG = {V_R_HIP_JOINT, V_R_THIGH, V_R_KNEE, V_R_CALF, V_R_ANKLE}


def build_body_skeleton(cfg):
    """Build the stick-figure skeleton with muscle-definition vertices.

    Returns (verts, edges, radii) where:
        verts: list of (x, y, z) positions
        edges: list of (i, j) index pairs
        radii: dict mapping vertex index to (rx, ry)

    This function is shared between mesh.py and clothing.py so clothing
    can reuse the same skeleton with inflated radii.
    """
    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    arm_len = cfg["arm_length"]
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    neck_len = cfg["neck_length"]
    lt = cfg.get("limb_thickness", 1.0)
    td = cfg.get("torso_depth", 0.20)
    gender = cfg.get("gender", "neutral")

    # Vertical layout (bottom-up)
    foot_top = 0.06
    knee_z = foot_top + leg_len * 0.48
    hip_z = foot_top + leg_len
    waist_z = hip_z + torso_len * 0.35
    lower_waist_z = hip_z + torso_len * 0.15
    lower_chest_z = hip_z + torso_len * 0.70
    chest_z = hip_z + torso_len
    neck_z = chest_z + neck_len

    # Arm positions
    shoulder_x = sw + 0.04
    arm_top_z = chest_z - 0.04
    upper_arm_len = arm_len * 0.48
    elbow_z = arm_top_z - upper_arm_len
    lower_arm_len = arm_len * 0.52
    wrist_z = elbow_z - lower_arm_len

    # Muscle vertex positions along arms
    deltoid_z = arm_top_z - upper_arm_len * 0.25
    bicep_z = arm_top_z - upper_arm_len * 0.60
    forearm_z = elbow_z - lower_arm_len * 0.30

    # Muscle vertex positions along legs
    thigh_z = hip_z - (hip_z - knee_z) * 0.35
    calf_z = knee_z - (knee_z - foot_top) * 0.30

    waist_half_w = min(sw, hw) * 0.72

    # --- Gender-specific adjustments ---
    # These modify the radii to create distinct male/female silhouettes.
    # Male: trapezius rise, pectoral protrusion, larger arms/legs, build-scaled
    # Female: hourglass emphasis, wider/rounder glutes, different chest shape
    # Both: enhanced gluteal area compared to neutral

    # Trapezius rise: male inner shoulder is positioned higher
    trap_z_offset = 0.0
    # Pectoral depth multiplier (ry on chest vertices)
    pec_depth = 1.0
    # Neck thickness multiplier
    neck_thick = 1.0
    # Arm muscle multiplier (applied on top of lt)
    arm_muscle = 1.0
    # Leg muscle multiplier
    leg_muscle = 1.0
    # Glute enhancement (pelvis/hip ry multiplier)
    glute_depth = 1.0
    # Hip width radius boost
    hip_rx_mult = 1.0
    # Waist narrowing (lower = narrower)
    waist_mult = 1.0
    # Chest width multiplier
    chest_rx_mult = 1.0

    if gender == "male":
        trap_z_offset = 0.025         # inner shoulder sits higher → trapezius rise
        pec_depth = 1.25              # pectorals protrude forward
        neck_thick = 1.20             # thicker neck
        arm_muscle = 1.25             # much larger arms
        leg_muscle = 1.30             # legs even larger than arms
        glute_depth = 1.15            # enhanced butt area
        chest_rx_mult = 1.08          # wider chest
    elif gender == "female":
        pec_depth = 1.15              # moderate chest protrusion
        neck_thick = 0.88             # slimmer neck
        arm_muscle = 0.88             # slimmer arms
        leg_muscle = 0.95             # slightly slimmer legs
        glute_depth = 1.30            # pronounced butt/hip area
        hip_rx_mult = 1.12            # wider hips
        waist_mult = 0.88             # narrower waist for hourglass
        chest_rx_mult = 0.95          # narrower chest width

    # --- Vertices (31 total) ---
    verts = [
        # Spine (0-6)
        (0, 0, hip_z - 0.02),         # 0: Pelvis base
        (0, 0, hip_z),                 # 1: Hip center
        (0, 0, lower_waist_z),         # 2: Lower waist (belly)
        (0, 0, waist_z),               # 3: Waist (narrowest)
        (0, 0, lower_chest_z),         # 4: Lower chest (rib flare)
        (0, 0, chest_z),               # 5: Chest top
        (0, 0, neck_z),                # 6: Neck top

        # Left arm (7-13) — inner shoulder raised for male trapezius
        (shoulder_x * 0.4, 0, chest_z - 0.01 + trap_z_offset),  # 7: L inner shoulder
        (shoulder_x, 0, arm_top_z),               # 8: L shoulder tip
        (shoulder_x, 0, deltoid_z),               # 9: L deltoid
        (shoulder_x, 0, bicep_z),                 # 10: L bicep peak
        (shoulder_x, 0, elbow_z),                 # 11: L elbow
        (shoulder_x, 0, forearm_z),               # 12: L forearm
        (shoulder_x, 0, wrist_z),                 # 13: L wrist

        # Right arm (14-20) — mirror
        (-shoulder_x * 0.4, 0, chest_z - 0.01 + trap_z_offset),  # 14: R inner shoulder
        (-shoulder_x, 0, arm_top_z),              # 15: R shoulder tip
        (-shoulder_x, 0, deltoid_z),              # 16: R deltoid
        (-shoulder_x, 0, bicep_z),                # 17: R bicep peak
        (-shoulder_x, 0, elbow_z),                # 18: R elbow
        (-shoulder_x, 0, forearm_z),              # 19: R forearm
        (-shoulder_x, 0, wrist_z),                # 20: R wrist

        # Left leg (21-25)
        (hw, 0, hip_z),               # 21: L hip joint
        (hw, 0, thigh_z),             # 22: L thigh peak
        (hw, 0, knee_z),              # 23: L knee
        (hw, 0, calf_z),              # 24: L calf peak
        (hw, 0, foot_top),            # 25: L ankle

        # Right leg (26-30)
        (-hw, 0, hip_z),              # 26: R hip joint
        (-hw, 0, thigh_z),            # 27: R thigh peak
        (-hw, 0, knee_z),             # 28: R knee
        (-hw, 0, calf_z),             # 29: R calf peak
        (-hw, 0, foot_top),           # 30: R ankle
    ]

    # --- Edges ---
    edges = [
        # Spine
        (0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6),
        # Left arm
        (5, 7), (7, 8), (8, 9), (9, 10), (10, 11), (11, 12), (12, 13),
        # Right arm
        (5, 14), (14, 15), (15, 16), (16, 17), (17, 18), (18, 19), (19, 20),
        # Left leg
        (1, 21), (21, 22), (22, 23), (23, 24), (24, 25),
        # Right leg
        (1, 26), (26, 27), (27, 28), (28, 29), (29, 30),
    ]

    # --- Per-vertex radii (rx, ry) ---
    # Base hourglass silhouette with gender-specific modifications
    radii = {
        # Spine — hourglass with gender shaping
        0:  (hw * hip_rx_mult + 0.04, td * 0.48 * glute_depth),    # Pelvis base
        1:  (hw * hip_rx_mult + 0.05, td * 0.52 * glute_depth),    # Hip center
        2:  (hw * 0.8, td * 0.44),                                  # Lower waist
        3:  (waist_half_w * waist_mult, td * 0.40),                 # Waist (narrowest)
        4:  (sw * 0.90 * chest_rx_mult, td * 0.54 * pec_depth),    # Lower chest
        5:  (sw * 1.05 * chest_rx_mult, td * 0.58 * pec_depth),    # Chest top
        6:  (0.055 * lt * neck_thick, 0.055 * lt * neck_thick),     # Neck

        # Left arm — gender-scaled muscle
        7:  (sw * 0.40, td * 0.45 * arm_muscle),            # L inner shoulder
        8:  (0.068 * lt * arm_muscle, 0.060 * lt * arm_muscle),  # L shoulder tip
        9:  (0.072 * lt * arm_muscle, 0.064 * lt * arm_muscle),  # L deltoid
        10: (0.062 * lt * arm_muscle, 0.058 * lt * arm_muscle),  # L bicep peak
        11: (0.046 * lt * arm_muscle, 0.046 * lt * arm_muscle),  # L elbow
        12: (0.052 * lt * arm_muscle, 0.048 * lt * arm_muscle),  # L forearm
        13: (0.038 * lt * arm_muscle, 0.034 * lt * arm_muscle),  # L wrist

        # Right arm — mirror
        14: (sw * 0.40, td * 0.45 * arm_muscle),            # R inner shoulder
        15: (0.068 * lt * arm_muscle, 0.060 * lt * arm_muscle),  # R shoulder tip
        16: (0.072 * lt * arm_muscle, 0.064 * lt * arm_muscle),  # R deltoid
        17: (0.062 * lt * arm_muscle, 0.058 * lt * arm_muscle),  # R bicep peak
        18: (0.046 * lt * arm_muscle, 0.046 * lt * arm_muscle),  # R elbow
        19: (0.052 * lt * arm_muscle, 0.048 * lt * arm_muscle),  # R forearm
        20: (0.038 * lt * arm_muscle, 0.034 * lt * arm_muscle),  # R wrist

        # Left leg — gender-scaled muscle
        21: (0.082 * lt * leg_muscle, 0.074 * lt * leg_muscle * glute_depth),   # L hip joint
        22: (0.088 * lt * leg_muscle, 0.078 * lt * leg_muscle),  # L thigh peak
        23: (0.060 * lt * leg_muscle, 0.058 * lt * leg_muscle),  # L knee
        24: (0.066 * lt * leg_muscle, 0.058 * lt * leg_muscle),  # L calf peak
        25: (0.048 * lt * leg_muscle, 0.046 * lt * leg_muscle),  # L ankle

        # Right leg — mirror
        26: (0.082 * lt * leg_muscle, 0.074 * lt * leg_muscle * glute_depth),   # R hip joint
        27: (0.088 * lt * leg_muscle, 0.078 * lt * leg_muscle),  # R thigh peak
        28: (0.060 * lt * leg_muscle, 0.058 * lt * leg_muscle),  # R knee
        29: (0.066 * lt * leg_muscle, 0.058 * lt * leg_muscle),  # R calf peak
        30: (0.048 * lt * leg_muscle, 0.046 * lt * leg_muscle),  # R ankle
    }

    return verts, edges, radii


def _apply_skin_modifier(verts, edges, radii, name="SkinBody",
                         branch_smoothing=0.7, subsurf_level=1):
    """Create a mesh from skeleton and apply Skin + Subdivision Surface.

    Args:
        verts, edges, radii: from build_body_skeleton()
        name: object name
        branch_smoothing: 0-1, how smooth branch junctions are
        subsurf_level: subdivision level (0 = no subdivision)

    Returns the mesh object with modifiers applied.
    """
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(verts, edges, [])
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Skin modifier
    skin_mod = obj.modifiers.new(name="Skin", type='SKIN')
    skin_mod.branch_smoothing = branch_smoothing
    skin_mod.use_smooth_shade = True

    # Set per-vertex radii and mark root
    skin_data = mesh.skin_vertices[0].data
    for i, sv in enumerate(skin_data):
        rx, ry = radii.get(i, (0.05, 0.05))
        sv.radius = (rx, ry)
        if i == 0:
            sv.use_root = True

    # Subdivision Surface
    if subsurf_level > 0:
        subsurf = obj.modifiers.new(name="Subsurf", type='SUBSURF')
        subsurf.levels = subsurf_level
        subsurf.render_levels = subsurf_level

    # Apply modifiers
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="Skin")
    if subsurf_level > 0:
        bpy.ops.object.modifier_apply(modifier="Subsurf")

    return obj


def create_body(cfg):
    """Build the complete humanoid mesh from config values.

    The character is built standing upright with feet at Z=0.
    Uses Blender's Skin modifier for the torso, arms, and legs to create
    smooth organic forms with natural shoulder rounding and muscle definition.
    Head, hands, feet, and facial features are added as separate primitives.

    Args:
        cfg: dict with body proportion values.

    Returns:
        Tuple of (body_obj, hair_obj_or_None, clothing_list).
    """
    _clear_scene()

    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    head_r = cfg["head_size"]
    arm_len = cfg["arm_length"]
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    neck_len = cfg["neck_length"]
    hand_size = cfg["hand_size"]
    foot_len = cfg["foot_length"]
    foot_w = cfg["foot_width"]
    lt = cfg.get("limb_thickness", 1.0)
    td = cfg.get("torso_depth", 0.20)
    skin_tone = cfg.get("skin_tone", None)

    # Vertical layout
    foot_top = 0.06
    hip_z = foot_top + leg_len
    chest_z = hip_z + torso_len
    neck_z = chest_z + neck_len
    head_z = neck_z + head_r

    # Arm positions
    shoulder_x = sw + 0.04
    arm_top_z = chest_z - 0.04
    upper_arm_len = arm_len * 0.48
    elbow_z = arm_top_z - upper_arm_len
    lower_arm_len = arm_len * 0.52
    wrist_z = elbow_z - lower_arm_len

    parts = []

    # --- Skin-modifier body (torso + arms + legs) ---
    verts, edges, radii = build_body_skeleton(cfg)
    skin_body = _apply_skin_modifier(verts, edges, radii, name="SkinBody",
                                     branch_smoothing=0.7)
    parts.append(skin_body)

    # --- Head (sphere, scaled for human proportions) ---
    head = _create_sphere("Head", head_r, (0, 0, head_z), segments=14, rings=10)
    head.scale = (0.88, 0.92, 1.05)
    bpy.context.view_layer.objects.active = head
    bpy.ops.object.transform_apply(scale=True)
    parts.append(head)

    # --- Hands (spheres at wrist ends) ---
    for side, x_sign in [("L", 1), ("R", -1)]:
        hand = _create_sphere(
            f"Hand.{side}", hand_size,
            (x_sign * shoulder_x, 0, wrist_z - hand_size * 0.5),
            segments=8, rings=5,
        )
        parts.append(hand)

    # --- Feet (boxes) ---
    for side, x_sign in [("L", 1), ("R", -1)]:
        x = x_sign * hw
        foot = _create_box(
            f"Foot.{side}",
            size=(foot_w, foot_len, 0.06),
            location=(x, foot_len * 0.15, 0.03),
        )
        parts.append(foot)

    # --- Face (eyes + nose) ---
    eye_r = head_r * 0.06
    eye_spacing = head_r * 0.28
    eye_y = head_r * 0.82
    eye_z = head_z + head_r * 0.12

    eye_mat = bpy.data.materials.new(name="Eye_Material")
    eye_mat.use_nodes = True
    eye_bsdf = eye_mat.node_tree.nodes.get("Principled BSDF")
    if eye_bsdf:
        eye_bsdf.inputs["Base Color"].default_value = (0.05, 0.05, 0.08, 1.0)
        eye_bsdf.inputs["Roughness"].default_value = 0.3

    for side, x_sign in [("L", 1), ("R", -1)]:
        eye = _create_sphere(
            f"Eye.{side}", eye_r,
            (x_sign * eye_spacing, eye_y, eye_z),
            segments=6, rings=4,
        )
        eye.data.materials.append(eye_mat)
        parts.append(eye)

    nose_r = head_r * 0.07
    nose = _create_sphere(
        "Nose", nose_r,
        (0, head_r * 0.86, head_z - head_r * 0.06),
        segments=6, rings=4,
    )
    parts.append(nose)

    # --- Join all parts ---
    body = _join_objects(parts)

    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

    # Smooth shading
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.shade_smooth()
    mod = body.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
    mod.split_angle = math.radians(50)

    _apply_material(body, skin_tone)

    # --- Hair (separate object, will be parented to Head bone) ---
    hair_obj = None
    hair_style = cfg.get("hair_style", "short")
    hair_color = cfg.get("hair_color", None)
    if hair_style and hair_style != "none":
        from . import hair as hair_module
        hair_obj = hair_module.create_hair(head_z, head_r, hair_style, hair_color)

    # --- Clothing (separate objects, skinned to armature) ---
    clothing_objs = []
    clothing_type = cfg.get("clothing", "tshirt,pants")
    if clothing_type and clothing_type != "none":
        from . import clothing as clothing_module
        clothing_color = cfg.get("clothing_color", None)
        clothing_objs = clothing_module.create_clothing(cfg, clothing_type,
                                                        clothing_color)

    return body, hair_obj, clothing_objs
