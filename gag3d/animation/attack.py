"""Right-handed overhead swing attack."""

from __future__ import annotations

import bpy

from ._common import (
    keyframe_euler,
    new_action,
    push_to_nla,
    reset_pose,
    set_pose_mode,
)


def attack(arm_obj: bpy.types.Object) -> None:
    reset_pose(arm_obj)
    set_pose_mode(arm_obj)
    action = new_action(arm_obj, "Attack")

    pose = arm_obj.pose.bones

    # frame, upper_arm_x, lower_arm_x, spine_twist_z
    keyframes = [
        (1,    0,    0,    0),
        (5,  -90,  -60,   20),   # wind-up
        (12,  60, -100,  -25),   # swing through
        (18,  20,  -40,   -5),   # recover
        (24,   0,    0,    0),
    ]

    for f, upper, lower, twist in keyframes:
        if "UpperArm.R" in pose:
            keyframe_euler(pose["UpperArm.R"], f, x=upper)
        if "LowerArm.R" in pose:
            keyframe_euler(pose["LowerArm.R"], f, x=lower)
        if "Spine2" in pose:
            keyframe_euler(pose["Spine2"], f, z=twist)

    push_to_nla(arm_obj, action)
