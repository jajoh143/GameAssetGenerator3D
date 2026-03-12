"""Low-poly humanoid mesh construction.

Builds the body from simple geometric primitives (cubes, cylinders) that are
joined into a single mesh. Designed to be ~300-500 faces — light enough for
mobile/web games while still reading as a humanoid silhouette.
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


def _create_cylinder(name, radius, depth, location, segments=8):
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


def _create_sphere(name, radius, location, segments=8, rings=6):
    """Create a low-poly sphere (UV sphere with few segments)."""
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


def _smooth_normals(obj):
    """Apply smooth shading and an edge-split modifier for a clean low-poly look."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    mod = obj.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
    mod.split_angle = math.radians(30)


def _apply_material(obj, skin_tone=None):
    """Apply a base material with configurable skin tone."""
    mat = bpy.data.materials.new(name="Humanoid_Base")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        color = skin_tone if skin_tone else (0.65, 0.55, 0.45, 1.0)
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.8
    obj.data.materials.append(mat)


def create_body(cfg):
    """Build the complete humanoid mesh from config values.

    The character is built standing upright with feet at Z=0.

    Args:
        cfg: dict with body proportion values.

    Returns:
        The joined Blender mesh object.
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

    parts = []

    # --- Head ---
    head = _create_sphere("Head", head_r, (0, 0, head_z), segments=10, rings=7)
    parts.append(head)

    # --- Neck ---
    neck_r = 0.05 * lt
    neck = _create_cylinder("Neck", neck_r, neck_len, (0, 0, chest_z + neck_len / 2), segments=8)
    parts.append(neck)

    # --- Torso (upper chest) ---
    chest = _create_box(
        "Chest",
        size=(sw * 2, td * 1.1, torso_len * 0.55),
        location=(0, 0, chest_z - torso_len * 0.55 / 2),
    )
    parts.append(chest)

    # --- Torso (lower / waist) ---
    waist = _create_box(
        "Waist",
        size=(hw * 2 + 0.06, td * 0.9, torso_len * 0.45),
        location=(0, 0, hip_z + torso_len * 0.45 / 2),
    )
    parts.append(waist)

    # --- Pelvis ---
    pelvis = _create_box(
        "Pelvis",
        size=(hw * 2 + 0.04, td * 0.9, 0.12),
        location=(0, 0, hip_z - 0.02),
    )
    parts.append(pelvis)

    # --- Legs ---
    upper_leg_r = 0.065 * lt
    lower_leg_r = 0.055 * lt
    for side, x_sign in [("L", 1), ("R", -1)]:
        x = x_sign * hw

        # Upper leg
        upper_leg_len = knee_z - hip_z
        upper_leg = _create_cylinder(
            f"UpperLeg.{side}", upper_leg_r, abs(upper_leg_len),
            (x, 0, (hip_z + knee_z) / 2), segments=8,
        )
        parts.append(upper_leg)

        # Lower leg
        lower_leg_len = knee_z - foot_top
        lower_leg = _create_cylinder(
            f"LowerLeg.{side}", lower_leg_r, lower_leg_len,
            (x, 0, (foot_top + knee_z) / 2), segments=8,
        )
        parts.append(lower_leg)

        # Foot
        foot = _create_box(
            f"Foot.{side}",
            size=(foot_w, foot_len, 0.06),
            location=(x, foot_len * 0.15, 0.03),
        )
        parts.append(foot)

    # --- Arms (hanging down at sides) ---
    upper_arm_r = 0.05 * lt
    lower_arm_r = 0.04 * lt
    for side, x_sign in [("L", 1), ("R", -1)]:
        shoulder_x = x_sign * (sw + 0.04)
        arm_top_z = chest_z - 0.06  # shoulder attachment point

        # Upper arm (vertical, hanging down)
        upper_arm_len = arm_len * 0.48
        elbow_z = arm_top_z - upper_arm_len
        upper_arm = _create_cylinder(
            f"UpperArm.{side}", upper_arm_r, upper_arm_len,
            (shoulder_x, 0, (arm_top_z + elbow_z) / 2), segments=8,
        )
        parts.append(upper_arm)

        # Lower arm (vertical, continuing down)
        lower_arm_len = arm_len * 0.52
        wrist_z = elbow_z - lower_arm_len
        lower_arm = _create_cylinder(
            f"LowerArm.{side}", lower_arm_r, lower_arm_len,
            (shoulder_x, 0, (elbow_z + wrist_z) / 2), segments=8,
        )
        parts.append(lower_arm)

        # Hand
        hand = _create_sphere(
            f"Hand.{side}", hand_size,
            (shoulder_x, 0, wrist_z - hand_size * 0.5), segments=6, rings=4,
        )
        parts.append(hand)

    # --- Hair ---
    hair_style = cfg.get("hair_style", "none")
    hair_color = cfg.get("hair_color", None)
    if hair_style and hair_style != "none":
        from . import hair as hair_module
        hair_parts = hair_module.create_hair(head_z, head_r, hair_style, hair_color)
        parts.extend(hair_parts)

    # --- Join everything ---
    body = _join_objects(parts)

    # Set origin to base of feet
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

    _smooth_normals(body)
    _apply_material(body, skin_tone)

    return body
