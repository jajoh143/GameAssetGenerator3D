"""Humanoid animation library.

Provides a set of game-ready animations as separate Blender Actions on the
armature. Each animation is self-contained and loops where appropriate.

Available animations:
    - Idle:   subtle breathing / weight-shift loop (48 frames)
    - Walk:   standard bipedal walk cycle (24 frames)
    - Run:    faster gait with wider stride and arm pump (16 frames)
    - Jump:   non-looping crouch → launch → airborne → land (32 frames)
    - Attack: right-hand melee swing (20 frames)

Bone rotation conventions:
    - Euler XYZ rotation mode throughout
    - Positive X rotation = forward swing (legs) / backward lean (spine)
    - All angles specified in degrees, converted to radians internally
"""

import math


# ───────────────────────────────────────────────────────────────────────────
# Shared helpers
# ───────────────────────────────────────────────────────────────────────────

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


def _make_cyclic(action):
    """Add cyclic F-curve modifiers for seamless looping."""
    # Blender 4.x layered actions may not expose fcurves directly;
    # fall back to iterating via action.layers/strips if needed.
    fcurves = getattr(action, 'fcurves', None)
    if fcurves is None or len(fcurves) == 0:
        # Try the Blender 4.x layered-action API
        for layer in getattr(action, 'layers', []):
            for strip in getattr(layer, 'strips', []):
                for fcurve in getattr(strip, 'channels', []):
                    mod = fcurve.modifiers.new(type='CYCLES')
                    mod.mode_before = 'REPEAT'
                    mod.mode_after = 'REPEAT'
        return
    for fcurve in fcurves:
        mod = fcurve.modifiers.new(type='CYCLES')
        mod.mode_before = 'REPEAT'
        mod.mode_after = 'REPEAT'


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


# ───────────────────────────────────────────────────────────────────────────
# Animation parameters
# ───────────────────────────────────────────────────────────────────────────

ANIM_PARAMS = {
    "idle": {
        "cycle_frames": 48,
        "fps": 24,
        "breath_chest": 2,       # chest expansion rotation (degrees)
        "breath_spine": 1.5,
        "head_look": 3,          # subtle head turn
        "hip_shift": 1.5,        # weight shift side-to-side
        "arm_drift": 3,          # arms hang, slight sway
    },
    "walk": {
        "cycle_frames": 24,
        "fps": 24,
        "upper_leg_swing": 30,
        "lower_leg_bend": 40,
        "foot_rock": 15,
        "upper_arm_swing": 20,
        "lower_arm_bend": 25,
        "spine_twist": 3,
        "hip_bob": 0.02,
        "hip_sway": 2,
    },
    "run": {
        "cycle_frames": 16,
        "fps": 24,
        "upper_leg_swing": 50,
        "lower_leg_bend": 70,
        "foot_rock": 20,
        "upper_arm_swing": 40,
        "lower_arm_bend": 55,
        "spine_lean": 8,         # forward lean
        "spine_twist": 5,
        "hip_bob": 0.04,
        "hip_sway": 3,
    },
    "jump": {
        "total_frames": 32,
        "fps": 24,
        # Phase breakdown (frame ranges)
        "crouch_end": 8,
        "launch_end": 12,
        "apex": 20,
        "land_end": 28,
        # Angles
        "crouch_legs": 60,
        "crouch_spine": -15,
        "launch_legs": -20,
        "launch_spine": 10,
        "tuck_legs": 30,
        "arm_raise": -40,
        "land_absorb": 45,
        "hip_height": 0.15,
    },
    "attack": {
        "total_frames": 20,
        "fps": 24,
        # Phase breakdown
        "windup_end": 6,
        "strike_end": 10,
        "follow_end": 14,
        # Angles
        "windup_arm": -80,
        "windup_forearm": -90,
        "strike_arm": 60,
        "strike_forearm": -20,
        "torso_twist": 25,
        "lunge_leg": 20,
        "rear_leg": -15,
    },
}


# ───────────────────────────────────────────────────────────────────────────
# Individual animation builders
# ───────────────────────────────────────────────────────────────────────────

def create_idle(armature_obj, cfg):
    """Idle: subtle breathing, weight-shift, and head turn. Loops."""
    _enter_pose(armature_obj)
    _reset_pose(armature_obj)

    p = ANIM_PARAMS["idle"]
    f = p["cycle_frames"]
    q = f // 4
    pb = armature_obj.pose.bones
    action = _new_action(armature_obj, "Idle")

    # Breathing: chest + spine expand/contract over full cycle
    chest = pb.get("Chest")
    spine = pb.get("Spine")
    if chest and spine:
        for frame, chest_angle, spine_angle in [
            (0,     0,                    0),
            (q,     p["breath_chest"],    p["breath_spine"]),
            (q * 2, 0,                    0),
            (q * 3, p["breath_chest"] * 0.7, p["breath_spine"] * 0.7),
            (f,     0,                    0),
        ]:
            _set_rot(chest, frame, 'X', -chest_angle)  # lean back slightly = breathing in
            _set_rot(spine, frame, 'X', -spine_angle)

    # Subtle head look left/right
    head = pb.get("Head")
    if head:
        for frame, angle in [
            (0, 0), (q, p["head_look"]), (q * 2, 0),
            (q * 3, -p["head_look"]), (f, 0),
        ]:
            _set_rot(head, frame, 'Z', angle)

    # Weight shift — hips sway
    hips = pb.get("Hips")
    if hips:
        hs = p["hip_shift"]
        for frame, sway in [
            (0, 0), (q, hs), (q * 2, 0), (q * 3, -hs), (f, 0),
        ]:
            _set_rot(hips, frame, 'Z', sway)

    # Arms hang with gentle sway (opposite to hip shift)
    for side_mult, side in [(1, "L"), (-1, "R")]:
        ua = pb.get(f"UpperArm.{side}")
        if ua:
            ad = p["arm_drift"]
            for frame, angle in [
                (0, 0), (q, -ad * side_mult), (q * 2, 0),
                (q * 3, ad * side_mult), (f, 0),
            ]:
                _set_rot(ua, frame, 'Z', angle)

    _make_cyclic(action)
    _exit_pose()
    return action


def create_walk_cycle(armature_obj, cfg):
    """Walk: standard bipedal gait. Loops."""
    _enter_pose(armature_obj)
    _reset_pose(armature_obj)

    wp = ANIM_PARAMS["walk"]
    frames = wp["cycle_frames"]
    half = frames // 2
    pb = armature_obj.pose.bones

    action = _new_action(armature_obj, "Walk")

    uls = wp["upper_leg_swing"]
    llb = wp["lower_leg_bend"]
    fr = wp["foot_rock"]
    uas = wp["upper_arm_swing"]
    lab = wp["lower_arm_bend"]

    # Leg swing patterns (L / R are half-cycle offset)
    left_leg = [
        (0,          uls,   -llb * 0.3,  -fr),
        (half // 2,  0,     -llb,         0),
        (half,      -uls,   -llb * 0.1,   fr),
        (half + half // 2, 0, -llb * 0.6, 0),
        (frames,     uls,   -llb * 0.3,  -fr),
    ]
    right_leg = [
        (0,         -uls,   -llb * 0.1,   fr),
        (half // 2,  0,     -llb * 0.6,   0),
        (half,       uls,   -llb * 0.3,  -fr),
        (half + half // 2, 0, -llb,       0),
        (frames,    -uls,   -llb * 0.1,   fr),
    ]

    # Arms counter-swing
    left_arm = [
        (0, -uas, -lab * 0.2), (half // 2, 0, -lab * 0.1),
        (half, uas, -lab), (half + half // 2, 0, -lab * 0.1),
        (frames, -uas, -lab * 0.2),
    ]
    right_arm = [
        (0, uas, -lab), (half // 2, 0, -lab * 0.1),
        (half, -uas, -lab * 0.2), (half + half // 2, 0, -lab * 0.1),
        (frames, uas, -lab),
    ]

    for data, side in [(left_leg, "L"), (right_leg, "R")]:
        ul = pb.get(f"UpperLeg.{side}")
        ll = pb.get(f"LowerLeg.{side}")
        ft = pb.get(f"Foot.{side}")
        if not ul:
            continue
        for frame, ul_a, ll_a, ft_a in data:
            _set_rot(ul, frame, 'X', ul_a)
            _set_rot(ll, frame, 'X', ll_a)
            _set_rot(ft, frame, 'X', ft_a)

    for data, side in [(left_arm, "L"), (right_arm, "R")]:
        ua = pb.get(f"UpperArm.{side}")
        la = pb.get(f"LowerArm.{side}")
        if not ua:
            continue
        for frame, ua_a, la_a in data:
            _set_rot(ua, frame, 'X', ua_a)
            _set_rot(la, frame, 'X', la_a)

    hips = pb.get("Hips")
    if hips:
        bob = wp["hip_bob"]
        sway = wp["hip_sway"]
        for frame, b, s in [
            (0, 0, -sway), (half // 2, bob, 0), (half, 0, sway),
            (half + half // 2, bob, 0), (frames, 0, -sway),
        ]:
            _set_loc(hips, frame, 'Z', b)
            _set_rot(hips, frame, 'Z', s)

    spine_bone = pb.get("Spine")
    if spine_bone:
        st = wp["spine_twist"]
        for frame, twist in [
            (0, st), (half // 2, 0), (half, -st),
            (half + half // 2, 0), (frames, st),
        ]:
            _set_rot(spine_bone, frame, 'Z', twist)

    _make_cyclic(action)
    _exit_pose()
    return action


def create_run_cycle(armature_obj, cfg):
    """Run: faster gait with wider stride, more arm pump, forward lean. Loops."""
    _enter_pose(armature_obj)
    _reset_pose(armature_obj)

    rp = ANIM_PARAMS["run"]
    frames = rp["cycle_frames"]
    half = frames // 2
    pb = armature_obj.pose.bones

    action = _new_action(armature_obj, "Run")

    uls = rp["upper_leg_swing"]
    llb = rp["lower_leg_bend"]
    fr = rp["foot_rock"]
    uas = rp["upper_arm_swing"]
    lab = rp["lower_arm_bend"]

    # Legs — same pattern as walk but amplified with higher knee lift
    left_leg = [
        (0,          uls,    -llb * 0.2,  -fr),
        (half // 2,  uls * 0.3, -llb,     0),
        (half,      -uls,    -llb * 0.1,   fr),
        (half + half // 2, 0, -llb * 0.5, 0),
        (frames,     uls,    -llb * 0.2,  -fr),
    ]
    right_leg = [
        (0,         -uls,    -llb * 0.1,   fr),
        (half // 2,  0,      -llb * 0.5,   0),
        (half,       uls,    -llb * 0.2,  -fr),
        (half + half // 2, uls * 0.3, -llb, 0),
        (frames,    -uls,    -llb * 0.1,   fr),
    ]

    for data, side in [(left_leg, "L"), (right_leg, "R")]:
        ul = pb.get(f"UpperLeg.{side}")
        ll = pb.get(f"LowerLeg.{side}")
        ft = pb.get(f"Foot.{side}")
        if not ul:
            continue
        for frame, ul_a, ll_a, ft_a in data:
            _set_rot(ul, frame, 'X', ul_a)
            _set_rot(ll, frame, 'X', ll_a)
            _set_rot(ft, frame, 'X', ft_a)

    # Arms — pumping hard, elbows bent
    left_arm = [
        (0, -uas, -lab * 0.8), (half // 2, 0, -lab * 0.5),
        (half, uas, -lab), (half + half // 2, 0, -lab * 0.5),
        (frames, -uas, -lab * 0.8),
    ]
    right_arm = [
        (0, uas, -lab), (half // 2, 0, -lab * 0.5),
        (half, -uas, -lab * 0.8), (half + half // 2, 0, -lab * 0.5),
        (frames, uas, -lab),
    ]

    for data, side in [(left_arm, "L"), (right_arm, "R")]:
        ua = pb.get(f"UpperArm.{side}")
        la = pb.get(f"LowerArm.{side}")
        if not ua:
            continue
        for frame, ua_a, la_a in data:
            _set_rot(ua, frame, 'X', ua_a)
            _set_rot(la, frame, 'X', la_a)

    # Forward lean on spine + chest
    spine = pb.get("Spine")
    chest = pb.get("Chest")
    if spine:
        lean = rp["spine_lean"]
        twist = rp["spine_twist"]
        for frame, tw in [
            (0, twist), (half // 2, 0), (half, -twist),
            (half + half // 2, 0), (frames, twist),
        ]:
            _set_rot(spine, frame, 'X', lean)   # constant forward lean
            _set_rot(spine, frame, 'Z', tw)
    if chest:
        for frame in [0, half // 2, half, half + half // 2, frames]:
            _set_rot(chest, frame, 'X', rp["spine_lean"] * 0.5)

    # Hip bob (more bounce than walk)
    hips = pb.get("Hips")
    if hips:
        bob = rp["hip_bob"]
        sway = rp["hip_sway"]
        for frame, b, s in [
            (0, 0, -sway), (half // 2, bob, 0), (half, 0, sway),
            (half + half // 2, bob, 0), (frames, 0, -sway),
        ]:
            _set_loc(hips, frame, 'Z', b)
            _set_rot(hips, frame, 'Z', s)

    _make_cyclic(action)
    _exit_pose()
    return action


def create_jump(armature_obj, cfg):
    """Jump: non-looping sequence — anticipation, launch, airborne, land.

    Phases:
        0 → crouch_end:   Anticipation squat
        crouch_end → launch_end: Explosive extension
        launch_end → apex:  Airborne tuck
        apex → land_end:   Landing absorption
        land_end → total:  Return to stand
    """
    _enter_pose(armature_obj)
    _reset_pose(armature_obj)

    jp = ANIM_PARAMS["jump"]
    f_total = jp["total_frames"]
    pb = armature_obj.pose.bones

    action = _new_action(armature_obj, "Jump")

    f_crouch = jp["crouch_end"]
    f_launch = jp["launch_end"]
    f_apex = jp["apex"]
    f_land = jp["land_end"]

    # ---- Frame 0: standing neutral ----
    for bone_name in ["Spine", "Chest", "Hips"]:
        b = pb.get(bone_name)
        if b:
            _set_rot(b, 0, 'X', 0)

    for side in ["L", "R"]:
        for bone_name in [f"UpperLeg.{side}", f"LowerLeg.{side}", f"Foot.{side}",
                          f"UpperArm.{side}", f"LowerArm.{side}"]:
            b = pb.get(bone_name)
            if b:
                _set_rot(b, 0, 'X', 0)

    hips = pb.get("Hips")
    if hips:
        _set_loc(hips, 0, 'Z', 0)

    # ---- Crouch (anticipation) ----
    cl = jp["crouch_legs"]
    cs = jp["crouch_spine"]
    for side in ["L", "R"]:
        ul = pb.get(f"UpperLeg.{side}")
        ll = pb.get(f"LowerLeg.{side}")
        ft = pb.get(f"Foot.{side}")
        if ul:
            _set_rot(ul, f_crouch, 'X', cl)
            _set_rot(ll, f_crouch, 'X', -cl * 1.2)
        if ft:
            _set_rot(ft, f_crouch, 'X', cl * 0.3)

    spine = pb.get("Spine")
    chest = pb.get("Chest")
    if spine:
        _set_rot(spine, f_crouch, 'X', cs)
    if chest:
        _set_rot(chest, f_crouch, 'X', cs * 0.6)
    if hips:
        _set_loc(hips, f_crouch, 'Z', -0.08)

    # Arms pull back for preparation
    for side in ["L", "R"]:
        ua = pb.get(f"UpperArm.{side}")
        la = pb.get(f"LowerArm.{side}")
        if ua:
            _set_rot(ua, f_crouch, 'X', 25)
            _set_rot(la, f_crouch, 'X', -40)

    # ---- Launch (explosive extension) ----
    ll_launch = jp["launch_legs"]
    ls = jp["launch_spine"]
    for side in ["L", "R"]:
        ul = pb.get(f"UpperLeg.{side}")
        ll = pb.get(f"LowerLeg.{side}")
        ft = pb.get(f"Foot.{side}")
        if ul:
            _set_rot(ul, f_launch, 'X', ll_launch)
            _set_rot(ll, f_launch, 'X', -5)
        if ft:
            _set_rot(ft, f_launch, 'X', -30)  # toe push off

    if spine:
        _set_rot(spine, f_launch, 'X', ls)
    if chest:
        _set_rot(chest, f_launch, 'X', ls * 0.5)
    if hips:
        _set_loc(hips, f_launch, 'Z', jp["hip_height"])

    # Arms swing up
    ar = jp["arm_raise"]
    for side in ["L", "R"]:
        ua = pb.get(f"UpperArm.{side}")
        la = pb.get(f"LowerArm.{side}")
        if ua:
            _set_rot(ua, f_launch, 'X', ar)
            _set_rot(la, f_launch, 'X', -20)

    # ---- Apex (airborne tuck) ----
    tl = jp["tuck_legs"]
    for side in ["L", "R"]:
        ul = pb.get(f"UpperLeg.{side}")
        ll = pb.get(f"LowerLeg.{side}")
        if ul:
            _set_rot(ul, f_apex, 'X', tl)
            _set_rot(ll, f_apex, 'X', -tl * 1.3)

    if spine:
        _set_rot(spine, f_apex, 'X', 5)
    if chest:
        _set_rot(chest, f_apex, 'X', 3)
    if hips:
        _set_loc(hips, f_apex, 'Z', jp["hip_height"] * 0.8)

    for side in ["L", "R"]:
        ua = pb.get(f"UpperArm.{side}")
        if ua:
            _set_rot(ua, f_apex, 'X', -15)

    # ---- Landing absorption ----
    la_legs = jp["land_absorb"]
    for side in ["L", "R"]:
        ul = pb.get(f"UpperLeg.{side}")
        ll = pb.get(f"LowerLeg.{side}")
        ft = pb.get(f"Foot.{side}")
        if ul:
            _set_rot(ul, f_land, 'X', la_legs)
            _set_rot(ll, f_land, 'X', -la_legs * 1.1)
        if ft:
            _set_rot(ft, f_land, 'X', 10)

    if spine:
        _set_rot(spine, f_land, 'X', -10)
    if chest:
        _set_rot(chest, f_land, 'X', -8)
    if hips:
        _set_loc(hips, f_land, 'Z', -0.06)

    for side in ["L", "R"]:
        ua = pb.get(f"UpperArm.{side}")
        la = pb.get(f"LowerArm.{side}")
        if ua:
            _set_rot(ua, f_land, 'X', 15)
            _set_rot(la, f_land, 'X', -25)

    # ---- Return to neutral ----
    for bone_name in ["Spine", "Chest"]:
        b = pb.get(bone_name)
        if b:
            _set_rot(b, f_total, 'X', 0)

    for side in ["L", "R"]:
        for bone_name in [f"UpperLeg.{side}", f"LowerLeg.{side}", f"Foot.{side}",
                          f"UpperArm.{side}", f"LowerArm.{side}"]:
            b = pb.get(bone_name)
            if b:
                _set_rot(b, f_total, 'X', 0)

    if hips:
        _set_loc(hips, f_total, 'Z', 0)

    # Jump does NOT loop
    _exit_pose()
    return action


def create_attack(armature_obj, cfg):
    """Attack: right-hand melee swing. Non-looping.

    Phases:
        0 → windup_end:   Wind up (arm back, torso twist)
        windup_end → strike_end: Forward strike
        strike_end → follow_end: Follow-through
        follow_end → total: Return to neutral
    """
    _enter_pose(armature_obj)
    _reset_pose(armature_obj)

    ap = ANIM_PARAMS["attack"]
    f_total = ap["total_frames"]
    pb = armature_obj.pose.bones

    action = _new_action(armature_obj, "Attack")

    f_windup = ap["windup_end"]
    f_strike = ap["strike_end"]
    f_follow = ap["follow_end"]

    # ---- Frame 0: neutral ----
    for bone_name in ["Spine", "Chest"]:
        b = pb.get(bone_name)
        if b:
            _set_rot(b, 0, 'X', 0)
            _set_rot(b, 0, 'Z', 0)

    for side in ["L", "R"]:
        for bn in [f"UpperArm.{side}", f"LowerArm.{side}",
                   f"UpperLeg.{side}", f"LowerLeg.{side}"]:
            b = pb.get(bn)
            if b:
                _set_rot(b, 0, 'X', 0)

    # ---- Windup: twist torso back, pull right arm up/back ----
    spine = pb.get("Spine")
    chest = pb.get("Chest")
    if spine:
        _set_rot(spine, f_windup, 'Z', -ap["torso_twist"])
        _set_rot(spine, f_windup, 'X', -5)
    if chest:
        _set_rot(chest, f_windup, 'Z', -ap["torso_twist"] * 0.6)

    r_ua = pb.get("UpperArm.R")
    r_la = pb.get("LowerArm.R")
    if r_ua:
        _set_rot(r_ua, f_windup, 'X', ap["windup_arm"])
        _set_rot(r_la, f_windup, 'X', ap["windup_forearm"])

    # Left arm stays guarding
    l_ua = pb.get("UpperArm.L")
    l_la = pb.get("LowerArm.L")
    if l_ua:
        _set_rot(l_ua, f_windup, 'X', -15)
        _set_rot(l_la, f_windup, 'X', -45)

    # Legs: shift weight — front leg forward, rear leg back
    r_ul = pb.get("UpperLeg.R")
    l_ul = pb.get("UpperLeg.L")
    if r_ul:
        _set_rot(r_ul, f_windup, 'X', ap["rear_leg"])
    if l_ul:
        _set_rot(l_ul, f_windup, 'X', ap["lunge_leg"] * 0.5)

    # ---- Strike: snap torso forward, drive right arm down ----
    if spine:
        _set_rot(spine, f_strike, 'Z', ap["torso_twist"] * 0.8)
        _set_rot(spine, f_strike, 'X', 8)
    if chest:
        _set_rot(chest, f_strike, 'Z', ap["torso_twist"] * 0.5)

    if r_ua:
        _set_rot(r_ua, f_strike, 'X', ap["strike_arm"])
        _set_rot(r_la, f_strike, 'X', ap["strike_forearm"])

    if l_ua:
        _set_rot(l_ua, f_strike, 'X', -20)
        _set_rot(l_la, f_strike, 'X', -35)

    # Lunge forward
    if l_ul:
        _set_rot(l_ul, f_strike, 'X', ap["lunge_leg"])
        l_ll = pb.get("LowerLeg.L")
        if l_ll:
            _set_rot(l_ll, f_strike, 'X', -ap["lunge_leg"] * 0.5)
    if r_ul:
        _set_rot(r_ul, f_strike, 'X', ap["rear_leg"])

    # ---- Follow-through: arm continues past, torso settles ----
    if spine:
        _set_rot(spine, f_follow, 'Z', ap["torso_twist"] * 0.3)
        _set_rot(spine, f_follow, 'X', 3)
    if chest:
        _set_rot(chest, f_follow, 'Z', ap["torso_twist"] * 0.2)

    if r_ua:
        _set_rot(r_ua, f_follow, 'X', ap["strike_arm"] + 15)
        _set_rot(r_la, f_follow, 'X', ap["strike_forearm"] - 10)

    # ---- Return to neutral ----
    for bn in ["Spine", "Chest"]:
        b = pb.get(bn)
        if b:
            _set_rot(b, f_total, 'X', 0)
            _set_rot(b, f_total, 'Z', 0)

    for side in ["L", "R"]:
        for bn in [f"UpperArm.{side}", f"LowerArm.{side}",
                   f"UpperLeg.{side}", f"LowerLeg.{side}"]:
            b = pb.get(bn)
            if b:
                _set_rot(b, f_total, 'X', 0)

    # Attack does NOT loop
    _exit_pose()
    return action


# ───────────────────────────────────────────────────────────────────────────
# Public API
# ───────────────────────────────────────────────────────────────────────────

# Registry of all available animations
ANIMATIONS = {
    "idle":   create_idle,
    "walk":   create_walk_cycle,
    "run":    create_run_cycle,
    "jump":   create_jump,
    "attack": create_attack,
}


def create_all_animations(armature_obj, cfg):
    """Generate all animations and return them as a dict of Actions.

    Each action is stored independently in bpy.data.actions so the game
    engine can reference them by name.
    """
    actions = {}
    for name, builder in ANIMATIONS.items():
        actions[name] = builder(armature_obj, cfg)

    # Leave the idle animation active by default
    if "idle" in actions:
        armature_obj.animation_data.action = actions["idle"]

    return actions
