"""Demon bartender animations — extends humanoid animation set.

Provides bartender-specific animations as separate Blender Actions on the
armature. Follows the same conventions as generators/humanoid/animation.py:

    - Euler XYZ rotation mode throughout
    - All angles in degrees, converted to radians internally
    - Looping animations use CYCLES F-curve modifiers
    - Each animation is a self-contained Blender Action

Available animations:
    - idle:        Subtle breathing + gentle head sway (48-frame loop)
    - serve_drink: Right arm raises and places a drink on the bar (72 frames)
    - wipe_bar:    Right arm wipes the bar counter in a sweeping motion (60-frame loop)
    - point:       Raise right arm and point forward (48-frame one-shot)
"""

import math


# ---------------------------------------------------------------------------
# Shared helpers (mirrors humanoid/animation.py style)
# ---------------------------------------------------------------------------

def _set_rot(pose_bone, frame, axis, angle_deg):
    """Set a rotation keyframe on a single Euler axis."""
    pose_bone.rotation_mode = 'XYZ'
    idx = {'X': 0, 'Y': 1, 'Z': 2}[axis]
    pose_bone.rotation_euler[idx] = math.radians(angle_deg)
    pose_bone.keyframe_insert(data_path="rotation_euler", index=idx, frame=frame)


def _set_loc(pose_bone, frame, axis, value):
    """Set a location keyframe on a single axis."""
    idx = {'X': 0, 'Y': 1, 'Z': 2}[axis]
    pose_bone.location[idx] = value
    pose_bone.keyframe_insert(data_path="location", index=idx, frame=frame)


def _get_fcurves(armature_obj):
    """Get all F-Curves from the active action, supporting both legacy and 5.0+ API."""
    anim_data = armature_obj.animation_data
    if not anim_data or not anim_data.action:
        return []
    action = anim_data.action
    # Legacy Blender (< 5.0): action.fcurves exists directly
    if hasattr(action, 'fcurves'):
        return action.fcurves
    # Blender 5.0+: F-Curves live in channelbags accessed via action slots
    from bpy_extras import anim_utils
    slot = anim_data.action_slot
    if slot is None:
        return []
    channelbag = anim_utils.action_get_channelbag_for_slot(action, slot)
    if channelbag is None:
        return []
    return channelbag.fcurves


def _make_cyclic(armature_obj):
    """Add CYCLES modifier to all F-curves for seamless looping."""
    fcurves = _get_fcurves(armature_obj)
    for fc in fcurves:
        mod = fc.modifiers.new(type='CYCLES')
        mod.mode_before = 'REPEAT'
        mod.mode_after = 'REPEAT'


def _equalize_keyframes(armature_obj):
    """Ensure all F-Curves share the same set of keyed frames.

    The glTF exporter warns when channel tracks have different keyframe
    counts.  This helper fills gaps by inserting evaluated keyframes so
    every curve has the full frame set.
    """
    fcurves = _get_fcurves(armature_obj)
    if not fcurves:
        return

    all_frames = set()
    for fc in fcurves:
        for kp in fc.keyframe_points:
            all_frames.add(kp.co[0])
    all_frames = sorted(all_frames)

    for fc in fcurves:
        existing = {kp.co[0] for kp in fc.keyframe_points}
        missing = [f for f in all_frames if f not in existing]
        if not missing:
            continue
        for frame in missing:
            value = fc.evaluate(frame)
            fc.keyframe_points.insert(frame, value, options={'FAST'})
        fc.update()


def _new_action(armature_obj, name):
    """Create a new Action, link it to the armature, and return it."""
    import bpy
    action = bpy.data.actions.new(name=name)
    if not armature_obj.animation_data:
        armature_obj.animation_data_create()
    armature_obj.animation_data.action = action
    return action


def _enter_pose(armature_obj):
    """Switch to pose mode on the given armature."""
    import bpy
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='POSE')


def _exit_pose():
    import bpy
    bpy.ops.object.mode_set(mode='OBJECT')


def _reset_pose(armature_obj):
    """Clear all pose transforms so each animation starts from rest."""
    for pb in armature_obj.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)


# ---------------------------------------------------------------------------
# Individual animation builders
# ---------------------------------------------------------------------------

def _create_idle(armature):
    """Idle: subtle breathing + slight head sway. 48-frame loop.

    - Chest: gentle rotation X ±2° synced with breathing
    - Head: slight Z rotation ±3° for a natural look-around sway
    - Both arms hang naturally with a tiny sympathetic drift
    """
    _enter_pose(armature)
    _reset_pose(armature)

    action = _new_action(armature, "DemonBartender_Idle")
    pb = armature.pose.bones
    f = 48   # total loop frames
    q = f // 4   # quarter-cycle = 12

    # Breathing: Chest expands on inhale (frames 0→q), contracts on exhale
    chest = pb.get("Chest")
    spine = pb.get("Spine")
    if chest:
        for frame, angle in [(0, 0.0), (q, -2.0), (q * 2, 0.0), (q * 3, -1.4), (f, 0.0)]:
            _set_rot(chest, frame, 'X', angle)
    if spine:
        for frame, angle in [(0, 0.0), (q, -1.0), (q * 2, 0.0), (q * 3, -0.7), (f, 0.0)]:
            _set_rot(spine, frame, 'X', angle)

    # Head sway: gentle Z rotation left/right
    head = pb.get("Head")
    if head:
        for frame, angle in [
            (0, 0.0), (q, 3.0), (q * 2, 0.0), (q * 3, -3.0), (f, 0.0),
        ]:
            _set_rot(head, frame, 'Z', angle)

    # Arms hang naturally — small sympathetic X drift from breathing
    for side in ["L", "R"]:
        ua = pb.get(f"UpperArm.{side}")
        if ua:
            for frame, angle in [
                (0, 0.0), (q, 0.8), (q * 2, 0.0), (q * 3, 0.6), (f, 0.0),
            ]:
                _set_rot(ua, frame, 'X', angle)

    _make_cyclic(armature)
    _equalize_keyframes(armature)
    _exit_pose()
    return action


def _create_serve_drink(armature):
    """Serve drink: 72-frame animation of placing a drink on the bar.

    Phases:
        0-20:  Right arm raises and extends forward
        20-40: Hand lowers toward bar surface
        40-55: Pause (drink placed — hold position)
        55-72: Arm returns to rest
    """
    _enter_pose(armature)
    _reset_pose(armature)

    action = _new_action(armature, "DemonBartender_ServeDrink")
    pb = armature.pose.bones

    # Bone references
    r_sh = pb.get("Shoulder.R")
    r_ua = pb.get("UpperArm.R")
    r_la = pb.get("LowerArm.R")
    r_hand = pb.get("Hand.R")
    spine = pb.get("Spine")
    chest = pb.get("Chest")

    # ---- Frame 0: neutral rest ----
    for bone in [r_sh, r_ua, r_la, r_hand, spine, chest]:
        if bone:
            for axis in ['X', 'Y', 'Z']:
                _set_rot(bone, 0, axis, 0.0)

    # ---- Frames 0-20: raise arm and extend forward ----
    if r_sh:
        _set_rot(r_sh, 20, 'X', -10.0)   # shoulder rotates slightly forward
    if r_ua:
        _set_rot(r_ua, 20, 'X', -50.0)   # upper arm lifts forward
        _set_rot(r_ua, 20, 'Z', -15.0)   # slight inward rotation
    if r_la:
        _set_rot(r_la, 20, 'X', -20.0)   # forearm extends
    if r_hand:
        _set_rot(r_hand, 20, 'X', 10.0)  # wrist angles down slightly
    if spine:
        _set_rot(spine, 20, 'X', -5.0)   # slight lean forward
    if chest:
        _set_rot(chest, 20, 'X', -3.0)

    # ---- Frames 20-40: lower hand to bar surface ----
    if r_ua:
        _set_rot(r_ua, 40, 'X', -35.0)   # arm lowers a bit
        _set_rot(r_ua, 40, 'Z', -10.0)
    if r_la:
        _set_rot(r_la, 40, 'X', -35.0)   # forearm bends down to reach bar
    if r_hand:
        _set_rot(r_hand, 40, 'X', 20.0)  # wrist curls to set down the drink
    if r_sh:
        _set_rot(r_sh, 40, 'X', -8.0)
    if spine:
        _set_rot(spine, 40, 'X', -8.0)   # lean into the motion
    if chest:
        _set_rot(chest, 40, 'X', -5.0)

    # ---- Frames 40-55: hold (drink placed) ----
    # Repeat the frame 40 values at frame 55 to create a static hold
    if r_ua:
        _set_rot(r_ua, 55, 'X', -35.0)
        _set_rot(r_ua, 55, 'Z', -10.0)
    if r_la:
        _set_rot(r_la, 55, 'X', -35.0)
    if r_hand:
        _set_rot(r_hand, 55, 'X', 20.0)
    if r_sh:
        _set_rot(r_sh, 55, 'X', -8.0)
    if spine:
        _set_rot(spine, 55, 'X', -8.0)
    if chest:
        _set_rot(chest, 55, 'X', -5.0)

    # ---- Frames 55-72: return to rest ----
    for bone in [r_sh, r_ua, r_la, r_hand, spine, chest]:
        if bone:
            for axis in ['X', 'Y', 'Z']:
                _set_rot(bone, 72, axis, 0.0)

    # Serve drink does NOT loop
    _equalize_keyframes(armature)
    _exit_pose()
    return action


def _create_wipe_bar(armature):
    """Wipe bar: 60-frame loop of wiping the bar counter with the right arm.

    The right arm stays extended forward while the shoulder rocks left/right
    and the forearm oscillates in a scrubbing motion.
    """
    _enter_pose(armature)
    _reset_pose(armature)

    action = _new_action(armature, "DemonBartender_WipeBar")
    pb = armature.pose.bones

    r_sh = pb.get("Shoulder.R")
    r_ua = pb.get("UpperArm.R")
    r_la = pb.get("LowerArm.R")
    r_hand = pb.get("Hand.R")
    spine = pb.get("Spine")

    f = 60    # loop length
    half = f // 2   # 30

    # ---- Constant forward extension of the right arm ----
    # Upper arm held forward throughout (X = -45° = arm up/forward)
    # The wiping motion comes from Z rotation oscillation (side-to-side sweep)

    for frame in [0, half, f]:
        if spine:
            _set_rot(spine, frame, 'X', -5.0)   # lean slightly forward

    # Wipe sweep: shoulder + upper arm sweep left at frame 0, right at frame 30
    for frame, sh_z, ua_z, la_z, hand_z in [
        (0,    -20.0, -30.0,  10.0,  5.0),   # arm swept to right (from character POV)
        (half,  20.0,  30.0, -10.0, -5.0),   # arm swept to left
        (f,    -20.0, -30.0,  10.0,  5.0),   # back to start (loop point)
    ]:
        # Arm is extended forward (X) and rocks side-to-side (Z)
        if r_ua:
            _set_rot(r_ua, frame, 'X', -40.0)  # forward raise — constant
            _set_rot(r_ua, frame, 'Z', ua_z)   # sweep
        if r_la:
            _set_rot(r_la, frame, 'X', -15.0)  # slight forearm extension
            _set_rot(r_la, frame, 'Z', la_z)   # counter-sweep for scrubbing
        if r_hand:
            _set_rot(r_hand, frame, 'X', 10.0) # wrist faces down to bar
            _set_rot(r_hand, frame, 'Z', hand_z)
        if r_sh:
            _set_rot(r_sh, frame, 'Z', sh_z)   # shoulder rock

    _make_cyclic(armature)
    _equalize_keyframes(armature)
    _exit_pose()
    return action


def _create_point(armature):
    """Point: 48-frame one-shot — raises right arm and points forward.

    Phases:
        0-15:  Arm raises with shoulder rotation (wind-up)
        15-30: Arm extends fully to point forward
        30-48: Hold point, then return to rest
    """
    _enter_pose(armature)
    _reset_pose(armature)

    action = _new_action(armature, "DemonBartender_Point")
    pb = armature.pose.bones

    r_sh = pb.get("Shoulder.R")
    r_ua = pb.get("UpperArm.R")
    r_la = pb.get("LowerArm.R")
    r_hand = pb.get("Hand.R")
    spine = pb.get("Spine")
    chest = pb.get("Chest")

    # ---- Frame 0: neutral rest ----
    for bone in [r_sh, r_ua, r_la, r_hand, spine, chest]:
        if bone:
            for axis in ['X', 'Y', 'Z']:
                _set_rot(bone, 0, axis, 0.0)

    # ---- Frames 0-15: shoulder and upper arm begin to rise ----
    if r_sh:
        _set_rot(r_sh, 15, 'X', -15.0)    # shoulder comes forward
        _set_rot(r_sh, 15, 'Z', -10.0)
    if r_ua:
        _set_rot(r_ua, 15, 'X', -60.0)    # upper arm halfway up
        _set_rot(r_ua, 15, 'Z', -20.0)    # slight inward
    if r_la:
        _set_rot(r_la, 15, 'X', -30.0)    # forearm partially extended
    if r_hand:
        _set_rot(r_hand, 15, 'X', 5.0)
    if spine:
        _set_rot(spine, 15, 'Z', 10.0)    # torso turns slightly to face pointing direction
    if chest:
        _set_rot(chest, 15, 'Z', 6.0)

    # ---- Frames 15-30: fully extend arm and point ----
    if r_sh:
        _set_rot(r_sh, 30, 'X', -20.0)
        _set_rot(r_sh, 30, 'Z', -15.0)
    if r_ua:
        _set_rot(r_ua, 30, 'X', -85.0)    # arm near horizontal, pointing forward
        _set_rot(r_ua, 30, 'Z', -10.0)
    if r_la:
        _set_rot(r_la, 30, 'X', -5.0)     # forearm nearly straight
    if r_hand:
        _set_rot(r_hand, 30, 'X', -5.0)   # wrist level for pointing
    if spine:
        _set_rot(spine, 30, 'Z', 12.0)
        _set_rot(spine, 30, 'X', -5.0)    # slight lean forward
    if chest:
        _set_rot(chest, 30, 'Z', 8.0)

    # ---- Frames 30-40: hold the point ----
    # Repeat frame 30 values at frame 40 to hold the pose
    if r_sh:
        _set_rot(r_sh, 40, 'X', -20.0)
        _set_rot(r_sh, 40, 'Z', -15.0)
    if r_ua:
        _set_rot(r_ua, 40, 'X', -85.0)
        _set_rot(r_ua, 40, 'Z', -10.0)
    if r_la:
        _set_rot(r_la, 40, 'X', -5.0)
    if r_hand:
        _set_rot(r_hand, 40, 'X', -5.0)
    if spine:
        _set_rot(spine, 40, 'Z', 12.0)
        _set_rot(spine, 40, 'X', -5.0)
    if chest:
        _set_rot(chest, 40, 'Z', 8.0)

    # ---- Frames 40-48: return to rest ----
    for bone in [r_sh, r_ua, r_la, r_hand, spine, chest]:
        if bone:
            for axis in ['X', 'Y', 'Z']:
                _set_rot(bone, 48, axis, 0.0)

    # Point does NOT loop
    _equalize_keyframes(armature)
    _exit_pose()
    return action


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Registry of bartender-specific animations
BARTENDER_ANIMATIONS = {
    "idle":         _create_idle,
    "serve_drink":  _create_serve_drink,
    "wipe_bar":     _create_wipe_bar,
    "point":        _create_point,
}


def create_bartender_animations(armature, anim_names):
    """Create the requested animations on the armature.

    Each animation is stored as a separate Blender Action so the game
    engine can reference them by name. The last created animation remains
    active; callers may reassign armature.animation_data.action as needed.

    Args:
        armature:   Blender armature object (must already be rigged).
        anim_names: Iterable of animation name strings. Valid names are
                    keys of BARTENDER_ANIMATIONS.
    """
    import bpy

    if armature.animation_data is None:
        armature.animation_data_create()

    created = {}
    for name in anim_names:
        builder = BARTENDER_ANIMATIONS.get(name)
        if builder is not None:
            created[name] = builder(armature)

    # Leave idle active by default if it was created
    if "idle" in created and armature.animation_data:
        armature.animation_data.action = created["idle"]

    return created
