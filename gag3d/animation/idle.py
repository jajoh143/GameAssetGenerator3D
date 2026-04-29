"""Subtle idle: chest breath + tiny head sway."""

from __future__ import annotations

import bpy

from ._common import (
    keyframe_euler,
    keyframe_loc,
    new_action,
    push_to_nla,
    reset_pose,
    set_pose_mode,
)


def idle(arm_obj: bpy.types.Object) -> None:
    reset_pose(arm_obj)
    set_pose_mode(arm_obj)
    action = new_action(arm_obj, "Idle")

    spine2 = arm_obj.pose.bones.get("Spine2")
    head = arm_obj.pose.bones.get("Head")
    hips = arm_obj.pose.bones.get("Hips")

    frames = [(1, 0.0), (30, 1.0), (60, 0.0)]
    for f, t in frames:
        if spine2:
            keyframe_euler(spine2, f, x=-1.5 * t)
        if head:
            keyframe_euler(head, f, z=2.0 * t)
        if hips:
            keyframe_loc(hips, f, dz=0.005 * t)

    action.frame_range  # touch to ensure populated
    push_to_nla(arm_obj, action)
