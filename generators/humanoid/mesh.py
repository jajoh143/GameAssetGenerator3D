"""Low-poly humanoid mesh construction.

Builds the body using Blender's Skin modifier on a stick-figure skeleton.
The Skin modifier generates smooth, organic geometry from vertices and edges,
with per-vertex radii controlling body thickness at each joint. This produces
natural shoulder rounding and smooth torso tapering without stacking primitives.

A Subdivision Surface modifier (level 1) is applied on top for additional
smoothing. The head, eyes, nose, hands, and feet are added as separate
primitives and joined into the final mesh.
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


def _build_skin_body(cfg):
    """Build the torso, arms, and legs using the Skin modifier.

    Creates a stick-figure mesh (vertices + edges) and applies:
    1. Skin modifier — generates organic quad geometry with per-vertex radii
    2. Subdivision Surface — smooths the result (level 1 for low-poly)

    The Skin modifier naturally creates smooth transitions at joints like
    shoulders, making the torso-to-arm connection look organic rather than
    stacked boxes.

    Returns the applied mesh object (modifiers baked into geometry).
    """
    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    arm_len = cfg["arm_length"]
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    neck_len = cfg["neck_length"]
    head_r = cfg["head_size"]
    lt = cfg.get("limb_thickness", 1.0)
    td = cfg.get("torso_depth", 0.20)

    # Vertical layout (bottom-up)
    foot_top = 0.06
    knee_z = foot_top + leg_len * 0.48
    hip_z = foot_top + leg_len
    waist_z = hip_z + torso_len * 0.35
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

    # --- Define stick-figure vertices ---
    verts = [
        # Spine (center line)
        (0, 0, hip_z - 0.02),       # 0: Pelvis base
        (0, 0, hip_z),              # 1: Hip center
        (0, 0, waist_z),            # 2: Waist
        (0, 0, chest_z),            # 3: Chest top
        (0, 0, chest_z + neck_len), # 4: Neck top

        # Left arm
        (shoulder_x * 0.3, 0, chest_z - 0.01),   # 5: L inner shoulder
        (shoulder_x, 0, arm_top_z),               # 6: L shoulder tip
        (shoulder_x, 0, elbow_z),                 # 7: L elbow
        (shoulder_x, 0, wrist_z),                 # 8: L wrist

        # Right arm
        (-shoulder_x * 0.3, 0, chest_z - 0.01),  # 9: R inner shoulder
        (-shoulder_x, 0, arm_top_z),              # 10: R shoulder tip
        (-shoulder_x, 0, elbow_z),                # 11: R elbow
        (-shoulder_x, 0, wrist_z),                # 12: R wrist

        # Left leg
        (hw, 0, hip_z),             # 13: L hip joint
        (hw, 0, knee_z),            # 14: L knee
        (hw, 0, foot_top),          # 15: L ankle

        # Right leg
        (-hw, 0, hip_z),            # 16: R hip joint
        (-hw, 0, knee_z),           # 17: R knee
        (-hw, 0, foot_top),         # 18: R ankle
    ]

    # --- Define edges (skeleton connectivity) ---
    edges = [
        # Spine
        (0, 1), (1, 2), (2, 3), (3, 4),
        # Left arm (branches from chest)
        (3, 5), (5, 6), (6, 7), (7, 8),
        # Right arm (branches from chest)
        (3, 9), (9, 10), (10, 11), (11, 12),
        # Left leg (branches from hip)
        (1, 13), (13, 14), (14, 15),
        # Right leg (branches from hip)
        (1, 16), (16, 17), (17, 18),
    ]

    # --- Per-vertex skin radii (rx, ry) ---
    # rx = side-to-side width, ry = front-to-back depth
    waist_half_w = min(sw, hw) * 0.85
    radii = {
        0:  (hw + 0.02, td * 0.45),           # Pelvis base
        1:  (hw + 0.02, td * 0.50),            # Hip center
        2:  (waist_half_w, td * 0.48),         # Waist (narrower)
        3:  (sw, td * 0.55),                   # Chest top (shoulder width)
        4:  (0.052 * lt, 0.052 * lt),          # Neck top

        5:  (sw * 0.35, td * 0.42),            # L inner shoulder
        6:  (0.055 * lt, 0.050 * lt),          # L shoulder tip
        7:  (0.042 * lt, 0.042 * lt),          # L elbow
        8:  (0.034 * lt, 0.030 * lt),          # L wrist

        9:  (sw * 0.35, td * 0.42),            # R inner shoulder
        10: (0.055 * lt, 0.050 * lt),          # R shoulder tip
        11: (0.042 * lt, 0.042 * lt),          # R elbow
        12: (0.034 * lt, 0.030 * lt),          # R wrist

        13: (0.072 * lt, 0.065 * lt),          # L hip joint
        14: (0.058 * lt, 0.055 * lt),          # L knee
        15: (0.048 * lt, 0.045 * lt),          # L ankle

        16: (0.072 * lt, 0.065 * lt),          # R hip joint
        17: (0.058 * lt, 0.055 * lt),          # R knee
        18: (0.048 * lt, 0.045 * lt),          # R ankle
    }

    # --- Create the mesh ---
    mesh = bpy.data.meshes.new("SkinBody_Mesh")
    mesh.from_pydata(verts, edges, [])
    mesh.update()

    obj = bpy.data.objects.new("SkinBody", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # --- Add Skin modifier ---
    skin_mod = obj.modifiers.new(name="Skin", type='SKIN')
    skin_mod.branch_smoothing = 0.8
    skin_mod.use_smooth_shade = True

    # Set per-vertex radii and mark root
    skin_data = mesh.skin_vertices[0].data
    for i, sv in enumerate(skin_data):
        rx, ry = radii.get(i, (0.05, 0.05))
        sv.radius = (rx, ry)
        if i == 0:
            sv.use_root = True

    # --- Add Subdivision Surface for smoothing ---
    subsurf = obj.modifiers.new(name="Subsurf", type='SUBSURF')
    subsurf.levels = 1
    subsurf.render_levels = 1

    # --- Apply modifiers to bake into geometry ---
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="Skin")
    bpy.ops.object.modifier_apply(modifier="Subsurf")

    return obj


def create_body(cfg):
    """Build the complete humanoid mesh from config values.

    The character is built standing upright with feet at Z=0.
    Uses Blender's Skin modifier for the torso, arms, and legs to create
    smooth organic forms with natural shoulder rounding. Head, hands, feet,
    and facial features are added as separate primitives and joined in.

    Args:
        cfg: dict with body proportion values.

    Returns:
        Tuple of (body_obj, hair_obj_or_None, clothing_list).
    """
    _clear_scene()

    h = cfg["height"]
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

    # Body variation parameters
    lt = cfg.get("limb_thickness", 1.0)
    td = cfg.get("torso_depth", 0.20)
    skin_tone = cfg.get("skin_tone", None)

    # Vertical layout
    foot_top = 0.06
    knee_z = foot_top + leg_len * 0.48
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
    skin_body = _build_skin_body(cfg)
    parts.append(skin_body)

    # --- Head (sphere, scaled for human proportions) ---
    # Reference model head ratio W:H:D = 0.70:1.00:0.79
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

    # Smooth shading on the joined mesh
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
        clothing_objs = clothing_module.create_clothing(cfg, clothing_type, clothing_color)

    return body, hair_obj, clothing_objs
