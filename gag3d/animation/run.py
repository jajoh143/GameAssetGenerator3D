"""Run cycle — same shape as walk but bigger swing, shorter cycle, more bob."""

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


def run(arm_obj: bpy.types.Object) -> None:
    reset_pose(arm_obj)
    set_pose_mode(arm_obj)
    action = new_action(arm_obj, "Run")

    pose = arm_obj.pose.bones

    keyframes = [
        (1,  45, -55, -0.02),
        (5,   0,   0,  0.05),
        (9, -45,  55, -0.02),
        (13,  0,   0,  0.05),
        (16, 45, -55, -0.02),
    ]

    for f, leg, arm, bob in keyframes:
        if "UpperLeg.L" in pose:
            keyframe_euler(pose["UpperLeg.L"], f, x=leg)
        if "UpperLeg.R" in pose:
            keyframe_euler(pose["UpperLeg.R"], f, x=-leg)
        if "LowerLeg.L" in pose:
            keyframe_euler(pose["LowerLeg.L"], f, x=abs(leg) * 0.8)
        if "LowerLeg.R" in pose:
            keyframe_euler(pose["LowerLeg.R"], f, x=abs(leg) * 0.8)
        if "UpperArm.L" in pose:
            keyframe_euler(pose["UpperArm.L"], f, x=arm)
        if "UpperArm.R" in pose:
            keyframe_euler(pose["UpperArm.R"], f, x=-arm)
        if "LowerArm.L" in pose:
            keyframe_euler(pose["LowerArm.L"], f, x=-60)
        if "LowerArm.R" in pose:
            keyframe_euler(pose["LowerArm.R"], f, x=-60)
        if "Hips" in pose:
            keyframe_loc(pose["Hips"], f, dz=bob)

    push_to_nla(arm_obj, action)
