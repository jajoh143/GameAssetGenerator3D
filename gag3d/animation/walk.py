"""Walk cycle: alternating leg swing + opposing arm swing + hip bob."""

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


def walk(arm_obj: bpy.types.Object) -> None:
    reset_pose(arm_obj)
    set_pose_mode(arm_obj)
    action = new_action(arm_obj, "Walk")

    pose = arm_obj.pose.bones

    # 24-frame cycle: contact-passing-contact-passing
    keyframes = [
        # frame, leg_swing_deg, arm_swing_deg, hip_bob
        (1,  25,  -25, 0.00),
        (7,   0,    0, 0.02),
        (13, -25,  25, 0.00),
        (19,  0,    0, 0.02),
        (24,  25, -25, 0.00),
    ]

    for f, leg, arm, bob in keyframes:
        if "UpperLeg.L" in pose:
            keyframe_euler(pose["UpperLeg.L"], f, x=leg)
        if "UpperLeg.R" in pose:
            keyframe_euler(pose["UpperLeg.R"], f, x=-leg)
        if "LowerLeg.L" in pose:
            keyframe_euler(pose["LowerLeg.L"], f, x=max(0, -leg) * 0.6)
        if "LowerLeg.R" in pose:
            keyframe_euler(pose["LowerLeg.R"], f, x=max(0, leg) * 0.6)
        if "UpperArm.L" in pose:
            keyframe_euler(pose["UpperArm.L"], f, x=arm)
        if "UpperArm.R" in pose:
            keyframe_euler(pose["UpperArm.R"], f, x=-arm)
        if "Hips" in pose:
            keyframe_loc(pose["Hips"], f, dz=bob)

    push_to_nla(arm_obj, action)
