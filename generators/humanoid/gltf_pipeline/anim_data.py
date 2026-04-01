"""Animation data and keyframe builders for the humanoid gltf_pipeline.

Pure numpy/quaternion port of the animation parameters from animation.py.
No bpy imports.
"""

import numpy as np


# ── Animation parameters (copied from animation.py) ───────────────────────────

ANIM_PARAMS = {
    "idle": {
        "cycle_frames": 48,
        "fps": 24,
        "breath_chest": 1.5,
        "breath_spine": 1.0,
        "head_look": 2,
        "hip_shift": 1.0,
        "arm_breath": 0.8,
        "shoulder_breath": 0.5,
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
        "spine_lean": 4,
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
        "spine_lean": 8,
        "spine_twist": 5,
        "hip_bob": 0.04,
        "hip_sway": 3,
    },
    "jump": {
        "total_frames": 32,
        "fps": 24,
        "crouch_end": 8,
        "launch_end": 12,
        "apex": 20,
        "land_end": 28,
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
        "windup_end": 6,
        "strike_end": 10,
        "follow_end": 14,
        "windup_arm": -80,
        "windup_forearm": -90,
        "strike_arm": 60,
        "strike_forearm": -20,
        "torso_twist": 25,
        "lunge_leg": 20,
        "rear_leg": -15,
    },
}


IDENTITY_QUAT = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)


def euler_to_quat(rx_deg: float, ry_deg: float, rz_deg: float) -> np.ndarray:
    """Convert Euler XYZ angles (degrees) to quaternion [x, y, z, w].

    Rotation order: X then Y then Z (intrinsic).
    """
    rx, ry, rz = np.radians([rx_deg, ry_deg, rz_deg])
    cx, sx = np.cos(rx / 2), np.sin(rx / 2)
    cy, sy = np.cos(ry / 2), np.sin(ry / 2)
    cz, sz = np.cos(rz / 2), np.sin(rz / 2)
    w = cx * cy * cz + sx * sy * sz
    x = sx * cy * cz - cx * sy * sz
    y = cx * sy * cz + sx * cy * sz
    z = cx * cy * sz - sx * sy * cz
    return np.array([x, y, z, w], dtype=np.float32)


def _rot(bone: str, frame: int, fps: float,
         rx: float = 0.0, ry: float = 0.0, rz: float = 0.0):
    """Helper: return (time, bone, quat) tuple."""
    return (frame / fps, bone, euler_to_quat(rx, ry, rz))


def _trans(bone: str, frame: int, fps: float, x: float, y: float, z: float):
    """Helper: return (time, bone, vec3) tuple."""
    return (frame / fps, bone, np.array([x, y, z], dtype=np.float32))


# ── Idle animation ────────────────────────────────────────────────────────────

def idle_keyframes(cfg) -> tuple:
    """Generate idle animation keyframes.

    Returns:
        (rot_kfs, trans_kfs) where each item is a list of (t, bone_name, data).
    """
    p = ANIM_PARAMS["idle"]
    f = p["cycle_frames"]
    fps = p["fps"]
    q = f // 4

    bc = p["breath_chest"]
    bs = p["breath_spine"]
    hl = p["head_look"]
    hs = p["hip_shift"]
    ab = p["arm_breath"]
    sb = p["shoulder_breath"]

    rot_kfs = []
    trans_kfs = []

    # Chest breathing
    for frame, chest_angle, spine_angle in [
        (0,     0,              0),
        (q,     bc,             bs),
        (q * 2, 0,              0),
        (q * 3, bc * 0.7,       bs * 0.7),
        (f,     0,              0),
    ]:
        rot_kfs.append(_rot("Chest", frame, fps, rx=-chest_angle))
        rot_kfs.append(_rot("Spine", frame, fps, rx=-spine_angle))

    # Head look left/right
    for frame, angle in [
        (0, 0), (q, hl), (q * 2, 0), (q * 3, -hl), (f, 0),
    ]:
        rot_kfs.append(_rot("Head", frame, fps, rz=angle))

    # Hip sway (Z rotation)
    for frame, sway in [
        (0, 0), (q, hs), (q * 2, 0), (q * 3, -hs), (f, 0),
    ]:
        rot_kfs.append(_rot("Hips", frame, fps, rz=sway))

    # Arm breathing
    for side in ["L", "R"]:
        for frame, angle in [
            (0, 0), (q, ab), (q * 2, 0), (q * 3, ab * 0.7), (f, 0),
        ]:
            rot_kfs.append(_rot(f"UpperArm.{side}", frame, fps, rx=angle))
        for frame, angle in [
            (0, 0), (q, -sb), (q * 2, 0), (q * 3, -sb * 0.7), (f, 0),
        ]:
            rot_kfs.append(_rot(f"Shoulder.{side}", frame, fps, rx=angle))

    return rot_kfs, trans_kfs


# ── Walk animation ─────────────────────────────────────────────────────────────

def walk_keyframes(cfg) -> tuple:
    """Generate walk cycle keyframes."""
    wp = ANIM_PARAMS["walk"]
    frames = wp["cycle_frames"]
    fps = wp["fps"]
    half = frames // 2
    hh = half // 2

    uls = wp["upper_leg_swing"]
    llb = wp["lower_leg_bend"]
    fr = wp["foot_rock"]
    uas = wp["upper_arm_swing"]
    lab = wp["lower_arm_bend"]

    rot_kfs = []
    trans_kfs = []

    # Left leg
    left_leg_data = [
        (0,          uls,         -llb * 0.3,  -fr),
        (hh,         0,           -llb,          0),
        (half,      -uls,         -llb * 0.1,   fr),
        (half + hh,  0,           -llb * 0.6,   0),
        (frames,     uls,         -llb * 0.3,  -fr),
    ]
    right_leg_data = [
        (0,         -uls,         -llb * 0.1,   fr),
        (hh,         0,           -llb * 0.6,   0),
        (half,       uls,         -llb * 0.3,  -fr),
        (half + hh,  0,           -llb,          0),
        (frames,    -uls,         -llb * 0.1,   fr),
    ]

    for data, side in [(left_leg_data, "L"), (right_leg_data, "R")]:
        for frame, ul_a, ll_a, ft_a in data:
            rot_kfs.append(_rot(f"UpperLeg.{side}", frame, fps, rx=ul_a))
            rot_kfs.append(_rot(f"LowerLeg.{side}", frame, fps, rx=ll_a))
            rot_kfs.append(_rot(f"Foot.{side}", frame, fps, rx=ft_a))

    # Arms (counter-swing)
    left_arm_data = [
        (0,          -uas, -lab * 0.2),
        (hh,          0,   -lab * 0.1),
        (half,        uas, -lab),
        (half + hh,   0,   -lab * 0.1),
        (frames,     -uas, -lab * 0.2),
    ]
    right_arm_data = [
        (0,           uas, -lab),
        (hh,          0,   -lab * 0.1),
        (half,       -uas, -lab * 0.2),
        (half + hh,   0,   -lab * 0.1),
        (frames,      uas, -lab),
    ]

    for data, side in [(left_arm_data, "L"), (right_arm_data, "R")]:
        for frame, ua_a, la_a in data:
            rot_kfs.append(_rot(f"UpperArm.{side}", frame, fps, rx=ua_a))
            rot_kfs.append(_rot(f"LowerArm.{side}", frame, fps, rx=la_a))

    # Hip bob + sway
    bob = wp["hip_bob"]
    sway = wp["hip_sway"]
    for frame, b, s in [
        (0,          0,    -sway),
        (hh,         bob,   0),
        (half,       0,     sway),
        (half + hh,  bob,   0),
        (frames,     0,    -sway),
    ]:
        trans_kfs.append(_trans("Hips", frame, fps, 0, 0, b))
        rot_kfs.append(_rot("Hips", frame, fps, rz=s))

    # Spine twist + lean
    st = wp["spine_twist"]
    sl = wp.get("spine_lean", 0)
    for frame, twist, lean in [
        (0,          st,   sl),
        (hh,         0,   -sl * 0.5),
        (half,      -st,   sl),
        (half + hh,  0,   -sl * 0.5),
        (frames,     st,   sl),
    ]:
        rot_kfs.append(_rot("Spine", frame, fps, rx=lean, rz=twist))

    return rot_kfs, trans_kfs


# ── Run animation ──────────────────────────────────────────────────────────────

def run_keyframes(cfg) -> tuple:
    """Generate run cycle keyframes."""
    rp = ANIM_PARAMS["run"]
    frames = rp["cycle_frames"]
    fps = rp["fps"]
    half = frames // 2
    hh = half // 2

    uls = rp["upper_leg_swing"]
    llb = rp["lower_leg_bend"]
    fr = rp["foot_rock"]
    uas = rp["upper_arm_swing"]
    lab = rp["lower_arm_bend"]

    rot_kfs = []
    trans_kfs = []

    left_leg = [
        (0,          uls,         -llb * 0.2,  -fr),
        (hh,         uls * 0.3,   -llb,          0),
        (half,      -uls,         -llb * 0.1,   fr),
        (half + hh,  0,           -llb * 0.5,   0),
        (frames,     uls,         -llb * 0.2,  -fr),
    ]
    right_leg = [
        (0,         -uls,         -llb * 0.1,   fr),
        (hh,         0,           -llb * 0.5,   0),
        (half,       uls,         -llb * 0.2,  -fr),
        (half + hh,  uls * 0.3,   -llb,          0),
        (frames,    -uls,         -llb * 0.1,   fr),
    ]

    for data, side in [(left_leg, "L"), (right_leg, "R")]:
        for frame, ul_a, ll_a, ft_a in data:
            rot_kfs.append(_rot(f"UpperLeg.{side}", frame, fps, rx=ul_a))
            rot_kfs.append(_rot(f"LowerLeg.{side}", frame, fps, rx=ll_a))
            rot_kfs.append(_rot(f"Foot.{side}", frame, fps, rx=ft_a))

    left_arm = [
        (0,          -uas, -lab * 0.8),
        (hh,          0,   -lab * 0.5),
        (half,        uas, -lab),
        (half + hh,   0,   -lab * 0.5),
        (frames,     -uas, -lab * 0.8),
    ]
    right_arm = [
        (0,           uas, -lab),
        (hh,          0,   -lab * 0.5),
        (half,       -uas, -lab * 0.8),
        (half + hh,   0,   -lab * 0.5),
        (frames,      uas, -lab),
    ]

    for data, side in [(left_arm, "L"), (right_arm, "R")]:
        for frame, ua_a, la_a in data:
            rot_kfs.append(_rot(f"UpperArm.{side}", frame, fps, rx=ua_a))
            rot_kfs.append(_rot(f"LowerArm.{side}", frame, fps, rx=la_a))

    # Spine lean (constant forward) + twist
    lean = rp["spine_lean"]
    twist = rp["spine_twist"]
    for frame, tw in [
        (0,          twist),
        (hh,         0),
        (half,      -twist),
        (half + hh,  0),
        (frames,     twist),
    ]:
        rot_kfs.append(_rot("Spine", frame, fps, rx=lean, rz=tw))

    for frame in [0, hh, half, half + hh, frames]:
        rot_kfs.append(_rot("Chest", frame, fps, rx=lean * 0.5))

    # Hip bob
    bob = rp["hip_bob"]
    sway = rp["hip_sway"]
    for frame, b, s in [
        (0,          0,    -sway),
        (hh,         bob,   0),
        (half,       0,     sway),
        (half + hh,  bob,   0),
        (frames,     0,    -sway),
    ]:
        trans_kfs.append(_trans("Hips", frame, fps, 0, 0, b))
        rot_kfs.append(_rot("Hips", frame, fps, rz=s))

    return rot_kfs, trans_kfs


# ── Jump animation ─────────────────────────────────────────────────────────────

def jump_keyframes(cfg) -> tuple:
    """Generate jump (non-looping) keyframes."""
    jp = ANIM_PARAMS["jump"]
    f_total = jp["total_frames"]
    fps = jp["fps"]
    f_crouch = jp["crouch_end"]
    f_launch = jp["launch_end"]
    f_apex = jp["apex"]
    f_land = jp["land_end"]

    rot_kfs = []
    trans_kfs = []

    # Frame 0: neutral
    for bn in ["Spine", "Chest", "Hips"]:
        rot_kfs.append(_rot(bn, 0, fps))
    for side in ["L", "R"]:
        for bn in [f"UpperLeg.{side}", f"LowerLeg.{side}", f"Foot.{side}",
                   f"UpperArm.{side}", f"LowerArm.{side}"]:
            rot_kfs.append(_rot(bn, 0, fps))
    trans_kfs.append(_trans("Hips", 0, fps, 0, 0, 0))

    # Crouch
    cl = jp["crouch_legs"]
    cs = jp["crouch_spine"]
    for side in ["L", "R"]:
        rot_kfs.append(_rot(f"UpperLeg.{side}", f_crouch, fps, rx=cl))
        rot_kfs.append(_rot(f"LowerLeg.{side}", f_crouch, fps, rx=-cl * 1.2))
        rot_kfs.append(_rot(f"Foot.{side}", f_crouch, fps, rx=cl * 0.3))
        rot_kfs.append(_rot(f"UpperArm.{side}", f_crouch, fps, rx=25))
        rot_kfs.append(_rot(f"LowerArm.{side}", f_crouch, fps, rx=-40))
    rot_kfs.append(_rot("Spine", f_crouch, fps, rx=cs))
    rot_kfs.append(_rot("Chest", f_crouch, fps, rx=cs * 0.6))
    trans_kfs.append(_trans("Hips", f_crouch, fps, 0, 0, -0.08))

    # Launch
    ll_launch = jp["launch_legs"]
    ls = jp["launch_spine"]
    ar = jp["arm_raise"]
    for side in ["L", "R"]:
        rot_kfs.append(_rot(f"UpperLeg.{side}", f_launch, fps, rx=ll_launch))
        rot_kfs.append(_rot(f"LowerLeg.{side}", f_launch, fps, rx=-5))
        rot_kfs.append(_rot(f"Foot.{side}", f_launch, fps, rx=-30))
        rot_kfs.append(_rot(f"UpperArm.{side}", f_launch, fps, rx=ar))
        rot_kfs.append(_rot(f"LowerArm.{side}", f_launch, fps, rx=-20))
    rot_kfs.append(_rot("Spine", f_launch, fps, rx=ls))
    rot_kfs.append(_rot("Chest", f_launch, fps, rx=ls * 0.5))
    trans_kfs.append(_trans("Hips", f_launch, fps, 0, 0, jp["hip_height"]))

    # Apex tuck
    tl = jp["tuck_legs"]
    for side in ["L", "R"]:
        rot_kfs.append(_rot(f"UpperLeg.{side}", f_apex, fps, rx=tl))
        rot_kfs.append(_rot(f"LowerLeg.{side}", f_apex, fps, rx=-tl * 1.3))
        rot_kfs.append(_rot(f"UpperArm.{side}", f_apex, fps, rx=-15))
    rot_kfs.append(_rot("Spine", f_apex, fps, rx=5))
    rot_kfs.append(_rot("Chest", f_apex, fps, rx=3))
    trans_kfs.append(_trans("Hips", f_apex, fps, 0, 0, jp["hip_height"] * 0.8))

    # Landing
    la = jp["land_absorb"]
    for side in ["L", "R"]:
        rot_kfs.append(_rot(f"UpperLeg.{side}", f_land, fps, rx=la))
        rot_kfs.append(_rot(f"LowerLeg.{side}", f_land, fps, rx=-la * 1.1))
        rot_kfs.append(_rot(f"Foot.{side}", f_land, fps, rx=10))
        rot_kfs.append(_rot(f"UpperArm.{side}", f_land, fps, rx=15))
        rot_kfs.append(_rot(f"LowerArm.{side}", f_land, fps, rx=-25))
    rot_kfs.append(_rot("Spine", f_land, fps, rx=-10))
    rot_kfs.append(_rot("Chest", f_land, fps, rx=-8))
    trans_kfs.append(_trans("Hips", f_land, fps, 0, 0, -0.06))

    # Return to neutral
    for bn in ["Spine", "Chest"]:
        rot_kfs.append(_rot(bn, f_total, fps))
    for side in ["L", "R"]:
        for bn in [f"UpperLeg.{side}", f"LowerLeg.{side}", f"Foot.{side}",
                   f"UpperArm.{side}", f"LowerArm.{side}"]:
            rot_kfs.append(_rot(bn, f_total, fps))
    trans_kfs.append(_trans("Hips", f_total, fps, 0, 0, 0))

    return rot_kfs, trans_kfs


# ── Attack animation ───────────────────────────────────────────────────────────

def attack_keyframes(cfg) -> tuple:
    """Generate attack (non-looping) keyframes."""
    ap = ANIM_PARAMS["attack"]
    f_total = ap["total_frames"]
    fps = ap["fps"]
    f_windup = ap["windup_end"]
    f_strike = ap["strike_end"]
    f_follow = ap["follow_end"]

    rot_kfs = []
    trans_kfs = []

    # Frame 0: neutral
    for bn in ["Spine", "Chest"]:
        rot_kfs.append(_rot(bn, 0, fps))
    for side in ["L", "R"]:
        for bn in [f"UpperArm.{side}", f"LowerArm.{side}",
                   f"UpperLeg.{side}", f"LowerLeg.{side}"]:
            rot_kfs.append(_rot(bn, 0, fps))

    # Windup
    tt = ap["torso_twist"]
    rot_kfs.append(_rot("Spine",  f_windup, fps, rx=-5, rz=-tt))
    rot_kfs.append(_rot("Chest",  f_windup, fps, rz=-tt * 0.6))
    rot_kfs.append(_rot("UpperArm.R", f_windup, fps, rx=ap["windup_arm"]))
    rot_kfs.append(_rot("LowerArm.R", f_windup, fps, rx=ap["windup_forearm"]))
    rot_kfs.append(_rot("UpperArm.L", f_windup, fps, rx=-15))
    rot_kfs.append(_rot("LowerArm.L", f_windup, fps, rx=-45))
    rot_kfs.append(_rot("UpperLeg.R", f_windup, fps, rx=ap["rear_leg"]))
    rot_kfs.append(_rot("UpperLeg.L", f_windup, fps, rx=ap["lunge_leg"] * 0.5))

    # Strike
    rot_kfs.append(_rot("Spine",  f_strike, fps, rx=8, rz=tt * 0.8))
    rot_kfs.append(_rot("Chest",  f_strike, fps, rz=tt * 0.5))
    rot_kfs.append(_rot("UpperArm.R", f_strike, fps, rx=ap["strike_arm"]))
    rot_kfs.append(_rot("LowerArm.R", f_strike, fps, rx=ap["strike_forearm"]))
    rot_kfs.append(_rot("UpperArm.L", f_strike, fps, rx=-20))
    rot_kfs.append(_rot("LowerArm.L", f_strike, fps, rx=-35))
    rot_kfs.append(_rot("UpperLeg.L", f_strike, fps, rx=ap["lunge_leg"]))
    rot_kfs.append(_rot("LowerLeg.L", f_strike, fps, rx=-ap["lunge_leg"] * 0.5))
    rot_kfs.append(_rot("UpperLeg.R", f_strike, fps, rx=ap["rear_leg"]))

    # Follow-through
    rot_kfs.append(_rot("Spine",  f_follow, fps, rx=3, rz=tt * 0.3))
    rot_kfs.append(_rot("Chest",  f_follow, fps, rz=tt * 0.2))
    rot_kfs.append(_rot("UpperArm.R", f_follow, fps, rx=ap["strike_arm"] + 15))
    rot_kfs.append(_rot("LowerArm.R", f_follow, fps, rx=ap["strike_forearm"] - 10))

    # Return to neutral
    for bn in ["Spine", "Chest"]:
        rot_kfs.append(_rot(bn, f_total, fps))
    for side in ["L", "R"]:
        for bn in [f"UpperArm.{side}", f"LowerArm.{side}",
                   f"UpperLeg.{side}", f"LowerLeg.{side}"]:
            rot_kfs.append(_rot(bn, f_total, fps))

    return rot_kfs, trans_kfs
