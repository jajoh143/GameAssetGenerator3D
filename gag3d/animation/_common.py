"""Shared helpers for keyframing armature actions.

Imported only inside Blender — relies on bpy and mathutils.
"""

from __future__ import annotations

import math
from typing import Iterable

import bpy
from mathutils import Euler, Quaternion, Vector


def new_action(arm_obj: bpy.types.Object, name: str) -> bpy.types.Action:
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()
    action = bpy.data.actions.new(name=name)
    arm_obj.animation_data.action = action
    return action


def push_to_nla(arm_obj: bpy.types.Object, action: bpy.types.Action) -> None:
    """Stash the active action onto an NLA track so it survives glTF export."""
    track = arm_obj.animation_data.nla_tracks.new()
    track.name = action.name
    track.strips.new(action.name, int(action.frame_range[0]), action)
    arm_obj.animation_data.action = None


def set_pose_mode(arm_obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="POSE")


def reset_pose(arm_obj: bpy.types.Object) -> None:
    set_pose_mode(arm_obj)
    for pb in arm_obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)


def keyframe_euler(pb: bpy.types.PoseBone, frame: int, x: float = 0, y: float = 0, z: float = 0) -> None:
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = Euler((math.radians(x), math.radians(y), math.radians(z)), "XYZ")
    pb.keyframe_insert(data_path="rotation_euler", frame=frame)


def keyframe_loc(pb: bpy.types.PoseBone, frame: int, dx: float = 0, dy: float = 0, dz: float = 0) -> None:
    pb.location = Vector((dx, dy, dz))
    pb.keyframe_insert(data_path="location", frame=frame)


def has_bone(arm_obj: bpy.types.Object, name: str) -> bool:
    return name in arm_obj.pose.bones


def safe_bones(arm_obj: bpy.types.Object, names: Iterable[str]) -> list[bpy.types.PoseBone]:
    return [arm_obj.pose.bones[n] for n in names if has_bone(arm_obj, n)]
