"""Procedural base mesh with ring-based cross-section construction.

Builds a complete low-poly humanoid body as a single unified bmesh with
fixed topology (~350-450 quads). The mesh is constructed from octagonal
cross-section rings connected by quad strips.

Architecture inspired by MB-Lab/MakeHuman: a fixed-topology base mesh
with morph targets for body variation, rather than modifier-based generation.

The base mesh is always built for the "neutral average" body proportions.
Body variation (gender, build, preset) is applied via the morph system
in morphs.py.

Key design decisions:
- 8 vertices per ring (octagonal cross-section) for clean quad topology
- Branch junctions (crotch, shoulders) use a few tris where unavoidable
- All vertex positions computed from config params for morph generation
- Vertex groups assigned at construction time for deterministic skinning
- Feet at Z=0, character faces -Y direction
"""

import math
from mathutils import Vector, Matrix


# Ring vertex count — octagonal cross-sections
RING_VERTS = 8


def _make_ring(bm, center, rx, ry, n=RING_VERTS, z_up=True):
    """Create a ring of vertices in an elliptical cross-section.

    Args:
        bm: bmesh instance
        center: (x, y, z) center of the ring
        rx: radius in the X direction (width)
        ry: radius in the Y direction (depth/front-back)
        n: number of vertices in the ring
        z_up: if True, ring lies in XY plane (for vertical body parts)

    Returns:
        List of bmesh vertices forming the ring.
    """
    verts = []
    cx, cy, cz = center
    for i in range(n):
        angle = 2 * math.pi * i / n
        # Start at front (-Y) and go clockwise when viewed from above
        lx = cx + rx * math.sin(angle)
        ly = cy - ry * math.cos(angle)
        verts.append(bm.verts.new((lx, ly, cz)))
    return verts


def _make_arm_ring(bm, center, rx, ry, n=RING_VERTS):
    """Create a ring of vertices for an arm cross-section (XY plane at given Z).

    Same as _make_ring but explicitly for limbs that run vertically.
    """
    return _make_ring(bm, center, rx, ry, n)


def _bridge_rings(bm, ring_a, ring_b):
    """Connect two rings with quad faces.

    Rings must have the same vertex count. Creates one quad per
    pair of adjacent vertices between the rings.

    Returns list of created faces.
    """
    n = len(ring_a)
    assert len(ring_b) == n, f"Ring sizes must match: {len(ring_a)} vs {len(ring_b)}"
    faces = []
    for i in range(n):
        j = (i + 1) % n
        # Wind faces consistently (outward-facing normals)
        f = bm.faces.new([ring_a[i], ring_a[j], ring_b[j], ring_b[i]])
        faces.append(f)
    return faces


def _cap_ring(bm, ring, top=True):
    """Close a ring with a fan of triangles from a center vertex.

    Args:
        ring: list of bmesh vertices forming the ring
        top: if True, normals point up; if False, normals point down
    """
    # Compute center
    center = Vector((0, 0, 0))
    for v in ring:
        center += v.co
    center /= len(ring)

    cap_vert = bm.verts.new(center)
    faces = []
    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        if top:
            f = bm.faces.new([cap_vert, ring[i], ring[j]])
        else:
            f = bm.faces.new([cap_vert, ring[j], ring[i]])
        faces.append(f)
    return cap_vert, faces


def _build_torso_rings(bm, cfg):
    """Build torso as a series of cross-section rings from pelvis to chest.

    Ring dimensions calibrated against Synty reference meshes
    (Characters_Matt.obj, Characters_Sam.obj):
      chest  rx/sw ≈ 0.87, ry/rx ≈ 0.862
      waist  rx/sw ≈ 0.76, ry/rx ≈ 0.671
      hip    rx/sw ≈ 1.00, ry/rx ≈ 0.530

    Returns dict mapping region names to ring vertex lists, plus
    a list of all (ring, bone_name) pairs for vertex group assignment.
    """
    sw = cfg["shoulder_width"]
    hw = cfg["hip_width"]
    torso_len = cfg["torso_length"]
    leg_len = cfg["leg_length"]
    neck_len = cfg["neck_length"]
    head_r = cfg.get("head_size", 0.17)
    gender = cfg.get("gender", "neutral")

    foot_top = 0.06
    hip_z = foot_top + leg_len
    lower_waist_z = hip_z + torso_len * 0.20
    waist_z = hip_z + torso_len * 0.42
    lower_chest_z = hip_z + torso_len * 0.68
    chest_z = hip_z + torso_len
    neck_z = chest_z + neck_len

    # Gender-specific per-ring multipliers add shape nuance on top of the
    # global sw/hw scaling already set by presets.GENDERS.
    if gender == "male":
        chest_rx_mult  = 1.05   # broader chest → V-shape
        waist_rx_mult  = 0.97   # slightly tighter waist
        hip_rx_mult    = 0.95   # less hip flare
        pelvis_rx_mult = 0.96
    elif gender == "female":
        chest_rx_mult  = 0.97   # relatively narrower chest
        waist_rx_mult  = 0.95   # more pronounced hourglass waist
        hip_rx_mult    = 1.08   # wider hip flare
        pelvis_rx_mult = 1.10   # wider pelvis
    else:  # neutral
        chest_rx_mult  = 1.00
        waist_rx_mult  = 1.00
        hip_rx_mult    = 1.00
        pelvis_rx_mult = 1.00

    # Ring radii (rx=X-width, ry=Y-depth) calibrated to Synty reference.
    # Using sw as reference unit; ry proportional via measured d/w ratios.
    rings_spec = [
        # (z, rx, ry, bone_name)
        (hip_z - 0.02, sw * 1.07 * pelvis_rx_mult, sw * 0.57, "Hips"),   # pelvis base
        (hip_z,        sw * 1.00 * hip_rx_mult,    sw * 0.53, "Hips"),   # hip centre
        (lower_waist_z, sw * 0.94,                 sw * 0.53, "Hips"),   # lower abdomen
        (waist_z,      sw * 0.76 * waist_rx_mult,  sw * 0.51, "Spine"),  # waist (hourglass)
        (lower_chest_z, sw * 0.68,                 sw * 0.63, "Chest"),  # lower chest / rib cage
        (chest_z,      sw * 0.87 * chest_rx_mult,  sw * 0.75, "Chest"),  # chest top
        (neck_z,       head_r * 0.35,               head_r * 0.32, "Neck"),  # neck base (scaled to head)
    ]

    rings = {}
    ring_groups = []  # (ring_verts, bone_name)

    for i, (z, rx, ry, bone_name) in enumerate(rings_spec):
        name = ["pelvis", "hip", "lower_waist", "waist",
                "lower_chest", "chest", "neck"][i]
        ring = _make_ring(bm, (0, 0, z), rx, ry)
        rings[name] = ring
        ring_groups.append((ring, bone_name))

    # Bridge adjacent rings
    ring_names = ["pelvis", "hip", "lower_waist", "waist",
                  "lower_chest", "chest", "neck"]
    for i in range(len(ring_names) - 1):
        _bridge_rings(bm, rings[ring_names[i]], rings[ring_names[i + 1]])

    return rings, ring_groups


def _build_leg(bm, cfg, side, hip_ring):
    """Build one leg from hip joint to ankle.

    The leg branches from the hip ring. We extract the relevant half of
    the hip ring (4 verts on the appropriate side) and create a transition
    ring at the hip joint, then build leg rings down to the ankle.

    Args:
        bm: bmesh instance
        cfg: body config
        side: "L" or "R"
        hip_ring: the hip ring vertices from torso

    Returns:
        (ankle_ring, ring_groups) where ring_groups is list of
        (ring_verts, bone_name) for vertex group assignment.
    """
    hw = cfg["hip_width"]
    leg_len = cfg["leg_length"]
    lt = cfg.get("limb_thickness", 1.0)

    foot_top = 0.06
    hip_z = foot_top + leg_len
    # Thigh peak sits ~18% below hip junction — clearly above the mid-thigh
    thigh_z = hip_z - leg_len * 0.18
    # Mid-thigh ring provides a smooth taper from thigh peak down to knee
    mid_thigh_z = hip_z - leg_len * 0.35
    # Knee at 48% of leg height from floor — classic anatomical knee position
    knee_z = foot_top + leg_len * 0.48
    # Calf muscle peak ~30% of the shin-to-knee span below the knee
    calf_z = knee_z - (knee_z - foot_top) * 0.30
    ankle_z = foot_top

    x_sign = 1 if side == "L" else -1
    x = x_sign * hw

    # Knee protrudes forward (in -Y, the face direction) relative to the
    # straight-leg axis.  A small Y offset on the knee and calf rings
    # mimics the slight forward angle of the lower leg and the kneecap bump.
    knee_y_fwd = -0.018 * lt   # knees pushed forward (-Y = face direction)

    # Leg ring radii derived from Synty reference OBJ analysis (Matt + Lis,
    # scaled to code body height and corrected for clothing thickness):
    #
    #   hip junction  rx≈0.115  ry≈0.095  (wide hip attachment, slightly flat front-back)
    #   thigh peak    rx≈0.130  ry≈0.112  (full thigh, rounder cross-section)
    #   mid-thigh     rx≈0.110  ry≈0.098  (tapers toward knee)
    #   knee          rx≈0.090  ry≈0.098  (kneecap makes knee deeper than wide)
    #   calf peak     rx≈0.096  ry≈0.090  (calf muscle, nearly round)
    #   ankle         rx≈0.062  ry≈0.058  (tapered but not bony)
    #
    # Key reference ratios (from OBJ, post clothing deduction):
    #   thigh/knee rx  ≈ 1.44  (thigh clearly thicker than knee)
    #   thigh/ankle rx ≈ 2.10  (strong taper from thigh to ankle)
    #   knee ry > rx   (kneecap depth makes knee deeper than wide)
    leg_rings_spec = [
        # (z, y_offset, rx, ry, bone_name)
        (hip_z,       0,          0.115 * lt, 0.095 * lt, f"UpperLeg.{side}"),  # hip junction
        (thigh_z,     0,          0.130 * lt, 0.112 * lt, f"UpperLeg.{side}"),  # thigh peak (widest)
        (mid_thigh_z, 0,          0.110 * lt, 0.098 * lt, f"UpperLeg.{side}"),  # mid-thigh taper
        (knee_z,      knee_y_fwd, 0.090 * lt, 0.098 * lt, f"LowerLeg.{side}"),  # knee (deeper than wide)
        (calf_z,      knee_y_fwd, 0.096 * lt, 0.090 * lt, f"LowerLeg.{side}"),  # calf peak
        (ankle_z,     0,          0.062 * lt, 0.058 * lt, f"LowerLeg.{side}"),  # ankle
    ]

    rings = []
    ring_groups = []

    for z, y_off, rx, ry, bone_name in leg_rings_spec:
        ring = _make_ring(bm, (x, y_off, z), rx, ry)
        rings.append(ring)
        ring_groups.append((ring, bone_name))

    # Bridge leg rings
    for i in range(len(rings) - 1):
        _bridge_rings(bm, rings[i], rings[i + 1])

    # Connect top leg ring to hip ring via junction faces
    _build_leg_junction(bm, hip_ring, rings[0], side)

    ankle_ring = rings[-1]
    return ankle_ring, ring_groups


def _build_leg_junction(bm, hip_ring, leg_top_ring, side):
    """Connect a leg's top ring to the torso hip ring.

    Creates triangular junction faces bridging from the torso to the leg.
    The hip ring has 8 verts; we use the 4 on the correct side to
    connect to the leg's 8-vert ring.
    """
    # Determine which hip ring verts are on this side
    # Hip ring verts go around the torso. For "L" side, we want verts
    # with positive X; for "R" side, negative X.
    x_sign = 1 if side == "L" else -1

    # Sort hip ring verts by angle relative to the leg center
    leg_center = Vector((0, 0, 0))
    for v in leg_top_ring:
        leg_center += v.co
    leg_center /= len(leg_top_ring)

    # Find the 4 closest hip verts to the leg center
    hip_dists = [(v, (v.co - leg_center).length) for v in hip_ring]
    hip_dists.sort(key=lambda x: x[1])
    closest_hip = [v for v, d in hip_dists[:4]]

    # Sort both sets by angle around the leg center for consistent winding
    def angle_around(v, center):
        dx = v.co.x - center.x
        dy = v.co.y - center.y
        return math.atan2(dy, dx)

    closest_hip.sort(key=lambda v: angle_around(v, leg_center))
    leg_sorted = sorted(leg_top_ring, key=lambda v: angle_around(v, leg_center))

    # Bridge the 4 hip verts to 8 leg verts using a mix of quads and tris
    # Each hip vert connects to 2 leg verts
    n_hip = len(closest_hip)
    n_leg = len(leg_sorted)
    ratio = n_leg // n_hip  # should be 2

    for i in range(n_hip):
        h0 = closest_hip[i]
        h1 = closest_hip[(i + 1) % n_hip]
        l_base = i * ratio
        for j in range(ratio):
            l0 = leg_sorted[(l_base + j) % n_leg]
            l1 = leg_sorted[(l_base + j + 1) % n_leg]
            if j == 0:
                # Quad connecting hip edge to first leg pair
                try:
                    bm.faces.new([h0, h1, l1, l0])
                except ValueError:
                    pass  # face may already exist
            else:
                # Triangle filling the gap
                try:
                    bm.faces.new([h0, l1, l0])
                except ValueError:
                    pass


def _build_arm(bm, cfg, side, chest_ring):
    """Build one arm from shoulder to wrist.

    Args:
        bm: bmesh instance
        cfg: body config
        side: "L" or "R"
        chest_ring: the chest ring vertices from torso

    Returns:
        (wrist_ring, ring_groups)
    """
    sw = cfg["shoulder_width"]
    arm_len = cfg["arm_length"]
    lt = cfg.get("limb_thickness", 1.0)
    torso_len = cfg["torso_length"]
    leg_len = cfg["leg_length"]

    foot_top = 0.06
    hip_z = foot_top + leg_len
    chest_z = hip_z + torso_len

    x_sign = 1 if side == "L" else -1
    shoulder_x = x_sign * (sw + 0.04)

    arm_top_z = chest_z              # flush with chest for clean shoulder merge
    upper_arm_len = arm_len * 0.48
    elbow_z = arm_top_z - upper_arm_len
    lower_arm_len = arm_len * 0.52
    wrist_z = elbow_z - lower_arm_len

    deltoid_z = arm_top_z - upper_arm_len * 0.20  # higher deltoid = rounder cap
    bicep_z = arm_top_z - upper_arm_len * 0.60
    forearm_z = elbow_z - lower_arm_len * 0.30

    # Arm ring radii calibrated against Synty reference OBJ analysis
    # (Characters_Matt.obj h=1.401m, Characters_Shaun.obj h=1.419m),
    # scaled to the default average body height of ~2.0m (lt=1.0):
    #
    #   upper-arm avg radius / body height  ≈ 4.9%  → rx ≈ 0.098m at 2.0m
    #   forearm avg radius   / body height  ≈ 4.0%  → rx ≈ 0.080m at 2.0m
    #   wrist    avg radius  / body height  ≈ 2.3%  → rx ≈ 0.046m at 2.0m
    #   upper-arm:forearm taper ratio       ≈ 1.25:1
    #   elbow is narrowest point of lower arm (thinner than forearm belly)
    #   deltoid is widest point of upper arm (peaks ~25% down from shoulder)
    #
    # ry/rx held at ≈ 0.88 (arms are slightly flattened front-to-back).
    arm_rings_spec = [
        # (z, rx, ry, bone_name)
        # Shoulder attachment sits at chest_z so it merges cleanly with the
        # torso.  Larger rx (0.092) gives more shoulder area for the cap.
        # Deltoid is bigger (0.108) and higher (20% down) for a cartoony
        # rounded-shoulder silhouette.
        (arm_top_z,   0.092 * lt, 0.080 * lt, f"UpperArm.{side}"),   # shoulder (flush with chest)
        (deltoid_z,   0.108 * lt, 0.094 * lt, f"UpperArm.{side}"),   # deltoid peak (widest, more cap)
        (bicep_z,     0.090 * lt, 0.079 * lt, f"UpperArm.{side}"),   # bicep
        (elbow_z,     0.068 * lt, 0.060 * lt, f"LowerArm.{side}"),   # elbow (narrowest)
        (forearm_z,   0.082 * lt, 0.072 * lt, f"LowerArm.{side}"),   # forearm belly
        (wrist_z,     0.046 * lt, 0.040 * lt, f"Hand.{side}"),       # wrist
    ]

    rings = []
    ring_groups = []

    for z, rx, ry, bone_name in arm_rings_spec:
        ring = _make_ring(bm, (shoulder_x, 0, z), rx, ry)
        rings.append(ring)
        ring_groups.append((ring, bone_name))

    # Bridge arm rings
    for i in range(len(rings) - 1):
        _bridge_rings(bm, rings[i], rings[i + 1])

    # Connect shoulder ring to chest ring via junction
    _build_arm_junction(bm, chest_ring, rings[0], side)

    wrist_ring = rings[-1]
    return wrist_ring, ring_groups


def _build_arm_junction(bm, chest_ring, arm_top_ring, side):
    """Connect an arm's top ring to the torso with a clean shoulder cap.

    The arm ring has 8 verts.  Half face toward the torso (inner side) and
    half face away (outer / lateral side = the shoulder cap).

      inner verts  → connected to the 4 nearest chest ring verts with quads
      outer verts  → capped with a triangle fan to a raised central vert,
                     forming a visible domed shoulder cap

    This replaces the previous mixed quad/triangle fan that produced uneven
    topology at the shoulder seam.
    """
    x_sign = 1 if side == "L" else -1

    # Arm ring centre
    arm_cx = sum(v.co.x for v in arm_top_ring) / len(arm_top_ring)
    arm_cy = sum(v.co.y for v in arm_top_ring) / len(arm_top_ring)
    arm_cz = sum(v.co.z for v in arm_top_ring) / len(arm_top_ring)

    def angle_xy(v, cx, cy):
        return math.atan2(v.co.y - cy, v.co.x - cx)

    # Split arm verts: inner (toward torso centre) vs outer (shoulder side)
    # Condition: x_sign * v.co.x < x_sign * arm_cx → inner (toward centre)
    inner_arm = sorted(
        [v for v in arm_top_ring if (v.co.x * x_sign) < (arm_cx * x_sign)],
        key=lambda v: angle_xy(v, arm_cx, arm_cy),
    )
    outer_arm = sorted(
        [v for v in arm_top_ring if (v.co.x * x_sign) >= (arm_cx * x_sign)],
        key=lambda v: angle_xy(v, arm_cx, arm_cy),
    )

    # 4 closest chest verts, sorted by angle from arm centre
    chest_by_dist = sorted(chest_ring,
                           key=lambda v: (v.co.x - arm_cx) ** 2 + (v.co.y - arm_cy) ** 2)
    closest_chest = sorted(chest_by_dist[:4],
                           key=lambda v: angle_xy(v, arm_cx, arm_cy))

    # Inner arm → chest: quad strip
    n = min(len(closest_chest), len(inner_arm))
    for i in range(n):
        c0 = closest_chest[i]
        c1 = closest_chest[(i + 1) % len(closest_chest)]
        a0 = inner_arm[i % len(inner_arm)]
        a1 = inner_arm[(i + 1) % len(inner_arm)]
        try:
            bm.faces.new([c0, c1, a1, a0])
        except ValueError:
            pass

    # Outer arm → shoulder cap: triangle fan to a slightly raised centre vert
    if outer_arm:
        cap_cx = sum(v.co.x for v in outer_arm) / len(outer_arm)
        cap_cy = sum(v.co.y for v in outer_arm) / len(outer_arm)
        cap_v  = bm.verts.new((cap_cx, cap_cy, arm_cz + 0.015))
        for i in range(len(outer_arm)):
            j = (i + 1) % len(outer_arm)
            try:
                if x_sign > 0:
                    bm.faces.new([outer_arm[i], outer_arm[j], cap_v])
                else:
                    bm.faces.new([outer_arm[j], outer_arm[i], cap_v])
            except ValueError:
                pass


def _make_head_ring(bm, center, rx, ry, n=RING_VERTS, front_offsets=None):
    """Create a head ring with optional per-vertex offsets for facial features.

    Like _make_ring but allows pushing individual vertices forward/backward
    to create facial geometry (nose, brow, chin, etc.).

    Args:
        front_offsets: optional dict mapping vertex index (0=front center)
            to (dx, dy, dz) offset applied after base position.
    """
    verts = []
    cx, cy, cz = center
    for i in range(n):
        angle = 2 * math.pi * i / n
        lx = cx + rx * math.sin(angle)
        ly = cy - ry * math.cos(angle)
        lz = cz
        # Apply per-vertex offsets for facial features
        if front_offsets and i in front_offsets:
            dx, dy, dz = front_offsets[i]
            lx += dx
            ly += dy
            lz += dz
        verts.append(bm.verts.new((lx, ly, lz)))
    return verts


def _build_head_rings(bm, cfg, neck_ring):
    """Build head with facial features from neck ring to crown.

    Creates a detailed head with:
    - Chin point and jawline
    - Nose bridge and tip
    - Mouth indent
    - Brow ridge
    - Ear bumps
    - Eye socket indentations
    - Smooth cranium

    The head uses 8-vert rings with per-vertex offsets to sculpt
    facial features from the standard ring topology.

    Returns ring_groups for vertex group assignment.
    """
    head_r = cfg["head_size"]
    neck_len = cfg["neck_length"]
    torso_len = cfg["torso_length"]
    leg_len = cfg["leg_length"]

    foot_top = 0.06
    hip_z = foot_top + leg_len
    chest_z = hip_z + torso_len
    neck_z = chest_z + neck_len
    head_z = neck_z + head_r  # center of head

    # Ring indices (for 8-vert ring starting at front -Y, clockwise from above):
    # 0 = front center (face)
    # 1 = front-left
    # 2 = left
    # 3 = back-left
    # 4 = back center
    # 5 = back-right
    # 6 = right
    # 7 = front-right

    rings = []
    ring_groups = []

    # Head ring proportions calibrated from reference blend file analysis
    # (Characters_Matt.blend / Characters_Shaun.blend):
    #   head width ≈ head height  (near-square, width/height ≈ 1.03)
    #   total head height ≈ head_r * 1.90 (jaw_base at +0.02 → crown at +0.90)
    #   → widest rx ≈ head_r * 0.95  (so 2*0.95*head_r ≈ head_r*1.90 = height)
    #
    # Previous rings were too narrow (widest rx was head_r*0.88, making head
    # visibly taller than wide). All rx/ry values scaled up by ~1.08x.

    # --- Ring 0: Jaw base (transition ring) ---
    jaw_base_z = neck_z + head_r * 0.02
    jaw_base_ring = _make_head_ring(bm, (0, 0, jaw_base_z),
                                    head_r * 0.54, head_r * 0.50)
    rings.append(jaw_base_ring)
    ring_groups.append((jaw_base_ring, "Head"))

    # --- Ring 1: Chin ---
    # Wider square Synty jawline.
    chin_z = neck_z + head_r * 0.06
    chin_ring = _make_head_ring(bm, (0, 0, chin_z),
                                head_r * 0.70, head_r * 0.64,
                                front_offsets={
                                    0: (0, -head_r * 0.08, -head_r * 0.02),
                                    1: (0, -head_r * 0.03, 0),
                                    7: (0, -head_r * 0.03, 0),
                                })
    rings.append(chin_ring)
    ring_groups.append((chin_ring, "Head"))

    # --- Ring 2: Mouth / lower jaw ---
    mouth_z = neck_z + head_r * 0.32
    mouth_ring = _make_head_ring(bm, (0, 0, mouth_z),
                                 head_r * 0.80, head_r * 0.74,
                                 front_offsets={
                                     0: (0, -head_r * 0.04, 0),
                                     1: (0, -head_r * 0.02, 0),
                                     7: (0, -head_r * 0.02, 0),
                                 })
    rings.append(mouth_ring)
    ring_groups.append((mouth_ring, "Head"))

    # --- Ring 3: Cheekbone / nose base ---
    # Widest ring — rx ≈ 0.95 makes the head near-square (width ≈ height).
    nose_z = neck_z + head_r * 0.57
    nose_ring = _make_head_ring(bm, (0, 0, nose_z),
                                head_r * 0.95, head_r * 0.88,
                                front_offsets={
                                    0: (0, -head_r * 0.08, 0),
                                    1: (0, -head_r * 0.03, 0),
                                    7: (0, -head_r * 0.03, 0),
                                    2: (head_r * 0.04, 0, 0),
                                    6: (-head_r * 0.04, 0, 0),
                                })
    rings.append(nose_ring)
    ring_groups.append((nose_ring, "Head"))

    # --- Ring 4: Eye level ---
    eye_z = neck_z + head_r * 0.82
    eye_ring = _make_head_ring(bm, (0, 0, eye_z),
                               head_r * 0.90, head_r * 0.83,
                               front_offsets={
                                   0: (0, -head_r * 0.05, 0),
                                   1: (head_r * 0.02, head_r * 0.02, 0),
                                   7: (-head_r * 0.02, head_r * 0.02, 0),
                                   2: (head_r * 0.04, 0, 0),
                                   6: (-head_r * 0.04, 0, 0),
                               })
    rings.append(eye_ring)
    ring_groups.append((eye_ring, "Head"))

    # --- Ring 5: Brow ridge ---
    brow_z = neck_z + head_r * 1.00
    brow_ring = _make_head_ring(bm, (0, 0, brow_z),
                                head_r * 0.88, head_r * 0.82,
                                front_offsets={
                                    0: (0, -head_r * 0.05, 0),
                                    1: (0, -head_r * 0.04, 0),
                                    7: (0, -head_r * 0.04, 0),
                                })
    rings.append(brow_ring)
    ring_groups.append((brow_ring, "Head"))

    # --- Ring 6: Forehead ---
    forehead_z = head_z + head_r * 0.28
    forehead_ring = _make_head_ring(bm, (0, 0, forehead_z),
                                    head_r * 0.74, head_r * 0.68,
                                    front_offsets={
                                        0: (0, -head_r * 0.04, 0),
                                        1: (0, -head_r * 0.02, 0),
                                        7: (0, -head_r * 0.02, 0),
                                    })
    rings.append(forehead_ring)
    ring_groups.append((forehead_ring, "Head"))

    # --- Ring 7: Upper cranium ---
    upper_z = head_z + head_r * 0.58
    upper_ring = _make_ring(bm, (0, 0, upper_z),
                            head_r * 0.54, head_r * 0.50)
    rings.append(upper_ring)
    ring_groups.append((upper_ring, "Head"))

    # --- Ring 8: Crown approach ---
    crown_z = head_z + head_r * 0.90
    crown_ring = _make_ring(bm, (0, 0, crown_z),
                            head_r * 0.31, head_r * 0.28)
    rings.append(crown_ring)
    ring_groups.append((crown_ring, "Head"))

    # Bridge neck to jaw base transition ring, then jaw base to first chin ring
    _bridge_rings(bm, neck_ring, rings[0])

    # Bridge all head rings
    for i in range(len(rings) - 1):
        _bridge_rings(bm, rings[i], rings[i + 1])

    # Cap the top of the head
    cap_vert, _ = _cap_ring(bm, rings[-1], top=True)
    ring_groups.append(([cap_vert], "Head"))

    return ring_groups, rings


def _build_hand(bm, cfg, side, wrist_ring):
    """Build a hand with palm, finger block, and thumb.

    The hand extends downward from the wrist with:
    - A wider palm section
    - A tapered finger block
    - A thumb extending to the side

    Returns ring_groups for vertex group assignment.
    """
    sw = cfg["shoulder_width"]
    hand_size = cfg["hand_size"]
    arm_len = cfg["arm_length"]
    leg_len = cfg["leg_length"]
    torso_len = cfg["torso_length"]

    foot_top = 0.06
    hip_z = foot_top + leg_len
    chest_z = hip_z + torso_len

    x_sign = 1 if side == "L" else -1
    shoulder_x = x_sign * (sw + 0.04)

    arm_top_z = chest_z - 0.04
    upper_arm_len = arm_len * 0.48
    elbow_z = arm_top_z - upper_arm_len
    lower_arm_len = arm_len * 0.52
    wrist_z = elbow_z - lower_arm_len

    s = hand_size
    palm_len = s * 1.1
    finger_len = s * 0.90

    # Palm ring — wider than wrist, flattened (wider in X, narrow in Y)
    palm_z = wrist_z - palm_len
    palm_ring = _make_ring(bm, (shoulder_x, 0, palm_z),
                           s * 0.55, s * 0.20)

    # Knuckle ring — slightly wider than palm
    knuckle_z = palm_z - s * 0.15
    knuckle_ring = _make_ring(bm, (shoulder_x, 0, knuckle_z),
                              s * 0.52, s * 0.18)

    # Finger mid ring
    finger_mid_z = knuckle_z - finger_len * 0.50
    finger_mid_ring = _make_ring(bm, (shoulder_x, 0, finger_mid_z),
                                 s * 0.42, s * 0.15)

    # Finger tip ring (tapered)
    finger_z = knuckle_z - finger_len
    finger_ring = _make_ring(bm, (shoulder_x, 0, finger_z),
                             s * 0.28, s * 0.10)

    # Bridge wrist -> palm -> knuckles -> finger_mid -> finger tips
    _bridge_rings(bm, wrist_ring, palm_ring)
    _bridge_rings(bm, palm_ring, knuckle_ring)
    _bridge_rings(bm, knuckle_ring, finger_mid_ring)
    _bridge_rings(bm, finger_mid_ring, finger_ring)

    # Cap finger tips
    cap_vert, _ = _cap_ring(bm, finger_ring, top=False)

    ring_groups = [
        (palm_ring, f"Hand.{side}"),
        (knuckle_ring, f"Hand.{side}"),
        (finger_mid_ring, f"Hand.{side}"),
        (finger_ring, f"Hand.{side}"),
        ([cap_vert], f"Hand.{side}"),
    ]

    # --- Thumb ---
    # Thumb extends from the palm toward the front of the body (-Y)
    # and slightly outward (in X direction based on side)
    thumb_base_z = wrist_z - palm_len * 0.30
    thumb_r = s * 0.14

    # Thumb base (at palm level, offset toward body front)
    tb_x = shoulder_x + x_sign * s * 0.40
    tb_y = -s * 0.20

    thumb_base = _make_ring(bm, (tb_x, tb_y, thumb_base_z),
                            thumb_r, thumb_r, n=6)

    # Thumb tip (angled outward and forward)
    tt_x = shoulder_x + x_sign * s * 0.55
    tt_y = -s * 0.35
    thumb_tip_z = thumb_base_z - s * 0.55
    thumb_tip = _make_ring(bm, (tt_x, tt_y, thumb_tip_z),
                           thumb_r * 0.70, thumb_r * 0.70, n=6)

    _bridge_rings(bm, thumb_base, thumb_tip)
    thumb_cap, _ = _cap_ring(bm, thumb_tip, top=False)

    ring_groups.append((thumb_base, f"Hand.{side}"))
    ring_groups.append((thumb_tip, f"Hand.{side}"))
    ring_groups.append(([thumb_cap], f"Hand.{side}"))

    return ring_groups


def _build_foot(bm, cfg, side, ankle_ring):
    """Build a foot from the ankle ring.

    Creates a wedge-shaped foot pointing forward (-Y direction).
    The foot is built as rings along the Y axis rather than Z.

    Returns ring_groups for vertex group assignment.
    """
    hw = cfg["hip_width"]
    foot_len = cfg["foot_length"]
    foot_w = cfg["foot_width"]

    x_sign = 1 if side == "L" else -1
    # Feet are slightly narrower stance than hip width (~85%)
    x = x_sign * hw * 0.85

    # Derive foot height from the ankle ring's actual Z position rather than
    # hardcoding 0.06.  The ankle ring arrives at foot_top (0.06 by default)
    # but using the ring itself keeps the foot consistent if leg proportions change.
    ankle_z = ankle_ring[0].co.z  # all ankle ring verts share the same Z
    foot_h = ankle_z              # foot spans from Z=0 (ground) up to ankle_z

    half_w = foot_w / 2

    # Heel ring — heel extends back (+Y, character faces -Y) from ankle centre.
    # Adjusted from 0.30 → 0.40 to match reference anatomy (40% of foot length
    # sits behind the ankle centre).
    heel_y = foot_len * 0.40
    heel_half_w = half_w * 0.85  # heel is narrower than ball
    heel_ring = _make_ring(bm, (x, heel_y, foot_h / 2),
                           heel_half_w, foot_h / 2)

    # Ball ring — the widest part of the foot, just behind the toes.
    # Moved slightly further forward from -0.20 → -0.25.
    ball_y = -foot_len * 0.25
    ball_half_w = half_w          # full width at ball
    ball_ring = _make_ring(bm, (x, ball_y, foot_h / 2),
                           ball_half_w, foot_h * 0.45)

    # Toe ring — tapered tip, extended further forward from -0.70 → -0.60
    # (60% of foot length in front of ankle centre).
    toe_y = -foot_len * 0.60
    toe_half_w = half_w * 0.65   # toes taper in
    toe_ring = _make_ring(bm, (x, toe_y, foot_h * 0.35),
                          toe_half_w, foot_h * 0.35)

    # Bridge ankle -> heel -> ball -> toe
    _bridge_rings(bm, ankle_ring, heel_ring)
    _bridge_rings(bm, heel_ring, ball_ring)
    _bridge_rings(bm, ball_ring, toe_ring)

    # Cap the toe tip
    cap_vert, _ = _cap_ring(bm, toe_ring, top=False)

    # Add ground plane faces (bottom of foot) — close the sole.
    # Create sole rings at Z=0 mirroring the heel and toe ring XY positions,
    # then bridge and cap to form a closed sole.
    sole_heel = []
    for v in heel_ring:
        sv = bm.verts.new((v.co.x, v.co.y, 0))
        sole_heel.append(sv)

    sole_toe = []
    for v in toe_ring:
        sv = bm.verts.new((v.co.x, v.co.y, 0))
        sole_toe.append(sv)

    # Bridge sole rings (bottom face strip connecting heel sole to toe sole)
    _bridge_rings(bm, sole_heel, sole_toe)
    # Connect heel sole ring up to the heel ring (side walls of the heel)
    _bridge_rings(bm, sole_heel, heel_ring)
    # Cap the heel bottom so the underside of the heel is fully closed
    _cap_ring(bm, sole_heel, top=False)

    ring_groups = [
        (heel_ring, f"Foot.{side}"),
        (ball_ring, f"Foot.{side}"),
        (toe_ring, f"Foot.{side}"),
        ([cap_vert], f"Foot.{side}"),
        (sole_heel, f"Foot.{side}"),
        (sole_toe, f"Foot.{side}"),
    ]
    return ring_groups


def _build_facial_details(bm, cfg, head_rings):
    """Build eyes, ears, and nose bridge detail using head ring positions.

    Eyes are oval shapes placed at the eye-socket level with proper depth.
    Ears are C-shaped 3D geometry extending from the sides of the head.
    Nose is a 3D wedge shape built between nose-tip and eye rings.

    Args:
        bm: bmesh instance
        cfg: body config
        head_rings: list of head ring vertex lists from _build_head_rings

    Returns:
        (ring_groups, eye_face_indices) where eye_face_indices is a list of
        bmesh face indices for the eye geometry (used to assign eye material).
    """
    head_r = cfg["head_size"]
    neck_len = cfg["neck_length"]
    torso_len = cfg["torso_length"]
    leg_len = cfg["leg_length"]

    foot_top = 0.06
    hip_z = foot_top + leg_len
    chest_z = hip_z + torso_len
    neck_z = chest_z + neck_len
    head_z = neck_z + head_r

    ring_groups = []
    eye_face_indices = []

    # ── Eye positions ──────────────────────────────────────────────────────
    # Eye ring (ring 4 in _build_head_rings) sits at neck_z + head_r * 0.82
    # with ry = 0.83 * head_r. Face surface at that level ≈ y = -0.83*head_r.
    eye_z       = neck_z + head_r * 0.82
    eye_spacing = head_r * 0.38
    face_y_eye  = -(head_r * 0.83)   # approximate face surface at eye level

    # Recessed socket design:
    #   outer_ring — at face surface, larger (socket rim, skin material)
    #   inner_ring — recessed 0.06*head_r behind face, the dark eyeball disc
    eye_outer_rx = head_r * 0.16
    eye_outer_ry = head_r * 0.12
    eye_rx       = head_r * 0.11
    eye_ry       = head_r * 0.08
    eye_recess   = head_r * 0.06    # depth of socket

    for x_sign in [1, -1]:
        ex = x_sign * eye_spacing

        outer_ring = _make_ring(bm, (ex, face_y_eye, eye_z),
                                eye_outer_rx, eye_outer_ry, n=8)
        inner_ring = _make_ring(bm, (ex, face_y_eye + eye_recess, eye_z),
                                eye_rx, eye_ry, n=8)

        _bridge_rings(bm, outer_ring, inner_ring)

        eye_cap_start = len(bm.faces)
        _cap_ring(bm, inner_ring, top=True)
        eye_face_indices.extend(range(eye_cap_start, len(bm.faces)))

        ring_groups.append((outer_ring + inner_ring, "Head"))

    # ── Brow arches ────────────────────────────────────────────────────────
    # Small raised ridge above each eye socket for expression depth.
    brow_z = neck_z + head_r * 0.96
    brow_y = face_y_eye - head_r * 0.02   # slightly more forward than face

    for x_sign in [1, -1]:
        ex  = x_sign * eye_spacing
        bw  = eye_outer_rx * 1.2

        top_in  = bm.verts.new((ex - x_sign * bw * 0.30, brow_y,                  brow_z + head_r * 0.04))
        top_out = bm.verts.new((ex + x_sign * bw * 0.80, brow_y - head_r * 0.01,  brow_z + head_r * 0.02))
        bot_in  = bm.verts.new((ex - x_sign * bw * 0.30, brow_y + head_r * 0.03,  brow_z))
        bot_out = bm.verts.new((ex + x_sign * bw * 0.80, brow_y + head_r * 0.03,  brow_z))
        back_in  = bm.verts.new((ex - x_sign * bw * 0.30, brow_y + head_r * 0.04, brow_z + head_r * 0.02))
        back_out = bm.verts.new((ex + x_sign * bw * 0.80, brow_y + head_r * 0.04, brow_z + head_r * 0.01))

        try:
            if x_sign > 0:
                bm.faces.new([top_in, top_out, bot_out, bot_in])
                bm.faces.new([top_in, back_in, back_out, top_out])
            else:
                bm.faces.new([top_out, top_in, bot_in, bot_out])
                bm.faces.new([top_out, back_out, back_in, top_in])
        except ValueError:
            pass

        ring_groups.append(([top_in, top_out, bot_in, bot_out,
                              back_in, back_out], "Head"))

    # ── Nose ───────────────────────────────────────────────────────────────
    # Nose clearly protrudes beyond the cheekbone face surface (ry=0.88).
    # nose_tip_y pushed ~12% beyond that surface for clear visibility.
    nose_bridge_z = neck_z + head_r * 0.74
    nose_tip_z    = neck_z + head_r * 0.54
    nose_w        = head_r * 0.10
    nose_bridge_y = -(head_r * 0.94)
    nose_tip_y    = -(head_r * 1.00)

    nb_verts = [
        bm.verts.new(( nose_w,       nose_bridge_y,                 nose_bridge_z + head_r * 0.03)),
        bm.verts.new(( nose_w,       nose_bridge_y - head_r * 0.04, nose_bridge_z)),
        bm.verts.new((-nose_w,       nose_bridge_y - head_r * 0.04, nose_bridge_z)),
        bm.verts.new((-nose_w,       nose_bridge_y,                 nose_bridge_z + head_r * 0.03)),
    ]
    nt_verts = [
        bm.verts.new(( nose_w * 1.5, nose_tip_y + head_r * 0.04, nose_tip_z + head_r * 0.02)),
        bm.verts.new(( nose_w * 1.5, nose_tip_y,                 nose_tip_z - head_r * 0.02)),
        bm.verts.new((-nose_w * 1.5, nose_tip_y,                 nose_tip_z - head_r * 0.02)),
        bm.verts.new((-nose_w * 1.5, nose_tip_y + head_r * 0.04, nose_tip_z + head_r * 0.02)),
    ]

    for i in range(4):
        j = (i + 1) % 4
        try:
            bm.faces.new([nb_verts[i], nb_verts[j], nt_verts[j], nt_verts[i]])
        except ValueError:
            pass
    try:
        bm.faces.new(nt_verts)
    except ValueError:
        pass

    ring_groups.append((nb_verts + nt_verts, "Head"))

    # ── Lips ───────────────────────────────────────────────────────────────
    # Subtle raised lip panel at mouth ring level (neck_z + head_r * 0.32).
    # Mouth ring ry = 0.74, face surface ≈ -0.74*head_r. Lips protrude beyond.
    lip_z      = neck_z + head_r * 0.32
    lip_face_y = -(head_r * 0.80)
    lip_w      = head_r * 0.18

    ul_l = bm.verts.new((-lip_w,        lip_face_y, lip_z + head_r * 0.05))
    ul_r = bm.verts.new(( lip_w,        lip_face_y, lip_z + head_r * 0.05))
    ll_l = bm.verts.new((-lip_w * 1.15, lip_face_y, lip_z - head_r * 0.04))
    ll_r = bm.verts.new(( lip_w * 1.15, lip_face_y, lip_z - head_r * 0.04))
    cr_l = bm.verts.new((-lip_w * 0.85, lip_face_y + head_r * 0.02, lip_z - head_r * 0.10))
    cr_r = bm.verts.new(( lip_w * 0.85, lip_face_y + head_r * 0.02, lip_z - head_r * 0.10))

    try: bm.faces.new([ul_l, ul_r, ll_r, ll_l])
    except ValueError: pass
    try: bm.faces.new([ll_l, ll_r, cr_r, cr_l])
    except ValueError: pass

    ring_groups.append(([ul_l, ul_r, ll_l, ll_r, cr_l, cr_r], "Head"))

    # ── Ears ───────────────────────────────────────────────────────────────
    ear_z     = neck_z + head_r * 0.62
    ear_h     = head_r * 0.22
    ear_depth = head_r * 0.09

    for x_sign in [1, -1]:
        ear_base_x  = x_sign * (head_r * 0.95)
        ear_outer_x = x_sign * (head_r * 0.95 + head_r * 0.13)
        ear_y = head_r * 0.04

        inner_ear = [
            bm.verts.new((ear_base_x, ear_y - ear_depth,        ear_z + ear_h)),
            bm.verts.new((ear_base_x, ear_y + ear_depth,        ear_z + ear_h * 0.7)),
            bm.verts.new((ear_base_x, ear_y + ear_depth,        ear_z - ear_h * 0.5)),
            bm.verts.new((ear_base_x, ear_y - ear_depth * 0.5,  ear_z - ear_h)),
        ]
        outer_ear = [
            bm.verts.new((ear_outer_x, ear_y - ear_depth * 0.7, ear_z + ear_h * 0.85)),
            bm.verts.new((ear_outer_x, ear_y + ear_depth * 0.5, ear_z + ear_h * 0.60)),
            bm.verts.new((ear_outer_x, ear_y + ear_depth * 0.5, ear_z - ear_h * 0.40)),
            bm.verts.new((ear_outer_x, ear_y - ear_depth * 0.4, ear_z - ear_h * 0.75)),
        ]

        n = len(inner_ear)
        for i in range(n):
            j = (i + 1) % n
            try:
                if x_sign > 0:
                    bm.faces.new([inner_ear[i], inner_ear[j],
                                  outer_ear[j], outer_ear[i]])
                else:
                    bm.faces.new([inner_ear[j], inner_ear[i],
                                  outer_ear[i], outer_ear[j]])
            except ValueError:
                pass

        try:
            if x_sign > 0:
                bm.faces.new(outer_ear)
            else:
                bm.faces.new(list(reversed(outer_ear)))
        except ValueError:
            pass

        ring_groups.append((inner_ear + outer_ear, "Head"))

    return ring_groups, eye_face_indices


def build_base_mesh(cfg=None):
    """Build the complete humanoid base mesh.

    Args:
        cfg: body config dict. If None, uses neutral average defaults.

    Returns:
        (bm, vertex_groups) where:
            bm: bmesh with the complete body
            vertex_groups: dict mapping bone names to lists of
                (vertex_index, weight) tuples
    """
    import bmesh

    if cfg is None:
        from .presets import PRESETS
        cfg = dict(PRESETS["average"])
        cfg["gender"] = "neutral"

    bm = bmesh.new()

    # Track all vertex->bone assignments
    all_ring_groups = []

    # --- Torso ---
    torso_rings, torso_groups = _build_torso_rings(bm, cfg)
    all_ring_groups.extend(torso_groups)

    # --- Legs ---
    for side in ["L", "R"]:
        ankle_ring, leg_groups = _build_leg(bm, cfg, side, torso_rings["hip"])
        all_ring_groups.extend(leg_groups)

        # --- Feet ---
        foot_groups = _build_foot(bm, cfg, side, ankle_ring)
        all_ring_groups.extend(foot_groups)

    # --- Arms ---
    for side in ["L", "R"]:
        wrist_ring, arm_groups = _build_arm(bm, cfg, side, torso_rings["chest"])
        all_ring_groups.extend(arm_groups)

        # --- Hands ---
        hand_groups = _build_hand(bm, cfg, side, wrist_ring)
        all_ring_groups.extend(hand_groups)

    # --- Head ---
    head_groups, head_rings = _build_head_rings(bm, cfg, torso_rings["neck"])
    all_ring_groups.extend(head_groups)

    # --- Facial details (eyes, ears) ---
    face_groups, eye_face_indices = _build_facial_details(bm, cfg, head_rings)
    all_ring_groups.extend(face_groups)

    # Ensure consistent normals
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    # Build vertex groups dict: bone_name -> [(vert_index, weight)]
    bm.verts.ensure_lookup_table()
    vertex_groups = {}
    for ring_verts, bone_name in all_ring_groups:
        if bone_name not in vertex_groups:
            vertex_groups[bone_name] = []
        for v in ring_verts:
            vertex_groups[bone_name].append((v.index, 1.0))

    return bm, vertex_groups, eye_face_indices


def build_base_mesh_positions(cfg):
    """Build base mesh and return just the vertex positions.

    This is a pure-data variant used by the morph system to compute
    vertex deltas without creating Blender objects.

    Args:
        cfg: body config dict

    Returns:
        List of (x, y, z) tuples, one per vertex, in index order.
    """
    import bmesh

    bm, _, _eye_indices = build_base_mesh(cfg)
    bm.verts.ensure_lookup_table()
    positions = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]
    bm.free()
    return positions
