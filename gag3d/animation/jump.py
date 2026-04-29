"""Jump: crouch → launch → apex → land → settle."""

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


def jump(arm_obj: bpy.types.Object) -> None:
    reset_pose(arm_obj)
    set_pose_mode(arm_obj)
    action = new_action(arm_obj, "Jump")

    pose = arm_obj.pose.bones

    # frame, hip_dz, knee_bend, arm_swing
    keyframes = [
        (1,   0.00,   0,   0),
        (8,  -0.10,  60, -30),  # crouch
        (12,  0.20,   0, 110),  # launch
        (20,  0.30,  20,  90),  # apex
        (26,  0.00,  40, -20),  # land
        (34,  0.00,   0,   0),  # settle
    ]

    for f, dz, knee, arm in keyframes:
        if "Hips" in pose:
            keyframe_loc(pose["Hips"], f, dz=dz)
        for n in ("LowerLeg.L", "LowerLeg.R"):
            if n in pose:
                keyframe_euler(pose[n], f, x=knee)
        for n in ("UpperLeg.L", "UpperLeg.R"):
            if n in pose:
                keyframe_euler(pose[n], f, x=-knee * 0.6)
        for n in ("UpperArm.L", "UpperArm.R"):
            if n in pose:
                keyframe_euler(pose[n], f, x=arm)

    push_to_nla(arm_obj, action)
