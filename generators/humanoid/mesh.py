"""Low-poly humanoid mesh construction.

Builds the body from geometric primitives that are joined into a single mesh.
Designed to be ~300-500 faces — light enough for mobile/web games while still
reading as a humanoid silhouette.

Body shaping uses tapered torso sections (wider chest, narrower waist, wider
hips) and higher-segment primitives for smoother organic forms. Smoothing uses
per-vertex normals with a wide edge-split angle for a clean, soft low-poly look.
"""

import bpy
import bmesh
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


def _create_cylinder(name, radius, depth, location, segments=10):
    """Create a low-poly cylinder."""
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=segments,
        radius=radius,
        depth=depth,
        location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _create_sphere(name, radius, location, segments=10, rings=8):
    """Create a low-poly sphere (UV sphere)."""
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        radius=radius,
        location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _create_tapered_cylinder(name, radius_top, radius_bottom, depth, location, segments=10):
    """Create a tapered cylinder (truncated cone) for organic body shapes."""
    bpy.ops.mesh.primitive_cone_add(
        vertices=segments,
        radius1=radius_bottom,
        radius2=radius_top,
        depth=depth,
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


def _smooth_normals(obj):
    """Apply smooth shading with subdivision and a wide edge-split angle.

    Matches the smooth per-vertex normals seen in the reference model:
    subdivision level 1 for rounder organic forms, smooth shading on all
    faces, and edge-split at 50 degrees to preserve intentional hard edges
    (like where limbs meet the torso) while keeping body surfaces soft.
    """
    bpy.context.view_layer.objects.active = obj

    # Subdivision surface for rounder shapes (level 1 keeps poly count low)
    sub = obj.modifiers.new(name="Subdivision", type='SUBSURF')
    sub.levels = 1
    sub.render_levels = 1

    # Edge split at a wide angle — only hard edges on sharp joins
    split = obj.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
    split.split_angle = math.radians(50)

    bpy.ops.object.shade_smooth()


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


def create_body(cfg):
    """Build the complete humanoid mesh from config values.

    The character is built standing upright with feet at Z=0.
    Body uses tapered torso sections for a natural silhouette with wider
    chest, narrower waist, and wider hips.

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

    # Body variation parameters (with backwards-compatible defaults)
    lt = cfg.get("limb_thickness", 1.0)   # multiplier for limb radii
    td = cfg.get("torso_depth", 0.20)     # front-to-back torso size
    skin_tone = cfg.get("skin_tone", None)

    # Vertical layout (bottom-up)
    foot_top = 0.06
    knee_z = foot_top + leg_len * 0.48
    hip_z = foot_top + leg_len
    waist_z = hip_z + torso_len * 0.35
    chest_z = hip_z + torso_len
    neck_z = chest_z + neck_len
    head_z = neck_z + head_r

    # Waist width — narrower than both chest and hips for hourglass taper
    waist_half_w = min(sw, hw) * 0.82

    parts = []

    # --- Head (more segments for smoother sphere) ---
    head = _create_sphere("Head", head_r, (0, 0, head_z), segments=12, rings=9)
    # Slightly flatten front-to-back for a more natural head shape
    head.scale = (1.0, 0.92, 1.02)
    bpy.context.view_layer.objects.active = head
    bpy.ops.object.transform_apply(scale=True)
    parts.append(head)

    # --- Neck (tapered — wider at base, narrower at top) ---
    neck_r_base = 0.058 * lt
    neck_r_top = 0.048 * lt
    neck = _create_tapered_cylinder(
        "Neck", neck_r_top, neck_r_base, neck_len,
        (0, 0, chest_z + neck_len / 2), segments=10,
    )
    parts.append(neck)

    # --- Upper Chest (tapered: shoulder-width at top, narrows toward waist) ---
    upper_torso_h = torso_len * 0.55
    chest_top_half_w = sw
    chest_bot_half_w = (sw + waist_half_w) / 2  # blend toward waist

    upper_chest = _create_box(
        "UpperChest",
        size=(1, 1, 1),
        location=(0, 0, chest_z - upper_torso_h / 2),
    )
    # Use bmesh to taper: scale top verts wider, bottom verts narrower
    bpy.context.view_layer.objects.active = upper_chest
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(upper_chest.data)
    for v in bm.verts:
        if v.co.z > 0:  # top half
            v.co.x *= chest_top_half_w
            v.co.y *= td * 0.58
            v.co.z *= upper_torso_h / 2
        else:  # bottom half
            v.co.x *= chest_bot_half_w
            v.co.y *= td * 0.48
            v.co.z *= upper_torso_h / 2
    bmesh.update_edit_mesh(upper_chest.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    parts.append(upper_chest)

    # --- Lower Torso / Waist (tapered: narrow at waist, widens to hips) ---
    lower_torso_h = torso_len * 0.45

    lower_torso = _create_box(
        "LowerTorso",
        size=(1, 1, 1),
        location=(0, 0, hip_z + lower_torso_h / 2),
    )
    bpy.context.view_layer.objects.active = lower_torso
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(lower_torso.data)
    for v in bm.verts:
        if v.co.z > 0:  # top = waist (narrow)
            v.co.x *= waist_half_w
            v.co.y *= td * 0.45
            v.co.z *= lower_torso_h / 2
        else:  # bottom = hips (wider)
            v.co.x *= hw + 0.03
            v.co.y *= td * 0.48
            v.co.z *= lower_torso_h / 2
    bmesh.update_edit_mesh(lower_torso.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    parts.append(lower_torso)

    # --- Pelvis ---
    pelvis = _create_box(
        "Pelvis",
        size=(hw * 2 + 0.04, td * 0.95, 0.10),
        location=(0, 0, hip_z - 0.01),
    )
    parts.append(pelvis)

    # --- Legs (tapered cylinders — thicker at top, thinner at bottom) ---
    for side, x_sign in [("L", 1), ("R", -1)]:
        x = x_sign * hw

        # Upper leg (tapered: wider at hip, narrower at knee)
        upper_leg_len = abs(knee_z - hip_z)
        upper_r_top = 0.072 * lt
        upper_r_bot = 0.058 * lt
        upper_leg = _create_tapered_cylinder(
            f"UpperLeg.{side}", upper_r_bot, upper_r_top, upper_leg_len,
            (x, 0, (hip_z + knee_z) / 2), segments=10,
        )
        parts.append(upper_leg)

        # Lower leg (tapered: wider at knee, narrower at ankle)
        lower_leg_len = knee_z - foot_top
        lower_r_top = 0.060 * lt
        lower_r_bot = 0.048 * lt
        lower_leg = _create_tapered_cylinder(
            f"LowerLeg.{side}", lower_r_bot, lower_r_top, lower_leg_len,
            (x, 0, (foot_top + knee_z) / 2), segments=10,
        )
        parts.append(lower_leg)

        # Foot
        foot = _create_box(
            f"Foot.{side}",
            size=(foot_w, foot_len, 0.06),
            location=(x, foot_len * 0.15, 0.03),
        )
        parts.append(foot)

    # --- Arms (tapered cylinders hanging down) ---
    for side, x_sign in [("L", 1), ("R", -1)]:
        shoulder_x = x_sign * (sw + 0.04)
        arm_top_z = chest_z - 0.06  # shoulder attachment point

        # Upper arm (tapered)
        upper_arm_len = arm_len * 0.48
        elbow_z = arm_top_z - upper_arm_len
        upper_arm = _create_tapered_cylinder(
            f"UpperArm.{side}", 0.042 * lt, 0.055 * lt, upper_arm_len,
            (shoulder_x, 0, (arm_top_z + elbow_z) / 2), segments=10,
        )
        parts.append(upper_arm)

        # Lower arm (tapered)
        lower_arm_len = arm_len * 0.52
        wrist_z = elbow_z - lower_arm_len
        lower_arm = _create_tapered_cylinder(
            f"LowerArm.{side}", 0.034 * lt, 0.044 * lt, lower_arm_len,
            (shoulder_x, 0, (elbow_z + wrist_z) / 2), segments=10,
        )
        parts.append(lower_arm)

        # Hand
        hand = _create_sphere(
            f"Hand.{side}", hand_size,
            (shoulder_x, 0, wrist_z - hand_size * 0.5), segments=8, rings=5,
        )
        parts.append(hand)

    # --- Face (eyes + nose) ---
    eye_r = head_r * 0.06
    eye_spacing = head_r * 0.32
    eye_y = head_r * 0.85       # front of head
    eye_z = head_z + head_r * 0.1

    # Eye material (dark)
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

    # Nose (small sphere protruding from front of face)
    nose_r = head_r * 0.07
    nose = _create_sphere(
        "Nose", nose_r,
        (0, head_r * 0.90, head_z - head_r * 0.08),
        segments=6, rings=4,
    )
    parts.append(nose)

    # --- Join body parts ---
    body = _join_objects(parts)

    # Set origin to base of feet
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

    _smooth_normals(body)
    _apply_material(body, skin_tone)

    # --- Hair (separate object, will be parented to Head bone) ---
    hair_obj = None
    hair_style = cfg.get("hair_style", "short")
    hair_color = cfg.get("hair_color", None)
    if hair_style and hair_style != "none":
        from . import hair as hair_module
        hair_obj = hair_module.create_hair(head_z, head_r, hair_style, hair_color)

    # --- Clothing (separate objects, parented to appropriate bones) ---
    clothing_objs = []
    clothing_type = cfg.get("clothing", "tshirt,pants")
    if clothing_type and clothing_type != "none":
        from . import clothing as clothing_module
        clothing_color = cfg.get("clothing_color", None)
        clothing_objs = clothing_module.create_clothing(cfg, clothing_type, clothing_color)

    return body, hair_obj, clothing_objs
