"""Low-poly humanoid mesh construction.

Builds the body from geometric primitives that are joined into a single mesh.
Designed to produce a clean, game-ready mesh with smooth organic forms.

Body shaping uses truncated cones for tapered torso, limbs, and neck.
Smoothing uses per-vertex normals (shade_smooth) with a wide edge-split
angle so organic surfaces are soft while intentional edges stay crisp.
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


def _create_cylinder(name, radius, depth, location, segments=12):
    """Create a cylinder."""
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=segments,
        radius=radius,
        depth=depth,
        location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
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


def _create_cone(name, r_bottom, r_top, depth, location, segments=12):
    """Create a truncated cone (clean tapered primitive, no bmesh needed)."""
    bpy.ops.mesh.primitive_cone_add(
        vertices=segments,
        radius1=r_bottom,
        radius2=r_top,
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
    """Apply smooth shading with a wide edge-split angle.

    Uses shade_smooth for soft per-vertex normals on organic surfaces,
    and edge-split at 50 degrees to keep only intentional hard edges
    (like where limbs meet the torso) crisp.
    """
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    mod = obj.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
    mod.split_angle = math.radians(50)


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
    Uses truncated cones for organic tapered forms on the torso, limbs, and
    neck to match the silhouette of the reference model.

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

    # Vertical layout (bottom-up)
    foot_top = 0.06
    knee_z = foot_top + leg_len * 0.48
    hip_z = foot_top + leg_len
    waist_z = hip_z + torso_len * 0.35
    chest_z = hip_z + torso_len
    neck_z = chest_z + neck_len
    head_z = neck_z + head_r

    # Waist is narrower than both chest and hips for an hourglass taper
    waist_half_w = min(sw, hw) * 0.85

    parts = []

    # --- Head ---
    # Reference model head ratio W:H:D = 0.70:1.00:0.79
    # Make it taller and slightly narrower than a sphere
    head = _create_sphere("Head", head_r, (0, 0, head_z), segments=14, rings=10)
    head.scale = (0.88, 0.92, 1.05)
    bpy.context.view_layer.objects.active = head
    bpy.ops.object.transform_apply(scale=True)
    parts.append(head)

    # --- Neck (tapered: wider at base, narrower at top) ---
    neck_r_base = 0.058 * lt
    neck_r_top = 0.046 * lt
    neck = _create_cone("Neck", neck_r_base, neck_r_top, neck_len,
                        (0, 0, chest_z + neck_len / 2), segments=10)
    parts.append(neck)

    # --- Torso ---
    # Built as 3 stacked truncated cones for a smooth organic taper:
    #   Upper chest: shoulder-width at top, tapers toward waist
    #   Lower chest: continues taper to waist
    #   Lower torso: waist at top, widens to hips at bottom

    upper_chest_h = torso_len * 0.35
    lower_chest_h = torso_len * 0.20
    lower_torso_h = torso_len * 0.45

    # Upper chest (widest at top = shoulder width, narrows down)
    mid_chest_w = (sw + waist_half_w) / 2
    upper_chest = _create_cone(
        "UpperChest",
        r_bottom=mid_chest_w,           # bottom edge (mid-chest)
        r_top=sw,                        # top edge (shoulder width)
        depth=upper_chest_h,
        location=(0, 0, chest_z - upper_chest_h / 2),
        segments=12,
    )
    # Flatten front-to-back relative to width
    upper_chest.scale = (1.0, td / sw * 1.2, 1.0)
    bpy.context.view_layer.objects.active = upper_chest
    bpy.ops.object.transform_apply(scale=True)
    parts.append(upper_chest)

    # Lower chest (continues narrowing to waist)
    lower_chest = _create_cone(
        "LowerChest",
        r_bottom=waist_half_w + 0.01,   # near-waist width
        r_top=mid_chest_w,               # mid-chest width
        depth=lower_chest_h,
        location=(0, 0, chest_z - upper_chest_h - lower_chest_h / 2),
        segments=12,
    )
    lower_chest.scale = (1.0, td / mid_chest_w * 1.1, 1.0)
    bpy.context.view_layer.objects.active = lower_chest
    bpy.ops.object.transform_apply(scale=True)
    parts.append(lower_chest)

    # Lower torso (waist → hips, widens toward bottom)
    lower_torso = _create_cone(
        "LowerTorso",
        r_bottom=hw + 0.02,             # hip width at bottom
        r_top=waist_half_w,              # waist width at top
        depth=lower_torso_h,
        location=(0, 0, hip_z + lower_torso_h / 2),
        segments=12,
    )
    lower_torso.scale = (1.0, td / waist_half_w * 1.05, 1.0)
    bpy.context.view_layer.objects.active = lower_torso
    bpy.ops.object.transform_apply(scale=True)
    parts.append(lower_torso)

    # --- Pelvis ---
    pelvis = _create_cone(
        "Pelvis",
        r_bottom=hw - 0.01,
        r_top=hw + 0.02,
        depth=0.10,
        location=(0, 0, hip_z - 0.01),
        segments=12,
    )
    pelvis.scale = (1.0, td / (hw + 0.02) * 1.0, 1.0)
    bpy.context.view_layer.objects.active = pelvis
    bpy.ops.object.transform_apply(scale=True)
    parts.append(pelvis)

    # --- Legs (tapered cylinders) ---
    for side, x_sign in [("L", 1), ("R", -1)]:
        x = x_sign * hw

        # Upper leg (thicker at hip, thinner at knee)
        upper_leg_len = abs(knee_z - hip_z)
        upper_leg = _create_cone(
            f"UpperLeg.{side}",
            r_bottom=0.058 * lt,   # knee end (thinner)
            r_top=0.072 * lt,      # hip end (thicker)
            depth=upper_leg_len,
            location=(x, 0, (hip_z + knee_z) / 2),
            segments=10,
        )
        parts.append(upper_leg)

        # Lower leg (thicker at knee, thinner at ankle)
        lower_leg_len = knee_z - foot_top
        lower_leg = _create_cone(
            f"LowerLeg.{side}",
            r_bottom=0.048 * lt,   # ankle end (thinner)
            r_top=0.060 * lt,      # knee end (thicker)
            depth=lower_leg_len,
            location=(x, 0, (foot_top + knee_z) / 2),
            segments=10,
        )
        parts.append(lower_leg)

        # Foot
        foot = _create_box(
            f"Foot.{side}",
            size=(foot_w, foot_len, 0.06),
            location=(x, foot_len * 0.15, 0.03),
        )
        parts.append(foot)

    # --- Arms (tapered, hanging down at sides) ---
    for side, x_sign in [("L", 1), ("R", -1)]:
        shoulder_x = x_sign * (sw + 0.04)
        arm_top_z = chest_z - 0.06

        # Upper arm
        upper_arm_len = arm_len * 0.48
        elbow_z = arm_top_z - upper_arm_len
        upper_arm = _create_cone(
            f"UpperArm.{side}",
            r_bottom=0.042 * lt,   # elbow (thinner)
            r_top=0.055 * lt,      # shoulder (thicker)
            depth=upper_arm_len,
            location=(shoulder_x, 0, (arm_top_z + elbow_z) / 2),
            segments=10,
        )
        parts.append(upper_arm)

        # Lower arm
        lower_arm_len = arm_len * 0.52
        wrist_z = elbow_z - lower_arm_len
        lower_arm = _create_cone(
            f"LowerArm.{side}",
            r_bottom=0.034 * lt,   # wrist (thinner)
            r_top=0.044 * lt,      # elbow (thicker)
            depth=lower_arm_len,
            location=(shoulder_x, 0, (elbow_z + wrist_z) / 2),
            segments=10,
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

    # --- Join body parts ---
    body = _join_objects(parts)

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

    # --- Clothing (separate objects, skinned to armature) ---
    clothing_objs = []
    clothing_type = cfg.get("clothing", "tshirt,pants")
    if clothing_type and clothing_type != "none":
        from . import clothing as clothing_module
        clothing_color = cfg.get("clothing_color", None)
        clothing_objs = clothing_module.create_clothing(cfg, clothing_type, clothing_color)

    return body, hair_obj, clothing_objs
