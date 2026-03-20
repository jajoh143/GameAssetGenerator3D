"""Humanoid armature and automatic weight painting.

Creates a standard game-ready skeleton with:
  - Hips (root) -> Spine -> Chest -> Neck -> Head
  - Shoulder -> UpperArm -> LowerArm -> Hand  (L/R)
  - UpperLeg -> LowerLeg -> Foot               (L/R)

Bone names follow the glTF / Mixamo-compatible convention so the rig
can be retargeted to other animation libraries easily.
"""

import bpy
import math
from mathutils import Vector


def _create_bone(edit_bones, name, head, tail, parent=None, connect=True):
    """Add a bone to the armature in edit mode."""
    bone = edit_bones.new(name)
    bone.head = Vector(head)
    bone.tail = Vector(tail)
    if parent:
        bone.parent = parent
        bone.use_connect = connect
    return bone


def _skin_to_armature(armature_obj, obj):
    """Parent an object to the armature with automatic weights.

    This makes the object deform with the skeleton — vertices near arm bones
    follow the arms, vertices near leg bones follow the legs, etc.
    """
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')


def create_rig(cfg, body_obj, hair_obj=None, clothing_objs=None):
    """Build the armature, parent the mesh, and apply automatic weights.

    Args:
        cfg: dict with body proportion values.
        body_obj: the mesh object to skin.
        hair_obj: optional hair mesh to parent to Head bone.
        clothing_objs: optional list of (obj, bone_name) tuples for clothing.

    Returns:
        The armature object.
    """
    h = cfg["height"]
    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    arm_len = cfg["arm_length"]
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]
    neck_len = cfg["neck_length"]
    head_r = cfg["head_size"]

    # Key Z positions (must match mesh.py)
    foot_top = 0.06
    knee_z = foot_top + leg_len * 0.48
    hip_z = foot_top + leg_len
    waist_z = hip_z + torso_len * 0.42
    chest_z = hip_z + torso_len
    neck_z = chest_z + neck_len
    head_z = neck_z + head_r
    head_top = head_z + head_r

    # ------------------------------------------------------------------ #
    # Create armature
    # ------------------------------------------------------------------ #
    bpy.ops.object.armature_add(location=(0, 0, 0))
    armature_obj = bpy.context.active_object
    armature_obj.name = "Humanoid_Armature"
    armature_obj.show_in_front = True

    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature_obj.data.edit_bones

    # Remove the default bone
    for b in edit_bones:
        edit_bones.remove(b)

    # ---- Spine chain ----
    hips = _create_bone(edit_bones, "Hips",
                        (0, 0, hip_z), (0, 0, waist_z), connect=False)

    spine = _create_bone(edit_bones, "Spine",
                         (0, 0, waist_z), (0, 0, (waist_z + chest_z) / 2), hips)

    chest = _create_bone(edit_bones, "Chest",
                         (0, 0, (waist_z + chest_z) / 2), (0, 0, chest_z), spine)

    neck = _create_bone(edit_bones, "Neck",
                        (0, 0, chest_z), (0, 0, neck_z), chest)

    head = _create_bone(edit_bones, "Head",
                        (0, 0, neck_z), (0, 0, head_top), neck)

    # ---- Legs ----
    for side, x_sign in [("L", 1), ("R", -1)]:
        x = x_sign * hw

        upper_leg = _create_bone(edit_bones, f"UpperLeg.{side}",
                                 (x, 0, hip_z), (x, 0, knee_z), hips, connect=False)

        lower_leg = _create_bone(edit_bones, f"LowerLeg.{side}",
                                 (x, 0, knee_z), (x, 0, foot_top), upper_leg)

        foot = _create_bone(edit_bones, f"Foot.{side}",
                            (x, 0, foot_top), (x, -0.18, foot_top), lower_leg)

    # ---- Arms (hanging down at sides) ----
    for side, x_sign in [("L", 1), ("R", -1)]:
        shoulder_x = x_sign * (sw + 0.04)
        arm_z = chest_z - 0.06
        elbow_z = arm_z - arm_len * 0.48
        wrist_z = elbow_z - arm_len * 0.52
        hand_end_z = wrist_z - 0.1

        shoulder = _create_bone(edit_bones, f"Shoulder.{side}",
                                (0, 0, chest_z - 0.02),
                                (shoulder_x, 0, arm_z), chest, connect=False)

        upper_arm = _create_bone(edit_bones, f"UpperArm.{side}",
                                 (shoulder_x, 0, arm_z),
                                 (shoulder_x, 0, elbow_z), shoulder)

        lower_arm = _create_bone(edit_bones, f"LowerArm.{side}",
                                 (shoulder_x, 0, elbow_z),
                                 (shoulder_x, 0, wrist_z), upper_arm)

        hand_bone = _create_bone(edit_bones, f"Hand.{side}",
                                 (shoulder_x, 0, wrist_z),
                                 (shoulder_x, 0, hand_end_z), lower_arm)

    bpy.ops.object.mode_set(mode='OBJECT')

    # ------------------------------------------------------------------ #
    # Parent mesh to armature
    # ------------------------------------------------------------------ #
    # If the body already has vertex groups (from base_mesh.py), use them
    # directly with an Armature modifier instead of automatic weights.
    # This gives deterministic, reliable skinning.
    if body_obj.vertex_groups:
        body_obj.parent = armature_obj
        mod = body_obj.modifiers.new(name="Armature", type='ARMATURE')
        mod.object = armature_obj
    else:
        # Fallback to automatic weights for backward compatibility
        bpy.ops.object.select_all(action='DESELECT')
        body_obj.select_set(True)
        armature_obj.select_set(True)
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')

    # ------------------------------------------------------------------ #
    # Parent hair to Head bone (rigid — moves as one piece with the head)
    # ------------------------------------------------------------------ #
    if hair_obj is not None:
        bpy.ops.object.select_all(action='DESELECT')
        hair_obj.select_set(True)
        armature_obj.select_set(True)
        bpy.context.view_layer.objects.active = armature_obj
        armature_obj.data.bones.active = armature_obj.data.bones["Head"]
        bpy.ops.object.parent_set(type='BONE')

    # ------------------------------------------------------------------ #
    # Skin clothing to armature with automatic weights so sleeves follow
    # arms, pant legs follow legs, etc.
    # ------------------------------------------------------------------ #
    if clothing_objs:
        for obj, bone_name in clothing_objs:
            if bone_name:
                # Rigid parent to a specific bone (e.g. eyes → Head)
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                armature_obj.select_set(True)
                bpy.context.view_layer.objects.active = armature_obj
                armature_obj.data.bones.active = armature_obj.data.bones[bone_name]
                bpy.ops.object.parent_set(type='BONE')
            else:
                # Auto-weight skin to full armature (clothing, accessories)
                _skin_to_armature(armature_obj, obj)

    return armature_obj
