"""Basic humanoid animations.

Creates a looping walk cycle using keyframed bone rotations. The cycle
is 24 frames at 24 fps (1 second loop) and uses sinusoidal easing for
natural-looking motion.

Bone rotation conventions:
  - Positive X rotation = forward swing (for legs) / backward lean
  - All rotations in radians
"""

import bpy
import math


# Walk cycle parameters — angles in degrees, converted to radians at use.
WALK_PARAMS = {
    "cycle_frames": 24,
    "fps": 24,
    # Peak angles (degrees)
    "upper_leg_swing": 30,
    "lower_leg_bend": 40,
    "foot_rock": 15,
    "upper_arm_swing": 20,
    "lower_arm_bend": 25,
    "spine_twist": 3,
    "hip_bob": 0.02,        # vertical translation on hips
    "hip_sway": 2,          # side-to-side rotation (degrees)
}


def _set_rotation_keyframe(pose_bone, frame, axis, angle_deg):
    """Set a rotation keyframe on a single axis (Euler XYZ)."""
    pose_bone.rotation_mode = 'XYZ'
    idx = {'X': 0, 'Y': 1, 'Z': 2}[axis]
    pose_bone.rotation_euler[idx] = math.radians(angle_deg)
    pose_bone.keyframe_insert(data_path="rotation_euler", index=idx, frame=frame)


def _set_location_keyframe(pose_bone, frame, axis, value):
    """Set a location keyframe on a single axis."""
    idx = {'X': 0, 'Y': 1, 'Z': 2}[axis]
    pose_bone.location[idx] = value
    pose_bone.keyframe_insert(data_path="location", index=idx, frame=frame)


def _make_cyclic(action):
    """Add cyclic F-curve modifiers so the animation loops seamlessly."""
    for fcurve in action.fcurves:
        mod = fcurve.modifiers.new(type='CYCLES')
        mod.mode_before = 'REPEAT'
        mod.mode_after = 'REPEAT'


def create_walk_cycle(armature_obj, cfg):
    """Create a walk-cycle action on the armature.

    The walk is a standard bipedal gait: opposing arm/leg swing,
    subtle hip bob and spine counter-rotation.

    Args:
        armature_obj: the armature to animate.
        cfg: body config dict (used for proportional adjustments).

    Returns:
        The created Action.
    """
    wp = WALK_PARAMS
    frames = wp["cycle_frames"]
    half = frames // 2

    # Ensure we're in pose mode
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='POSE')

    pose_bones = armature_obj.pose.bones

    # Create a new action
    action = bpy.data.actions.new(name="Walk")
    armature_obj.animation_data_create()
    armature_obj.animation_data.action = action

    # Key poses at: 0 (contact L), half (contact R), frames (loop = 0)
    # We'll key 5 positions: 0, quarter, half, 3-quarter, end
    key_frames = [0, half // 2, half, half + half // 2, frames]

    # Swing angles at each key frame for the LEFT side
    # Format: (frame, upper_leg_angle, lower_leg_angle, foot_angle)
    # Positive = forward swing for legs
    uls = wp["upper_leg_swing"]
    llb = wp["lower_leg_bend"]
    fr = wp["foot_rock"]
    uas = wp["upper_arm_swing"]
    lab = wp["lower_arm_bend"]

    # Left leg swing pattern: forward, passing, back, passing, forward
    left_leg = [
        (0,          uls,   -llb * 0.3,  -fr),       # L forward contact
        (half // 2,  0,     -llb,         0),         # L passing
        (half,      -uls,   -llb * 0.1,   fr),       # L back contact
        (half + half // 2, 0, -llb * 0.6, 0),        # L passing (swing fwd)
        (frames,     uls,   -llb * 0.3,  -fr),       # loop
    ]

    # Right leg is opposite phase
    right_leg = [
        (0,         -uls,   -llb * 0.1,   fr),
        (half // 2,  0,     -llb * 0.6,   0),
        (half,       uls,   -llb * 0.3,  -fr),
        (half + half // 2, 0, -llb,       0),
        (frames,    -uls,   -llb * 0.1,   fr),
    ]

    # Arms swing opposite to their respective legs
    left_arm = [
        (0,         -uas,   -lab * 0.2),
        (half // 2,  0,     -lab * 0.1),
        (half,       uas,   -lab),
        (half + half // 2, 0, -lab * 0.1),
        (frames,    -uas,   -lab * 0.2),
    ]

    right_arm = [
        (0,          uas,   -lab),
        (half // 2,  0,     -lab * 0.1),
        (half,      -uas,   -lab * 0.2),
        (half + half // 2, 0, -lab * 0.1),
        (frames,     uas,   -lab),
    ]

    # Apply leg keyframes
    for data, side in [(left_leg, "L"), (right_leg, "R")]:
        ul = pose_bones.get(f"UpperLeg.{side}")
        ll = pose_bones.get(f"LowerLeg.{side}")
        ft = pose_bones.get(f"Foot.{side}")
        if not ul:
            continue
        for frame, ul_angle, ll_angle, ft_angle in data:
            _set_rotation_keyframe(ul, frame, 'X', ul_angle)
            _set_rotation_keyframe(ll, frame, 'X', ll_angle)
            _set_rotation_keyframe(ft, frame, 'X', ft_angle)

    # Apply arm keyframes
    for data, side in [(left_arm, "L"), (right_arm, "R")]:
        ua = pose_bones.get(f"UpperArm.{side}")
        la = pose_bones.get(f"LowerArm.{side}")
        if not ua:
            continue
        for frame, ua_angle, la_angle in data:
            _set_rotation_keyframe(ua, frame, 'X', ua_angle)  # forward/back
            _set_rotation_keyframe(la, frame, 'X', la_angle)

    # Hip bob (vertical bounce — two peaks per cycle)
    hips = pose_bones.get("Hips")
    if hips:
        bob = wp["hip_bob"]
        sway = wp["hip_sway"]
        hip_keys = [
            (0,          0,    -sway),
            (half // 2,  bob,   0),
            (half,       0,     sway),
            (half + half // 2, bob, 0),
            (frames,     0,    -sway),
        ]
        for frame, bob_val, sway_val in hip_keys:
            _set_location_keyframe(hips, frame, 'Z', bob_val)
            _set_rotation_keyframe(hips, frame, 'Z', sway_val)

    # Subtle spine counter-rotation
    spine_bone = pose_bones.get("Spine")
    if spine_bone:
        st = wp["spine_twist"]
        spine_keys = [
            (0,          st),
            (half // 2,  0),
            (half,      -st),
            (half + half // 2, 0),
            (frames,     st),
        ]
        for frame, twist in spine_keys:
            _set_rotation_keyframe(spine_bone, frame, 'Z', twist)

    # Make all curves cyclic
    _make_cyclic(action)

    # Set timeline
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = frames
    bpy.context.scene.render.fps = wp["fps"]

    bpy.ops.object.mode_set(mode='OBJECT')

    return action
